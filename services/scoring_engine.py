from __future__ import annotations
"""Advanced Scoring Engine - Review Intelligence System.

Implements a 4-layer hierarchy to prioritize customer complaints based on
business impact (Revenue at Risk) rather than frequency alone.

Layers:
1. Customer Importance Score (CIS) - Who is complaining?
2. Impact Score - How severe is their issue + customer value?
3. Product Priority Score (PPS) - Product-level aggregation
4. Final Global Score - Decision quadrants

Key Features:
- 10-day recency plateau (recent complaints weighted equally)
- Balanced issue severity (rating + sentiment don't cancel out)
- Zero-gate for positive reviews (rating > 3)
- Quadrant analysis for decision making
- Revenue at Risk calculation
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Union, Optional
import warnings

from services.sentiment import get_ai_sentiment, sentiment_to_pipeline_score
from utils.logger import log_event, log_warning, get_logger

logger = get_logger("scoring_engine")
warnings.filterwarnings('ignore')


def preprocess_and_validate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess raw review data with schema safety.
    
    Args:
        df: Raw DataFrame from API
        
    Returns:
        Cleaned DataFrame ready for scoring
        
    Handles:
        - Missing values with safe defaults
        - Log scaling for outlier reduction
        - Min-Max normalization [0, 1]
        - Schema changes (missing columns)
    """
    df = df.copy()
    
    # ===== 1. MISSING VALUE HANDLING =====
    # Fill numeric columns with safe defaults
    if 'customer_ltv' not in df.columns:
        df['customer_ltv'] = 0.0
    else:
        df['customer_ltv'] = df['customer_ltv'].fillna(0).astype(float)
    
    if 'order_value' not in df.columns:
        df['order_value'] = 0.0
    else:
        df['order_value'] = df['order_value'].fillna(0).astype(float)
    
    if 'helpful_votes' not in df.columns:
        df['helpful_votes'] = 0.0
    else:
        df['helpful_votes'] = df['helpful_votes'].fillna(0).astype(float)
    
    if 'days_since_purchase' not in df.columns:
        df['days_since_purchase'] = 30.0
    else:
        df['days_since_purchase'] = df['days_since_purchase'].fillna(30).astype(float)
    
    # Ensure required columns exist
    required_cols = ['rating', 'review_text', 'is_repeat_customer', 'verified_purchase']
    for col in required_cols:
        if col not in df.columns:
            if col == 'rating':
                df[col] = 3  # Default neutral rating
            elif col == 'review_text':
                df[col] = ''
            elif col in ['is_repeat_customer', 'verified_purchase']:
                df[col] = False
    
    # ===== 2. LOG SCALING (Minimize outlier impact) =====
    df['ltv_log'] = np.log1p(df['customer_ltv'])
    df['order_value_log'] = np.log1p(df['order_value'])
    
    # ===== 3. MIN-MAX NORMALIZATION [0, 1] =====
    def min_max_normalize(series: pd.Series) -> pd.Series:
        """Apply Min-Max normalization with epsilon to prevent division by zero."""
        min_val = series.min()
        max_val = series.max()
        if max_val == min_val:
            return pd.Series([0.0] * len(series), index=series.index)
        return ((series - min_val) / (max_val - min_val + 1e-9)).clip(0, 1)
    
    df['ltv_norm'] = min_max_normalize(df['ltv_log'])
    df['order_norm'] = min_max_normalize(df['order_value_log'])
    df['helpful_norm'] = min_max_normalize(df['helpful_votes'])
    
    # ===== 4. BOOLEAN ENCODING =====
    df['repeat'] = df['is_repeat_customer'].fillna(False).astype(int)
    df['verified'] = df['verified_purchase'].fillna(False).astype(int)
    
    # Ensure rating in valid range
    df['rating'] = df['rating'].clip(1, 5)
    
    return df


def calculate_recency_score(days_since_purchase: pd.Series) -> pd.Series:
    """
    Calculate recency score with 10-day plateau.
    
    Logic:
        - Reviews within 10 days: Full weight (score = 1.0)
        - After 10 days: Exponential decay
        - Formula: exp(-adj_days / 30) where adj_days = max(0, days - 10)
    
    Args:
        days_since_purchase: Series of days
        
    Returns:
        Recency scores in [0, 1]
        
    Example:
        >>> days = pd.Series([5, 10, 30, 60])
        >>> scores = calculate_recency_score(days)
        >>> # [1.0, 1.0, 0.45, 0.14]
    """
    # Plateau: reviews within 10 days get full weight
    adj_days = np.maximum(0, days_since_purchase - 10)
    
    # Exponential decay after plateau
    recency_score = np.exp(-adj_days / 30)
    
    return recency_score.clip(0, 1)


def calculate_issue_severity(rating: pd.Series, sentiment: Union[pd.Series, str] = 'neutral') -> pd.Series:
    """
    Calculate balanced issue severity combining rating and sentiment.
    
    Enhanced Logic:
    - Combines rating severity (linear) with sentiment negativity.
    - If sentiment is numerical [0, 1], it's treated as (1 - score) for negativity.
    - Formula: 0.6 * rating_severity + 0.4 * sentiment_negativity
    """
    # Convert rating to severity (5★ = 0 severity, 1★ = 1.0 severity)
    rating_severity = (5 - rating) / 4
    rating_severity = rating_severity.clip(0, 1)
    
    # Sentiment mapping
    if isinstance(sentiment, str):
        if sentiment.lower() == 'negative':
            sentiment_negativity = 1.0
        elif sentiment.lower() == 'positive':
            sentiment_negativity = 0.0
        else:  # neutral
            sentiment_negativity = 0.5
    elif isinstance(sentiment, pd.Series):
        if pd.api.types.is_numeric_dtype(sentiment):
            # If numeric (expected [0, 1]), then 1.0 is positive, so negativity is (1 - sentiment)
            sentiment_negativity = (1.0 - sentiment).clip(0, 1)
        else:
            # If string/object Series, map labels
            sentiment_negativity = sentiment.map({
                'negative': 1.0,
                'neutral': 0.5,
                'positive': 0.0
            }).fillna(0.5)
    else:
        sentiment_negativity = 0.5
    
    # Balanced formula
    issue_severity = (0.6 * rating_severity) + (0.4 * sentiment_negativity)
    
    return issue_severity.clip(0, 1)


def compute_cis(df: pd.DataFrame) -> pd.Series:
    """
    Compute Customer Importance Score (Layer 1).
    
    Formula:
    CIS = (0.30 × LTV_norm) + (0.20 × OrderValue_norm) + (0.15 × Repeat)
          + (0.10 × Verified) + (0.10 × Helpful_norm) + (0.15 × Recency)
    
    ENHANCEMENT: Loyal Advocate Multiplier
    If a customer is both Repeat AND Verified AND has >0.5 helpful votes, 
    their CIS gets a 1.2x multiplier (max 1.0).
    """
    cis = (
        0.30 * df['ltv_norm'] +
        0.20 * df['order_norm'] +
        0.15 * df['repeat'] +
        0.10 * df['verified'] +
        0.10 * df['helpful_norm'] +
        0.15 * df['recency_score']
    )
    
    # Apply Loyalty Boost
    loyalty_mask = (df['repeat'] == 1) & (df['verified'] == 1) & (df['helpful_norm'] > 0.5)
    cis = pd.Series(np.where(loyalty_mask, cis * 1.2, cis), index=df.index)
    
    return cis.clip(0, 1)


def compute_impact_score(df: pd.DataFrame) -> pd.Series:
    """
    Compute Impact Score (Layer 2) with non-linear "Crisis Factor".
    
    Logic:
    - Base Impact = CIS × issue_severity
    - ZERO-GATE: If rating > 3, force impact_score = 0
    
    ENHANCEMENT: Exponential Crisis Multiplier
    If both CIS > 0.7 (VIP) and Severity > 0.7 (Critical), the impact 
    is boosted by 1.5x to highlight immediate revenue risks.
    """
    impact = df['CIS'] * df['issue_severity']
    
    # Apply Crisis Multiplier for VIPs with Critical Issues
    crisis_mask = (df['CIS'] > 0.7) & (df['issue_severity'] > 0.7)
    impact = pd.Series(np.where(crisis_mask, impact * 1.5, impact), index=df.index)
    
    # ZERO-GATE: Positive reviews (rating > 3) have zero impact
    impact = impact.where(df['rating'] <= 3.0, 0)
    
    return impact.clip(0, 1)


def compute_pps(product_df: pd.DataFrame) -> pd.Series:
    """
    Compute Product Priority Score (Layer 3).
    
    Formula:
    PPS = (0.25 × Freq_norm) + (0.20 × AvgOrder_norm) + (0.20 × RepeatRate_norm)
          + (0.20 × RatingDrop_norm) + (0.15 × NegRatio_norm)
    
    Where:
        Freq = total reviews per product
        AvgOrder = average order value per product
        RepeatRate = % of repeat customers per product
        RatingDrop = 5 - avg_rating (higher = worse)
        NegRatio = % of reviews with rating <= 2.5
    
    Args:
        product_df: Product-aggregated DataFrame
        
    Returns:
        Series of PPS scores [0, 1]
    """
    # Normalize each metric
    def normalize(series):
        min_val = series.min()
        max_val = series.max()
        if max_val == min_val:
            return pd.Series([0.0] * len(series), index=series.index)
        return ((series - min_val) / (max_val - min_val + 1e-9)).clip(0, 1)
    
    freq_norm = normalize(product_df['total_reviews'])
    order_norm = normalize(product_df['avg_order_value'])
    repeat_norm = normalize(product_df['repeat_rate'])
    
    # Rating drop: lower rating = higher drop (worse)
    rating_drop = 5 - product_df['avg_rating']
    rating_drop_norm = normalize(rating_drop)
    
    # Negative ratio
    neg_norm = normalize(product_df['negative_ratio'])
    
    pps = (
        0.25 * freq_norm +
        0.20 * order_norm +
        0.20 * repeat_norm +
        0.20 * rating_drop_norm +
        0.15 * neg_norm
    )
    
    return pps.clip(0, 1)


def compute_final_score(product_df: pd.DataFrame) -> pd.Series:
    """
    Compute Final Global Score (Layer 4).
    
    Formula:
    FinalScore = ln(1 + TotalImpact) × (1 + PPS)
    
    Rationale:
    - log1p dampens the effect of extreme impact values
    - Multiplying by (1 + PPS) gives products with higher priority a boost
    
    Args:
        product_df: Product-aggregated DataFrame with total_impact and PPS
        
    Returns:
        Series of final scores
    """
    final_score = np.log1p(product_df['total_impact']) * (1 + product_df['PPS'])
    
    return final_score


def calculate_revenue_at_risk(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate Revenue at Risk scaled by issue severity.
    
    IMPROVED Logic:
    - Instead of just sum(LTV), we use LTV * issue_severity.
    - This reflects that a minor complaint from an MVP customer is less 
      risky than a total product failure from the same customer.
    """
    # Use issue_severity as a weight for the LTV risk
    df = df.copy()
    if 'issue_severity' not in df.columns:
        df['issue_severity'] = calculate_issue_severity(df['rating'])
    
    # Only consider negative/neutral reviews for risk
    risky_reviews = df[df['rating'] <= 3]
    
    weighted_rev_risk = (risky_reviews['customer_ltv'] * risky_reviews['issue_severity']).sum()
    num_risky_reviews = len(risky_reviews)
    
    # Also track 'Hard Risk' (Legacy sum of LTV for very negative reviews)
    hard_risk = df[df['rating'] <= 2.5]['customer_ltv'].sum()
    
    return {
        'total_rev_risk': weighted_rev_risk,
        'hard_risk': hard_risk,
        'num_risky_reviews': num_risky_reviews,
        'avg_ltv_per_risk': weighted_rev_risk / num_risky_reviews if num_risky_reviews > 0 else 0
    }


def apply_scoring_pipeline(df: pd.DataFrame, groq_key: Optional[str] = None) -> pd.DataFrame:
    """
    Apply ENHANCED scoring pipeline with AI sentiment.
    """
    # Step 1: Preprocess and validate
    df = preprocess_and_validate(df)
    
    # Step 2: AI Sentiment Score (Layer 0)
    def _safe_get_sentiment(text):
        if not text or not isinstance(text, str) or not text.strip():
            return 0.5
        try:
            raw = get_ai_sentiment(text, groq_key=groq_key)
            return sentiment_to_pipeline_score(raw)
        except:
            return 0.5

    # Check if we should run AI (only if text exists)
    if 'review_text' in df.columns:
        # Note: In a real prod env, we might use batching or async here
        df['sentiment_score'] = df['review_text'].apply(_safe_get_sentiment)
    else:
        df['sentiment_score'] = 0.5
        
    # Step 3: Create is_negative flag EARLY
    df['is_negative'] = np.where(df['rating'] <= 2, 1, 0)
    
    # Step 4: Calculate recency with 10-day plateau
    df['recency_score'] = calculate_recency_score(df['days_since_purchase'])
    
    # Step 5: Calculate issue severity (rating + AI sentiment)
    df['issue_severity'] = calculate_issue_severity(df['rating'], df['sentiment_score'])
    
    # Step 6: Compute CIS (Layer 1) with Loyalty Boost
    df['CIS'] = compute_cis(df)
    
    # Step 7: Compute impact score (Layer 2) with Crisis Multiplier
    df['impact_score'] = compute_impact_score(df)
    
    # Ensure no NaNs
    df = df.fillna(0)
    
    log_event("SCORING_PIPELINE_RUN", {"total_rows": len(df)})
    
    return df


def aggregate_to_products(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate review-level data to product level for PPS and final scores.
    
    Args:
        df: Review-level DataFrame with scoring columns
        
    Returns:
        Product-level DataFrame with PPS and final scores
    """
    # Ensure product column exists and is valid
    if 'product' not in df.columns:
        df['product'] = 'General'
    
    # Clean product column: remove NaN, empty strings, convert to string
    df['product'] = df['product'].fillna('Unknown').astype(str).str.strip()
    df = df[df['product'] != '']
    
    # Ensure customer_ltv is numeric
    if 'customer_ltv' not in df.columns:
        df['customer_ltv'] = 0
    df['customer_ltv'] = pd.to_numeric(df['customer_ltv'], errors='coerce').fillna(0)
    
    # DEBUG: Log data overview
    print(f"\n[DEBUG] Aggregation Input:")
    print(f"  - Total reviews: {len(df)}")
    print(f"  - Unique products: {df['product'].nunique()}")
    print(f"  - Customer LTV range: {df['customer_ltv'].min()} to {df['customer_ltv'].max()}")
    print(f"  - Negative reviews (rating <= 2.5): {len(df[df['rating'] <= 2.5])}")
    
    # Group by product
    product_df = df.groupby('product', as_index=False).agg({
        'impact_score': 'sum',
        'rating': 'mean',
        'repeat': 'mean',
        'customer_ltv': ['mean', 'sum'],
        'order_value': 'mean'
    })
    
    # Flatten column names
    product_df.columns = ['product', 'total_impact', 'avg_rating', 'repeat_rate',
                          'avg_customer_ltv', 'total_ltv', 'avg_order_value']
    
    # Count reviews per product
    review_counts = df.groupby('product', as_index=False).size()
    review_counts.columns = ['product', 'total_reviews']
    product_df = product_df.merge(review_counts, on='product')
    
    # Calculate negative ratio (rating <= 2.5)
    negative_counts = df[df['rating'] <= 2.5].groupby('product', as_index=False).size()
    negative_counts.columns = ['product', 'negative_count']
    product_df = product_df.merge(negative_counts, on='product', how='left')
    product_df['negative_count'] = product_df['negative_count'].fillna(0)
    product_df['negative_ratio'] = product_df['negative_count'] / product_df['total_reviews']
    
    # Calculate revenue at risk per product
    # ENHANCED: Weighted Risk = LTV * issue_severity (proportional risk)
    df['weighted_risk_val'] = df['customer_ltv'] * df['issue_severity']
    
    # Factor: Only apply risk to reviews that are actually problematic (rating <= 3)
    # Neutral/Positive reviews don't contribute to 'risk' even if they have some severity
    df['active_risk'] = np.where(df['rating'] <= 3.0, df['weighted_risk_val'], 0)
    
    rev_at_risk = df.groupby('product')['active_risk'].sum().reset_index()
    rev_at_risk.columns = ['product', 'total_revenue_at_risk']
    
    # Also calculate 'Hard Risk' (Legacy: full LTV of negative reviews rating <= 2)
    hard_risk = df[df['rating'] <= 2.0].groupby('product')['customer_ltv'].sum().reset_index()
    hard_risk.columns = ['product', 'hard_revenue_risk']
    
    product_df = product_df.merge(rev_at_risk, on='product', how='left')
    product_df = product_df.merge(hard_risk, on='product', how='left')
    
    product_df['total_revenue_at_risk'] = product_df['total_revenue_at_risk'].fillna(0)
    product_df['hard_revenue_risk'] = product_df['hard_revenue_risk'].fillna(0)
    
    # DEBUG: Log revenue at risk details
    print(f"\n[DEBUG] Revenue at Risk Calculation:")
    print(f"  - Risky reviews analyzed (rating <= 3.0): {len(df[df['rating'] <= 3.0])}")
    print(f"  - Total revenue at risk: INR {product_df['total_revenue_at_risk'].sum():,.2f}")
    print(f"  - Revenue by product (top 5):")
    top_rev = product_df.nlargest(5, 'total_revenue_at_risk')[['product', 'total_revenue_at_risk']]
    for idx, row in top_rev.iterrows():
        print(f"    - {row['product']}: INR {row['total_revenue_at_risk']:,.2f}")
    
    # Backward compatibility: create alias for existing code that uses 'revenue_at_risk'
    product_df['revenue_at_risk'] = product_df['total_revenue_at_risk']
    
    # Compute PPS (Layer 3)
    product_df['PPS'] = compute_pps(product_df)
    
    # Compute Final Score (Layer 4)
    product_df['final_score'] = compute_final_score(product_df)
    
    # Sort by final score (descending)
    product_df = product_df.sort_values('final_score', ascending=False).reset_index(drop=True)
    
    print(f"\n[DEBUG] Aggregation Output:")
    print(f"  - Products: {len(product_df)}")
    print(f"  - Avg revenue at risk per product: INR {product_df['total_revenue_at_risk'].mean():,.2f}")
    
    return product_df


def classify_quadrants(product_df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify products using quadrant analysis based on 75th percentile.
    
    Quadrants:
        1. "The Fire-Fight": total_revenue_at_risk > p75 AND neg_ratio > p75 → "Immediate Fix Required"
        2. "The VIP Nudge": total_impact > p75 AND neg_ratio < p75 → "High-Value Outreach"
        3. "The Slow Burn": total_revenue_at_risk < p75 AND neg_ratio > p75 → "Product Experience Gap"
        4. "The Noise": Everything else → "Monitor / Backlog"
    
    Args:
        product_df: Product-level aggregated DataFrame
        
    Returns:
        DataFrame with 'quadrant' and 'action' columns
    """
    # Ensure total_revenue_at_risk column exists (handle backward compatibility)
    if 'total_revenue_at_risk' not in product_df.columns and 'revenue_at_risk' in product_df.columns:
        product_df['total_revenue_at_risk'] = product_df['revenue_at_risk']
    
    if 'total_revenue_at_risk' not in product_df.columns:
        product_df['total_revenue_at_risk'] = 0.0
    
    # Calculate 75th percentiles
    p75_rev = product_df['total_revenue_at_risk'].quantile(0.75)
    p75_neg = product_df['negative_ratio'].quantile(0.75)
    p75_impact = product_df['total_impact'].quantile(0.75)
    
    # Classify by quadrant
    def classify(row):
        rev_risk = row['total_revenue_at_risk']
        neg_ratio = row['negative_ratio']
        total_impact = row['total_impact']
        
        if rev_risk > p75_rev and neg_ratio > p75_neg:
            return "The Fire-Fight", "Immediate Fix Required"
        elif total_impact > p75_impact and neg_ratio < p75_neg:
            return "The VIP Nudge", "High-Value Outreach"
        elif rev_risk < p75_rev and neg_ratio > p75_neg:
            return "The Slow Burn", "Product Experience Gap"
        else:
            return "The Noise", "Monitor / Backlog"
    
    product_df[['quadrant', 'action']] = product_df.apply(
        lambda row: pd.Series(classify(row)), axis=1
    )
    
    return product_df


def summary_stats(df: pd.DataFrame, product_df: pd.DataFrame = None) -> Dict:
    """
    Generate summary statistics including Total Revenue at Risk.
    
    Args:
        df: Review-level DataFrame
        product_df: Optional product-level DataFrame
        
    Returns:
        dict with comprehensive metrics
    """
    # Revenue at Risk
    rev_risk_stats = calculate_revenue_at_risk(df)
    
    stats = {
        'total_reviews': len(df),
        'total_revenue_at_risk': rev_risk_stats['total_rev_risk'],
        'risky_reviews': rev_risk_stats['num_risky_reviews'],
        'avg_ltv_per_risky_review': rev_risk_stats['avg_ltv_per_risk'],
        'avg_rating': df['rating'].mean(),
        'repeat_customer_pct': (df['repeat'].sum() / len(df) * 100) if len(df) > 0 else 0,
        'verified_purchase_pct': (df['verified'].sum() / len(df) * 100) if len(df) > 0 else 0,
    }
    
    if product_df is not None:
        stats['total_products'] = len(product_df)
        stats['avg_final_score'] = product_df['final_score'].mean()
        stats['max_final_score'] = product_df['final_score'].max()
        stats['critical_products'] = len(product_df[product_df['quadrant'] == 'The Fire-Fight'])
        stats['vip_products'] = len(product_df[product_df['quadrant'] == 'The VIP Nudge'])
    
    return stats


def print_summary_stats(stats: Dict) -> None:
    """Pretty-print summary statistics."""
    print("\n" + "="*60)
    print("📊 SCORING ENGINE SUMMARY STATISTICS")
    print("="*60)
    print(f"\n📈 Review-Level Metrics:")
    print(f"   • Total Reviews: {stats['total_reviews']:,}")
    print(f"   • Average Rating: {stats['avg_rating']:.2f}/5.0")
    print(f"   • Repeat Customers: {stats['repeat_customer_pct']:.1f}%")
    print(f"   • Verified Purchases: {stats['verified_purchase_pct']:.1f}%")
    
    print(f"\n💰 Revenue at Risk:")
    print(f"   • Total Revenue at Risk: ${stats['total_revenue_at_risk']:,.2f}")
    print(f"   • Risky Reviews (rating ≤ 2.5): {stats['risky_reviews']:,}")
    if stats['risky_reviews'] > 0:
        print(f"   • Average LTV per Risky Review: ${stats['avg_ltv_per_risky_review']:,.2f}")
    
    if 'total_products' in stats:
        print(f"\n🎯 Product-Level Metrics:")
        print(f"   • Total Products: {stats['total_products']}")
        print(f"   • Average Final Score: {stats['avg_final_score']:.3f}")
        print(f"   • Max Final Score: {stats['max_final_score']:.3f}")
        print(f"   • 🔴 Critical (Fire-Fight): {stats['critical_products']}")
        print(f"   • 🟠 VIP Nudge: {stats['vip_products']}")
    
    print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    print("Scoring Engine module loaded successfully ✅")
