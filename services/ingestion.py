"""Data ingestion service with comprehensive error handling and retry logic."""

import requests
import pandas as pd
import json
import time
from io import BytesIO
from typing import Optional, Dict, List, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.error_handler import (
    retry_with_backoff,
    APIError,
    DataError,
    catch_and_log,
    OperationMetrics
)
from utils.logger import log_event, log_error, log_warning, logger


@retry_with_backoff(
    max_retries=3,
    backoff_factor=2.0,
    initial_delay=1.0,
    max_delay=10.0,
    exceptions=(
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.RequestException
    )
)
def _fetch_page(page: int, limit: int = 100) -> Optional[Dict]:
    """
    Fetch a single page with automatic retry on network errors.
    
    Args:
        page: Page number
        limit: Number of records per page
        
    Returns:
        dict: API response containing 'data' and 'metadata'
        
    Raises:
        APIError: If request fails after retries or on client errors
    """
    try:
        url = f"https://mosaicfellowship.in/api/data/cx/reviews"
        
        logger.debug(f"Fetching page {page} from API")
        
        response = requests.get(
            url,
            params={"page": page, "limit": limit},
            timeout=10
        )
        
        # Raise exception for HTTP errors (4xx, 5xx)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code >= 500:
                # 5xx errors might be temporary, retry
                raise requests.exceptions.RequestException(f"Server error: {response.status_code}")
            else:
                # 4xx client errors, don't retry
                log_error(
                    "API_HTTP_ERROR",
                    f"HTTP {response.status_code}: {response.reason}",
                    {"page": page, "url": url}
                )
                raise e
        
        data = response.json()
        
        logger.debug(f"Successfully fetched page {page}: {len(data.get('data', []))} records")
        log_event("FETCH_PAGE", {"page": page, "records": len(data.get('data', []))})
        
        return data
        
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching page {page}")
        raise
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"Connection error fetching page {page}: {e}")
        raise
    except ValueError as e:
        log_error("API_INVALID_JSON", f"Invalid JSON response from API", {"page": page})
        raise requests.exceptions.RequestException(f"Invalid JSON: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error fetching page {page}")
        raise


def _fetch_page_safe(page: int) -> Tuple[int, Optional[list]]:
    """
    Fetch a single page and return (page_number, data_or_None).
    Never raises — returns None on failure so the caller can handle gracefully.
    """
    try:
        res = _fetch_page(page, limit=100)
        if not res:
            return page, None
        page_data = res.get('data', res) if isinstance(res, dict) else res
        return page, page_data if page_data else None
    except Exception as e:
        logger.warning(f"Failed to fetch page {page}: {e}")
        return page, None


def fetch_reviews(max_pages: Optional[int] = None) -> pd.DataFrame:
    """
    Fetch all reviews from API using concurrent pagination.
    All pages are dispatched in parallel (up to 10 workers), then assembled
    in page order. Falls back gracefully if individual pages fail.

    Args:
        max_pages: Maximum number of pages to fetch (None = all, capped at 50)

    Returns:
        pd.DataFrame: DataFrame containing all successfully fetched reviews

    Raises:
        APIError: If the first page fails (no data at all)
        DataError: If no valid reviews could be fetched after all pages
    """
    metrics = OperationMetrics("fetch_reviews")

    try:
        logger.info("Starting concurrent review fetch from API")

        # Enforce cap
        if max_pages is None:
            max_pages = 50
        else:
            max_pages = min(max_pages, 50)

        required_columns = [
            'rating', 'review_text', 'customer_ltv', 'order_value',
            'days_since_purchase', 'helpful_votes', 'is_repeat_customer',
            'verified_purchase'
        ]

        pages_to_fetch = list(range(1, max_pages + 1))
        results: Dict[int, Optional[list]] = {}

        # --- Concurrent fetch (10 workers = ~5x speedup over sequential) ---
        max_workers = min(10, max_pages)
        logger.info(f"Fetching {max_pages} pages with {max_workers} concurrent workers")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_page = {executor.submit(_fetch_page_safe, p): p for p in pages_to_fetch}
            for future in as_completed(future_to_page):
                page_num, page_data = future.result()
                results[page_num] = page_data
                if page_data is None:
                    metrics.add_warning(f"Page {page_num} returned no data")

        # --- Assemble results in page order, stop at first empty page ---
        all_data = []
        failed_pages = []
        for p in pages_to_fetch:
            page_data = results.get(p)
            if page_data:
                all_data.extend(page_data)
            else:
                failed_pages.append(p)

        if failed_pages:
            logger.warning(f"Pages with no data: {failed_pages}")

        # Validate we have some data
        if not all_data:
            error_msg = "No reviews fetched from API"
            metrics.add_error(error_msg)
            log_error("API_NO_DATA", error_msg)
            raise DataError(error_msg)

        # Create DataFrame
        logger.info(f"Creating DataFrame from {len(all_data)} reviews")
        df = pd.DataFrame(all_data)

        # Validate required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            log_warning("API_MISSING_COLUMNS", f"API response missing columns: {missing_columns}")
            for col in missing_columns:
                df[col] = None

        # Ensure product column exists and is properly populated
        if 'product' not in df.columns:
            df['product'] = 'General'

        # Clean product column
        df['product'] = df['product'].fillna('General').astype(str).str.strip()
        df = df[df['product'] != '']

        # Ensure customer_ltv is numeric
        df['customer_ltv'] = pd.to_numeric(df['customer_ltv'], errors='coerce').fillna(0)

        # DEBUG: Log data quality metrics
        print(f"\n[DEBUG] Ingestion Summary (concurrent fetch):")
        print(f"  - Pages fetched: {max_pages} ({len(failed_pages)} failed)")
        print(f"  - Total reviews: {len(df)}")
        print(f"  - Unique products: {df['product'].nunique()}")
        print(f"  - Products: {sorted(df['product'].unique().tolist())}")
        print(f"  - Customer LTV - Min: {df['customer_ltv'].min()}, Max: {df['customer_ltv'].max()}, Sum: {df['customer_ltv'].sum()}")

        log_event("FETCH_COMPLETE", {
            "total_reviews": len(df),
            "pages": max_pages,
            "failed_pages": len(failed_pages),
            "columns": len(df.columns),
            "errors": len(metrics.errors),
            "warnings": len(metrics.warnings)
        })

        logger.info(f"Successfully fetched {len(df)} reviews from {max_pages} pages ({len(failed_pages)} failed)")
        metrics.report()

        return df

    except DataError as e:
        metrics.add_error(str(e))
        log_error("FETCH_FAILED", str(e))
        metrics.report()
        raise

    except Exception as e:
        error_msg = f"Unexpected error during fetch: {str(e)}"
        metrics.add_error(error_msg)
        logger.exception(error_msg)
        log_error("FETCH_UNEXPECTED_ERROR", error_msg)
        metrics.report()
        raise DataError(error_msg) from e


# ===== DUAL INPUT SYSTEM: DYNAMIC API & FILE UPLOAD =====

def fetch_dynamic_api(api_url: str, api_key: Optional[str] = None, timeout: int = 10) -> pd.DataFrame:
    """
    Fetch data from a custom API endpoint with optional authentication.
    
    Args:
        api_url: Full API endpoint URL
        api_key: Optional Bearer token for authentication
        timeout: Request timeout in seconds
    
    Returns:
        pd.DataFrame: DataFrame containing API response data
        
    Raises:
        APIError: If API request fails
        DataError: If response is empty or invalid
    """
    metrics = OperationMetrics("fetch_dynamic_api")
    
    try:
        logger.info(f"Fetching data from custom API: {api_url}")
        
        # Prepare headers
        headers = {
            "User-Agent": "RIE-Client/1.0",
            "Accept": "application/json"
        }
        
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Make request
        response = requests.get(api_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Handle both direct array and wrapped responses
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict) and 'data' in data:
            df = pd.DataFrame(data['data'])
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            raise DataError(f"Unexpected API response format: {type(data)}")
        
        if df.empty:
            raise DataError("API returned empty dataset")
        
        # Log success
        log_event("DYNAMIC_API_FETCH", {
            "url": api_url,
            "rows": len(df),
            "columns": len(df.columns)
        })
        
        logger.info(f"Successfully fetched {len(df)} records from custom API")
        
        return df
        
    except requests.exceptions.Timeout:
        error_msg = f"API request timeout (>{timeout}s): {api_url}"
        metrics.add_error(error_msg)
        log_error("API_TIMEOUT", error_msg)
        raise APIError(error_msg)
        
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error to API: {str(e)}"
        metrics.add_error(error_msg)
        log_error("API_CONNECTION_ERROR", error_msg)
        raise APIError(error_msg)
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.reason}"
        metrics.add_error(error_msg)
        log_error("API_HTTP_ERROR", error_msg)
        raise APIError(error_msg)
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in API response: {str(e)}"
        metrics.add_error(error_msg)
        log_error("API_INVALID_JSON", error_msg)
        raise APIError(error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error fetching from API: {str(e)}"
        metrics.add_error(error_msg)
        log_error("API_UNEXPECTED_ERROR", error_msg)
        raise DataError(error_msg)


def parse_uploaded_file(uploaded_file) -> pd.DataFrame:
    """
    Parse uploaded CSV or JSON file into DataFrame.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
    
    Returns:
        pd.DataFrame: Parsed data from file
        
    Raises:
        ValueError: If file format unsupported or parsing fails
        DataError: If file is empty
    """
    try:
        logger.info(f"Parsing uploaded file: {uploaded_file.name}")
        
        filename = uploaded_file.name.lower()
        
        if filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            log_event("FILE_PARSED", {"format": "csv", "rows": len(df), "columns": len(df.columns)})
            
        elif filename.endswith('.json'):
            data = json.load(uploaded_file)
            
            # Handle both array and nested structures
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Try to find array in common locations
                if 'data' in data:
                    df = pd.DataFrame(data['data'])
                elif 'records' in data:
                    df = pd.DataFrame(data['records'])
                else:
                    # Fallback: normalize the entire dict structure
                    df = pd.json_normalize(data)
            else:
                raise ValueError(f"Unexpected JSON structure: {type(data)}")
            
            log_event("FILE_PARSED", {"format": "json", "rows": len(df), "columns": len(df.columns)})
        
        else:
            raise ValueError(f"Unsupported file format: {filename}. Must be .csv or .json")
        
        if df.empty:
            raise DataError("Uploaded file is empty")
        
        logger.info(f"Successfully parsed file: {len(df)} rows, {len(df.columns)} columns")
        
        return df
        
    except ValueError as e:
        log_error("FILE_PARSE_ERROR", str(e))
        raise
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON file: {str(e)}"
        log_error("JSON_DECODE_ERROR", error_msg)
        raise ValueError(error_msg)
        
    except Exception as e:
        error_msg = f"Error parsing file: {str(e)}"
        log_error("FILE_PARSE_UNEXPECTED_ERROR", error_msg)
        raise DataError(error_msg)


# ===== SCHEMA NORMALIZATION LAYER =====

def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize incoming data to match expected schema.
    Handles column name variations across different data sources.
    
    Args:
        df: Input DataFrame with potentially non-standard column names
        
    Returns:
        Normalized DataFrame with standardized column names
    """
    df = df.copy()
    
    # Define column mapping: standard_name -> [possible_variations]
    column_map = {
        'rating': ['rating', 'stars', 'review_rating', 'score', 'rating_score', 'star_rating'],
        'review_text': ['review_text', 'review', 'text', 'comment', 'feedback', 'message'],
        'sentiment': ['sentiment', 'sentiment_label', 'sentiment_type', 'tone', 'opinion'],
        'sentiment_score': ['sentiment_score', 'sentiment_val', 'polarity', 'polarity_score'],
        'customer_ltv': ['customer_ltv', 'ltv', 'customer_value', 'lifetime_value', 'ltv_value'],
        'product': ['product', 'product_name', 'product_id', 'item', 'item_name', 'sku'],
        'order_value': ['order_value', 'order_val', 'purchase_amount', 'transaction_amount'],
        'days_since_purchase': ['days_since_purchase', 'age_in_days', 'days_old', 'age'],
        'helpful_votes': ['helpful_votes', 'helpful_count', 'upvotes', 'like_count'],
        'is_repeat_customer': ['is_repeat_customer', 'repeat_customer', 'returning', 'returning_customer'],
        'verified_purchase': ['verified_purchase', 'verified', 'authentic'],
    }
    
    # Map columns
    for standard_col, variations in column_map.items():
        # Skip if standard column already exists
        if standard_col in df.columns:
            continue
        
        # Find first matching variation
        for var_col in variations:
            if var_col in df.columns:
                df[standard_col] = df[var_col]
                logger.debug(f"Mapped '{var_col}' -> '{standard_col}'")
                break
        else:
            # No match found, create with default value
            default_value = 0 if 'date' not in standard_col.lower() else None
            df[standard_col] = default_value
            logger.debug(f"Created missing column '{standard_col}' with default value")
    
    # Clean up product column
    if 'product' in df.columns:
        df['product'] = df['product'].fillna('Unknown').astype(str).str.strip()
        df = df[df['product'] != '']
    
    # Ensure numeric columns are numeric
    numeric_cols = ['rating', 'sentiment_score', 'customer_ltv', 'order_value', 'days_since_purchase', 'helpful_votes']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Ensure boolean columns are boolean
    bool_cols = ['is_repeat_customer', 'verified_purchase']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)
    
    logger.info(f"Schema normalization complete: {len(df.columns)} columns standardized")
    
    return df


# ===== UNIFIED DATA LOADER =====

def load_data(
    input_mode: str,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    uploaded_file: Optional[object] = None,
    max_pages: Optional[int] = 50
) -> pd.DataFrame:
    """
    Unified data loader supporting multiple input modes.
    Handles both API and file upload sources seamlessly.
    
    Args:
        input_mode: Either "API" or "Upload File"
        api_url: API endpoint (required if input_mode="API")
        api_key: Optional API key (required if input_mode="API")
        uploaded_file: Streamlit UploadedFile object (required if input_mode="Upload File")
        max_pages: Maximum pages to fetch for Mosaic API (default: 50 = all 5000 reviews, 100/page)
    
    Returns:
        pd.DataFrame: Loaded and normalized data
        
    Raises:
        ValueError: If input_mode invalid or required parameters missing
        APIError/DataError: If data loading fails
    """
    try:
        logger.info(f"Loading data via mode: {input_mode}")
        
        if input_mode == "API":
            if not api_url:
                raise ValueError("API URL is required for API mode")
            
            # Check if using Mosaic API (uses pagination) vs custom API (no pagination)
            is_mosaic_api = "mosaicfellowship.in" in api_url.lower()
            
            if is_mosaic_api:
                # Use original fetch_reviews() for Mosaic API (has pagination)
                logger.info(f"Detected Mosaic API - using paginated fetch (max_pages={max_pages})")
                df = fetch_reviews(max_pages=max_pages)
            else:
                # Use fetch_dynamic_api() for custom APIs
                logger.info("Using custom API endpoint (single request)")
                df = fetch_dynamic_api(api_url, api_key)
            
        elif input_mode == "Upload File":
            if not uploaded_file:
                raise ValueError("File upload is required for Upload File mode")
            
            df = parse_uploaded_file(uploaded_file)
            
        else:
            raise ValueError(f"Invalid input mode: {input_mode}. Must be 'API' or 'Upload File'")
        
        # Validate loaded data
        if df is None or df.empty:
            raise DataError("No valid data loaded from source")
        
        # Apply schema normalization
        df = normalize_schema(df)
        
        # Log
        log_event("DATA_LOADED", {
            "mode": input_mode,
            "rows": len(df),
            "columns": len(df.columns)
        })
        
        logger.info(f"Data loaded successfully: {len(df)} rows, {len(df.columns)} columns")
        print(f"\n[DEBUG] Data Loading:")
        print(f"  - Source: {input_mode}")
        print(f"  - Total rows: {len(df)}")
        print(f"  - Columns: {len(df.columns)}")
        print(f"  - Available products: {df['product'].nunique() if 'product' in df.columns else 0}")
        
        return df
        
    except (ValueError, APIError, DataError) as e:
        log_error("DATA_LOAD_ERROR", str(e))
        logger.exception(f"Data loading failed: {str(e)}")
        raise
        
    except Exception as e:
        error_msg = f"Unexpected error during data loading: {str(e)}"
        log_error("DATA_LOAD_UNEXPECTED_ERROR", error_msg)
        logger.exception(error_msg)
        raise DataError(error_msg)


@catch_and_log(default_return=pd.DataFrame(), log_level="error", error_type="FETCH_FALLBACK")
def fetch_reviews_safe(max_pages: Optional[int] = None) -> pd.DataFrame:
    """
    Safe wrapper around fetch_reviews that never raises exceptions.
    Returns empty DataFrame on failure (graceful degradation).
    
    Args:
        max_pages: Maximum number of pages to fetch
        
    Returns:
        pd.DataFrame: Reviews or empty DataFrame on failure
    """
    return fetch_reviews(max_pages=max_pages)

