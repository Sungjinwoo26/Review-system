"""
Error handling and retry logic for MVP
"""
import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom exception for API errors"""
    pass


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2.0):
    """
    Decorator for exponential backoff retry logic
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries (2.0 = exponential)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = 1  # Start with 1 second delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries reached for {func.__name__}: {str(e)}")
                        raise
                    
                    logger.warning(f"Attempt {attempt + 1} failed. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= backoff_factor
        
        return wrapper
    return decorator


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide without division by zero errors"""
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


def safe_get(data: dict, key: str, default: Any = None) -> Any:
    """Safely get dictionary value"""
    try:
        return data.get(key, default)
    except (AttributeError, TypeError):
        return default


class ErrorState:
    """Represents an error state for UI rendering"""
    
    def __init__(self, error_type: str, message: str, recoverable: bool = True):
        self.error_type = error_type
        self.message = message
        self.recoverable = recoverable
    
    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "recoverable": self.recoverable
        }
