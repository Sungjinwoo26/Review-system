# 5000-REVIEW TRUNCATION ROOT CAUSE IDENTIFIED

## Summary
**The 5000-review truncation to 100 reviews is happening in `/api/data/fetch` endpoint.**

## The Problem

### Current Flow (BROKEN)
```
User sends API request to /api/data/fetch
        ↓
Flask endpoint calls fetch_dynamic_api()
        ↓
fetch_dynamic_api() makes SINGLE API call
        ↓
Mosaic API returns 1 page = 100 reviews
        ↓
Dashboard gets only 100 reviews instead of 5000 ✗
```

### Evidence
- **Test Result**: `fetch_dynamic_api()` returns **100 records** from single API call
- **Location**: `api_server.py`, line 371, function `fetch_with_api_key()`
- **Root Cause**: Using wrong function for Mosaic API pagination

### The Correct Flow (SHOULD BE)
```
User sends API request to /api/data/fetch
        ↓
Flask endpoint calls fetch_reviews(max_pages=50)
        ↓
fetch_reviews() makes PARALLEL paginated calls:
  - 50 pages × 100 reviews per page = 5000 reviews total
  - Uses ThreadPoolExecutor for concurrent fetching
        ↓
All 5000 reviews assembled and normalized
        ↓
Dashboard gets complete 5000 reviews ✓
```

## The Fix Required

**File**: `api_server.py`
**Function**: `fetch_with_api_key()` 
**Line**: ~371

### Current Code (BROKEN):
```python
# Call the real fetch function from services.ingestion
raw_df = fetch_dynamic_api(
    api_url=MOSAIC_API_URL,
    api_key=api_key,
    timeout=30
)
```

### Fixed Code:
```python
# Import fetch_reviews at top of file
from services.ingestion import fetch_reviews

# Then in fetch_with_api_key():
# Use paginated fetch for Mosaic API (5000 reviews = 50 pages × 100/page)
raw_df = fetch_reviews(max_pages=50)
```

## Impact

| Function | Returns | Use Case |
|----------|---------|----------|
| `fetch_dynamic_api()` | ~100 reviews | Custom single-request APIs |
| `fetch_reviews()` | ~5000 reviews | Mosaic API with pagination |

## Why This Happened

1. **Current `/api/data/fetch` uses `fetch_dynamic_api()`** 
   - Designed for generic single-request APIs
   - Returns whatever 1 API call gives (1 page = 100 records)
   
2. **But Mosaic API requires pagination**
   - Has 5000 reviews total
   - Splits into 50 pages of 100 reviews each
   - Needs `fetch_reviews()` to fetch all pages concurrently

3. **Two different fetch functions exist in codebase**
   - `fetch_reviews()` ← handles Mosaic API pagination ✓
   - `fetch_dynamic_api()` ← handles generic APIs (single call only) ✓
   - Wrong one was being used in Flask endpoint ✗

## Verification Steps

After fix is applied:
```
python test_root_cause.py

Expected output:
  TEST 1: fetch_dynamic_api() → 100 reviews ✓ (single API call)
  TEST 2: fetch_reviews()     → 5000 reviews ✓ (50 paginated calls)
```

## Dashboard Impact

Once fixed:
- HTML/JS dashboard will receive 5000 reviews instead of 100
- Product filtering will show complete dataset
- ML pipeline will process full data (better accuracy)
- Risk scores will be based on complete review set
- Reports will contain accurate statistics

---

**Status**: Root cause identified and documented. Ready for fix implementation.
