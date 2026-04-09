"""Feature engineering service."""

import pandas as pd
import numpy as np


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features for review intelligence model.
    
    Adds:
    - severity_rating: (5 - rating) / 4, clipped to [0, 1]
    - recency: exp(-days_since_purchase / 30), clipped to [0, 1]
    - sentiment_score: mapped sentiment or 0.5 default, clipped to [0, 1]
    - is_negative: 1 if rating <= 2, else 0
    
    Args:
        df: Preprocessed DataFrame with rating, days_since_purchase, and optional sentiment
    
    Returns:
        DataFrame with new feature columns added
    """
    df = df.copy()
    
    # 1. Rating-based severity
    df['severity_rating'] = (5 - df['rating']) / 4
    df['severity_rating'] = np.clip(df['severity_rating'], 0, 1)
    
    # 2. Recency score
    df['recency'] = np.exp(-df['days_since_purchase'] / 30)
    df['recency'] = np.clip(df['recency'], 0, 1)
    
    # 3. Sentiment score
    if 'sentiment' in df.columns:
        sentiment_map = {'positive': 1, 'neutral': 0.5, 'negative': 0}
        df['sentiment_score'] = df['sentiment'].map(sentiment_map)
        # Fill any unmapped values with 0.5 as fallback
        df['sentiment_score'] = df['sentiment_score'].fillna(0.5)
    else:
        df['sentiment_score'] = 0.5
    df['sentiment_score'] = np.clip(df['sentiment_score'], 0, 1)
    
    # 4. Negative review flag
    df['is_negative'] = (df['rating'] <= 2).astype(int)
    
    # Ensure no NaN values remain in new columns
    df[['severity_rating', 'recency', 'sentiment_score', 'is_negative']] = \
        df[['severity_rating', 'recency', 'sentiment_score', 'is_negative']].fillna(0)
    
    return df
