# Data Robustness Layer - Integration Guide

## Quick Integration (3 Steps)

### Step 1: Update `app.py` → Use Robust Pipeline

**Before:**
```python
from services.ingestion import fetch_reviews
from services.preprocessing import preprocess_data

def run_pipeline(df):
    review_df = preprocess_data(df)
    product_df = aggregate_to_products(review_df)
    return review_df, product_df
```

**After:**
```python
from services.data_robustness import robust_data_pipeline

def run_pipeline_robust(max_pages=None):
    # Get clean, validated data guaranteed ready for scoring
    review_df, robustness_report = robust_data_pipeline(
        max_pages=max_pages,
        include_report=True
    )
    
    # Log any robustness warnings
    if robustness_report["success"]:
        logger.info(f"✅ Data validated: {review_df.shape}")
    else:
        logger.warning(f"⚠️ Data issues: {robustness_report['warnings']}")
    
    # Continue with existing pipeline
    product_df = aggregate_to_products(review_df)
    product_df = classify_quadrants(product_df)
    
    return review_df, product_df
```

### Step 2: Update Dashboard Data Fetching

**In `app.py` main() function:**

```python
def main():
    st.title("🎯 Review Intelligence Engine")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 Data Ingestion",
        "📊 Review Analytics",
        "🎯 Product Priorities",
        "ℹ️ About"
    ])
    
    with tab1:
        st.header("Data Ingestion & Processing")
        
        if st.button("🚀 Run Full Pipeline (Robust)"):
            with st.spinner("Processing with data robustness layer..."):
                try:
                    # Use robust pipeline
                    from services.data_robustness import robust_data_pipeline
                    
                    raw_df, robustness_data = robust_data_pipeline(
                        max_pages=5,
                        include_report=True
                    )
                    
                    # Store in session
                    st.session_state.pipeline_df = raw_df
                    st.session_state.robustness_report = robustness_data
                    st.session_state.data_fetched = True
                    
                    # Show robustness metrics
                    if robustness_data["success"]:
                        st.success("✅ Data validation passed!")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Rows", robustness_data["dataset_shape"][0])
                        with col2:
                            st.metric("Columns", robustness_data["dataset_shape"][1])
                        with col3:
                            st.metric("Memory", f"{robustness_data['memory_usage_mb']:.2f} MB")
                        
                        # Show warnings if any
                        if robustness_data.get("warnings"):
                            with st.expander("⚠️ Data Quality Warnings"):
                                for warning in robustness_data["warnings"]:
                                    st.warning(warning)
                    else:
                        st.error("❌ Critical data validation errors!")
                        for error in robustness_data["errors"]:
                            st.error(error)
                        
                except Exception as e:
                    st.error(f"Pipeline error: {str(e)}")
```

### Step 3: Add Robustness Monitoring Tab

**Optional: Add monitoring tab to dashboard:**

```python
with st.expander("🔍 Data Quality Report"):
    if st.session_state.get("robustness_report"):
        report = st.session_state.robustness_report
        
        st.subheader("Pipeline Stages")
        for stage, details in report.get("pipeline_stages", {}).items():
            st.write(f"**{stage}**: {details}")
        
        st.subheader("Data Quality Checks")
        checks = report.get("nan_check", {})
        st.json({
            "total_nan": checks.get("total_nan", 0),
            "critical_violations": checks.get("critical_violations", [])
        })
```

---

## Module Reference

### `services/data_robustness.py`

**Main Functions:**

```python
# Option 1: With report
df, report = robust_data_pipeline(max_pages=5, include_report=True)

# Option 2: Without report (faster)
df, _ = robust_data_pipeline(max_pages=5)

# Option 3: Quick access
df = get_clean_data(max_pages=5)

# Option 4: Validate output
is_valid, report = validate_pipeline_output(df)
```

### `utils/validation.py`

**Utility Functions:**

```python
# Schema validation
df, report = validate_schema(df, strict=False)

# Safe normalization
normalized = safe_minmax(df["column"], clip_range=(0, 1))

# NaN detection
report = check_nan_propagation(df, critical_cols=["rating", "sentiment"])

# Sanity checks
is_valid, issues = sanity_checks(df)

# Generate report
report = generate_robustness_report(df, schema_report, sanity_issues)
```

### `services/robust_preprocessing.py`

**Preprocessing Functions:**

```python
# Full robust pipeline
df, report = robust_preprocess_data(df)

# Backward compatible
df = preprocess_data(df)

# Just missing values
df, report = robust_fill_missing_values(df)
```

---

## Configuration

### Adjust Defaults

Edit `utils/validation.py`:

```python
DEFAULTS = {
    "rating": 3.0,                  # Change neutral rating default
    "sentiment_score": 0.5,         # Change neutral sentiment
    "customer_ltv": 0.0,            # Change unknown LTV default
    "order_value": 0.0,             # Change unknown order value
    "days_since_purchase": 30,      # Change average days
    # ... etc
}
```

### Adjust Value Ranges

```python
VALUE_RANGES = {
    "rating": (1.0, 5.0),           # Allow 1-5 ratings
    "sentiment_score": (0.0, 1.0),  # Allow 0-1 sentiment
    # Add more as needed
}
```

---

## Monitoring & Logging

### View Logs

Robustness issues are logged to `review_system.log`:

```
2026-04-09 15:19:38 - review_system - INFO - EVENT: PREPROCESSING_COMPLETE
2026-04-09 15:19:38 - review_system - WARNING - Filled 5 missing values in 'customer_ltv'
2026-04-09 15:19:38 - review_system - INFO - Step 1: Validating schema...
```

### Common Warnings

| Warning | Cause | Action |
|---------|-------|--------|
| "Missing column X filled with default Y" | API didn't return column | Normal, using default |
| "Filled N missing values in column X" | NaN values present | Normal, filled with default |
| "Clipped N out-of-range values in X" | Values outside [min, max] | Normal, clipped to range |
| "Constant column detected: X = Y" | All values identical | Normal, normalization handles it |

### Critical Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Dataset is empty" | No data from API | Check API/network |
| "Missing required columns: X" | API schema changed | Update EXPECTED_SCHEMA |
| "Critical NaN violation" | Column entirely null | Check data source |

---

## Testing

### Run All Tests

```bash
# All robustness tests
pytest tests/test_data_robustness.py -v

# Specific test class
pytest tests/test_data_robustness.py::TestSchemaValidation -v

# Specific test
pytest tests/test_data_robustness.py::TestRobustnessWithBadData -v
```

### Test with Your Data

```python
from services.data_robustness import robust_data_pipeline, validate_pipeline_output

# Test with real API data
df, report = robust_data_pipeline(max_pages=2, include_report=True)

# Validate output
is_valid, validation = validate_pipeline_output(df)
print(f"Valid: {is_valid}")
print(f"Checks: {validation['checks']}")
print(f"Warnings: {validation['warnings']}")
```

---

## Deployment

### Before Production

1. ✅ Run all tests: `pytest tests/test_data_robustness.py -v`
2. ✅ Test with real API data: `get_clean_data(max_pages=10)`
3. ✅ Check logs for warnings
4. ✅ Validate output fits scoring pipeline
5. ✅ Monitor memory usage (large datasets)

### Production Configuration

Set in `app.py`:

```python
# Fetch up to 50 pages (5000 reviews)
max_pages = 50

# Always include robustness report for monitoring
include_report = True

# Monitor memory
if report["memory_usage_mb"] > 500:
    st.warning(f"Large dataset: {report['memory_usage_mb']:.0f} MB")
```

---

## Troubleshooting

### Issue: "Schema validation failed"

**Solution:**
```python
from utils.validation import validate_schema

df, report = validate_schema(raw_df, strict=False)
print(report["filled_columns"])   # What was filled?
print(report["type_conversions"]) # What types changed?
print(report["errors"])           # Any errors?
```

### Issue: "NaN still present after pipeline"

**Solution:**
```python
from utils.validation import check_nan_propagation

report = check_nan_propagation(df)
print(report["columns_with_nan"])
print(report["critical_violations"])

# Force fill
for col in df.columns:
    if df[col].isna().any():
        df[col] = df[col].fillna(DEFAULTS.get(col, 0))
```

### Issue: "Normalization giving unexpected results"

**Solution:**
```python
from utils.validation import safe_minmax

# Check for constant columns
print(df["column"].min(), df["column"].max())

# If min == max, safe_minmax returns 0.5 for all
normalized = safe_minmax(df["column"])
print(normalized.unique())  # Should be [0.5] for constant
```

---

## Next Steps

1. Review [DATA_ROBUSTNESS_LAYER.md](DATA_ROBUSTNESS_LAYER.md) for detailed architecture
2. Run tests to verify your environment: `pytest tests/test_data_robustness.py -v`
3. Update `app.py` to use robust pipeline (see Step 1-3 above)
4. Deploy and monitor logs
5. Adjust defaults based on real data characteristics

---

## Support

For issues or questions:
1. Check logs: `tail -f review_system.log`
2. Run diagnostics: `python -c "from services.data_robustness import get_clean_data; df = get_clean_data(max_pages=2); print(df.info())"`
3. Review test cases for similar scenarios
4. Check DATA_ROBUSTNESS_LAYER.md for detailed API reference
