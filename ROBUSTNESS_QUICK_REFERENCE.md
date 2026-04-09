# Data Robustness Layer - Quick Reference

## 🚀 Quick Start (30 seconds)

```python
from services.data_robustness import get_clean_data

# Get clean, validated data ready for scoring
df = get_clean_data(max_pages=5)
print(df.shape)  # (500, 30)
```

---

## 📋 What It Does

✅ Fetches all data from paginated API
✅ Enforces schema (9 required columns)
✅ Creates missing columns with neutral defaults
✅ Coerces data types safely
✅ Fills all NaN values
✅ Normalizes numeric features
✅ Clips out-of-range values
✅ Validates output quality
✅ **NEVER CRASHES** on bad data

---

## 🔧 Core Functions

### Main Orchestrator
```python
from services.data_robustness import robust_data_pipeline

# With report
df, report = robust_data_pipeline(max_pages=5, include_report=True)

# Without report (faster)
df, _ = robust_data_pipeline(max_pages=5)

# Quick access
df = get_clean_data(max_pages=5)
```

### Schema Validation
```python
from utils.validation import validate_schema

df, report = validate_schema(raw_df, strict=False)
# Returns: validated DataFrame + {filled_columns, type_conversions, errors}
```

### Safe Normalization
```python
from utils.validation import safe_minmax

normalized = safe_minmax(df["column"])
# Handles constant columns (returns 0.5), clipping, NaN

normalized_clipped = safe_minmax(df["rating"], clip_range=(1, 5))
```

### Sanity Checks
```python
from utils.validation import sanity_checks

is_valid, issues = sanity_checks(df)
# Returns: valid bool + [issues list with ❌ or ⚠️ prefix]
```

---

## 📊 Schema Definition

| Column | Type | Default | Range |
|--------|------|---------|-------|
| rating | float | 3.0 | [1, 5] |
| sentiment_score | float | 0.5 | [0, 1] |
| customer_ltv | float | 0.0 | any |
| order_value | float | 0.0 | any |
| repeat | int | 0 | 0/1 |
| verified | int | 0 | 0/1 |
| helpful_votes | int | 0 | any |
| days_since_purchase | int | 30 | any |
| detected_issues | str | "unknown" | any |

---

## ⚙️ Configuration

### Change Defaults
```python
# Edit utils/validation.py
DEFAULTS = {
    "rating": 3.0,
    "sentiment_score": 0.5,
    "customer_ltv": 0.0,
    # ... etc
}
```

### Change Value Ranges
```python
VALUE_RANGES = {
    "rating": (1.0, 5.0),
    "sentiment_score": (0.0, 1.0),
}
```

---

## 🧪 Testing

```bash
# Run all 23 tests
pytest tests/test_data_robustness.py -v

# Expected output:
# ======= 23 passed in 1.02s =======
```

---

## 📚 Output Guarantees

After pipeline completes, you get:

✅ Non-empty DataFrame
✅ All required columns present
✅ Correct data types
✅ No NaN values
✅ Valid ranges (rating [1-5], sentiment [0-1])
✅ Ready for scoring engine

---

## 🔍 Robustness Features

### Handles These Errors Without Crashing:

| Error | Handling |
|-------|----------|
| Missing columns | Creates with defaults |
| All-NaN columns | Fills with defaults |
| Invalid types | Coerces safely |
| Out-of-range | Clips to [min, max] |
| Empty API response | Returns empty with valid schema |
| Tuple from API | Extracts data automatically |
| Constant columns | Normalization returns 0.5 |
| Extreme values | Handled by normalization |
| Unicode strings | Preserved as-is |
| Single-row data | Processed normally |
| Completely null data | Filled with all defaults |

---

## 📈 Performance

- **Speed**: 500 reviews in < 1 second
- **Memory**: Efficient vectorized operations
- **Scalability**: Tested up to 5000 reviews
- **Determinism**: Same input → same output

---

## 🎯 Integration with Dashboard

### Current Code (Without Robustness)
```python
raw_df = fetch_reviews(max_pages=5)
df = preprocess_data(raw_df)  # May crash on bad data
```

### Recommended Code (With Robustness)
```python
from services.data_robustness import robust_data_pipeline

df, report = robust_data_pipeline(max_pages=5, include_report=True)
if report["success"]:
    # Use df safely for scoring
    scored_df = apply_scoring_pipeline(df)
```

---

## 📋 Pipeline Stages

```
Stage 1: API Fetch
    ↓ Pagination, error handling, tuple extraction
Stage 2: Robust Preprocessing
    ↓ Schema validation, type coercion, normalization
Stage 3: Integrity Checks
    ↓ Column completeness, NaN elimination, type validation
Stage 4: Final Validation
    ↓ Sanity checks, value clipping, critical violations
    ↓
✅ Clean Data Ready for Scoring
```

---

## 🚨 Common Issues

### Issue: "NaN still present"
**Solution**: All stages fill NaN. Check critical column:
```python
from utils.validation import check_nan_propagation
report = check_nan_propagation(df)
print(report["critical_violations"])
```

### Issue: "Schema validation failed"
**Solution**: View what was filled:
```python
df, report = validate_schema(raw_df, strict=False)
print(report["filled_columns"])
```

### Issue: "Normalization giving 0.5 everywhere"
**Solution**: Column is constant (all same value). This is correct:
```python
print(df["column"].min(), df["column"].max())  # Same value?
# safe_minmax returns 0.5 for constant columns
```

---

## 📂 Files

- `utils/validation.py` - Schema, normalization, checks
- `services/robust_preprocessing.py` - 8-step preprocessing
- `services/data_robustness.py` - Main orchestrator
- `tests/test_data_robustness.py` - 23 comprehensive tests

---

## 🔗 Related Documentation

- [DATA_ROBUSTNESS_LAYER.md](DATA_ROBUSTNESS_LAYER.md) - Full architecture & API
- [ROBUSTNESS_INTEGRATION.md](ROBUSTNESS_INTEGRATION.md) - Integration guide
- [tests/test_data_robustness.py](tests/test_data_robustness.py) - Test examples

---

## ✅ Success Checklist

- [ ] Ran tests: `pytest tests/test_data_robustness.py -v`
- [ ] Tested with real data: `get_clean_data(max_pages=2)`
- [ ] Output has no NaN values
- [ ] All required columns present
- [ ] Data types are correct
- [ ] Scoring pipeline accepts output
- [ ] Logs show no critical errors

---

## 💡 Pro Tips

1. **Always use robust pipeline** for production API data
2. **Check robustness report** for data quality warnings
3. **Monitor logs** for schema changes in API
4. **Adjust defaults** based on your data characteristics
5. **Run tests regularly** to catch regressions
6. **Use include_report=True** in development, False in production (faster)

---

## 📞 Quick Commands

```bash
# Test everything works
pytest tests/test_data_robustness.py -v

# Try with real data
python -c "from services.data_robustness import get_clean_data; df=get_clean_data(2); print(df.shape)"

# Check validation only
python -c "from utils.validation import validate_schema; df, r = validate_schema(raw_df, False); print(r['filled_columns'])"

# View logs
tail -f review_system.log | grep -i robust
```

---

**Ready to use? Start with:**
```python
from services.data_robustness import get_clean_data
df = get_clean_data(5)  # 500 reviews, validated, ready to score ✅
```
