import os
import json
import time
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessingMetrics:
    """Metrics for a single processing session."""
    series_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    chapters_processed: int = 0
    chapters_skipped: int = 0
    chapters_failed: int = 0
    total_duration: float = 0.0
    avg_chapter_duration: float = 0.0
    memory_peak: float = 0.0
    cpu_peak: float = 0.0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return data


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available: float
    disk_usage_percent: float
    network_io: Dict[str, float]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self, metrics_dir: str = "metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(exist_ok=True)
        
        self.current_session: Optional[ProcessingMetrics] = None
        self.system_metrics: List[SystemMetrics] = []
        self.monitoring_active = False
        
        # Performance thresholds
        self.memory_threshold = 90.0  # Alert if memory usage > 90%
        self.cpu_threshold = 95.0     # Alert if CPU usage > 95%
        self.disk_threshold = 85.0    # Alert if disk usage > 85%
    
    def start_session(self, series_name: str) -> ProcessingMetrics:
        """Start monitoring a processing session."""
        self.current_session = ProcessingMetrics(
            series_name=series_name,
            start_time=datetime.now()
        )
        logger.info(f"Started performance monitoring for {series_name}")
        return self.current_session
    
    def end_session(self):
        """End the current processing session."""
        if self.current_session:
            self.current_session.end_time = datetime.now()
            self.current_session.total_duration = (
                self.current_session.end_time - self.current_session.start_time
            ).total_seconds()
            
            if self.current_session.chapters_processed > 0:
                self.current_session.avg_chapter_duration = (
                    self.current_session.total_duration / self.current_session.chapters_processed
                )
            
            self._save_session_metrics()
            logger.info(f"Ended performance monitoring for {self.current_session.series_name}")
            self.current_session = None
    
    def record_chapter_processed(self, duration: float = None):
        """Record a successfully processed chapter."""
        if self.current_session:
            self.current_session.chapters_processed += 1
            if duration:
                # Update average duration
                total_duration = self.current_session.avg_chapter_duration * (self.current_session.chapters_processed - 1) + duration
                self.current_session.avg_chapter_duration = total_duration / self.current_session.chapters_processed
    
    def record_chapter_skipped(self):
        """Record a skipped chapter."""
        if self.current_session:
            self.current_session.chapters_skipped += 1
    
    def record_chapter_failed(self, error: str):
        """Record a failed chapter."""
        if self.current_session:
            self.current_session.chapters_failed += 1
            self.current_session.errors.append(error)
    
    def start_system_monitoring(self, interval: float = 5.0):
        """Start monitoring system resources."""
        self.monitoring_active = True
        logger.info(f"Started system monitoring (interval: {interval}s)")
        
        # In a real implementation, this would run in a separate thread
        # For now, we'll just collect metrics when called
    
    def stop_system_monitoring(self):
        """Stop monitoring system resources."""
        self.monitoring_active = False
        logger.info("Stopped system monitoring")
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available / (1024**3)  # GB
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            
            # Network I/O
            network = psutil.net_io_counters()
            network_io = {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            }
            
            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available=memory_available,
                disk_usage_percent=disk_usage_percent,
                network_io=network_io
            )
            
            self.system_metrics.append(metrics)
            
            # Check thresholds and log warnings
            if memory_percent > self.memory_threshold:
                logger.warning(f"High memory usage: {memory_percent:.1f}%")
            
            if cpu_percent > self.cpu_threshold:
                logger.warning(f"High CPU usage: {cpu_percent:.1f}%")
            
            if disk_usage_percent > self.disk_threshold:
                logger.warning(f"High disk usage: {disk_usage_percent:.1f}%")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return None
    
    def _save_session_metrics(self):
        """Save session metrics to file."""
        if not self.current_session:
            return
        
        try:
            filename = f"session_{self.current_session.series_name}_{self.current_session.start_time.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.metrics_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.current_session.to_dict(), f, indent=2)
            
            logger.info(f"Saved session metrics to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving session metrics: {e}")
    
    def get_performance_summary(self, days: int = 7) -> Dict:
        """Get performance summary for the last N days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            sessions = []
            
            # Load session files
            for filepath in self.metrics_dir.glob("session_*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        session = ProcessingMetrics(**data)
                        if session.start_time >= cutoff_date:
                            sessions.append(session)
                except Exception as e:
                    logger.warning(f"Error loading session file {filepath}: {e}")
            
            if not sessions:
                return {"message": "No session data found"}
            
            # Calculate summary statistics
            total_sessions = len(sessions)
            total_chapters = sum(s.chapters_processed for s in sessions)
            total_duration = sum(s.total_duration for s in sessions)
            total_errors = sum(len(s.errors) for s in sessions)
            
            avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
            avg_chapters = total_chapters / total_sessions if total_sessions > 0 else 0
            
            return {
                "period_days": days,
                "total_sessions": total_sessions,
                "total_chapters_processed": total_chapters,
                "total_duration_hours": total_duration / 3600,
                "total_errors": total_errors,
                "avg_session_duration_minutes": avg_duration / 60,
                "avg_chapters_per_session": avg_chapters,
                "success_rate": (total_chapters / (total_chapters + total_errors)) * 100 if (total_chapters + total_errors) > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
            return {"error": str(e)}
    
    def cleanup_old_metrics(self, days: int = 30):
        """Clean up metrics older than N days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0
            
            for filepath in self.metrics_dir.glob("*.json"):
                try:
                    # Check file modification time
                    if datetime.fromtimestamp(filepath.stat().st_mtime) < cutoff_date:
                        filepath.unlink()
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Error deleting old metrics file {filepath}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old metrics files")
            
        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {e}")


class Analytics:
    """High-level analytics and reporting."""
    
    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor
    
    def generate_report(self, output_file: str = None) -> str:
        """Generate a comprehensive performance report."""
        try:
            summary = self.monitor.get_performance_summary()
            
            if "error" in summary:
                return f"Error generating report: {summary['error']}"
            
            report_lines = [
                "=" * 60,
                "AUDIOBOOK PROCESSING PERFORMANCE REPORT",
                "=" * 60,
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "SUMMARY STATISTICS:",
                f"  Period: Last {summary.get('period_days', 0)} days",
                f"  Total Sessions: {summary.get('total_sessions', 0)}",
                f"  Chapters Processed: {summary.get('total_chapters_processed', 0)}",
                f"  Total Duration: {summary.get('total_duration_hours', 0):.1f} hours",
                f"  Success Rate: {summary.get('success_rate', 0):.1f}%",
                "",
                "AVERAGES:",
                f"  Session Duration: {summary.get('avg_session_duration_minutes', 0):.1f} minutes",
                f"  Chapters per Session: {summary.get('avg_chapters_per_session', 0):.1f}",
                "",
                "ERRORS:",
                f"  Total Errors: {summary.get('total_errors', 0)}",
                ""
            ]
            
            report = "\n".join(report_lines)
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                logger.info(f"Report saved to {output_file}")
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"Error generating report: {e}"
    
    def get_series_performance(self, series_name: str) -> Dict:
        """Get performance data for a specific series."""
        try:
            series_sessions = []
            
            for filepath in self.monitor.metrics_dir.glob(f"session_{series_name}_*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        session = ProcessingMetrics(**data)
                        series_sessions.append(session)
                except Exception as e:
                    logger.warning(f"Error loading session file {filepath}: {e}")
            
            if not series_sessions:
                return {"message": f"No data found for series: {series_name}"}
            
            # Calculate series-specific statistics
            total_chapters = sum(s.chapters_processed for s in series_sessions)
            total_duration = sum(s.total_duration for s in series_sessions)
            total_errors = sum(len(s.errors) for s in series_sessions)
            
            return {
                "series_name": series_name,
                "total_sessions": len(series_sessions),
                "total_chapters": total_chapters,
                "total_duration_hours": total_duration / 3600,
                "avg_chapters_per_session": total_chapters / len(series_sessions),
                "avg_session_duration_minutes": total_duration / len(series_sessions) / 60,
                "total_errors": total_errors,
                "success_rate": (total_chapters / (total_chapters + total_errors)) * 100 if (total_chapters + total_errors) > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting series performance: {e}")
            return {"error": str(e)}


# Global performance monitor instance
performance_monitor = PerformanceMonitor()
analytics = Analytics(performance_monitor)

