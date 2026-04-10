import requests
import json

print("=" * 60)
print("TESTING FIXED API WITH REAL ML PIPELINE")
print("=" * 60)

with open("test_upload.csv", "rb") as f:
    files = {"file": f}
    r = requests.post("http://localhost:5000/api/data/upload", files=files)
    data = r.json()
    
    print(f"\nHTTP Status: {r.status_code}")
    print(f"Success: {data.get('success')}")
    print(f"Message: {data.get('message')}")
    print(f"Products Processed: {len(data.get('products', []))}")
    
    if data.get("success") and data.get("products"):
        print("\n" + "=" * 60)
        print("FIRST PRODUCT WITH REAL ML SCORES")
        print("=" * 60)
        prod = data["products"][0]
        
        print(f"Product Name:        {prod.get('name')}")
        print(f"Final Score (ML):    {prod.get('finalScore')}")
        print(f"Risk Probability:    {prod.get('riskProbability')}")
        print(f"Severity:            {prod.get('severity')}")
        print(f"Quadrant:            {prod.get('quadrant')}")
        print(f"Revenue At Risk:     {prod.get('revenueAtRisk')}")
        print(f"Total Reviews:       {prod.get('totalReviews')}")
        print(f"Raw Rating:          {prod.get('rating')}")
        print(f"Negative %:          {prod.get('negativePct')}")
        print(f"Frequency:           {prod.get('frequency')}")
        print(f"Impact Score:        {prod.get('impact')}")
        
        print("\n" + "=" * 60)
        print("STATS")
        print("=" * 60)
        stats = data.get("stats", {})
        print(f"Total Reviews Processed: {stats.get('reviews')}")
        print(f"Total Products: {stats.get('products')}")
        print(f"Source: {stats.get('source')}")
        
        print("\n✅ API IS WORKING WITH REAL ML PIPELINE!")
    else:
        print(f"\n❌ ERROR: {data.get('error')}")
