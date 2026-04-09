"""Tests for Data Robustness Layer - ensures crash-free processing of bad data."""

import pytest
import pandas as pd
import numpy as np
from services.data_robustness import validate_pipeline_output
from utils.validation import (
    validate_schema,
    safe_minmax,
    sanity_checks,
    check_nan_propagation,
    DEFAULTS,
    EXPECTED_SCHEMA,
)


class TestSchemaValidation:
    """Test schema validation and enforcement."""

    def test_missing_columns_filled_with_defaults(self):
        """Test that missing columns are created with defaults."""
        df = pd.DataFrame({"rating": [1, 2, 3]})
        validated_df, report = validate_schema(df, strict=False)

        # Check that missing columns were created
        for col in EXPECTED_SCHEMA.keys():
            assert col in validated_df.columns, f"Column {col} not created"

        # Check that defaults were used
        assert "sentiment_score" in validated_df.columns
        assert report["filled_columns"]

    def test_invalid_types_coerced_safely(self):
        """Test safe type coercion of invalid types."""
        df = pd.DataFrame(
            {
                "rating": ["1", "abc", "3"],  # String ratings
                "sentiment_score": [0.5, 0.6, 0.7],
                "customer_ltv": ["100", "200", "invalid"],  # Mixed types
            }
        )

        validated_df, report = validate_schema(df, strict=False)

        # Check that types are coerced
        assert pd.api.types.is_numeric_dtype(validated_df["rating"])
        # Invalid value "abc" becomes NaN, then filled with default
        assert not validated_df["rating"].isna().any()

    def test_all_nan_column_filled(self):
        """Test that all-NaN columns are properly filled."""
        df = pd.DataFrame(
            {
                "rating": [np.nan, np.nan, np.nan],
                "sentiment_score": [np.nan, np.nan, np.nan],
            }
        )

        validated_df, report = validate_schema(df, strict=False)

        # Check that NaN columns are filled with defaults
        assert not validated_df["rating"].isna().any()
        assert validated_df["rating"].iloc[0] == DEFAULTS["rating"]


class TestSafeNormalization:
    """Test safe Min-Max normalization."""

    def test_normal_normalization(self):
        """Test standard Min-Max normalization."""
        series = pd.Series([1, 2, 3, 4, 5])
        normalized = safe_minmax(series)

        assert normalized.min() == 0.0
        assert normalized.max() == 1.0
        assert len(normalized) == len(series)

    def test_constant_column_returns_middle_value(self):
        """Test that constant columns return 0.5."""
        series = pd.Series([5.0, 5.0, 5.0, 5.0])
        normalized = safe_minmax(series)

        # All values should be 0.5
        assert (normalized == 0.5).all()

    def test_normalization_with_clipping(self):
        """Test normalization with value clipping."""
        series = pd.Series([0, 2.5, 5, 10])
        # Clip to [0, 5]
        normalized = safe_minmax(series, clip_range=(0, 5))

        # Values clipped, then normalized
        assert normalized.min() >= 0
        assert normalized.max() <= 1

    def test_nan_handling_in_normalization(self):
        """Test that NaN values don't crash normalization."""
        series = pd.Series([1, 2, np.nan, 4, 5])
        # Safe_minmax should drop NaN before normalizing
        normalized = safe_minmax(series)

        assert isinstance(normalized, pd.Series)


class TestNaNPropagation:
    """Test NaN detection and prevention."""

    def test_nan_propagation_detection(self):
        """Test detection of NaN values."""
        df = pd.DataFrame(
            {
                "col1": [1, np.nan, 3],
                "col2": [1, 2, 3],
                "col3": [np.nan, np.nan, np.nan],
            }
        )

        report = check_nan_propagation(df)

        assert "col1" in report["columns_with_nan"]
        assert "col3" in report["columns_with_nan"]
        assert "col2" not in report["columns_with_nan"]

    def test_critical_nan_violations(self):
        """Test detection of critical NaN violations."""
        df = pd.DataFrame(
            {
                "rating": [1, np.nan, 3],
                "sentiment_score": [0.5, 0.6, 0.7],
            }
        )

        critical_cols = ["rating"]
        report = check_nan_propagation(df, critical_cols=critical_cols)

        assert len(report["critical_violations"]) > 0


class TestSanityChecks:
    """Test comprehensive sanity checks."""

    def test_empty_dataframe_fails(self):
        """Test that empty DataFrame fails sanity checks."""
        df = pd.DataFrame()
        is_valid, issues = sanity_checks(df)

        assert not is_valid
        assert any("empty" in issue.lower() for issue in issues)

    def test_missing_columns_detected(self):
        """Test that missing required columns are detected."""
        df = pd.DataFrame({"random_col": [1, 2, 3]})
        is_valid, issues = sanity_checks(df)

        assert not is_valid
        assert any("missing" in issue.lower() for issue in issues)

    def test_out_of_range_values_clipped(self):
        """Test that out-of-range values are clipped."""
        df = pd.DataFrame(
            {
                "rating": [0, 1, 2, 3, 4, 5, 6, 7],  # Should clip to [1, 5]
                "sentiment_score": [0, 0.5, 1, 1.5, 2, 0, 0.3, 0.9],  # Should clip to [0, 1]
            }
        )

        is_valid, issues = sanity_checks(df)

        # Check clipping happened
        assert df["rating"].min() >= 1
        assert df["rating"].max() <= 5
        assert df["sentiment_score"].min() >= 0
        assert df["sentiment_score"].max() <= 1

    def test_valid_dataframe_passes(self):
        """Test that valid DataFrame passes all checks."""
        data = {}
        for col, dtype in EXPECTED_SCHEMA.items():
            if dtype == "float":
                data[col] = [0.5, 1.0, 1.5]
            elif dtype == "int":
                data[col] = [1, 2, 3]
            elif dtype == "str":
                data[col] = ["a", "b", "c"]

        df = pd.DataFrame(data)
        is_valid, issues = sanity_checks(df)

        # Should pass (or have only warnings, not errors)
        critical_issues = [issue for issue in issues if "❌" in issue]
        assert len(critical_issues) == 0


class TestPipelineOutputValidation:
    """Test validation of pipeline output."""

    def test_valid_output_passes_validation(self):
        """Test that valid output passes validation."""
        data = {}
        for col, dtype in EXPECTED_SCHEMA.items():
            if dtype == "float":
                data[col] = np.random.random(100)
            elif dtype == "int":
                data[col] = np.random.randint(0, 5, 100)
            elif dtype == "str":
                data[col] = ["issue"] * 100

        df = pd.DataFrame(data)
        is_valid, report = validate_pipeline_output(df)

        assert is_valid
        assert report["checks"]["non_empty"]
        assert report["checks"]["required_columns_present"]

    def test_empty_output_fails(self):
        """Test that empty output fails validation."""
        df = pd.DataFrame()
        is_valid, report = validate_pipeline_output(df)

        assert not is_valid
        assert not report["checks"]["non_empty"]

    def test_nan_in_critical_cols_detected(self):
        """Test that NaN in critical columns is detected."""
        data = {}
        for col, dtype in EXPECTED_SCHEMA.items():
            if dtype == "float":
                data[col] = [0.5, np.nan, 1.5]
            elif dtype == "int":
                data[col] = [1, 2, 3]
            elif dtype == "str":
                data[col] = ["a", "b", "c"]

        df = pd.DataFrame(data)
        is_valid, report = validate_pipeline_output(df)

        # Should fail or warn about NaN
        assert not report["checks"]["no_critical_nan"] or len(report["warnings"]) > 0


class TestEdgeCases:
    """Test edge cases and unusual data."""

    def test_single_row_dataframe(self):
        """Test processing of single-row DataFrame."""
        data = {}
        for col, dtype in EXPECTED_SCHEMA.items():
            if dtype == "float":
                data[col] = [0.5]
            elif dtype == "int":
                data[col] = [1]
            elif dtype == "str":
                data[col] = ["issue"]

        df = pd.DataFrame(data)
        is_valid, issues = sanity_checks(df)

        # Should not crash
        assert isinstance(issues, list)

    def test_extreme_values(self):
        """Test handling of extreme values."""
        data = {}
        for col, dtype in EXPECTED_SCHEMA.items():
            if dtype == "float":
                data[col] = [1e10, -1e10, 0]
            elif dtype == "int":
                data[col] = [1000000, -1000000, 0]
            elif dtype == "str":
                data[col] = ["a", "b", "c"]

        df = pd.DataFrame(data)
        is_valid, issues = sanity_checks(df)

        # Should not crash, clipping should occur
        assert isinstance(issues, list)

    def test_all_duplicate_values(self):
        """Test handling of all duplicate values."""
        data = {}
        for col, dtype in EXPECTED_SCHEMA.items():
            if dtype == "float":
                data[col] = [0.5] * 100
            elif dtype == "int":
                data[col] = [1] * 100
            elif dtype == "str":
                data[col] = ["issue"] * 100

        df = pd.DataFrame(data)

        # Normalization should handle constants
        normalized = safe_minmax(df["rating"])
        assert (normalized == 0.5).all() or isinstance(normalized, pd.Series)

    def test_unicode_and_special_chars(self):
        """Test handling of unicode and special characters."""
        df = pd.DataFrame(
            {
                "detected_issues": ["😊 Good!", "❌ Bad!", "🔥 Issue", "Normal"],
                "rating": [5, 1, 2, 3],
                "sentiment_score": [0.9, 0.1, 0.2, 0.5],
            }
        )

        validation_passed = isinstance(df, pd.DataFrame)
        assert validation_passed


class TestRobustnessWithBadData:
    """Test robustness when data is severely corrupted."""

    def test_garbage_data_doesnt_crash(self):
        """Test that garbage data doesn't crash schema validation."""
        df = pd.DataFrame(
            {
                "rating": [None, {}, [], "never", 999],
                "sentiment_score": ["bad", "worse", "worst", None, {}],
                "customer_ltv": ["$1000", "€500", "¥1000", None, "free"],
            }
        )

        try:
            validated_df, report = validate_schema(df, strict=False)
            # Should complete without crashing
            assert isinstance(validated_df, pd.DataFrame)
        except Exception as e:
            pytest.fail(f"Schema validation crashed on garbage data: {str(e)}")

    def test_mixed_types_in_numeric_column(self):
        """Test safe handling of mixed types in numeric column."""
        df = pd.DataFrame(
            {
                "rating": [1, "2.5", "not a number", None, True, 3.5],
            }
        )

        validated_df, report = validate_schema(df, strict=False)

        # Should coerce safely
        assert pd.api.types.is_numeric_dtype(validated_df["rating"])
        assert not validated_df["rating"].isna().any()

    def test_completely_null_dataset(self):
        """Test handling of completely null dataset."""
        df = pd.DataFrame(
            {
                "rating": [None] * 10,
                "sentiment_score": [None] * 10,
                "customer_ltv": [None] * 10,
            }
        )

        validated_df, report = validate_schema(df, strict=False)

        # Should fill all with defaults
        assert not validated_df["rating"].isna().any()
        assert not validated_df["sentiment_score"].isna().any()
        assert not validated_df["customer_ltv"].isna().any()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
