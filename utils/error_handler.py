"""
Robust error handling, recovery, and retry logic for RIE
Implements layered error handling with graceful degradation
"""

import time
import logging
from typing import Callable, Any, Optional, TypeVar, Dict, List
from functools import wraps
import requests

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ===== CUSTOM EXCEPTION HIERARCHY =====

class RIEError(Exception):
    """Base exception for RIE system"""
    pass


class APIError(RIEError):
    """API communication errors"""
    def __init__(self, message: str, status_code: int = None, attempt: int = None):
        self.message = message
        self.status_code = status_code
        self.attempt = attempt
        super().__init__(self.message)


class DataError(RIEError):
    """Data validation/processing errors"""
    pass


class ScoringError(RIEError):
    """Scoring engine errors"""
    pass


class PipelineError(RIEError):
    """Pipeline orchestration errors"""
    pass


class ErrorState:
    """Structured error state for UI"""
    def __init__(self, error_type: str, message: str, is_recoverable: bool = True, suggestion: str = None):
        self.error_type = error_type
        self.message = message
        self.is_recoverable = is_recoverable
        self.suggestion = suggestion or self._get_suggestion(error_type)

    def _get_suggestion(self, error_type: str) -> str:
        """Get user-friendly suggestion for error type"""
        suggestions = {
            "API_TIMEOUT": "API is slow. Try again in a few moments.",
            "API_ERROR": "Cannot reach review server. Check your internet connection.",
            "DATA_INVALID": "Data format issue. Please contact support.",
            "SCORING_ERROR": "Internal processing error. Please try again.",
            "EMPTY_DATA": "No reviews available at the moment.",
        }
        return suggestions.get(error_type, "An unexpected error occurred. Please try again.")

    def __repr__(self):
        return f"ErrorState({self.error_type}: {self.message})"


# ===== RETRY LOGIC =====

def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for exponential backoff retry logic with advanced control
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exceptions: Tuple of exceptions to retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e
                    is_last_attempt = attempt == max_retries - 1

                    # Log differently based on exception type
                    if isinstance(e, requests.exceptions.Timeout):
                        logger.warning(
                            f"[Timeout] {func.__name__} attempt {attempt + 1}/{max_retries}"
                        )
                    elif isinstance(e, requests.exceptions.ConnectionError):
                        logger.warning(
                            f"[Connection Error] {func.__name__} attempt {attempt + 1}/{max_retries}"
                        )
                    elif isinstance(e, requests.exceptions.HTTPError):
                        logger.error(
                            f"[HTTP Error] {func.__name__}: {str(e)}"
                        )
                        # Don't retry on 4xx errors (client's fault)
                        if hasattr(e.response, 'status_code') and 400 <= e.response.status_code < 500:
                            raise
                    else:
                        logger.exception(
                            f"[Exception] {func.__name__} attempt {attempt + 1}/{max_retries}: {str(e)}"
                        )

                    if is_last_attempt:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                        raise APIError(
                            f"Failed after {max_retries} attempts: {str(e)}",
                            attempt=max_retries
                        ) from e

                    # Calculate delay with cap
                    delay = min(delay * backoff_factor, max_delay)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)

        return wrapper
    return decorator


# ===== SAFE OPERATIONS =====

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide without division by zero errors"""
    try:
        if denominator == 0 or denominator is None or not isinstance(numerator, (int, float)):
            return default
        return float(numerator) / float(denominator)
    except (TypeError, ValueError):
        logger.warning(f"Division error: {numerator} / {denominator}, using default {default}")
        return default


def safe_get_nested(data: Dict, keys: List[str], default: Any = None) -> Any:
    """Safely get nested dictionary values"""
    try:
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        return value if value is not None else default
    except (KeyError, TypeError, AttributeError):
        return default


# ===== EXECUTION GUARDS =====

def catch_and_log(
    default_return: Any = None,
    log_level: str = "error",
    error_type: str = "EXECUTION_ERROR"
) -> Callable:
    """
    Decorator to catch exceptions, log them, and return a safe default
    Use for non-critical operations that should not crash the system
    
    Args:
        default_return: Value to return if exception occurs
        log_level: Logging level (debug, info, warning, error, critical)
        error_type: Error type label for logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level.lower(), logger.error)
                log_func(
                    f"[{error_type}] {func.__name__} failed: {str(e)}"
                )
                logger.debug(f"Exception details: {type(e).__name__}: {str(e)}", exc_info=True)
                return default_return
        return wrapper
    return decorator


# ===== VALIDATION =====

def assert_schema(df, required_columns: List[str], context: str = ""):
    """
    Assert DataFrame has required schema
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        context: Context for error message
        
    Raises:
        DataError: If schema is invalid
    """
    try:
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise DataError(
                f"Schema validation failed{' - ' + context if context else ''}: "
                f"Missing columns {missing}"
            )
    except AttributeError as e:
        raise DataError(f"Invalid DataFrame object: {str(e)}")


def assert_not_empty(df, context: str = ""):
    """
    Assert DataFrame is not empty
    
    Args:
        df: DataFrame to validate
        context: Context for error message
        
    Raises:
        DataError: If DataFrame is empty
    """
    if df is None or (hasattr(df, 'empty') and df.empty):
        raise DataError(
            f"Empty dataset{' - ' + context if context else ''}"
        )


# ===== METRICS =====

class OperationMetrics:
    """Track operation metrics for monitoring"""
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = time.time()
        self.errors = []
        self.warnings = []

    def add_error(self, error: str):
        self.errors.append(error)
        logger.error(f"[{self.operation_name}] {error}")

    def add_warning(self, warning: str):
        self.warnings.append(warning)
        logger.warning(f"[{self.operation_name}] {warning}")

    def duration_ms(self) -> float:
        return (time.time() - self.start_time) * 1000

    def report(self):
        """Log operation summary"""
        logger.info(
            f"[{self.operation_name}] Completed in {self.duration_ms():.1f}ms "
            f"(errors={len(self.errors)}, warnings={len(self.warnings)})"
        )
        return {
            "operation": self.operation_name,
            "duration_ms": self.duration_ms(),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "error_list": self.errors,
            "warning_list": self.warnings,
        }



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
