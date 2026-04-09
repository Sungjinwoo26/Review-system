"""Scoring service - Review Intelligence Engine.

This module implements the core scoring logic for the Review Intelligence Engine,
following a 5-layer hierarchy:

1. Normalization & Scaling: Log-scale LTV/order_value, min-max other features
2. Feature Engineering: Severity rating, sentiment scores, recency calculations
3. Customer Importance Score (CIS): Weighted sum of customer/engagement factors
4. Issue Severity & Impact: Combines severity + CIS to get review impact
5. Validation: Ensures scoring logic is sound and unbiased

Weight Hierarchy:
- CIS: 30% LTV + 20% order value + 15% repeat + 10% verified + 10% helpful + 15% recency
- Severity: 60% rating severity + 40% sentiment score
- Impact: CIS × Severity

Formulas:
- Severity Rating: (5 - rating) / 4
- Recency: exp(-days_since_purchase / 30)
- Impact Score: CIS × Severity
"""

import pandas as pd
import numpy as np


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute weighted importance scores for each review (Layer 3).
    
    Combines customer importance (CIS) and issue severity to quantify
    which reviews matter most to the business.
    
    FORMULA LAYER 3:
    ---------------
    CIS = (0.30 × LTV_norm) + (0.20 × OrderValue_norm) + (0.15 × Repeat) 
          + (0.10 × Verified) + (0.10 × Helpful_norm) + (0.15 × Recency)
    
    FORMULA LAYER 5:
    FinalScore = ln(1 + TotalImpact) × (1 + PPS)
    
    Severity = (0.60 × SeverityRating) + (0.40 × (1 - SentimentScore))
    
    Impact Score = CIS × Severity
    
    Args:
        df: DataFrame containing preprocessed and engineered features
        
    Required Input Columns:
        - ltv_norm, order_norm, helpful_norm (from preprocessing)
        - repeat, verified (from preprocessing, binary 0/1)
        - severity_rating, recency, sentiment_score (from feature engineering)
        - rating (original rating for validation)
        - customer_ltv (original LTV for validation)
        
    Returns:
        DataFrame with new scoring columns:
        - CIS: Customer Importance Score [0, 1]
        - severity: Issue Severity Score [0, 1]
        - impact_score: Review Impact = CIS × Severity [0, 1]
        
    Constraints:
        - All outputs clipped to [0, 1] range
        - No NaN values in output (filled with 0)
        - Vectorized operations only (no loops)
    """
    df = df.copy()
    
    # ===== LAYER 3: CUSTOMER IMPORTANCE SCORE (CIS) =====
    # Purpose: Quantifies how important the customer is to the business
    # Weight Rationale:
    #   - 30% LTV: Direct financial value
    #   - 20% Order Value: Purchase power indicator
    #   - 15% Repeat: Customer loyalty
    #   - 10% Verified: Purchase authenticity
    #   - 10% Helpful Votes: Influence on others
    #   - 15% Recency: How recent the complaint is
    
    df['CIS'] = (
        0.30 * df['ltv_norm'] +
        0.20 * df['order_norm'] +
        0.15 * df['repeat'] +
        0.10 * df['verified'] +
        0.10 * df['helpful_norm'] +
        0.15 * df['recency']
    )
    
    # ===== LAYER 3B: ISSUE SEVERITY SCORE =====
    # Purpose: Measures how bad the complaint is
    # Weight Rationale:
    #   - 60% Severity Rating: Quantifies poor experience (1-5 scale)
    #   - 40% Sentiment Negativity: Emotional negativity of complaint
    # NOTE: We invert sentiment_score (1 - sentiment_score) so that:
    #   - Positive sentiment (1.0) reduces severity
    #   - Negative sentiment (0.0) increases severity
    #   - Example: 5-star positive = severity 0; 1-star negative = severity 1
    
    df['severity'] = (
        0.60 * df['severity_rating'] +
        0.40 * (1.0 - df['sentiment_score'])
    )
    
    # ===== LAYER 4: REVIEW IMPACT SCORE =====
    # Purpose: Captures true business impact
    # Logic: High-value customers with bad experiences matter more
    # Example: 1★ from $10k LTV customer >> 1★ from $100 LTV customer
    
    df['impact_score'] = df['CIS'] * df['severity']
    
    # ===== VALIDATION & SAFETY =====
    # Clip all scores to [0, 1] range for consistency
    df['CIS'] = df['CIS'].clip(0, 1)
    df['severity'] = df['severity'].clip(0, 1)
    df['impact_score'] = df['impact_score'].clip(0, 1)
    
    # Ensure no NaN values remain (fill with 0)
    df['CIS'] = df['CIS'].fillna(0)
    df['severity'] = df['severity'].fillna(0)
    df['impact_score'] = df['impact_score'].fillna(0)
    
    return df


def validation_check(df: pd.DataFrame) -> dict:
    """
    Validate the scoring logic to ensure proper weighting.
    
    Key Assertion:
    "A 1-star review from a high-LTV customer should score higher than
     a 1-star review from a low-LTV customer"
    
    This test confirms that CIS weighting (30% LTV) properly captures
    customer value differences.
    
    Args:
        df: DataFrame with scoring columns (CIS, severity, impact_score)
           and original columns (rating, customer_ltv)
    
    Returns:
        dict: Validation results with keys:
        - passed: bool (all checks passed)
        - high_ltv_vs_low_ltv: float (comparison ratio)
        - detail_messages: list (validation details)
    
    Example:
        >>> df = pd.DataFrame({
        ...     'rating': [1, 1],
        ...     'customer_ltv': [10000, 100],
        ...     'CIS': [0.8, 0.2],
        ...     'severity': [1.0, 1.0],
        ...     'impact_score': [0.8, 0.2]
        ... })
        >>> result = validation_check(df)
        >>> assert result['passed'] == True
    """
    results = {
        'passed': True,
        'detail_messages': []
    }
    
    try:
        # Check for required columns
        required_cols = ['rating', 'customer_ltv', 'CIS', 'severity', 'impact_score']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            results['passed'] = False
            results['detail_messages'].append(f"Missing columns: {missing}")
            return results
        
        # Test 1: High-LTV vs Low-LTV comparison for same rating
        low_rating_mask = df['rating'] <= 2
        if low_rating_mask.sum() > 0:
            low_rating_df = df[low_rating_mask]
            
            # Separate high and low LTV
            ltv_median = df['customer_ltv'].median()
            high_ltv = low_rating_df[low_rating_df['customer_ltv'] >= ltv_median]
            low_ltv = low_rating_df[low_rating_df['customer_ltv'] < ltv_median]
            
            if len(high_ltv) > 0 and len(low_ltv) > 0:
                high_ltv_avg_impact = high_ltv['impact_score'].mean()
                low_ltv_avg_impact = low_ltv['impact_score'].mean()
                
                # Store comparison ratio
                if low_ltv_avg_impact > 0:
                    ratio = high_ltv_avg_impact / low_ltv_avg_impact
                    results['high_ltv_vs_low_ltv'] = ratio
                    
                    if ratio > 1.0:
                        results['detail_messages'].append(
                            f"✅ High-LTV reviews score {ratio:.2f}x higher than low-LTV (PASS)"
                        )
                    else:
                        results['passed'] = False
                        results['detail_messages'].append(
                            f"❌ High-LTV reviews score {ratio:.2f}x vs low-LTV (FAIL)"
                        )
        
        # Test 2: Check CIS range
        if not ((df['CIS'] >= 0) & (df['CIS'] <= 1)).all():
            results['passed'] = False
            results['detail_messages'].append(
                f"CIS out of range [0,1]: min={df['CIS'].min():.3f}, max={df['CIS'].max():.3f}"
            )
        else:
            results['detail_messages'].append(
                f"✅ CIS in valid range: [{df['CIS'].min():.3f}, {df['CIS'].max():.3f}]"
            )
        
        # Test 3: Check severity range
        if not ((df['severity'] >= 0) & (df['severity'] <= 1)).all():
            results['passed'] = False
            results['detail_messages'].append(
                f"Severity out of range [0,1]: min={df['severity'].min():.3f}, max={df['severity'].max():.3f}"
            )
        else:
            results['detail_messages'].append(
                f"✅ Severity in valid range: [{df['severity'].min():.3f}, {df['severity'].max():.3f}]"
            )
        
        # Test 4: Check impact_score range
        if not ((df['impact_score'] >= 0) & (df['impact_score'] <= 1)).all():
            results['passed'] = False
            results['detail_messages'].append(
                f"Impact score out of range [0,1]: min={df['impact_score'].min():.3f}, max={df['impact_score'].max():.3f}"
            )
        else:
            results['detail_messages'].append(
                f"✅ Impact score in valid range: [{df['impact_score'].min():.3f}, {df['impact_score'].max():.3f}]"
            )
        
        # Test 5: Check for NaNs
        nan_counts = df[['CIS', 'severity', 'impact_score']].isna().sum()
        if nan_counts.sum() > 0:
            results['passed'] = False
            results['detail_messages'].append(f"NaN values found: {nan_counts.to_dict()}")
        else:
            results['detail_messages'].append("✅ No NaN values in scoring columns")
        
    except Exception as e:
        results['passed'] = False
        results['detail_messages'].append(f"Validation error: {str(e)}")
    
    return results
