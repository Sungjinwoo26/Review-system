"""Quick verification of Data Robustness Layer."""

from services.data_robustness import robust_data_pipeline, get_clean_data, validate_pipeline_output
from utils.validation import sanity_checks

print("=" * 80)
print("TESTING DATA ROBUSTNESS LAYER")
print("=" * 80)

# Test 1: Quick access
print("\nTest 1: Quick access function")
try:
    df = get_clean_data(max_pages=2)
    print(f"✅ get_clean_data() returned: {df.shape}")
    print(f"   Columns: {list(df.columns[:5])}...")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: With report
print("\nTest 2: Robust pipeline with report")
try:
    df, report = robust_data_pipeline(max_pages=2, include_report=True)
    print(f"✅ Pipeline success: {report['success']}")
    print(f"   Shape: {df.shape}")
    print(f"   Memory: {report['memory_usage_mb']:.2f} MB")
    print(f"   NaN count: {report['nan_check']['total_nan']}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Data quality
print("\nTest 3: Data quality checks")
try:
    is_valid, issues = sanity_checks(df)
    valid2, validation = validate_pipeline_output(df)
    print(f"✅ Sanity checks: {is_valid}")
    print(f"✅ Pipeline output valid: {valid2}")
    print(f"   All checks: {validation['checks']}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 80)
print("ROBUSTNESS LAYER VERIFICATION COMPLETE ✅")
print("=" * 80)
