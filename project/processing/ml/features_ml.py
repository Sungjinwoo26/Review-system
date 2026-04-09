"""
ML Feature Preparation Module

Prepares product-level features from aggregated review data for ML model training and prediction.
Features are derived from existing aggregated metrics to ensure consistency with scoring engine.

Input: aggregated_df (output from aggregation.py)
Output: Enhanced DataFrame with computed ML features + feature list for model training
"""

import pandas as pd
import numpy as np


def prepare_ml_features(df: pd.DataFrame) -> tuple:
    """
    Prepare product-level ML features from aggregated review data.
    
    This function:
    - Creates derived ML features from existing aggregated metrics
    - Computes missing features (avg_severity, rating_drop) from available columns
    - Handles missing values gracefully (fillna with 0)
    - Returns feature list for model training
    
    Args:
        df: Product-level aggregated DataFrame containing:
            - total_impact, negative_ratio, total_reviews
            - repeat_rate, avg_order_value, avg_rating
            - final_score, total_revenue_at_risk
    
    Returns:
        Tuple of (enhanced_df, feature_list)
        - enhanced_df: DataFrame with computed features
        - feature_list: List of feature column names for ML model
    
    Feature Engineering:
    - impact_per_review: total_impact divided by total_reviews
    - avg_severity: Computed from negative_ratio if missing (proxy: negative_ratio)
    - rating_drop: Computed from avg_rating if missing (5 - avg_rating)
    - Additional calculated features for robustness
    """
    
    df = df.copy()
    
    # ===== FEATURE CREATION =====
    
    # 1. Impact per review (average impact magnitude per review)
    df['impact_per_review'] = np.where(
        df['total_reviews'] > 0,
        df['total_impact'] / df['total_reviews'],
        0
    )
    
    # 2. Negative reviews count (derived from negative_ratio)
    df['negative_reviews'] = np.where(
        df['total_reviews'] > 0,
        (df['negative_ratio'] * df['total_reviews']).round().astype(int),
        0
    )
    
    # 3. Average severity (compute from negative_ratio if not available)
    if 'avg_severity' not in df.columns:
        # Proxy: use negative_ratio as a measure of issue severity
        # Higher negative ratio = more severe issues
        df['avg_severity'] = df['negative_ratio'].clip(0, 1)
    df['avg_severity'] = df['avg_severity'].fillna(df['negative_ratio'])
    
    # 4. Rating drop (compute if not available)
    if 'rating_drop' not in df.columns:
        if 'avg_rating' in df.columns:
            df['rating_drop'] = (5 - df['avg_rating']).clip(0, 5)
        else:
            df['rating_drop'] = 0
    df['rating_drop'] = df['rating_drop'].fillna(0)
    
    # 5. Recency score (if not available, default to 0)
    if 'recency_score' not in df.columns:
        df['recency_score'] = 0
    
    # 6. Review velocity (total_reviews scaled by recency)
    df['review_velocity'] = df['total_reviews'] * (1 + df.get('recency_score', 0))
    
    # 7. Severity-weighted impact (high severity + high impact = high risk)
    df['severity_impact'] = df['avg_severity'] * df['impact_per_review']
    
    # ===== FEATURE LIST FOR ML MODEL =====
    # These features are selected based on:
    # - Availability in aggregated data (no missing columns)
    # - Predictive power for product risk
    # - Interpretability for business users
    
    features = [
        'avg_severity',           # Layer 1: Issue severity score
        'negative_ratio',         # Layer 2: Proportion of negative reviews
        'total_impact',           # Layer 3: Aggregated impact score
        'total_reviews',          # Layer 4: Review volume
        'repeat_rate',            # Customer relationship signal
        'avg_order_value',        # Business value signal
        'rating_drop',            # Satisfaction trend signal
        'recency_score',          # Temporal relevance signal (if exists)
        'impact_per_review',      # Computed: Average impact magnitude
        'severity_impact',        # Computed: Severity × Impact interaction
        'review_velocity'         # Computed: Volume × Recency velocity
    ]
    
    # Remove features that don't exist in the dataframe
    available_features = [f for f in features if f in df.columns]
    
    # If critical features are missing, raise an error
    critical_features = ['total_impact', 'negative_ratio', 'total_reviews', 'avg_order_value']
    missing_critical = [f for f in critical_features if f not in df.columns]
    if missing_critical:
        raise ValueError(f"Missing critical features: {missing_critical}")
    
    # ===== DATA CLEANING =====
    # Fill missing values with 0 (safe default for aggregated metrics)
    for feature in available_features:
        df[feature] = df[feature].fillna(0)
    
    # Ensure no infinite or NaN values in features
    df[available_features] = df[available_features].replace([np.inf, -np.inf], 0)
    
    return df, available_features
