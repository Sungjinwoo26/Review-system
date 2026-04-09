"""Enhanced robust preprocessing with safe value handling and normalization."""

import pandas as pd
import numpy as np
from typing import Tuple, Dict
from utils.logger import log_event, log_error, logger
from utils.validation import (
    validate_schema,
    safe_minmax,
    sanity_checks,
    check_nan_propagation,
    generate_robustness_report,
    DEFAULTS,
)


def robust_fill_missing_values(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Fill missing values using domain-aware strategy.
    
    Args:
        df: DataFrame with potential missing values
        
    Returns:
        Tuple of (cleaned_df, fill_report)
    """
    df = df.copy()
    report = {"columns_filled": {}, "nan_count_before": df.isna().sum().sum()}

    for col, default_val in DEFAULTS.items():
        if col in df.columns:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                df[col] = df[col].fillna(default_val)
                report["columns_filled"][col] = nan_count
                logger.info(f"Filled {nan_count} missing values in '{col}'")

    report["nan_count_after"] = df.isna().sum().sum()
    report["total_nan_filled"] = report["nan_count_before"] - report["nan_count_after"]

    return df, report


def robust_preprocess_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Complete robust preprocessing pipeline:
    1. Schema validation
    2. Fill missing values
    3. Safe type coercion
    4. Safe normalization
    5. Sanity checks
    
    Args:
        df: Raw DataFrame from API
        
    Returns:
        Tuple of (processed_df, robustness_report)
    """
    df = df.copy()
    pipeline_report = {"steps": {}, "success": False, "errors": []}

    try:
        # Step 1: Schema Validation
        logger.info("🔍 Step 1: Validating schema...")
        df, schema_report = validate_schema(df, strict=False)
        pipeline_report["steps"]["schema_validation"] = schema_report

        # Step 2: Fill Missing Values
        logger.info("🔍 Step 2: Filling missing values...")
        df, fill_report = robust_fill_missing_values(df)
        pipeline_report["steps"]["fill_missing"] = fill_report

        # Step 3: Log Scaling (safe application)
        logger.info("🔍 Step 3: Applying log scaling...")
        try:
            df["customer_ltv"] = df["customer_ltv"].astype(float)
            df["order_value"] = df["order_value"].astype(float)
            df["ltv_log"] = np.log1p(df["customer_ltv"])
            df["order_value_log"] = np.log1p(df["order_value"])
            pipeline_report["steps"]["log_scaling"] = "✅ Applied"
        except Exception as e:
            pipeline_report["errors"].append(f"Log scaling failed: {str(e)}")
            log_error("LOG_SCALING", str(e))
            df["ltv_log"] = df["customer_ltv"]
            df["order_value_log"] = df["order_value"]

        # Step 4: Safe Normalization
        logger.info("🔍 Step 4: Normalizing features...")
        try:
            df["ltv_norm"] = safe_minmax(df["ltv_log"])
            df["order_norm"] = safe_minmax(df["order_value_log"])
            df["helpful_norm"] = safe_minmax(df["helpful_votes"])
            pipeline_report["steps"]["normalization"] = "✅ Applied safely"
        except Exception as e:
            pipeline_report["errors"].append(f"Normalization failed: {str(e)}")
            log_error("NORMALIZATION", str(e))

        # Step 5: Encode Boolean Features
        logger.info("🔍 Step 5: Encoding boolean features...")
        if "is_repeat_customer" in df.columns:
            df["repeat"] = df["is_repeat_customer"].fillna(0).astype(int)
        else:
            df["repeat"] = DEFAULTS["repeat"]

        if "verified_purchase" in df.columns:
            df["verified"] = df["verified_purchase"].fillna(0).astype(int)
        else:
            df["verified"] = DEFAULTS["verified"]

        pipeline_report["steps"]["boolean_encoding"] = "✅ Applied"

        # Step 6: Final NaN Check
        logger.info("🔍 Step 6: Running final NaN check...")
        nan_check = check_nan_propagation(df)
        pipeline_report["steps"]["nan_check_final"] = nan_check

        # Step 7: Sanity Checks
        logger.info("🔍 Step 7: Running sanity checks...")
        is_valid, sanity_issues = sanity_checks(df)
        pipeline_report["steps"]["sanity_checks"] = {"valid": is_valid, "issues": sanity_issues}

        # Log any issues
        if sanity_issues:
            for issue in sanity_issues:
                if "❌" in issue:
                    log_error("SANITY_CHECK_CRITICAL", issue)
                    pipeline_report["errors"].append(issue)
                else:
                    logger.warning(issue)

        # Step 8: Final cleanup - ensure no NaN remains
        logger.info("🔍 Step 8: Final NaN elimination...")
        for col in df.columns:
            if df[col].isna().any():
                default_val = DEFAULTS.get(col, 0)
                df[col] = df[col].fillna(default_val)
                logger.warning(f"Final NaN fill in '{col}' with default {default_val}")

        pipeline_report["success"] = is_valid or not any("❌" in issue for issue in sanity_issues)
        pipeline_report["final_shape"] = df.shape

        log_event("PREPROCESSING_COMPLETE", {"rows": len(df), "success": pipeline_report["success"]})

        return df, pipeline_report

    except Exception as e:
        pipeline_report["errors"].append(f"Preprocessing pipeline failed: {str(e)}")
        log_error("PREPROCESSING_PIPELINE", str(e))
        raise


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Backward-compatible wrapper for existing code.
    
    Args:
        df: Raw DataFrame
        
    Returns:
        Processed DataFrame
    """
    processed_df, _ = robust_preprocess_data(df)
    return processed_df
