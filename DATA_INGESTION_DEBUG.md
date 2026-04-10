## DATA INGESTION + UI INTEGRATION DEBUG GUIDE

This guide explains the data flow and how to debug issues with the data source configuration system.

---

## SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER BROWSER                                 │
│                   (HTML/JS Frontend)                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ dashboard.html + script.js                               │  │
│  │ - Data source config UI                                  │  │
│  │ - Dashboard/charts/tables                                │  │
│  │ - Local state management (PRODUCTS array)                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP API Calls
                         │ (fetch API)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK API SERVER (5000)                      │
│                      (api_server.py)                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ /api/data/default       - Load default sample data       │  │
│  │ /api/data/fetch         - Fetch from Mosaic API          │  │
│  │ /api/data/upload        - Parse CSV/JSON upload          │  │
│  │ /api/data/current       - Get currently loaded data      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ├─→ services.ingestion.fetch_dynamic_api │
│                         ├─→ services.scoring_engine.*            │
│                         └─→ pandas (CSV/JSON parsing)            │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
    [Mosaic API]   [Uploaded Files]  [Python Backend]
```

---

## DATA FLOW

### 1. DEFAULT DATA LOAD

```
Click "Use Default" Button
  ↓
POST /api/data/default
  ↓
api_server.py: generate sample data
  ↓
normalize_dataframe() → validate schema
  ↓
transform_to_dashboard_format() → convert to PRODUCTS format
  ↓
Return JSON: {success: true, products: [...]}
  ↓
script.js: Update PRODUCTS array, re-render dashboard
```

### 2. API KEY FETCH

```
Enter API Key + Click "Connect API"
  ↓
POST /api/data/fetch {api_key: "..."}
  ↓
api_server.py: call fetch_dynamic_api(api_url, api_key)
  ↓
Mosaic API returns review data
  ↓
normalize_dataframe() → validate schema
  ↓
transform_to_dashboard_format()
  ↓
Return JSON: {success: true, products: [...]}
  ↓
script.js: Update PRODUCTS array, re-render dashboard
```

### 3. FILE UPLOAD

```
Select CSV/JSON file + Upload
  ↓
POST /api/data/upload (multipart form-data)
  ↓
api_server.py: Save file to uploads/ folder
  ↓
Parse CSV or JSON using pandas
  ↓
validate_schema() → Check required columns
  ↓
normalize_dataframe() → Fill missing columns
  ↓
transform_to_dashboard_format()
  ↓
Return JSON: {success: true, products: [...]}
  ↓
script.js: Update PRODUCTS array, re-render dashboard
```

---

## SETUP INSTRUCTIONS

### 1. Install Dependencies

```bash
cd "d:\0 to 1cr\Pratice\Review system"
.\.venv\Scripts\activate
pip install -r requirements.txt
```

**Ensure Flask and werkzeug are installed:**
```bash
pip install flask werkzeug
```

### 2. Set Mosaic API Key

Edit `api_server.py` line 30:

```python
MOSAIC_DEFAULT_API_KEY = "YOUR_ACTUAL_MOSAIC_KEY_HERE"
```

Or store in environment variable:
```python
import os
MOSAIC_DEFAULT_API_KEY = os.getenv("MOSAIC_API_KEY", "default_key")
```

### 3. Start Flask API Server

```bash
# Option 1: Run batch file
run_api_server.bat

# Option 2: Manual
.\.venv\Scripts\activate
python api_server.py
```

Server will start on `http://localhost:5000`

### 4. Access Dashboard

Open browser and go to:
```
http://localhost:5000/dashboard.html
```

---

## DEBUGGING CHECKLIST

### Issue: API calls not reaching server

**Check:**
1. Flask server is running: `http://localhost:5000/api/health`
2. Browser console for network errors (F12 → Network tab)
3. Check CORS issues (should not be an issue since same origin)
4. Check if port 5000 is in use: `netstat -ano | findstr :5000`

**Fix:**
```bash
# Kill process on port 5000
taskkill /PID <PID> /F

# Or use different port in api_server.py
app.run(port=5001)
```

---

### Issue: Default data not loading

**Debug steps:**

1. Check Flask logs for errors:
```
POST /api/data/default - 200 OK
[SUCCESS] Default data loaded
```

2. Check if sample_data is being generated:
```python
# Add logging in api_server.py
print(f"Sample data shape: {sample_data.shape}")
print(f"Products transformed: {len(products)}")
```

3. Open browser console: Check that PRODUCTS array is updated
```javascript
console.log(PRODUCTS);  // Should show new products
```

4. Check that dashboard re-renders by looking at KPI cards

---

### Issue: API Key fetch failing

**Debug steps:**

1. **Verify API key is correct:**
   - Test manually: `curl -H "Authorization: Bearer YOUR_KEY" https://mosaicfellowship.in/api/data/cx/reviews`
   
2. **Check Flask logs for errors:**
   ```
   Fetching data from Mosaic API with key: YOUR_KEY...
   API Error: [error message]
   ```

3. **Check ingestion service logs:**
   ```python
   # In api_server.py, add debugging
   print(f"Calling fetch_dynamic_api with: {MOSAIC_API_URL}")
   print(f"Response: {df.shape}")
   ```

4. **Common issues:**
   - Wrong API key format
   - Network timeout (increase timeout in api_server.py line 118)
   - API rate limiting

---

### Issue: File upload not working

**Debug steps:**

1. **Check file is being saved:**
   - Files should appear in `uploads/` folder
   - Check file size and format

2. **Check schema validation:**
   - Required columns: product_name, rating
   - If validation fails, error message shown in UI

3. **Check file parsing:**
   ```python
   # Add debugging in api_server.py
   print(f"File: {filename}")
   print(f"Rows: {len(df)}")
   print(f"Columns: {df.columns.tolist()}")
   ```

4. **Common issues:**
   - CSV encoding (try UTF-8)
   - Missing required columns
   - File too large (>50MB)

---

### Issue: Dashboard not updating after data load

**Debug steps:**

1. **Check network response:**
   - Open browser → F12 → Network tab
   - Look for POST request to /api/data/*
   - Check response JSON has `"success": true` and `products` array

2. **Check PRODUCTS array:**
   ```javascript
   // In script.js, after data fetch
   console.log("PRODUCTS array:", PRODUCTS);
   console.log("Length:", PRODUCTS.length);
   ```

3. **Check if GUI renders:**
   - Look at KPI cards, table, charts
   - Check console for JavaScript errors

4. **Force re-render:**
   - Click "Apply Filters" button
   - Should trigger applyFilters() and renderAll()

---

### Issue: Dashboard layout breaking after data load

**Debug steps:**

1. **Check console errors:**
   - Look for "Uncaught Error: Cannot read property X of undefined"
   - This means a column is missing in the product object

2. **Verify data transformation:**
   - In api_server.py, check transform_to_dashboard_format()
   - Ensure all required fields exist:
     ```python
     required_fields = [
         'name', 'date', 'finalScore', 'revenueAtRisk',
         'riskProbability', 'negativePct', 'quadrant',
         'frequency', 'impact', 'rating', 'trend',
         'severity', 'totalReviews', 'issues'
     ]
     ```

3. **Add validation:**
   - Check schema.normalize_dataframe() fills all defaults
   - Verify transform_to_dashboard_format() creates all fields

4. **Fix schema issues:**
   ```python
   # If column X is missing, add default:
   if 'missing_field' not in df.columns:
       df['missing_field'] = 'default_value'
   ```

---

## LOGGING & MONITORING

### Enable detailed logging

**Create `.env` file:**
```
LOG_LEVEL=DEBUG
FLASK_ENV=development
```

**Check logs:**
```bash
tail -f review_system.log
```

### Add debugging prints to api_server.py

```python
import sys

@app.route('/api/data/upload', methods=['POST'])
def upload_file():
    print("=== FILE UPLOAD DEBUG ===", file=sys.stderr)
    print(f"Files in request: {request.files.keys()}", file=sys.stderr)
    print(f"File size: {request.content_length}", file=sys.stderr)
    # ... rest of function
```

---

## TEST COMMANDS

### Test Flask health

```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "running",
  "timestamp": "2026-04-10T...",
  "data_loaded": false
}
```

### Test default data endpoint

```bash
curl -X POST http://localhost:5000/api/data/default
```

### Test API fetch endpoint

```bash
curl -X POST http://localhost:5000/api/data/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "YOUR_KEY",
    "use_default": false
  }'
```

### Test get current data

```bash
curl http://localhost:5000/api/data/current
```

---

## PERFORMANCE TIPS

1. **Limit API pages:** In api_server.py, adjust fetch_dynamic_api() max_pages parameter
2. **Cache data:** Store in session_data so repeated refreshes don't re-fetch
3. **Async loading:** Consider making file parsing async for large files
4. **Pagination:** For large datasets, implement dashboard pagination

---

## KNOWN ISSUES & WORKAROUNDS

| Issue | Workaround |
|-------|-----------|
| API times out after 30s | Increase timeout in api_server.py |
| Large file parsing is slow | Limit to first 10,000 rows in upload |
| Dashboard freezes on upload | Show progress bar for large files |
| API key keeps resetting | Store in localStorage in script.js |

---

## NEXT STEPS

1. **Set actual Mosaic API key** in api_server.py
2. **Test each endpoint** with curl commands above
3. **Monitor logs** for errors during operation
4. **Optimize performance** based on data size
5. **Add persistence** (save loaded data to file)
6. **Consider caching** for frequently accessed data

---

Generated: 2026-04-10
Review Intelligence Engine
