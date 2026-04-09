"""
Robust logging setup for RIE with file and console handlers
Implements structured logging with proper formatting and severity levels
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }

    def format(self, record):
        # Add color to console output
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            levelname = record.levelname
            record.levelname = (
                f"{self.COLORS.get(levelname, '')}{levelname}{self.COLORS['RESET']}"
            )

        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        
        # Structured format
        msg = f"{timestamp} | {record.levelname:8s} | {record.name:20s} | {record.getMessage()}"
        
        # Add exception info if present
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            msg += f"\n{record.exc_text}"

        return msg


def setup_logger(name: str = "review_system", log_file: str = "review_system.log") -> logging.Logger:
    """
    Setup comprehensive logger with file and console handlers
    
    Args:
        name: Logger name
        log_file: Path to log file
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers
    if logger.hasHandlers():
        return logger
    
    # Set level to DEBUG (handlers will filter)
    logger.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = StructuredFormatter()
    
    # ===== Console Handler (INFO and above) =====
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ===== File Handler (DEBUG and above) =====
    try:
        # Ensure log directory exists
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")
    
    return logger


# Global logger instance
logger = setup_logger()


# ===== STRUCTURED LOGGING FUNCTIONS =====

def log_event(event_type: str, details: dict = None) -> None:
    """
    Log structured event with context
    
    Args:
        event_type: Type of event (e.g., "API_CALL", "PIPELINE_START")
        details: Dictionary of contextual information
    """
    details_str = " | " + str(details) if details else ""
    logger.info(f"EVENT: {event_type}{details_str}")


def log_error(error_type: str, error_message: str, context: dict = None) -> None:
    """
    Log error with context
    
    Args:
        error_type: Category of error (e.g., "API_ERROR", "DATA_VALIDATION")
        error_message: Error message
        context: Dictionary of contextual information
    """
    context_str = f" | Context: {context}" if context else ""
    logger.error(f"ERROR: {error_type} - {error_message}{context_str}")


def log_warning(warning_type: str, message: str, context: dict = None) -> None:
    """
    Log warning with context
    
    Args:
        warning_type: Category of warning
        message: Warning message
        context: Dictionary of contextual information
    """
    context_str = f" | Context: {context}" if context else ""
    logger.warning(f"WARNING: {warning_type} - {message}{context_str}")


def log_debug(component: str, details: str, data: dict = None) -> None:
    """
    Log debug information
    
    Args:
        component: Component name
        details: Debug details
        data: Optional data for inspection
    """
    data_str = f" | Data: {data}" if data else ""
    logger.debug(f"DEBUG: {component} - {details}{data_str}")


def log_performance(operation_name: str, duration_ms: float, row_count: int = None) -> None:
    """
    Log performance metrics
    
    Args:
        operation_name: Name of operation
        duration_ms: Duration in milliseconds
        row_count: Optional number of rows processed
    """
    rows_str = f", rows={row_count}" if row_count else ""
    logger.info(f"PERFORMANCE: {operation_name} completed in {duration_ms:.1f}ms{rows_str}")


def log_section(title: str) -> None:
    """Log a section header"""
    logger.info("=" * 80)
    logger.info(f"  {title}")
    logger.info("=" * 80)


# ===== EXCEPTION CONTEXT MANAGER =====

class ErrorContext:
    """Context manager for capturing and logging errors"""
    
    def __init__(self, operation_name: str, silent: bool = False):
        self.operation_name = operation_name
        self.silent = silent
        self.error = None
        self.occurred = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            self.occurred = True
            
            if not self.silent:
                logger.exception(
                    f"Exception in '{self.operation_name}': {exc_type.__name__}: {exc_val}"
                )
            
            return True  # Suppress exception
        
        return False


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module"""
    return logging.getLogger(name)

