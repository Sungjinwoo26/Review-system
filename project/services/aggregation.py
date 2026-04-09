import pandas as pd
import numpy as np


def aggregate_product_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate review-level data into product-level insights.
    Computes product priority score, revenue at risk, and final impact score.
    
    Args:
        df: DataFrame with review-level data containing:
            - impact_score, severity, is_negative
            - customer_ltv, order_value, repeat, rating
            - product (grouping column)
    
    Returns:
        product_df: Product-level aggregated DataFrame with priority scores
    """
    
    # Create a copy to avoid modifying input
    df = df.copy()
    
    # Step 1: Create revenue at risk at review level
    df['rev_risk'] = df['customer_ltv'] * df['is_negative']
    
    # Step 2: Product-level aggregation
    product_df = df.groupby('product', as_index=False).agg({
        'impact_score': 'sum',
        'severity': 'mean',
        'is_negative': 'mean',
        'customer_ltv': 'mean',
        'order_value': 'mean',
        'repeat': 'mean',
        'rating': 'mean',
        'rev_risk': 'sum'
    })
    
    # Add total_reviews count
    product_df['total_reviews'] = product_df.groupby('product')['impact_score'].transform('count')
    product_df = df.groupby('product', as_index=False).size().rename(columns={'size': 'total_reviews'}).merge(
        df.groupby('product', as_index=False).agg({
            'impact_score': 'sum',
            'severity': 'mean',
            'is_negative': 'mean',
            'customer_ltv': 'mean',
            'order_value': 'mean',
            'repeat': 'mean',
            'rating': 'mean',
            'rev_risk': 'sum'
        }),
        on='product'
    )
    
    # Rename aggregated columns for clarity
    product_df = product_df.rename(columns={
        'impact_score': 'total_impact',
        'severity': 'avg_severity',
        'is_negative': 'negative_ratio',
        'customer_ltv': 'avg_customer_ltv',
        'order_value': 'avg_order_value',
        'repeat': 'repeat_rate',
        'rating': 'avg_rating',
        'rev_risk': 'total_revenue_at_risk'
    })
    
    # Step 3: Derive metrics
    product_df['order_freq'] = product_df['total_reviews'].astype(float)
    product_df['rating_drop'] = 5 - product_df['avg_rating']
    
    # Step 4: Normalize features using Min-Max scaling
    features_to_normalize = [
        'order_freq', 'avg_order_value', 'repeat_rate', 'rating_drop', 'negative_ratio'
    ]
    
    for feature in features_to_normalize:
        feature_data = product_df[feature]
        min_val = feature_data.min()
        max_val = feature_data.max()
        product_df[f'{feature}_norm'] = (
            (feature_data - min_val) / (max_val - min_val + 1e-9)
        ).clip(0, 1)
    
    # Step 5: Compute Product Priority Score (PPS)
    product_df['PPS'] = (
        0.25 * product_df['order_freq_norm'] +
        0.20 * product_df['avg_order_value_norm'] +
        0.20 * product_df['repeat_rate_norm'] +
        0.20 * product_df['rating_drop_norm'] +
        0.15 * product_df['negative_ratio_norm']
    ).clip(0, 1)
    
    # Step 6: Compute Final Priority Score
    product_df['final_score'] = (
        np.log1p(product_df['total_impact']) * (1 + product_df['PPS'])
    )
    
    # Step 7: Optional spike detection (if review_date available)
    if 'review_date' in df.columns:
        try:
            df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
            current_date = df['review_date'].max()
            
            if pd.notna(current_date):
                # Calculate metrics for spike detection
                recent_cutoff = current_date - pd.Timedelta(days=14)
                df['is_recent'] = df['review_date'] >= recent_cutoff
                
                spike_stats = df.groupby('product', as_index=False).apply(
                    lambda x: pd.Series({
                        'recent_14': x['is_recent'].sum(),
                        'total_reviews_30': len(x)
                    })
                )
                
                # Compute spike score
                spike_stats['avg_30'] = spike_stats['total_reviews_30'] / 1  # Simplified
                spike_stats['spike_score'] = (
                    (spike_stats['recent_14'] - spike_stats['avg_30'] / 2.14) / 
                    (spike_stats['avg_30'] / 4.3 + 1e-9)
                )
                
                # Merge spike data
                product_df = product_df.merge(
                    spike_stats[['product', 'spike_score']], 
                    on='product', 
                    how='left'
                )
                product_df['spike_score'] = product_df['spike_score'].fillna(0)
                
                # Apply spike multiplier
                product_df['final_score'] = product_df.apply(
                    lambda row: row['final_score'] * 1.5 
                    if row['spike_score'] > 2 else row['final_score'],
                    axis=1
                )
        except Exception:
            pass  # Spike detection is optional
    
    # Step 8: Select final output columns
    final_columns = [
        'product',
        'total_reviews',
        'avg_order_value',
        'avg_rating',
        'negative_ratio',
        'repeat_rate',
        'total_impact',
        'PPS',
        'total_revenue_at_risk',
        'final_score'
    ]
    
    # Ensure no NaNs and return
    product_df = product_df.fillna(0)
    
    return product_df[final_columns]
