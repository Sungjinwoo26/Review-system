# Error Handling & Logging System for RIE

## Overview

The Review Intelligence Engine implements a **comprehensive, layered error handling system** that ensures:

✅ **Never crashes** on API failures, data issues, or processing errors
✅ **All failures logged** with full context for debugging
✅ **Graceful degradation** - system continues operating even when parts fail
✅ **User-friendly messages** - clean UI error presentation
✅ **Full traceability** - every error is logged with sufficient detail

---

## Architecture

### Layered Error Handling Approach

```
┌─────────────────────────────────────────────────────────┐
│           API Layer                                     │
│  (Fetch → Retry → Timeout/Error Handling)             │
├─────────────────────────────────────────────────────────┤
│           Data Validation Layer                        │
│  (Schema Checks → Type Coercion → NaN Handling)       │
├─────────────────────────────────────────────────────────┤
│           Processing Layer                              │
│  (Preprocessing → Scoring → Aggregation)              │
├─────────────────────────────────────────────────────────┤
│           Recovery Layer                                │
│  (Catch Exceptions → Log → Return Safe Fallback)      │
├─────────────────────────────────────────────────────────┤
│           UI Layer                                      │
│  (User-Friendly Messages → No Raw Exceptions)         │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Exception Hierarchy

```python
RIEError (Base)
├── APIError          # API communication issues
├── DataError         # Data validation/processing issues
├── ScoringError      # Scoring engine issues
└── PipelineError     # Pipeline orchestration issues
```

### Usage

```python
from utils.error_handler import APIError, DataError, ScoringError

try:
    api_response = fetch_data()
except APIError as e:
    # Handle API-specific failures
    log_error("API_FAILURE", str(e))
    
except DataError as e:
    # Handle data-specific failures
    log_error("DATA_FAILURE", str(e))
```

---

## 2. Retry Logic with Exponential Backoff

### API Layer (`services/ingestion.py`)

```python
@retry_with_backoff(
    max_retries=3,
    backoff_factor=2.0,        # 1s → 2s → 4s delays
    initial_delay=1.0,
    max_delay=10.0,            # Cap at 10 seconds
    exceptions=(
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.RequestException
    )
)
def _fetch_page(page: int, limit: int = 100) -> Dict:
    """Fetch page with automatic retry on network errors"""
    # Implementation handles:
    # - Timeout errors: retries with exponential backoff
    # - Connection errors: retries with exponential backoff
    # - HTTP 5xx errors: retries with exponential backoff
    # - HTTP 4xx errors: fails immediately (don't retry)
    # - Invalid JSON: fails immediately
```

### Retry Decision Tree

```
Network Error?
├─ Yes → Retry with exponential backoff
└─ No → Check HTTP Status
    ├─ 5xx (Server Error) → Retry with backoff
    ├─ 4xx (Client Error) → Fail immediately
    ├─ 3xx (Redirect) → Follow/Fail
    └─ 2xx (Success) → Process response
```

**Exponential Backoff Formula:**
```
delay = initial_delay × (backoff_factor ^ attempt)
delay = min(delay, max_delay)  # Cap at maximum

Example with backoff_factor=2:
Attempt 1: 1 second
Attempt 2: 2 seconds
Attempt 3: 4 seconds (max capped at 10)
```

---

## 3. Logging System

### Setup (`utils/logger.py`)

```python
from utils.logger import logger, log_event, log_error, log_warning

# Automatic setup with:
# - Console output (INFO and above)
# - File logging to review_system.log (DEBUG and above)
# - Structured format with timestamps and context
# - Color-coded console output
# - Exception stack traces in logs
```

### Log Levels (Mandatory Usage)

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Internal state, variable values | `logger.debug("Processing started")`  |
| INFO | Normal execution flow | `logger.info("Successfully fetched 100 reviews")` |
| WARNING | Recoverable issues, degradation | `logger.warning("Missing column, using default")` |
| ERROR | Component failure, retries exhausted | `logger.error("API failed after 3 retries")` |
| CRITICAL | System-level failure | `logger.critical("Database connection lost")` |

### Structured Logging Functions

```python
# Event logging
log_event("PIPELINE_START", {
    "method": "robust_data_pipeline",
    "max_pages": 5
})

# Error logging with context
log_error(
    "API_TIMEOUT",
    "Request timed out after 10 seconds",
    {"page": 3, "url": "https://...", "attempt": 2}
)

# Warning logging
log_warning(
    "MISSING_COLUMN",
    "Column 'sentiment_score' missing from API response",
    {"page": 1, "expected_columns": 9, "received_columns": 8}
)

# Performance logging
log_performance("scoring_engine", duration_ms=245.3, row_count=500)
```

### Log Output Format

```
2026-04-09 15:46:41 | INFO     | review_system        | EVENT: FETCH_PAGE | Details: {'page': 1, 'records': 100}
2026-04-09 15:46:45 | WARNING  | review_system        | WARNING: API_TIMEOUT - Timeout fetching page 2
2026-04-09 15:46:48 | ERROR    | review_system        | ERROR: API_ERROR - Failed after 3 retries
2026-04-09 15:46:50 | INFO     | review_system        | PERFORMANCE: fetch_reviews completed in 1234.5ms
```

---

## 4. Safe Operations Decorators

### `@catch_and_log` - Safe Graceful Degradation

```python
from utils.error_handler import catch_and_log

@catch_and_log(
    default_return=pd.DataFrame(),
    log_level="error",
    error_type="SCORING_FAILED"
)
def compute_scores(df):
    """Compute scores - returns empty DataFrame on error instead of crashing"""
    # If any exception occurs:
    # 1. Logs the full exception
    # 2. Returns default_return (empty DataFrame)
    # 3. Never raises exception
    return apply_scoring_pipeline(df)

# Usage - never crashes
result = compute_scores(df)  # Returns DataFrame or [] on error
```

### `@retry_with_backoff` - Automatic Retries

```python
@retry_with_backoff(
    max_retries=3,
    backoff_factor=2.0,
    exceptions=(requests.exceptions.Timeout,)
)
def fetch_api_data():
    """Automatically retries on timeout"""
    # Automatic retry logic included
    pass
```

---

## 5. Validation Functions

### Schema Validation

```python
from utils.error_handler import assert_schema

# Usage in pipeline
try:
    assert_schema(
        df,
        required_columns=['rating', 'sentiment_score', 'customer_ltv'],
        context="Review processing"
    )
except DataError as e:
    logger.error(str(e))  # Logs: "Schema validation failed - Review processing: ..."
```

### Empty Data Validation

```python
from utils.error_handler import assert_not_empty

try:
    assert_not_empty(df, context="Scoring phase")
except DataError as e:
    logger.error(str(e))  # Logs: "Empty dataset - Scoring phase"
```

### Safe Nested Dictionary Access

```python
from utils.error_handler import safe_get_nested

value = safe_get_nested(
    api_response,
    keys=['data', 'metrics', 'average_score'],
    default=0.0
)
# Returns value or 0.0, never crashes on missing keys
```

---

## 6. Graceful Degradation Patterns

### Pattern 1: Fallback Data

```python
from utils.error_handler import catch_and_log
import pandas as pd

@catch_and_log(
    default_return=pd.DataFrame({
        'rating': [],
        'sentiment': [],
        'customer_ltv': []
    }),
    error_type="DATA_FETCH_FAILED"
)
def get_reviews():
    """Fetch reviews, return empty DataFrame on failure"""
    return fetch_reviews(max_pages=5)

# UI layer usage
df = get_reviews()
if df.empty:
    st.warning("No data available. Please check API and try again later.")
else:
    st.success(f"Loaded {len(df)} reviews")
```

### Pattern 2: Skip Bad Records

```python
try:
    # Process reviews
    df = preprocess_data(df)
    
    # Drop records with critical missing values
    df = df.dropna(subset=['rating', 'customer_ltv'])
    
    # Continue processing
    df = apply_scoring_pipeline(df)
    
except Exception as e:
    logger.error(f"Processing error: {e}")
    # Return partial results if possible
    return df.dropna(subset=['rating'])
```

### Pattern 3: Partial Processing

```python
class SafePipeline:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def run(self, df):
        try:
            # Stage 1: Fetch & Validate
            df = self._validate_data(df)
        except Exception as e:
            self.errors.append(f"Validation failed: {e}")
            logger.error(str(e))

        try:
            # Stage 2: Preprocess
            df = self._preprocess(df)
        except Exception as e:
            self.errors.append(f"Preprocessing failed: {e}")
            self.warnings.append("Skipping preprocessing")
            logger.warning(str(e))

        try:
            # Stage 3: Score
            df = self._score(df)
        except Exception as e:
            self.errors.append(f"Scoring failed: {e}")
            self.warnings.append("Using default scores")
            logger.error(str(e))

        return df, self.errors, self.warnings
```

---

## 7. UI Error Presentation

### Safe UI Pattern (`app.py`)

```python
import streamlit as st
from utils.error_handler import ErrorState
from services.data_robustness import robust_data_pipeline

# DO: Use try-catch with user-friendly messages
try:
    with st.spinner("Processing data..."):
        df, report = robust_data_pipeline(max_pages=5, include_report=True)
    
    if report["success"]:
        st.success("✅ Data processed successfully!")
    else:
        # Show warnings, not errors
        for warning in report.get("warnings", []):
            st.warning(f"⚠️ {warning}")

except Exception as e:
    # DON'T show raw exception
    # st.error(str(e))  # ❌ BAD
    
    # DO show user-friendly message
    st.error("""
        ❌ Unable to load reviews. Possible causes:
        - API server is temporarily down
        - Your internet connection is unstable
        
        Please try again in a few moments.
    """)
    logger.exception("Pipeline failed in UI")

# DON'T access undefined session_state attributes
# if st.session_state.data:  # ❌ BAD - crashes if not initialized
#     pass

# DO use safe access with defaults
if st.session_state.get("data_fetched", False):
    st.write("Data loaded successfully")
```

### Error State Object

```python
from utils.error_handler import ErrorState

error = ErrorState(
    error_type="API_TIMEOUT",
    message="Server took too long to respond",
    is_recoverable=True,
    suggestion="Please try again in a moment"
)

st.error(f"❌ {error.error_type}: {error.suggestion}")
```

---

## 8. Anti-Patterns (DO NOT USE)

### ❌ Silent Failures

```python
# BAD - swallows all information
try:
    result = dangerous_operation()
except:
    pass

# GOOD - logs before failing
try:
    result = dangerous_operation()
except Exception as e:
    logger.exception("Operation failed")
    raise
```

### ❌ Ignoring Errors

```python
# BAD - error disappears
except Exception:
    return None

# GOOD - error is logged with context
except Exception as e:
    logger.error(f"Failed to fetch: {e}", extra={"page": 1})
    return None
```

### ❌ Exposing Raw Exceptions to UI

```python
# BAD - shows technical details to user
st.error(str(exception))
st.write(traceback.format_exc())

# GOOD - shows user-friendly message
st.error("Unable to fetch data. Please try again later.")
logger.exception("Technical details for support")
```

### ❌ Bare Except

```python
# BAD - catches everything including KeyboardInterrupt
try:
    operation()
except:
    pass

# GOOD - catches specific exceptions
try:
    operation()
except (ValueError, KeyError) as e:
    logger.error(f"Invalid data: {e}")
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
```

---

## 9. Monitoring & Debugging

### View Logs

```bash
# Real-time log monitoring
tail -f review_system.log

# Filter by error level
grep "ERROR" review_system.log

# Filter by date
grep "2026-04-09" review_system.log

# Filter by component
grep "API" review_system.log
```

### Operation Metrics

```python
from utils.error_handler import OperationMetrics

metrics = OperationMetrics("data_processing")
try:
    # Do work
    process_data()
except Exception as e:
    metrics.add_error(str(e))

# Get report
report = metrics.report()
# {
#     "operation": "data_processing",
#     "duration_ms": 1234.5,
#     "errors": 1,
#     "warnings": 2,
#     "error_list": ["..."],
#     "warning_list": ["..."]
# }
```

### Common Error Scenarios

| Scenario | Log Message | Recovery |
|----------|-------------|----------|
| API timeout | `[Timeout] fetch_page attempt 1/3` | Retry with backoff |
| Connection error | `[Connection Error] Failed to connect to API` | Retry with backoff |
| Invalid JSON | `ERROR: API_INVALID_JSON - Invalid JSON response` | Fail fast, don't retry |
| Missing column | `WARNING: API_MISSING_COLUMNS - missing: ['rating']` | Add column with null |
| Empty dataset | `ERROR: API_NO_DATA - No reviews fetched` | Return error to UI |
| Scoring error | `ERROR: SCORING_ERROR - Unexpected value in computation` | Skip record, log warning |

---

## 10. Best Practices

### 1. Log with Context
```python
# BAD
logger.error("Failed to fetch")

# GOOD
logger.error(f"Failed to fetch page {page}", extra={
    "attempt": attempt,
    "timeout": timeout_seconds,
    "url": url
})
```

### 2. Use Specific Exceptions
```python
# BAD
except Exception:
    pass

# GOOD
except (requests.Timeout, requests.ConnectionError) as e:
    logger.warning(f"Network error: {e}")
except requests.HTTPError as e:
    logger.error(f"Server error: {e.response.status_code}")
```

### 3. Include Recovery Information
```python
logger.error(
    "API failed",
    extra={
        "recovery_action": "Use fallback data",
        "next_step": "Check API status",
        "timestamp": datetime.now().isoformat()
    }
)
```

### 4. Test Error Paths
```python
# Test timeout handling
def test_api_timeout():
    with pytest.raises(APIError):
        fetch_page_with_timeout()

# Test fallback
def test_empty_data_fallback():
    result = fetch_reviews_safe()
    assert isinstance(result, pd.DataFrame)
    assert result.empty or len(result) > 0
```

---

## Summary

The RIE Error Handling & Logging system ensures:

✅ **Reliability**: Never crashes, always returns valid output
✅ **Debuggability**: Full logs with context for every operation
✅ **Usability**: Clean, user-friendly error messages in UI
✅ **Maintainability**: Structured approach makes issues easy to trace
✅ **Recoverability**: Graceful degradation allows system to continue operating

**Remember**: 
- **Log everything** important
- **Handle failures** gracefully
- **Never expose** raw exceptions to users
- **Always provide** context in logs
- **Test error paths** thoroughly

