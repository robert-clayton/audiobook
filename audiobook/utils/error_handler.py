import os
import sys
import traceback
import time
from typing import Callable, Any, Optional, Dict
from functools import wraps
from .logger import get_logger
from .colors import RED, YELLOW, GREEN, RESET

logger = get_logger(__name__)


class ErrorHandler:
    """Comprehensive error handling and recovery system."""
    
    def __init__(self):
        self.error_counts = {}
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
    
    def handle_error(self, error: Exception, context: str = "", retry_func: Optional[Callable] = None) -> bool:
        """
        Handle an error with optional retry logic.
        
        Args:
            error: The exception that occurred
            context: Context string for logging
            retry_func: Function to retry (if None, no retry)
        
        Returns:
            bool: True if error was handled successfully, False otherwise
        """
        error_type = type(error).__name__
        error_key = f"{context}:{error_type}"
        
        # Increment error count
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        current_count = self.error_counts[error_key]
        
        # Log the error
        logger.error(f"Error in {context}: {error}")
        logger.debug(f"Error count for {error_key}: {current_count}")
        
        # Check if we should retry
        if retry_func and current_count <= self.max_retries:
            logger.info(f"Retrying {context} (attempt {current_count}/{self.max_retries})")
            time.sleep(self.retry_delay * current_count)  # Exponential backoff
            
            try:
                retry_func()
                logger.info(f"Retry successful for {context}")
                return True
            except Exception as retry_error:
                logger.error(f"Retry failed for {context}: {retry_error}")
                return self.handle_error(retry_error, context, retry_func)
        
        # Max retries exceeded or no retry function
        if current_count > self.max_retries:
            logger.error(f"Max retries exceeded for {context}")
            print(f"{RED}Max retries exceeded for {context}. Skipping.{RESET}")
        
        return False
    
    def get_error_stats(self) -> Dict:
        """Get error statistics."""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_types": self.error_counts,
            "max_retries": self.max_retries
        }
    
    def reset_error_counts(self):
        """Reset error counts."""
        self.error_counts.clear()
        logger.info("Error counts reset")


class NetworkErrorHandler:
    """Specialized handler for network-related errors."""
    
    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
        self.rate_limit_delay = 60  # seconds
    
    def handle_http_error(self, error, context: str = "", retry_func: Optional[Callable] = None) -> bool:
        """Handle HTTP errors with rate limiting awareness."""
        if hasattr(error, 'response') and error.response is not None:
            status_code = error.response.status_code
            
            if status_code == 429:  # Rate limited
                logger.warning(f"Rate limited for {context}. Waiting {self.rate_limit_delay} seconds...")
                print(f"{YELLOW}Rate limited. Waiting {self.rate_limit_delay} seconds...{RESET}")
                time.sleep(self.rate_limit_delay)
                return True  # Don't count as error, just wait
            
            elif status_code >= 500:  # Server error
                logger.warning(f"Server error ({status_code}) for {context}")
                return self.error_handler.handle_error(error, context, retry_func)
            
            elif status_code == 404:  # Not found
                logger.error(f"Resource not found for {context}")
                return False  # Don't retry 404s
        
        # Handle other HTTP errors
        return self.error_handler.handle_error(error, context, retry_func)


class FileErrorHandler:
    """Specialized handler for file-related errors."""
    
    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
    
    def handle_file_error(self, error, file_path: str, context: str = "", retry_func: Optional[Callable] = None) -> bool:
        """Handle file-related errors."""
        if isinstance(error, FileNotFoundError):
            logger.error(f"File not found: {file_path}")
            print(f"{RED}File not found: {file_path}{RESET}")
            return False  # Don't retry missing files
        
        elif isinstance(error, PermissionError):
            logger.error(f"Permission denied: {file_path}")
            print(f"{RED}Permission denied: {file_path}{RESET}")
            return False  # Don't retry permission errors
        
        elif isinstance(error, OSError):
            # Handle disk space, I/O errors, etc.
            logger.warning(f"OS error for {file_path}: {error}")
            return self.error_handler.handle_error(error, f"{context} ({file_path})", retry_func)
        
        return self.error_handler.handle_error(error, f"{context} ({file_path})", retry_func)


def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for automatic retry on errors.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay on each retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                        logger.info(f"Retrying in {current_delay} seconds...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
            
            # Re-raise the last exception if all retries failed
            raise last_exception
        
        return wrapper
    return decorator


def safe_execute(func: Callable, *args, context: str = "", **kwargs) -> Optional[Any]:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        context: Context string for error messages
        *args, **kwargs: Arguments to pass to function
    
    Returns:
        Function result or None if execution failed
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in {context}: {e}")
        print(f"{RED}Error in {context}: {e}{RESET}")
        return None


def validate_environment() -> bool:
    """Validate that the environment is properly set up."""
    errors = []
    
    # Check for required directories
    required_dirs = ["speakers", "tmp"]
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            errors.append(f"Required directory '{dir_name}' not found")
    
    # Check for speaker files
    if os.path.exists("speakers"):
        speaker_files = [f for f in os.listdir("speakers") if f.endswith(".wav")]
        if not speaker_files:
            errors.append("No speaker files (.wav) found in speakers/ directory")
    
    # Check for ffmpeg
    try:
        import subprocess
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        errors.append("ffmpeg not found or not working properly")
    
    # Check for CUDA (optional)
    try:
        import torch
        if not torch.cuda.is_available():
            logger.warning("CUDA not available - TTS will be slower")
    except ImportError:
        errors.append("PyTorch not available")
    
    if errors:
        print(f"{RED}Environment validation failed:{RESET}")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print(f"{GREEN}Environment validation passed{RESET}")
    return True


# Global error handler instances
error_handler = ErrorHandler()
network_error_handler = NetworkErrorHandler(error_handler)
file_error_handler = FileErrorHandler(error_handler)

