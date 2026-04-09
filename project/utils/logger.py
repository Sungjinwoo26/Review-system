"""
Simple logging setup for MVP
"""
import logging
import sys
from datetime import datetime


def setup_logger(name: str = "review_system") -> logging.Logger:
    """Setup basic logger for the application"""
    logger = logging.getLogger(name)
    
    # Set level
    logger.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Global logger instance
logger = setup_logger()


def log_event(event_type: str, details: dict) -> None:
    """Log structured events"""
    logger.info(f"EVENT: {event_type} | Details: {details}")


def log_error(error_type: str, error_message: str, context: dict = None) -> None:
    """Log errors with context"""
    context_str = f" | Context: {context}" if context else ""
    logger.error(f"ERROR: {error_type} - {error_message}{context_str}")


def log_performance(function_name: str, duration_ms: float) -> None:
    """Log performance metrics"""
    logger.info(f"PERFORMANCE: {function_name} completed in {duration_ms:.2f}ms")
