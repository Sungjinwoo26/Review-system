"""Data validation and schema enforcement utilities for robustness."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from utils.logger import log_error, log_event, logger


# ===== SCHEMA DEFINITION =====
EXPECTED_SCHEMA = {
    "rating": "float",
    "sentiment_score": "float",
    "customer_ltv": "float",
    "order_value": "float",
    "repeat": "int",
    "verified": "int",
    "helpful_votes": "int",
    "days_since_purchase": "int",
    "detected_issues": "str",
}

# Domain-aware default values (neutral, non-biasing)
DEFAULTS = {
    "rating": 3.0,  # Neutral middle rating
    "sentiment_score": 0.5,  # Neutral sentiment
    "customer_ltv": 0.0,  # Unknown LTV = zero risk
    "order_value": 0.0,  # Unknown order value = zero
    "repeat": 0,  # Unknown repeat status = not repeat
    "verified": 0,  # Unknown verification = unverified
    "helpful_votes": 0,  # No helpful votes by default
    "days_since_purchase": 30,  # Average month for unknown
    "detected_issues": "unknown",  # Unknown issues tag
}

# Allowed value ranges for clipping
VALUE_RANGES = {
    "rating": (1.0, 5.0),
    "sentiment_score": (0.0, 1.0),
}


# ===== SCHEMA VALIDATION =====
def validate_schema(df: pd.DataFrame, strict: bool = False) -> Tuple[pd.DataFrame, Dict]:
    """
    Validate and enforce schema on DataFrame.
    
    Args:
        df: Input DataFrame
        strict: If True, raise error on missing columns. If False, create with defaults.
        
    Returns:
        Tuple of (validated_df, validation_report)
    """
    report = {
        "total_rows": len(df),
        "missing_columns": [],
        "filled_columns": [],
        "type_conversions": [],
        "errors": [],
    }

    df = df.copy()

    # Check for missing columns
    for col, dtype in EXPECTED_SCHEMA.items():
        if col not in df.columns:
            if strict:
                report["errors"].append(f"Missing required column: {col}")
                log_error("SCHEMA_VALIDATION", f"Missing column: {col}")
                continue
            else:
                # Create column with default value
                df[col] = DEFAULTS.get(col, None)
                report["filled_columns"].append(col)
                logger.info(f"📝 Created missing column '{col}' with default value")

    # Type coercion
    for col, expected_dtype in EXPECTED_SCHEMA.items():
        if col not in df.columns:
            continue

        if expected_dtype == "float":
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                # Fill NaN with default
                if df[col].isna().any():
                    default_val = DEFAULTS.get(col, 0.0)
                    df[col] = df[col].fillna(default_val)
                    report["type_conversions"].append(
                        f"{col}: converted to float (filled {df[col].isna().sum()} NaN)"
                    )
            except Exception as e:
                report["errors"].append(f"Failed to convert {col} to float: {str(e)}")
                log_error("TYPE_CONVERSION", str(e), {"column": col})

        elif expected_dtype == "int":
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(DEFAULTS.get(col, 0))
                df[col] = df[col].astype(int)
                report["type_conversions"].append(f"{col}: converted to int")
            except Exception as e:
                report["errors"].append(f"Failed to convert {col} to int: {str(e)}")
                log_error("TYPE_CONVERSION", str(e), {"column": col})

        elif expected_dtype == "str":
            try:
                df[col] = df[col].fillna(DEFAULTS.get(col, "unknown")).astype(str)
                report["type_conversions"].append(f"{col}: converted to str")
            except Exception as e:
                report["errors"].append(f"Failed to convert {col} to str: {str(e)}")
                log_error("TYPE_CONVERSION", str(e), {"column": col})

    if report["errors"]:
        log_event("SCHEMA_VALIDATION_WARNINGS", {"errors": len(report["errors"])})

    return df, report


# ===== SAFE NORMALIZATION =====
def safe_minmax(series: pd.Series, clip_range: Tuple = None) -> pd.Series:
    """
    Safe Min-Max normalization that handles constant columns.
    
    Args:
        series: Pandas Series to normalize
        clip_range: Optional tuple (min, max) to clip values before normalization
        
    Returns:
        Normalized Series [0, 1] or constant 0.5 if all values identical
    """
    try:
        if clip_range:
            series = series.clip(clip_range[0], clip_range[1])

        min_val = series.min()
        max_val = series.max()

        # Handle constant columns (all same value)
        if np.isclose(min_val, max_val):
            logger.debug(f"Constant column detected: {series.name} = {min_val}. Using 0.5")
            return pd.Series([0.5] * len(series), index=series.index)

        # Standard Min-Max normalization
        normalized = (series - min_val) / (max_val - min_val)
        return normalized

    except Exception as e:
        log_error("NORMALIZATION", str(e), {"series": series.name})
        # Fallback: return 0.5 for all values
        return pd.Series([0.5] * len(series), index=series.index)


# ===== NaN AND VALUE CHECKING =====
def check_nan_propagation(df: pd.DataFrame, critical_cols: List[str] = None) -> Dict:
    """
    Check for NaN values and report on critical columns.
    
    Args:
        df: DataFrame to check
        critical_cols: List of columns that must not have NaN
        
    Returns:
        Report dictionary with NaN statistics
    """
    if critical_cols is None:
        critical_cols = list(EXPECTED_SCHEMA.keys())

    report = {
        "total_nan": df.isna().sum().sum(),
        "columns_with_nan": {},
        "critical_violations": [],
    }

    for col in df.columns:
        nan_count = df[col].isna().sum()
        if nan_count > 0:
            report["columns_with_nan"][col] = {
                "count": nan_count,
                "percentage": (nan_count / len(df)) * 100,
            }

            if col in critical_cols:
                report["critical_violations"].append(
                    f"Critical column '{col}' has {nan_count} NaN values ({(nan_count / len(df)) * 100:.1f}%)"
                )

    if report["critical_violations"]:
        log_event("NAN_VIOLATIONS", report["critical_violations"])

    return report


# ===== SANITY CHECKS =====
def sanity_checks(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Run comprehensive sanity checks on DataFrame.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        Tuple of (is_valid, issues_list)
    """
    issues = []

    # Check 1: Not empty
    if len(df) == 0:
        issues.append("❌ Dataset is empty")
        return False, issues

    # Check 2: Required columns present
    required_cols = list(EXPECTED_SCHEMA.keys())
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        issues.append(f"❌ Missing columns: {missing}")

    # Check 3: No critical NaN columns
    critical_nan_check = check_nan_propagation(df, critical_cols=required_cols)
    if critical_nan_check["critical_violations"]:
        for violation in critical_nan_check["critical_violations"]:
            issues.append(f"❌ {violation}")

    # Check 4: Value ranges (clip if needed)
    for col, (min_val, max_val) in VALUE_RANGES.items():
        if col in df.columns:
            out_of_range = df[(df[col] < min_val) | (df[col] > max_val)]
            if len(out_of_range) > 0:
                df[col] = df[col].clip(min_val, max_val)
                issues.append(
                    f"⚠️ Clipped {len(out_of_range)} out-of-range values in '{col}' to [{min_val}, {max_val}]"
                )

    # Check 5: Data types
    for col, expected_dtype in EXPECTED_SCHEMA.items():
        if col not in df.columns:
            continue
        if expected_dtype == "float":
            if not pd.api.types.is_numeric_dtype(df[col]):
                issues.append(f"⚠️ Column '{col}' is not numeric")
        elif expected_dtype == "int":
            if not pd.api.types.is_integer_dtype(df[col]):
                issues.append(f"⚠️ Column '{col}' is not integer")
        elif expected_dtype == "str":
            if not pd.api.types.is_string_dtype(df[col]) and not pd.api.types.is_object_dtype(
                df[col]
            ):
                issues.append(f"⚠️ Column '{col}' is not string")

    is_valid = len(issues) == 0 or not any("❌" in issue for issue in issues)

    return is_valid, issues


# ===== SUMMARY REPORT =====
def generate_robustness_report(
    df: pd.DataFrame, validation_report: Dict, sanity_issues: List[str]
) -> Dict:
    """
    Generate comprehensive robustness report.
    
    Args:
        df: Validated DataFrame
        validation_report: Output from validate_schema()
        sanity_issues: Output from sanity_checks()
        
    Returns:
        Comprehensive report dictionary
    """
    return {
        "dataset_shape": df.shape,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "schema_validation": validation_report,
        "sanity_checks": sanity_issues,
        "nan_check": check_nan_propagation(df),
        "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
        "timestamp": pd.Timestamp.now().isoformat(),
    }
