"""Data ingestion service with error handling and retry logic."""

import requests
import pandas as pd
import time
from utils.error_handler import retry_with_backoff, APIError
from utils.logger import log_event, log_error, logger
from utils.cache import cached


@retry_with_backoff(max_retries=3, backoff_factor=2.0)
def _fetch_page(page: int, limit: int = 100) -> dict:
    """
    Fetch a single page with retry logic.
    
    Args:
        page: Page number
        limit: Number of records per page
        
    Returns:
        dict: API response
        
    Raises:
        APIError: If request fails
    """
    try:
        url = f"https://mosaicfellowship.in/api/data/cx/reviews?page={page}&limit={limit}"
        res = requests.get(url, timeout=10)
        res.raise_for_status()  # Raise exception for bad status codes
        return res.json()
    except requests.RequestException as e:
        log_error("API_REQUEST_FAILED", str(e), {"page": page})
        raise APIError(f"Failed to fetch page {page}: {str(e)}")


@cached(ttl=300)  # Cache for 5 minutes
def fetch_reviews(max_pages: int = None) -> pd.DataFrame:
    """
    Fetch all reviews from API using pagination with retry logic.
    
    Args:
        max_pages: Maximum number of pages to fetch (None = unlimited)
    
    Returns:
        pd.DataFrame: DataFrame containing all reviews with required columns
        
    Raises:
        ValueError: If required columns are missing
        APIError: If data fetch fails after retries
    """
    all_data = []
    page = 1
    required_columns = [
        'rating',
        'review_text',
        'customer_ltv',
        'order_value',
        'days_since_purchase',
        'helpful_votes',
        'is_repeat_customer',
        'verified_purchase'
    ]
    
    try:
        while max_pages is None or page <= max_pages:
            log_event("FETCH_PAGE", {"page": page})
            
            res = _fetch_page(page)
            
            if not res.get('data'):
                logger.info(f"Empty page received at page {page}. Stopping pagination.")
                break
            
            all_data.extend(res['data'])
            page += 1
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
        
        log_event("FETCH_COMPLETE", {"total_reviews": len(all_data), "pages": page - 1})
        
        if not all_data:
            logger.warning("No reviews fetched from API")
            return pd.DataFrame(columns=required_columns)
        
        df = pd.DataFrame(all_data)
        
        # Validate required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            log_error("MISSING_COLUMNS", "Required columns not found", {"missing": missing_columns})
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Add product column if missing (for MVP aggregation)
        if 'product' not in df.columns:
            df['product'] = 'General'
        
        return df
        
    except APIError as e:
        log_error("API_ERROR", "Failed to fetch reviews after retries", {"error": str(e)})
        raise
    except Exception as e:
        log_error("UNEXPECTED_ERROR", str(e), {"context": "fetch_reviews"})
        raise
