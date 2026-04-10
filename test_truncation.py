"""
Test to identify WHERE the 5000-review truncation is happening
Traces: Mosaic API → Flask → Dashboard
"""
import requests
import json

print("=" * 70)
print("TRUNCATION DIAGNOSIS: Trace data flow through Flask API")
print("=" * 70)

# Test 1: Check what Flask API /api/data/default returns
print("\n[TEST 1] /api/data/default endpoint")
print("-" * 70)
try:
    r = requests.post("http://localhost:5000/api/data/default")
    data = r.json()
    print(f"✓ Status: {r.status_code}")
    print(f"✓ Products returned: {len(data.get('products', []))}")
    print(f"✓ Reviews in stats: {data.get('stats', {}).get('reviews', 'N/A')}")
    print(f"  Details: {data.get('stats')}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: Check what Flask API /api/health returns
print("\n[TEST 2] /api/health endpoint")
print("-" * 70)
try:
    r = requests.get("http://localhost:5000/api/health")
    health = r.json()
    print(f"✓ Status: {r.status_code}")
    print(f"✓ Response: {json.dumps(health, indent=2)}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: Check /api/data/current to see stored session data
print("\n[TEST 3] /api/data/current endpoint (stored session data)")
print("-" * 70)
try:
    r = requests.get("http://localhost:5000/api/data/current")
    data = r.json()
    print(f"✓ Status: {r.status_code}")
    if 'record_count' in data:
        print(f"✓ Session record_count: {data['record_count']}")
    if 'review_count_in_session' in data:
        print(f"✓ Session review count: {data['review_count_in_session']}")
    print(f"  Full response: {json.dumps(data, indent=2)[:500]}...")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 4: Import and test Python functions directly
print("\n[TEST 4] Direct Python test - check ingestion functions")
print("-" * 70)
try:
    from services.ingestion import fetch_reviews, fetch_dynamic_api
    from config import MOSAIC_API_URL, MOSAIC_DEFAULT_API_KEY
    
    print(f"✓ Mosaic API URL: {MOSAIC_API_URL}")
    print(f"✓ Has API key: {bool(MOSAIC_DEFAULT_API_KEY)}")
    
    # Test fetch_reviews with default max_pages
    print("\n  Testing fetch_reviews() with default max_pages...")
    df_reviews = fetch_reviews(max_pages=None)  # Should be 50 pages by default
    print(f"  ✓ fetch_reviews() returned: {len(df_reviews)} reviews")
    
    # Test fetch_reviews with explicit 1 page
    print("\n  Testing fetch_reviews() with max_pages=1...")
    df_one = fetch_reviews(max_pages=1)
    print(f"  ✓ fetch_reviews(max_pages=1) returned: {len(df_one)} reviews")
    
    # Test fetch_dynamic_api
    print("\n  Testing fetch_dynamic_api()...")
    df_dynamic = fetch_dynamic_api(api_url=MOSAIC_API_URL, api_key=MOSAIC_DEFAULT_API_KEY)
    print(f"  ✓ fetch_dynamic_api() returned: {len(df_dynamic)} reviews")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 70)
print("DIAGNOSIS SUMMARY")
print("=" * 70)
print("""
Expected behavior:
  - fetch_reviews()        → Should return ~5000 reviews (50 pages × 100/page)
  - fetch_reviews(max_pages=1) → Should return ~100 reviews (1 page × 100/page)
  - fetch_dynamic_api()    → Should return whatever API returns
  - /api/data/default      → Should return 5 sample reviews

If any returns 100 when expecting 5000, that's the truncation point.
""")
