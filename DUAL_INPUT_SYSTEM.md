# 🧩 Dual Data Input System - RIE Dashboard

## Overview

The RIE dashboard now supports **two flexible data input methods**:
1. **API Mode** - Fetch data from any REST API with optional authentication
2. **Upload Mode** - Load data from CSV or JSON files

Both methods produce a standardized Pandas DataFrame that integrates seamlessly into the existing pipeline.

---

## ✅ Implementation Status

- ✅ API input handling with dynamic URLs
- ✅ File upload parsing (CSV & JSON)
- ✅ Schema normalization layer
- ✅ Unified data loader function
- ✅ Backward compatibility with Mosaic API
- ✅ Comprehensive error handling
- ✅ State management
- ✅ 50/50 tests passing (no regressions)

---

## 🎯 Key Features

### 1. API Mode
- **Dynamic URL**: Use any REST API endpoint
- **Authentication**: Optional Bearer token support
- **Flexible Response**: Handles both direct arrays and nested structures
- **Error Handling**: Timeout, connection, and HTTP error management
- **Default Fallback**: Pre-configured Mosaic API URL available

### 2. Upload Mode
- **CSV Support**: Direct CSV file parsing
- **JSON Support**: Handles both flat arrays and nested structures
- **Error Handling**: Invalid format and corrupt file detection
- **Streamlit Integration**: Native file uploader component

### 3. Schema Normalization
- **Column Mapping**: Automatically detects and normalizes column names
- **Type Conversion**: Ensures numeric columns are properly typed
- **Missing Columns**: Creates defaults for expected columns
- **Robustness**: Handles variations in naming across sources

---

## 📁 File Structure

### New Functions Added to `services/ingestion.py`:

```python
# Core dual input functions
fetch_dynamic_api()      # Fetch from custom API
parse_uploaded_file()    # Parse CSV/JSON files
normalize_schema()       # Standardize column names
load_data()             # Unified loader (main entry point)
```

### Updated `app.py`:
```python
# State management
init_session_state()    # Added input_mode, api_url, api_key states

# UI Components
input_mode selector     # Radio button: API vs Upload File
api_url input          # Text input for custom API URL
api_key input          # Password input for optional auth
file_uploader          # Streamlit file upload component

# Data Loading Logic
Updated fetch logic    # Uses load_data() instead of fetch_reviews()
```

---

## 🔧 Implementation Details

### 1. API Input Flow

```
User Selects "API" Mode
         ↓
[Optional] Enter Custom URL or Use Default
         ↓
[Optional] Enter API Key (Bearer token)
         ↓
Click "Load Data"
         ↓
fetch_dynamic_api(url, api_key)
  - Prepare headers with optional auth
  - Make GET request with timeout
  - Parse JSON response
  - Handle various response formats
         ↓
normalize_schema(df)
  - Map column variations to standard names
  - Convert types (numeric, boolean)
  - Handle missing columns
         ↓
load_data() returns normalized DataFrame
         ↓
Pipeline processes data
```

**Example Usage:**
```python
# Default Mosaic API
df = load_data(
    input_mode="API",
    api_url="https://mosaicfellowship.in/api/data/cx/reviews"
)

# Custom API with authentication
df = load_data(
    input_mode="API",
    api_url="https://api.example.com/reviews",
    api_key="your_bearer_token"
)
```

### 2. File Upload Flow

```
User Selects "Upload File" Mode
         ↓
Choose CSV or JSON file from disk
         ↓
Click "Load Data"
         ↓
parse_uploaded_file(file)
  - Detect file type from extension
  - Parse CSV with pd.read_csv()
  - Parse JSON handling various structures:
    * Direct array
    * Nested in 'data' key
    * Nested in 'records' key
    * Flat object (normalized)
         ↓
normalize_schema(df)
  - Map column variations to standard names
  - Convert types (numeric, boolean)
  - Handle missing columns
         ↓
load_data() returns normalized DataFrame
         ↓
Pipeline processes data
```

**Example File Formats:**

CSV:
```csv
rating,product,customer_ltv,review_text
5,Product A,1000,"Great product!"
2,Product B,500,"Not satisfied"
```

JSON (Direct Array):
```json
[
  {"rating": 5, "product": "Product A", "customer_ltv": 1000},
  {"rating": 2, "product": "Product B", "customer_ltv": 500}
]
```

JSON (Nested):
```json
{
  "data": [
    {"rating": 5, "product": "Product A", "customer_ltv": 1000},
    {"rating": 2, "product": "Product B", "customer_ltv": 500}
  ]
}
```

### 3. Schema Normalization

Maps common column name variations to standard schema:

```python
COLUMN_MAP = {
    'rating': ['rating', 'stars', 'review_rating', 'score', ...],
    'review_text': ['review_text', 'review', 'text', 'comment', ...],
    'sentiment': ['sentiment', 'sentiment_label', 'tone', ...],
    'sentiment_score': ['sentiment_score', 'sentiment_val', 'polarity', ...],
    'customer_ltv': ['customer_ltv', 'ltv', 'customer_value', ...],
    'product': ['product', 'product_name', 'product_id', 'item', ...],
    'order_value': ['order_value', 'order_val', 'purchase_amount', ...],
    'days_since_purchase': ['days_since_purchase', 'age_in_days', ...],
    'helpful_votes': ['helpful_votes', 'helpful_count', 'upvotes', ...],
    'is_repeat_customer': ['is_repeat_customer', 'repeat_customer', ...],
    'verified_purchase': ['verified_purchase', 'verified', 'authentic', ...]
}
```

**Example Transformation:**
```
Input CSV:
  rating, stars_given, customer_value, product_name
  5,      5,           1000,          Product A
  2,      2,           500,           Product B

Output (After Normalization):
  rating  review_text  sentiment  customer_ltv  product
  5       [default]    [default]  1000          Product A
  2       [default]    [default]  500          Product B
```

---

## 🎨 Streamlit UI Component

### Sidebar Layout

```
⚙️ CONTROL PANEL
────────────────────────────────────

📥 DATA SOURCE
  ○ API
  ● Upload File

───────────────────────────────────

📅 FILE UPLOAD
  📎 Upload CSV or JSON file
  [Choose File] ▼

───────────────────────────────────

[🔄 Load Data] [🗑️ Clear Cache]

───────────────────────────────────

📈 SYSTEM STATUS
  ⏳ Waiting for data load
```

### API Mode UI

```
📥 DATA SOURCE
  ○ API
  ● Upload File

───────────────────────────────────

**API CONFIGURATION**

☑ Use Default API
📌 Using: `https://mosaicfellowship.in/...`

API Key (Optional)
[••••••••••••••••••]

[🔄 Load Data] [🗑️ Clear Cache]
```

### Upload Mode UI

```
📥 DATA SOURCE
  ● API
  ○ Upload File

───────────────────────────────────

**FILE UPLOAD**

📎 Upload CSV or JSON file
  [Choose File] ▼

[🔄 Load Data] [🗑️ Clear Cache]
```

---

## 🔒 Error Handling

### API Mode Errors

| Error | Cause | Handling |
|-------|-------|----------|
| **Timeout** | API takes > 10 seconds | `st.error()` + `raise APIError` |
| **Connection Error** | Network/DNS issue | Same as timeout |
| **HTTP Error** | 4xx or 5xx response | `st.error()` with status code |
| **Invalid JSON** | Malformed response | `st.error()` with details |
| **Empty Response** | API returned no data | `st.error()` + `raise DataError` |

### Upload Mode Errors

| Error | Cause | Handling |
|-------|-------|----------|
| **Unsupported Format** | Not .csv or .json | `raise ValueError` |
| **Invalid JSON** | Malformed JSON file | `raise ValueError` |
| **Empty File** | No data in file | `st.error()` + `raise DataError` |
| **Parse Error** | Corrupted data | `raise DataError` |

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     RIE Dashboard (Streamlit)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────┐  ┌──────────────────────────┐    │
│  │   Input Mode Selector    │  │   Input Mode Selector    │    │
│  │  (API / Upload File)     │  │  (API / Upload File)     │    │
│  └────────────┬─────────────┘  └───────────┬──────────────┘    │
│               │                             │                   │
│      ┌────────▼─────────┐         ┌────────▼─────────┐         │
│      │  API Mode UI     │         │ Upload Mode UI   │         │
│      │ - Custom URL     │         │ - File selector  │         │
│      │ - API Key input  │         │ - CSV/JSON only  │         │
│      └────────┬─────────┘         └────────┬─────────┘         │
│              │                              │                   │
│              ▼                              ▼                   │
│      ┌─────────────────────────────────────────┐               │
│      │  Click "Load Data" Button               │               │
│      └────────────┬────────────────────────────┘               │
│                   │                                             │
│                   ▼                                             │
│      ┌──────────────────────────┐                              │
│      │  Validation              │                              │
│      │ - Check inputs           │                              │
│      │ - Verify requirements    │                              │
│      └─────────┬────────────────┘                              │
│              │                                                  │
│              ▼                                                  │
│      ┌─────────────────────────────────────────────┐          │
│      │  load_data()                                │          │
│      │  (Unified Loader)                           │          │
│      └──────┬──────────────┬─────────────────────┘          │
│             │              │                                   │
│      ┌──────▼──────┐ ┌─────▼──────────────┐                 │
│      │API Input    │ │File Upload Input    │                 │
│      │ fetch_      │ │ parse_uploaded_file │                 │
│      │ dynamic_api │ │                     │                 │
│      └──────┬──────┘ └─────┬──────────────┘                 │
│             │              │                                   │
│             └──────┬───────┘                                   │
│                    │                                           │
│                    ▼                                           │
│           ┌─────────────────┐                                │
│           │ normalize_schema │                                │
│           │ - Map columns    │                                │
│           │ - Convert types  │                                │
│           △ - Fill defaults  │                                │
│           └────────┬────────┘                                │
│                    │                                           │
│                    ▼                                           │
│   ┌───────────────────────────┐                              │
│   │ Normalized DataFrame      │                              │
│   │ (Standard Schema)         │                              │
│   └───────────┬───────────────┘                              │
│               │                                               │
│               ▼                                               │
│   ┌───────────────────────────────────────┐                 │
│   │ Existing Pipeline (Unchanged)         │                 │
│   │ ├─ preprocess_data()                 │                 │
│   │ ├─ engineer_features()               │                 │
│   │ ├─ apply_scoring_pipeline()          │                 │
│   │ ├─ aggregate_to_products()           │                 │
│   │ └─ classify_quadrants()              │                 │
│   └───────────┬───────────────────────────┘                 │
│               │                                               │
│               ▼                                               │
│   ┌───────────────────────────┐                              │
│   │ Dashboard Visualization   │                              │
│   │ ├─ KPI Cards              │                              │
│   │ ├─ Quadrant Chart         │                              │
│   │ ├─ Product Table          │                              │
│   │ └─ Analytics              │                              │
│   └───────────────────────────┘                              │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Usage Examples

### Example 1: Use Default Mosaic API

```python
# UI: Select "API" → ☑ "Use Default API" → Click "Load Data"
# Behind the scenes:
df = load_data(
    input_mode="API",
    api_url="https://mosaicfellowship.in/api/data/cx/reviews"
)
# Result: 500+ reviews from Mosaic API
```

### Example 2: Use Custom API with Authentication

```python
# UI: Select "API" → ☐ "Use Default API" 
#     → Enter "https://api.example.com/reviews/export"
#     → Enter API Key "sk-1234567890"
#     → Click "Load Data"

df = load_data(
    input_mode="API",
    api_url="https://api.example.com/reviews/export",
    api_key="sk-1234567890"
)
# Result: Reviews from custom API with Bearer auth
```

### Example 3: Upload CSV File

```python
# UI: Select "Upload File" → Browse to reviews.csv → Click "Load Data"

# File content (reviews.csv):
# rating,product,customer_ltv,review_text
# 5,"Laptop",5000,"Excellent performance"
# 2,"Mouse",50,"Broke after 2 weeks"

df = load_data(
    input_mode="Upload File",
    uploaded_file=<streamlit UploadedFile object>
)
# Result: 2 reviews parsed from CSV
```

### Example 4: Upload JSON File

```python
# UI: Select "Upload File" → Browse to reviews.json → Click "Load Data"

# File content (reviews.json):
# [
#   {"rating": 5, "product": "Keyboard", "customer_ltv": 2000},
#   {"rating": 3, "product": "Monitor", "customer_ltv": 15000}
# ]

df = load_data(
    input_mode="Upload File",
    uploaded_file=<streamlit UploadedFile object>
)
# Result: 2 reviews parsed from JSON
```

---

## 🧪 Testing & Validation

### All Tests Passing ✅

```
Dashboard Integration Tests: 24/24 PASS
Scoring Engine Tests: 26/26 PASS
─────────────────────────────────
Total: 50/50 PASS ✅
```

### No Regressions
- All existing functionality preserved
- Pipeline logic unchanged
- Column names standardized
- Data types validated

### Backward Compatibility
- Default Mosaic API still works
- Existing API flow preserved
- No breaking changes

---

## 📝 State Management

### Session State Keys

```python
# Data states
st.session_state.raw_data          # Original loaded data
st.session_state.processed_data    # After pipeline
st.session_state.aggregated_data   # Product-level aggregation
st.session_state.data_fetched      # Boolean: data loaded?
st.session_state.last_refresh      # Timestamp of last load

# Input mode states
st.session_state.input_mode        # "API" or "Upload File"
st.session_state.api_url           # Current API URL
st.session_state.api_key           # Current API key
st.session_state.use_default_api   # Using default? Boolean
```

---

## 🔍 Debug Output

When data loads, console shows:

```
[DEBUG] Data Loading:
  - Source: API
  - Total rows: 500
  - Columns: 12
  - Available products: 3

[DEBUG] Ingestion Summary:
  - Total reviews: 500
  - Unique products: 3
  - Products: ['Product A', 'Product B', 'Product C']
  - Customer LTV - Min: 0.0, Max: 50000.0, Sum: 5000000.0

[DEBUG] Aggregation Input:
  - Total reviews: 500
  - Unique products: 3
  - Customer LTV range: 0.0 to 50000.0
  - Negative reviews (rating <= 2.5): 75

[DEBUG] Revenue at Risk Calculation:
  - Negative reviews selected (rating <= 2.5): 75
  - Total revenue at risk: ₹1,234,567.89
```

---

## ✨ Key Benefits

1. **Flexibility** - Support any data source via API or file upload
2. **Standardization** - Schema normalization ensures consistency
3. **Robustness** - Comprehensive error handling for edge cases
4. **Backward Compatibility** - Existing Mosaic API flow still works
5. **Ease of Use** - Simple Streamlit UI for data input selection
6. **Transparency** - Debug output shows data flow at each step
7. **No Impact** - Existing pipeline logic completely unchanged
8. **Type Safety** - Proper numeric/boolean conversions validated

---

## 🚀 Next Steps

1. **Test with Live API** - Try custom API endpoints
2. **Upload Sample Files** - Test with CSV/JSON files
3. **Monitor Performance** - Check debug output for data quality
4. **Validate Results** - Verify products and revenue calculations
5. **Production Deploy** - Roll out with confidence (backward compatible)

---

## 📞 Troubleshooting

### API Connection Failed
- ✅ Check API URL is correct and accessible
- ✅ Verify API key if required
- ✅ Check network connection
- ✅ Ensure API returns valid JSON
- ✅ Look at console for detailed error message

### File Upload Failed
- ✅ File must be .csv or .json (check extension)
- ✅ JSON must be valid (use JSON validator)
- ✅ CSV must have properly formatted headers
- ✅ File should not be empty
- ✅ Check file size (very large files may timeout)

### Missing Columns After Load
- ✅ Check schema normalization mapped columns correctly
- ✅ Verify uploaded file has required fields
- ✅ Look at debug output to see parsed columns
- ✅ Ensure numeric columns are actually numeric

### Revenue at Risk Shows 0
- ✅ Verify data has negative reviews (rating ≤ 2.5)
- ✅ Check customer_ltv values are non-zero
- ✅ Look at debug output to confirm data loaded
- ✅ Review data quality check in dashboard

---

## 📋 Checklist for Production

- [x] API input working with custom URLs
- [x] File upload working with CSV/JSON
- [x] Schema normalization complete
- [x] Error handling comprehensive
- [x] State management correct
- [x] All tests passing (50/50)
- [x] No regressions
- [x] Backward compatible
- [x] Documentation complete
- [x] Debug output helpful

**Status: ✅ READY FOR PRODUCTION**
