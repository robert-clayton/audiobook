from flask import Flask, render_template, jsonify, request, redirect, url_for, Response
from pathlib import Path
import sys
import os
import threading
import time
import subprocess
import argparse
import queue
import json

# Add the parent directory to the path so we can import audiobook modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from audiobook.config import load_config, save_config
from audiobook.validators.config_validator import ConfigValidator, ConfigValidationError
from audiobook.utils.progress import ProgressTracker
from audiobook.utils.logger import setup_logger

app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key-here"  # Change this in production

# Global config file path
CONFIG_FILE = "config.yml"

# Setup logging
logger = setup_logger("audiobook-web", log_file=Path("logs/web.log"))

# Initialize components
progress_tracker = ProgressTracker()
config_validator = ConfigValidator()

# Global state for processing
processing_status = {
    "is_running": False,
    "current_series": None,
    "start_time": None,
    "process": None
}

# Global log queue for real-time streaming
log_queue = queue.Queue()


def get_config_path():
    """Get the current config file path."""
    return CONFIG_FILE


def stream_process_output(process, series_name):
    """Stream process output to the log queue."""
    global log_queue
    
    try:
        # Send start message
        log_queue.put({
            "timestamp": time.time(),
            "level": "INFO",
            "message": f"Started processing for series: {series_name or 'all series'}",
            "series": series_name
        })
        
        # Stream stdout
        for line in iter(process.stdout.readline, ''):
            if line:
                log_queue.put({
                    "timestamp": time.time(),
                    "level": "INFO",
                    "message": line.strip(),
                    "series": series_name
                })
        
        # Stream stderr
        for line in iter(process.stderr.readline, ''):
            if line:
                log_queue.put({
                    "timestamp": time.time(),
                    "level": "ERROR",
                    "message": line.strip(),
                    "series": series_name
                })
        
        # Send completion message
        return_code = process.wait()
        if return_code == 0:
            log_queue.put({
                "timestamp": time.time(),
                "level": "SUCCESS",
                "message": f"Processing completed successfully for {series_name or 'all series'}",
                "series": series_name
            })
        else:
            log_queue.put({
                "timestamp": time.time(),
                "level": "ERROR",
                "message": f"Processing failed with return code {return_code} for {series_name or 'all series'}",
                "series": series_name
            })
            
    except Exception as e:
        log_queue.put({
            "timestamp": time.time(),
            "level": "ERROR",
            "message": f"Error streaming output: {str(e)}",
            "series": series_name
        })


@app.route("/")
def index():
    """Main dashboard page."""
    try:
        # Load current config
        config = load_config(get_config_path())

        # Get progress summary
        summary = progress_tracker.get_summary()

        # Get recent activity
        recent_chapters = list(progress_tracker.progress.values())[-10:]

        return render_template(
            "index.html",
            config=config,
            summary=summary,
            recent_chapters=recent_chapters,
            processing_status=processing_status,
            config_file=get_config_path(),
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return render_template("error.html", error=str(e))


@app.route("/api/progress")
def api_progress():
    """API endpoint for progress data."""
    try:
        series_name = request.args.get("series")

        if series_name:
            pending = progress_tracker.get_pending_chapters(series_name)
            completed = progress_tracker.get_completed_chapters(series_name)
            failed = progress_tracker.get_failed_chapters(series_name)
        else:
            pending = progress_tracker.get_pending_chapters()
            completed = progress_tracker.get_completed_chapters()
            failed = progress_tracker.get_failed_chapters()

        return jsonify(
            {
                "pending": [p.to_dict() for p in pending],
                "completed": [p.to_dict() for p in completed],
                "failed": [p.to_dict() for p in failed],
                "summary": progress_tracker.get_summary(),
                "processing_status": processing_status,
            }
        )
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """API endpoint for configuration management."""
    if request.method == "GET":
        try:
            config = load_config(get_config_path())
            return jsonify(config)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return jsonify({"error": str(e)}), 500

    elif request.method == "POST":
        try:
            config_data = request.json

            # Validate configuration
            config_validator.validate_config(config_data)

            # Save configuration
            save_config(get_config_path(), config_data)

            logger.info("Configuration updated successfully")
            return jsonify({"message": "Configuration updated successfully"})
        except ConfigValidationError as e:
            logger.error(f"Configuration validation error: {e}")
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/api/series/<series_name>/reset", methods=["POST"])
def api_reset_series(series_name):
    """Reset progress for a specific series."""
    try:
        progress_tracker.reset_series(series_name)
        logger.info(f"Reset progress for series: {series_name}")
        return jsonify({"message": f"Reset progress for {series_name}"})
    except Exception as e:
        logger.error(f"Error resetting series {series_name}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear-completed", methods=["POST"])
def api_clear_completed():
    """Clear completed chapters from progress tracking."""
    try:
        progress_tracker.clear_completed()
        logger.info("Cleared completed chapters from progress tracking")
        return jsonify({"message": "Cleared completed chapters"})
    except Exception as e:
        logger.error(f"Error clearing completed chapters: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/start-processing", methods=["POST"])
def api_start_processing():
    """Start audiobook processing for a specific series or all series."""
    global processing_status
    
    if processing_status["is_running"]:
        return jsonify({"error": "Processing is already running"}), 400
    
    try:
        data = request.json
        series_name = data.get("series_name")  # None means all series
        
        # Build command
        cmd = ["poetry", "run", "audiobook"]
        if series_name:
            cmd.extend(["--series", series_name])
        
        # Add dev flag if using dev config
        if get_config_path() == "config_dev.yml":
            cmd.append("--dev")
        
        # Start processing in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
            bufsize=1,
            universal_newlines=True
        )
        
        processing_status.update({
            "is_running": True,
            "current_series": series_name,
            "start_time": time.time(),
            "process": process
        })
        
        # Start streaming output in background thread
        stream_thread = threading.Thread(
            target=stream_process_output,
            args=(process, series_name),
            daemon=True
        )
        stream_thread.start()
        
        logger.info(f"Started processing for series: {series_name or 'all'}")
        return jsonify({
            "message": f"Started processing for {series_name or 'all series'}",
            "process_id": process.pid
        })
        
    except Exception as e:
        logger.error(f"Error starting processing: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/stop-processing", methods=["POST"])
def api_stop_processing():
    """Stop current audiobook processing."""
    global processing_status
    
    if not processing_status["is_running"]:
        return jsonify({"error": "No processing is currently running"}), 400
    
    try:
        if processing_status["process"]:
            processing_status["process"].terminate()
            processing_status["process"].wait(timeout=10)
        
        processing_status.update({
            "is_running": False,
            "current_series": None,
            "start_time": None,
            "process": None
        })
        
        # Send stop message to log queue
        log_queue.put({
            "timestamp": time.time(),
            "level": "WARNING",
            "message": "Processing stopped by user",
            "series": processing_status.get("current_series")
        })
        
        logger.info("Stopped processing")
        return jsonify({"message": "Processing stopped successfully"})
        
    except Exception as e:
        logger.error(f"Error stopping processing: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/processing-status")
def api_processing_status():
    """Get current processing status."""
    global processing_status
    
    # Create a serializable copy of the status
    status = {
        "is_running": processing_status["is_running"],
        "current_series": processing_status["current_series"],
        "start_time": processing_status["start_time"],
        "process_id": processing_status["process"].pid if processing_status["process"] else None
    }
    
    if status["process_id"] and processing_status["process"]:
        # Check if process is still running
        if processing_status["process"].poll() is not None:
            # Process has finished
            processing_status.update({
                "is_running": False,
                "current_series": None,
                "start_time": None,
                "process": None
            })
            status.update({
                "is_running": False,
                "current_series": None,
                "start_time": None,
                "process_id": None
            })
    
    return jsonify(status)


@app.route("/api/logs/stream")
def api_logs_stream():
    """Stream real-time logs."""
    def generate():
        while True:
            try:
                # Get log entry from queue with timeout
                log_entry = log_queue.get(timeout=1)
                yield f"data: {json.dumps(log_entry)}\n\n"
            except queue.Empty:
                # Send keepalive
                yield f"data: {json.dumps({'timestamp': time.time(), 'keepalive': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'timestamp': time.time(), 'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/plain')


@app.route("/api/series/<series_name>/toggle", methods=["POST"])
def api_toggle_series(series_name):
    """Enable/disable a series."""
    try:
        config = load_config(get_config_path())
        
        # Find and toggle the series
        for series in config.get("series", []):
            if series.get("name") == series_name:
                series["enabled"] = not series.get("enabled", True)
                save_config(get_config_path(), config)
                
                status = "enabled" if series["enabled"] else "disabled"
                logger.info(f"Series '{series_name}' {status}")
                return jsonify({"message": f"Series '{series_name}' {status}"})
        
        return jsonify({"error": f"Series '{series_name}' not found"}), 404
        
    except Exception as e:
        logger.error(f"Error toggling series {series_name}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/validate-config", methods=["POST"])
def api_validate_config():
    """Validate configuration without saving."""
    try:
        config_data = request.json
        config_validator.validate_config(config_data)
        return jsonify({"message": "Configuration is valid"})
    except ConfigValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/series/<series_name>")
def series_detail(series_name):
    """Detailed view for a specific series."""
    try:
        config = load_config(get_config_path())
        series_config = None

        for series in config.get("series", []):
            if series.get("name") == series_name:
                series_config = series
                break

        if not series_config:
            return render_template(
                "error.html", error=f"Series '{series_name}' not found"
            )

        # Get progress for this series
        pending = progress_tracker.get_pending_chapters(series_name)
        completed = progress_tracker.get_completed_chapters(series_name)
        failed = progress_tracker.get_failed_chapters(series_name)

        return render_template(
            "series_detail.html",
            series=series_config,
            pending=pending,
            completed=completed,
            failed=failed,
            processing_status=processing_status,
            config_file=get_config_path(),
        )
    except Exception as e:
        logger.error(f"Error loading series detail for {series_name}: {e}")
        return render_template("error.html", error=str(e))


@app.route("/logs")
def logs():
    """View application logs."""
    try:
        log_file = Path("logs/web.log")
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                log_lines = f.readlines()[-100:]  # Last 100 lines
        else:
            log_lines = []

        return render_template("logs.html", log_lines=log_lines)
    except Exception as e:
        logger.error(f"Error loading logs: {e}")
        return render_template("error.html", error=str(e))


def main():
    """Main entry point for the web interface."""
    global CONFIG_FILE
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Audiobook Generator Web Interface")
    parser.add_argument("--dev", action="store_true", help="Use config_dev.yml instead of config.yml")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Set config file based on dev flag
    if args.dev:
        CONFIG_FILE = "config_dev.yml"
        logger.info(f"Running in development mode with config: {CONFIG_FILE}")
    else:
        logger.info(f"Running in production mode with config: {CONFIG_FILE}")
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Run the Flask app
    app.run(debug=args.debug, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
