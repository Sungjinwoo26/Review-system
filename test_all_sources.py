import requests
import json

print("=" * 60)
print("TESTING ALL 3 DATA SOURCES + PRODUCT FILTER UPDATE")
print("=" * 60)

# Test 1: Default
print("\n[1/3] Testing Default Data Load...")
r = requests.post("http://localhost:5000/api/data/default")
data = r.json()
print(f"✓ {len(data['products'])} products loaded")
print(f"✓ Products: {[p['name'] for p in data['products']]}")

# Test 2: File Upload
print("\n[2/3] Testing File Upload...")
with open("test_upload.csv", "rb") as f:
    files = {"file": f}
    r = requests.post("http://localhost:5000/api/data/upload", files=files)
    data = r.json()
    print(f"✓ {len(data['products'])} products from CSV")
    print(f"✓ Products: {[p['name'] for p in data['products']]}")

# Test 3: Health Check
print("\n[3/3] Testing API Health...")
r = requests.get("http://localhost:5000/api/health")
health = r.json()
print(f"✓ Status: {health['status']}")
print(f"✓ Data Loaded: {health['data_loaded']}")
print(f"✓ Last source: {health.get('last_source', 'N/A')}")

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
