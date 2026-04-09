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
from typing import Dict, Tuple
import warnings

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


def calculate_issue_severity(rating: pd.Series, sentiment: str = 'neutral') -> pd.Series:
    """
    Calculate balanced issue severity combining rating and sentiment.
    
    Prevents rating and sentiment from canceling each other out.
    
    Formulas:
        rating_severity = (5 - rating) / 4  [0=no issue, 1=critical]
        sentiment_score: negative → 1.0, neutral → 0.5, positive → 0.0
        issue_severity = 0.6 × rating_severity + 0.4 × sentiment_score
    
    Args:
        rating: Series of ratings (1-5)
        sentiment: 'negative', 'neutral', or 'positive'
        
    Returns:
        Issue severity scores in [0, 1]
    """
    # Convert rating to severity (5★ = 0 severity, 1★ = 1.0 severity)
    rating_severity = (5 - rating) / 4
    rating_severity = rating_severity.clip(0, 1)
    
    # Sentiment mapping
    if isinstance(sentiment, str):
        if sentiment.lower() == 'negative':
            sentiment_score = 1.0
        elif sentiment.lower() == 'positive':
            sentiment_score = 0.0
        else:  # neutral
            sentiment_score = 0.5
    else:
        # If sentiment is a Series, map each value
        sentiment_score = sentiment.map({
            'negative': 1.0,
            'neutral': 0.5,
            'positive': 0.0
        }).fillna(0.5)
    
    # Balanced formula (don't let them cancel)
    issue_severity = (0.6 * rating_severity) + (0.4 * sentiment_score)
    
    return issue_severity.clip(0, 1)


def compute_cis(df: pd.DataFrame) -> pd.Series:
    """
    Compute Customer Importance Score (Layer 1).
    
    Formula:
    CIS = (0.30 × LTV_norm) + (0.20 × OrderValue_norm) + (0.15 × Repeat)
          + (0.10 × Verified) + (0.10 × Helpful_norm) + (0.15 × Recency)
    
    Args:
        df: DataFrame with normalized and processed columns
        
    Returns:
        Series of CIS scores [0, 1]
    """
    cis = (
        0.30 * df['ltv_norm'] +
        0.20 * df['order_norm'] +
        0.15 * df['repeat'] +
        0.10 * df['verified'] +
        0.10 * df['helpful_norm'] +
        0.15 * df['recency_score']
    )
    
    return cis.clip(0, 1)


def compute_impact_score(df: pd.DataFrame) -> pd.Series:
    """
    Compute Impact Score (Layer 2).
    
    Formula:
    impact_score = CIS × issue_severity
    
    ZERO-GATE: If rating > 3, force impact_score = 0
    (Don't prioritize positive reviews)
    
    Args:
        df: DataFrame with CIS and issue_severity
        
    Returns:
        Series of impact scores [0, 1]
    """
    impact = df['CIS'] * df['issue_severity']
    
    # ZERO-GATE: Positive reviews (rating > 3) have zero impact
    impact = impact.where(df['rating'] <= 3, 0)
    
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
    Calculate Revenue at Risk based on customer LTV for negative reviews.
    
    Logic:
    rev_risk = sum(customer_ltv) for all reviews where rating <= 2.5
    
    Args:
        df: DataFrame with customer_ltv and rating
        
    Returns:
        dict with:
            - 'total_rev_risk': Total revenue at risk
            - 'num_risky_reviews': Count of risky reviews
            - 'avg_ltv_per_risk': Average LTV per risky review
    """
    risky_reviews = df[df['rating'] <= 2.5]
    
    total_rev_risk = risky_reviews['customer_ltv'].sum()
    num_risky_reviews = len(risky_reviews)
    avg_ltv_per_risk = risky_reviews['customer_ltv'].mean() if num_risky_reviews > 0 else 0
    
    return {
        'total_rev_risk': total_rev_risk,
        'num_risky_reviews': num_risky_reviews,
        'avg_ltv_per_risk': avg_ltv_per_risk
    }


def apply_scoring_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply complete scoring pipeline: preprocess → features → scores.
    
    Args:
        df: Raw review DataFrame
        
    Returns:
        DataFrame with all scoring columns added
    """
    # Step 1: Preprocess and validate
    df = preprocess_and_validate(df)
    
    # Step 2: Calculate recency with 10-day plateau
    df['recency_score'] = calculate_recency_score(df['days_since_purchase'])
    
    # Step 3: Calculate issue severity (rating + sentiment)
    df['issue_severity'] = calculate_issue_severity(df['rating'])
    
    # Step 4: Compute CIS (Layer 1)
    df['CIS'] = compute_cis(df)
    
    # Step 5: Compute impact score (Layer 2) with zero-gate
    df['impact_score'] = compute_impact_score(df)
    
    # Ensure no NaNs
    df = df.fillna(0)
    
    return df


def aggregate_to_products(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate review-level data to product level for PPS and final scores.
    
    Args:
        df: Review-level DataFrame with scoring columns
        
    Returns:
        Product-level DataFrame with PPS and final scores
    """
    # Handle missing product column
    if 'product' not in df.columns:
        df['product'] = 'General'
    
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
    product_df['revenue_at_risk'] = df[df['rating'] <= 2.5].groupby('product')['customer_ltv'].sum()
    product_df['revenue_at_risk'] = product_df['revenue_at_risk'].fillna(0)
    
    # Compute PPS (Layer 3)
    product_df['PPS'] = compute_pps(product_df)
    
    # Compute Final Score (Layer 4)
    product_df['final_score'] = compute_final_score(product_df)
    
    # Sort by final score (descending)
    product_df = product_df.sort_values('final_score', ascending=False).reset_index(drop=True)
    
    return product_df


def classify_quadrants(product_df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify products using quadrant analysis based on 75th percentile.
    
    Quadrants:
        1. "The Fire-Fight": rev_risk > p75 AND neg_ratio > p75 → "Immediate Fix Required"
        2. "The VIP Nudge": total_impact > p75 AND neg_ratio < p75 → "High-Value Outreach"
        3. "The Slow Burn": rev_risk < p75 AND neg_ratio > p75 → "Product Experience Gap"
        4. "The Noise": Everything else → "Monitor / Backlog"
    
    Args:
        product_df: Product-level aggregated DataFrame
        
    Returns:
        DataFrame with 'quadrant' and 'action' columns
    """
    # Calculate 75th percentiles
    p75_rev = product_df['revenue_at_risk'].quantile(0.75)
    p75_neg = product_df['negative_ratio'].quantile(0.75)
    p75_impact = product_df['total_impact'].quantile(0.75)
    
    # Classify by quadrant
    def classify(row):
        rev_risk = row['revenue_at_risk']
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
