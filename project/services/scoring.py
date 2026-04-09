"""Scoring service."""

import pandas as pd
import numpy as np


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute weighted importance scores for each review.
    
    Combines customer importance and issue severity to quantify
    which reviews matter most to the business.
    
    Args:
        df: DataFrame containing preprocessed and engineered features
        
    Required Input Columns:
        - ltv_norm, order_norm, helpful_norm (from preprocessing)
        - repeat, verified (from preprocessing)
        - severity_rating, recency, sentiment_score (from feature engineering)
        
    Returns:
        DataFrame with new scoring columns: CIS, severity, impact_score
    """
    df = df.copy()
    
    # 1. CUSTOMER IMPORTANCE SCORE (CIS)
    # Quantifies how important the customer is to the business
    df['CIS'] = (
        0.30 * df['ltv_norm'] +
        0.20 * df['order_norm'] +
        0.15 * df['repeat'] +
        0.10 * df['verified'] +
        0.10 * df['helpful_norm'] +
        0.15 * df['recency']
    )
    
    # 2. ISSUE SEVERITY SCORE
    # Measures how bad the complaint is
    df['severity'] = (
        0.60 * df['severity_rating'] +
        0.40 * df['sentiment_score']
    )
    
    # 3. REVIEW IMPACT SCORE
    # Captures true business impact (customer importance × severity)
    df['impact_score'] = df['CIS'] * df['severity']
    
    # 4. VALIDATION & SAFETY
    # Clip all scores to [0, 1] range
    df['CIS'] = df['CIS'].clip(0, 1)
    df['severity'] = df['severity'].clip(0, 1)
    df['impact_score'] = df['impact_score'].clip(0, 1)
    
    # Ensure no NaN values remain
    df['CIS'] = df['CIS'].fillna(0)
    df['severity'] = df['severity'].fillna(0)
    df['impact_score'] = df['impact_score'].fillna(0)
    
    return df
