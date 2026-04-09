"""Decision service."""
import pandas as pd
import numpy as np


def make_decisions(product_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert product-level metrics into actionable business decisions.
    
    Assigns action categories and priority levels based on business impact metrics.
    
    Args:
        product_df: DataFrame with columns: product, total_reviews, negative_ratio,
                   avg_rating, total_impact, PPS, total_revenue_at_risk, final_score
    
    Returns:
        DataFrame with added columns: action, priority
    """
    
    df = product_df.copy()
    
    # 1. DEFINE DYNAMIC THRESHOLDS
    high_rev_threshold = df['total_revenue_at_risk'].quantile(0.75)
    high_impact_threshold = df['total_impact'].quantile(0.75)
    high_neg_threshold = df['negative_ratio'].quantile(0.75)
    low_rating_threshold = df['avg_rating'].quantile(0.25)
    high_score_threshold = df['final_score'].quantile(0.75)
    
    # 2. DEFINE HELPER FUNCTION FOR PRIORITY ASSIGNMENT
    def assign_priority(score):
        """Assign priority level based on final_score."""
        if score >= high_score_threshold:
            return "High"
        elif score >= high_score_threshold * 0.5:
            return "Medium"
        else:
            return "Low"
    
    # 3. DEFINE DECISION LOGIC (PRIORITY ORDER MATTERS)
    def assign_decision(row):
        """Assign action based on business conditions."""
        
        # Rule 1: Immediate Fix Required (Critical)
        if (row['total_revenue_at_risk'] >= high_rev_threshold and 
            row['negative_ratio'] >= high_neg_threshold):
            return "Immediate Fix Required"
        
        # Rule 2: Investigate Root Cause (High Impact)
        if row['total_impact'] >= high_impact_threshold:
            return "Investigate Root Cause"
        
        # Rule 3: Improve Product Experience (Low Rating)
        if row['avg_rating'] <= low_rating_threshold:
            return "Improve Product Experience"
        
        # Rule 4: Respond to Customers (High Negative Ratio)
        if row['negative_ratio'] > 0.3:
            return "Respond to Customers"
        
        # Rule 5: Monitor (Default)
        return "Monitor"
    
    # 4. APPLY DECISIONS TO DATAFRAME
    df['action'] = df.apply(assign_decision, axis=1)
    df['priority'] = df['final_score'].apply(assign_priority)
    
    # 5. SORT BY FINAL SCORE (HIGHEST FIRST)
    df = df.sort_values(by='final_score', ascending=False).reset_index(drop=True)
    
    # 6. VALIDATION
    # Ensure no missing values
    assert df['action'].isna().sum() == 0, "Missing values in 'action' column"
    assert df['priority'].isna().sum() == 0, "Missing values in 'priority' column"
    
    # Ensure every product has a decision
    assert len(df) == len(product_df), "Number of products changed"
    
    return df
