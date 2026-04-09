"""Data preprocessing service."""

import pandas as pd
import numpy as np


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean, transform, and normalize raw review data.
    
    Args:
        df: Raw DataFrame with review data
        
    Returns:
        Processed DataFrame with normalized and engineered features
    """
    # Create a copy to avoid modifying original
    df = df.copy()
    
    # 1. Handle Missing Values
    df['customer_ltv'] = df['customer_ltv'].fillna(0)
    df['order_value'] = df['order_value'].fillna(0)
    df['helpful_votes'] = df['helpful_votes'].fillna(0)
    df['days_since_purchase'] = df['days_since_purchase'].fillna(30)
    
    # 2. Apply Log Scaling
    df['ltv_log'] = np.log1p(df['customer_ltv'])
    df['order_value_log'] = np.log1p(df['order_value'])
    
    # 3. Normalize Numerical Features using Min-Max scaling
    def normalize(series):
        """Apply Min-Max normalization with epsilon to prevent division by zero."""
        return (series - series.min()) / (series.max() - series.min() + 1e-9)
    
    df['ltv_norm'] = normalize(df['ltv_log'])
    df['order_norm'] = normalize(df['order_value_log'])
    df['helpful_norm'] = normalize(df['helpful_votes'])
    
    # 4. Encode Boolean Features
    df['repeat'] = df['is_repeat_customer'].astype(int)
    df['verified'] = df['verified_purchase'].astype(int)
    
    # Ensure no NaNs remain
    df = df.fillna(0)
    
    return df
