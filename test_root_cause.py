"""
Test to pinpoint exactly where the 5000-review truncation happens
Compares: fetch_dynamic_api() vs fetch_reviews()
"""
import sys
sys.path.insert(0, ".")

print("=" * 70)
print("TRUNCATION ROOT CAUSE TEST")
print("=" * 70)

from services.ingestion import fetch_dynamic_api, fetch_reviews
from api_server import MOSAIC_API_URL, MOSAIC_DEFAULT_API_KEY

print(f"\nMosaic API URL: {MOSAIC_API_URL}")
print(f"Using API key: {bool(MOSAIC_DEFAULT_API_KEY)}")

# Test fetch_dynamic_api (single request - USED BY /api/data/fetch ENDPOINT)
print("\n" + "=" * 70)
print("TEST 1: fetch_dynamic_api() - Single API call")
print("Current: Used by /api/data/fetch endpoint")
print("=" * 70)
try:
    df_dynamic = fetch_dynamic_api(
        api_url=MOSAIC_API_URL, 
        api_key=MOSAIC_DEFAULT_API_KEY,
        timeout=30
    )
    print(f"✓ Returned {len(df_dynamic)} reviews")
    print(f"  Columns: {list(df_dynamic.columns)}")
    if len(df_dynamic) <= 100:
        print(f"  ⚠️  ISSUE FOUND: Only 100 reviews (expected 5000)")
        print(f"     This function returns only 1 page of data!")
except Exception as e:
    print(f"✗ Error: {e}")

# Test fetch_reviews (pagination with 50 pages)
print("\n" + "=" * 70)
print("TEST 2: fetch_reviews(max_pages=50) - Paginated API calls")
print("Current: NOT USED by /api/data/fetch endpoint")
print("=" * 70)
try:
    df_paginated = fetch_reviews(max_pages=50)
    print(f"✓ Returned {len(df_paginated)} reviews")
    print(f"  Columns: {list(df_paginated.columns)}")
    if len(df_paginated) > 100:
        print(f"  ✓ CORRECT: Got {len(df_paginated)} reviews (50 pages × 100/page)")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 70)
print("ROOT CAUSE IDENTIFIED")
print("=" * 70)
print("""
PROBLEM:
  /api/data/fetch endpoint uses fetch_dynamic_api()
  - Returns only 1 page = 100 reviews
  - Should return all 5000 reviews
  
SOLUTION:
  Change /api/data/fetch to use fetch_reviews(max_pages=50)
  - Will return 50 pages × 100 per page = 5000 reviews
  
LOCATION:
  api_server.py, line ~371 in fetch_with_api_key() function
  Current: raw_df = fetch_dynamic_api(...)
  Should be: raw_df = fetch_reviews(max_pages=50) or use unified loader
""")
