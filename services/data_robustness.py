"""Data Robustness Layer - Complete orchestrator for robust data pipelines.

This module ensures all downstream components receive clean, consistent, reliable data
regardless of API inconsistencies or data quality issues.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional
from services.ingestion import fetch_reviews
from services.robust_preprocessing import robust_preprocess_data, preprocess_data
from utils.logger import log_event, log_error, logger
from utils.validation import (
    EXPECTED_SCHEMA,
    DEFAULTS,
    generate_robustness_report,
    sanity_checks,
)


def robust_data_pipeline(
    max_pages: int = None, include_report: bool = False
) -> Tuple[pd.DataFrame, Optional[Dict]]:
    """
    Complete robust data pipeline orchestrator.
    
    Pipeline stages:
    1. Fetch complete data from paginated API
    2. Validate schema and enforce data types
    3. Fill missing values with domain-aware defaults
    4. Apply safe transformations and normalization
    5. Run sanity checks
    6. Guarantee deterministic, crash-free output
    
    Args:
        max_pages: Maximum pages to fetch (None = unlimited)
        include_report: If True, return detailed robustness report
        
    Returns:
        If include_report=False:
            pd.DataFrame with clean, validated, normalized data
        If include_report=True:
            Tuple of (pd.DataFrame, robustness_report_dict)
            
    Raises:
        Exception: Only if critical validation fails (will be logged)
    """
    logger.info("=" * 80)
    logger.info("🚀 ROBUST DATA PIPELINE STARTING")
    logger.info("=" * 80)

    pipeline_report = {
        "stages": {},
        "success": False,
        "errors": [],
        "warnings": [],
    }

    try:
        # ===== STAGE 1: API FETCH =====
        logger.info("\n📡 STAGE 1: Fetching data from paginated API...")
        try:
            raw_df = fetch_reviews(max_pages=max_pages)
            pipeline_report["stages"]["api_fetch"] = {
                "rows": len(raw_df),
                "columns": len(raw_df.columns),
                "status": "✅ Success",
            }
            logger.info(f"✅ Fetched {len(raw_df)} reviews")
        except Exception as e:
            error_msg = f"API fetch failed: {str(e)}"
            pipeline_report["errors"].append(error_msg)
            log_error("API_FETCH", error_msg)
            raise

        # ===== STAGE 2: ROBUST PREPROCESSING =====
        logger.info("\n🧹 STAGE 2: Robust preprocessing...")
        try:
            processed_df, preprocess_report = robust_preprocess_data(raw_df)
            pipeline_report["stages"]["preprocessing"] = preprocess_report
            logger.info(f"✅ Processing complete: {processed_df.shape}")
        except Exception as e:
            error_msg = f"Preprocessing failed: {str(e)}"
            pipeline_report["errors"].append(error_msg)
            log_error("PREPROCESSING", error_msg)
            raise

        # ===== STAGE 3: DATA INTEGRITY CHECKS =====
        logger.info("\n✅ STAGE 3: Running integrity checks...")
        try:
            # Check 1: Non-empty
            if len(processed_df) == 0:
                raise ValueError("Dataset is empty after processing")

            # Check 2: Schema completeness
            schema_cols = list(EXPECTED_SCHEMA.keys())
            actual_cols = processed_df.columns.tolist()
            missing_schema_cols = [col for col in schema_cols if col not in actual_cols]

            if missing_schema_cols:
                pipeline_report["warnings"].append(f"Missing schema columns: {missing_schema_cols}")
                for col in missing_schema_cols:
                    processed_df[col] = DEFAULTS.get(col, 0)
                    logger.warning(f"Added missing column '{col}' with default")

            # Check 3: No NaN in critical columns
            critical_cols = schema_cols
            for col in critical_cols:
                if col in processed_df.columns:
                    nan_count = processed_df[col].isna().sum()
                    if nan_count > 0:
                        logger.warning(f"Critical column '{col}' has {nan_count} NaN; filling...")
                        processed_df[col] = processed_df[col].fillna(DEFAULTS.get(col, 0))

            # Check 4: Data types
            for col in processed_df.columns:
                if col in EXPECTED_SCHEMA:
                    expected_type = EXPECTED_SCHEMA[col]
                    if expected_type == "float":
                        processed_df[col] = pd.to_numeric(processed_df[col], errors="coerce").fillna(
                            DEFAULTS.get(col, 0)
                        )
                    elif expected_type == "int":
                        processed_df[col] = (
                            pd.to_numeric(processed_df[col], errors="coerce")
                            .fillna(DEFAULTS.get(col, 0))
                            .astype(int)
                        )

            pipeline_report["stages"]["integrity_checks"] = "✅ Passed"
            logger.info("✅ All integrity checks passed")

        except Exception as e:
            error_msg = f"Integrity check failed: {str(e)}"
            pipeline_report["errors"].append(error_msg)
            log_error("INTEGRITY_CHECK", error_msg)
            raise

        # ===== STAGE 4: FINAL VALIDATION =====
        logger.info("\n🔍 STAGE 4: Final validation...")
        try:
            is_valid, sanity_issues = sanity_checks(processed_df)

            for issue in sanity_issues:
                if "❌" in issue:
                    pipeline_report["errors"].append(issue)
                    log_error("FINAL_VALIDATION", issue)
                else:
                    pipeline_report["warnings"].append(issue)
                    logger.warning(issue)

            pipeline_report["stages"]["final_validation"] = {
                "valid": is_valid,
                "issues": sanity_issues,
            }

            if not is_valid and any("❌" in issue for issue in sanity_issues):
                raise ValueError("Critical validation failed")

            logger.info("✅ Final validation passed")

        except Exception as e:
            error_msg = f"Final validation failed: {str(e)}"
            pipeline_report["errors"].append(error_msg)
            log_error("FINAL_VALIDATION", error_msg)
            raise

        # ===== SUCCESS =====
        pipeline_report["success"] = True
        pipeline_report["final_shape"] = processed_df.shape
        pipeline_report["final_columns"] = processed_df.columns.tolist()

        logger.info("\n" + "=" * 80)
        logger.info(f"✅ PIPELINE SUCCESS - Ready for downstream processing")
        logger.info(f"   Rows: {processed_df.shape[0]}, Columns: {processed_df.shape[1]}")
        logger.info("=" * 80)

        log_event(
            "ROBUST_PIPELINE_COMPLETE",
            {
                "rows": len(processed_df),
                "columns": len(processed_df.columns),
                "success": True,
            },
        )

        if include_report:
            report = generate_robustness_report(processed_df, {}, [])
            report["pipeline_stages"] = pipeline_report["stages"]
            report["overall_success"] = pipeline_report["success"]
            report["errors"] = pipeline_report["errors"]
            report["warnings"] = pipeline_report["warnings"]
            return processed_df, report
        else:
            return processed_df, None

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error(f"❌ PIPELINE FAILED: {str(e)}")
        logger.error("=" * 80)
        pipeline_report["success"] = False

        if include_report:
            return pd.DataFrame(), pipeline_report
        else:
            raise


def validate_pipeline_output(df: pd.DataFrame) -> Tuple[bool, Dict]:
    """
    Validate that pipeline output meets quality standards.
    
    Args:
        df: Output DataFrame from pipeline
        
    Returns:
        Tuple of (is_valid, validation_report)
    """
    report = {
        "valid": False,
        "checks": {},
        "warnings": [],
    }

    try:
        # Check 1: Not empty
        report["checks"]["non_empty"] = len(df) > 0
        if not report["checks"]["non_empty"]:
            report["warnings"].append("DataFrame is empty")

        # Check 2: Required columns
        required_cols = list(EXPECTED_SCHEMA.keys())
        missing_cols = [col for col in required_cols if col not in df.columns]
        report["checks"]["required_columns_present"] = len(missing_cols) == 0
        if missing_cols:
            report["warnings"].append(f"Missing columns: {missing_cols}")

        # Check 3: No NaN in critical columns
        critical_nan = {}
        for col in required_cols:
            if col in df.columns:
                nan_count = df[col].isna().sum()
                critical_nan[col] = nan_count
                if nan_count > 0:
                    report["warnings"].append(f"Column '{col}' has {nan_count} NaN values")

        report["checks"]["no_critical_nan"] = all(count == 0 for count in critical_nan.values())

        # Check 4: Data types correct
        type_ok = True
        for col, expected_dtype in EXPECTED_SCHEMA.items():
            if col not in df.columns:
                continue
            if expected_dtype == "float":
                type_ok = type_ok and pd.api.types.is_numeric_dtype(df[col])
            elif expected_dtype == "int":
                type_ok = type_ok and pd.api.types.is_integer_dtype(df[col])
            elif expected_dtype == "str":
                type_ok = type_ok and (
                    pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col])
                )

        report["checks"]["correct_dtypes"] = type_ok

        # Overall validity
        report["valid"] = (
            report["checks"]["non_empty"]
            and report["checks"]["required_columns_present"]
            and report["checks"]["no_critical_nan"]
            and report["checks"]["correct_dtypes"]
        )

    except Exception as e:
        report["warnings"].append(f"Validation error: {str(e)}")

    return report["valid"], report


# ===== QUICK START FUNCTION =====
def get_clean_data(max_pages: int = None) -> pd.DataFrame:
    """
    Quick access function - returns clean data ready for scoring.
    
    Args:
        max_pages: Maximum pages to fetch
        
    Returns:
        Clean, validated DataFrame
    """
    df, _ = robust_data_pipeline(max_pages=max_pages, include_report=False)
    return df
