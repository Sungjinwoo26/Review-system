"""Feature engineering service."""

import pandas as pd
import numpy as np

from services.sentiment import get_ai_sentiment, sentiment_to_pipeline_score
from utils.logger import log_event, log_warning, get_logger

logger = get_logger("features")


def _compute_sentiment_score(row) -> float:
    """Compute sentiment score for a single row using AI/VADER.

    Priority:
    1. If a ``review_text`` column exists and is non-empty, run it through
       :func:`get_ai_sentiment` (Ollama → VADER fallback) and rescale
       the [-1, +1] result to [0, 1].
    2. Else if a legacy ``sentiment`` label column exists, use the static map.
    3. Otherwise return the neutral default (0.5).
    """
    # --- AI / VADER path (preferred) ----------------------------------------
    review_text = row.get("review_text", None)
    if review_text and isinstance(review_text, str) and review_text.strip():
        try:
            raw = get_ai_sentiment(review_text)
            return sentiment_to_pipeline_score(raw)
        except Exception as exc:
            log_warning(
                "FEATURE_SENTIMENT",
                f"AI sentiment failed for row, using fallback: {exc!r}",
            )

    # --- Legacy static-label path -------------------------------------------
    sentiment_label = row.get("sentiment", None)
    if sentiment_label and isinstance(sentiment_label, str):
        sentiment_map = {"positive": 1.0, "neutral": 0.5, "negative": 0.0}
        return sentiment_map.get(sentiment_label.lower(), 0.5)

    return 0.5  # neutral default


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features for review intelligence model.
    
    Adds:
    - severity_rating: (5 - rating) / 4, clipped to [0, 1]
    - recency: exp(-days_since_purchase / 30), clipped to [0, 1]
    - sentiment_score: AI-powered (Ollama / VADER) or legacy map, clipped to [0, 1]
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
    
    # 3. Sentiment score — AI-powered with safe fallback
    try:
        has_review_text = (
            'review_text' in df.columns
            and df['review_text'].astype(str).str.strip().str.len().sum() > 0
        )

        if has_review_text or 'sentiment' in df.columns:
            df['sentiment_score'] = df.apply(_compute_sentiment_score, axis=1)
            log_event("FEATURE_ENGINEERING", {
                "sentiment_method": "ai_powered" if has_review_text else "legacy_map",
                "rows": len(df),
            })
        else:
            df['sentiment_score'] = 0.5
            log_event("FEATURE_ENGINEERING", {
                "sentiment_method": "default_neutral",
                "rows": len(df),
            })
    except Exception as exc:
        # Absolute last-resort fallback — pipeline must never crash
        log_warning(
            "FEATURE_SENTIMENT",
            f"Sentiment computation failed entirely, defaulting to 0.5: {exc!r}",
        )
        df['sentiment_score'] = 0.5

    df['sentiment_score'] = np.clip(df['sentiment_score'], 0, 1)
    
    # 4. Negative review flag
    df['is_negative'] = (df['rating'] <= 2).astype(int)
    
    # Ensure no NaN values remain in new columns
    df[['severity_rating', 'recency', 'sentiment_score', 'is_negative']] = \
        df[['severity_rating', 'recency', 'sentiment_score', 'is_negative']].fillna(0)
    
    return df
