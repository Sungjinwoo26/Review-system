"""
Test: Verify 5000-review truncation is FIXED
Tests: /api/data/fetch endpoint after fix
"""
import requests
import time

print("=" * 70)
print("VERIFICATION TEST: 5000-Review Truncation Fix")
print("=" * 70)

time.sleep(2)  # Give server time to start

# Test 1: /api/data/fetch with default key
print("\n[TEST 1] /api/data/fetch with default Mosaic API key")
print("-" * 70)
try:
    r = requests.post(
        "http://localhost:5000/api/data/fetch",
        json={"use_default": True}
    )
    data = r.json()
    
    if r.status_code == 200:
        products = data.get('products', [])
        reviews = data.get('stats', {}).get('reviews', 0)
        print(f"[SUCCESS] Status: {r.status_code}")
        print(f"[SUCCESS] Reviews fetched: {reviews}")
        print(f"[SUCCESS] Products derived: {len(products)}")
        
        if reviews >= 5000:
            print(f"\n✓ FIXED! Got {reviews} reviews (expected ~5000)")
        elif reviews == 100:
            print(f"\n✗ ISSUE REMAINS: Still getting only 100 reviews")
        else:
            print(f"\n? Got {reviews} reviews (expected 5000)")
    else:
        print(f"[ERROR] Status: {r.status_code}")
        print(f"Response: {data}")
        
except Exception as e:
    print(f"[ERROR] Request failed: {e}")

# Test 2: Verify data in dashboard format
print("\n[TEST 2] Verify first product in dashboard format")
print("-" * 70)
try:
    r = requests.get("http://localhost:5000/api/data/current")
    data = r.json()
    
    if 'products' in data and len(data['products']) > 0:
        first_product = data['products'][0]
        print(f"[SUCCESS] First product: {first_product.get('name', 'N/A')}")
        print(f"  - Total Reviews: {first_product.get('totalReviews', 'N/A')}")
        print(f"  - Final Score: {first_product.get('finalScore', 'N/A')}")
        print(f"  - Risk Probability: {first_product.get('riskProbability', 'N/A')}")
    else:
        print("[INFO] No products in session yet (expected before first fetch)")
        
except Exception as e:
    print(f"[ERROR] Request failed: {e}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print("""
If you see:
  ✓ Reviews fetched: 5000+ → FIX SUCCESSFUL
  ✓ Reviews fetched: ~100  → FIX FAILED
  
Next steps:
  1. Open HTML/JS dashboard at http://localhost:5000
  2. Click "Use Mosaic API"
  3. Verify 5000+ reviews appear
  4. Check products and risk scores update correctly
""")
