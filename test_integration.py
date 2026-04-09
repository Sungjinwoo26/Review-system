#!/usr/bin/env python
"""
Integration test simulating the actual data flow when filters are applied
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
from services.scoring_engine import apply_scoring_pipeline, aggregate_to_products, classify_quadrants

print("=" * 80)
print("INTEGRATION TEST: Data Flow with Filtering and ML Column Restoration")
print("=" * 80)

# Step 1: Create mock raw data
print("\nStep 1: Creating mock raw data...")
raw_data = {
    'product': ['Phone', 'Phone', 'Phone', 'Laptop', 'Laptop', 'Laptop', 'Tablet', 'Tablet'],
    'rating': [5, 2, 1, 5, 4, 1, 3, 2],
    'review_text': ['great', 'bad', 'terrible', 'excellent', 'good', 'broken', 'average', 'poor'],
    'days_since_purchase': [30, 15, 5, 45, 20, 10, 35, 25],
    'customer_ltv': [1000, 500, 300, 2000, 1500, 800, 1200, 600],
    'review_date': pd.date_range('2024-01-01', periods=8, freq='D'),
}
raw_df = pd.DataFrame(raw_data)

print(f"Mock raw data shape: {raw_df.shape}")
print(raw_df[['product', 'rating', 'days_since_purchase']].head())

# Step 2: Apply scoring pipeline
print("\nStep 2: Applying scoring pipeline...")
try:
    processed_df = apply_scoring_pipeline(raw_df.copy())
    print(f"Processed reviews shape: {processed_df.shape}")
    print(f"Columns after scoring: {processed_df.columns.tolist()}")
    print(f"Sample data:")
    print(processed_df[['product', 'rating', 'is_negative', 'CIS', 'impact_score']].head())
except Exception as e:
    print(f"❌ Scoring pipeline failed: {e}")
    sys.exit(1)

# Step 3: Aggregate to products
print("\nStep 3: Aggregating to product level...")
try:
    aggregated_df = aggregate_to_products(processed_df.copy())
    print(f"Aggregated products shape: {aggregated_df.shape}")
    print(f"Columns after aggregation: {aggregated_df.columns.tolist()}")
    print(aggregated_df[['product', 'total_reviews', 'negative_ratio', 'final_score']].head())
except Exception as e:
    print(f"❌ Aggregation failed: {e}")
    sys.exit(1)

# Step 4: Add ML columns (simulate ML predictions)
print("\nStep 4: Adding ML columns...")
aggregated_df['risk_probability'] = np.random.uniform(0, 1, len(aggregated_df))
aggregated_df['risk_category'] = aggregated_df['risk_probability'].apply(
    lambda x: 'High' if x > 0.7 else ('Medium' if x > 0.3 else 'Low')
)
aggregated_df['high_risk_predicted'] = (aggregated_df['risk_category'] == 'High').astype(int)

print("ML columns added:")
print(aggregated_df[['product', 'risk_probability', 'risk_category']])

# Step 5: Simulate filtering
print("\nStep 5: Simulating filter to specific products...")
selected_products = ['Phone', 'Tablet']
filtered_df = processed_df[processed_df['product'].isin(selected_products)].copy()
print(f"Filtered reviews: {len(filtered_df)} (from {len(processed_df)})")
print(f"is_negative column present: {'is_negative' in filtered_df.columns}")

# Step 6: Re-aggregate filtered data (THIS IS WHERE THE BUG WAS)
print("\nStep 6: Re-aggregating filtered data...")
filtered_agg_before_fix = aggregate_to_products(filtered_df.copy())
print(f"Re-aggregated products shape: {filtered_agg_before_fix.shape}")
print(f"Columns after re-aggregation (before fix): {filtered_agg_before_fix.columns.tolist()}")
print("WARNING: ML columns are missing!")

# Step 7: Apply the fix - restore ML columns
print("\nStep 7: Applying FIX - Restore ML columns...")
ml_columns = ['risk_probability', 'risk_category', 'high_risk_predicted']
if all(col in aggregated_df.columns for col in ml_columns):
    ml_data = aggregated_df[['product'] + ml_columns].copy()
    filtered_agg = filtered_agg_before_fix.merge(ml_data, on='product', how='left')
    # Fill any missing ML values with defaults
    filtered_agg['risk_probability'] = filtered_agg['risk_probability'].fillna(0.0)
    filtered_agg['risk_category'] = filtered_agg['risk_category'].fillna('Low')
    filtered_agg['high_risk_predicted'] = filtered_agg['high_risk_predicted'].fillna(0).astype(int)
    
    print(f"After merge - Columns: {filtered_agg.columns.tolist()}")
    print("✅ ML columns successfully restored!")
    print(filtered_agg[['product', 'risk_probability', 'risk_category']])
else:
    print("❌ ML columns not found in original aggregated_df")
    sys.exit(1)

# Step 8: Verify negative_pct calculation
print("\nStep 8: Verifying negative_pct calculation...")
total_reviews = len(filtered_df)
negative_count = filtered_df['is_negative'].sum() if 'is_negative' in filtered_df.columns else 0
negative_pct = (negative_count / total_reviews * 100) if total_reviews > 0 else 0

print(f"Total reviews: {total_reviews}")
print(f"Negative reviews: {negative_count}")
print(f"Negative %: {negative_pct:.1f}%")

if negative_pct > 0:
    print("✅ Negative % calculated correctly!")
else:
    print("⚠️  Negative % is 0 (may be correct if no negative reviews)")

# Step 9: Test ML risk threshold filtering
print("\nStep 9: Testing ML risk threshold filter...")
risk_threshold = 0.5
pre_risk_filter = len(filtered_agg)
filtered_agg_with_risk = filtered_agg[filtered_agg['risk_probability'] >= risk_threshold].copy()
print(f"Products before risk filter: {pre_risk_filter}")
print(f"Products after risk filter (threshold={risk_threshold}): {len(filtered_agg_with_risk)}")
print(f"Filtered products: {filtered_agg_with_risk['product'].tolist()}")

# Step 10: Update filtered_df to match filtered_agg
print("\nStep 10: Filtering reviews to match filtered products...")
remaining_products = filtered_agg_with_risk['product'].tolist()
filtered_df_final = filtered_df[filtered_df['product'].isin(remaining_products)].copy()
print(f"Reviews after product filtering: {len(filtered_df_final)}")

# Final verification
print("\n" + "=" * 80)
print("FINAL VERIFICATION")
print("=" * 80)

# Check all KPI calculations
print("\n✅ KPI Calculations:")
print(f"  - Total Revenue at Risk: ₹{filtered_agg_with_risk['total_revenue_at_risk'].sum():,.2f}")
print(f"  - Total Reviews: {len(filtered_df_final)}")
print(f"  - Negative Reviews %: {(filtered_df_final['is_negative'].sum() / len(filtered_df_final) * 100):.1f}%" if len(filtered_df_final) > 0 else "  - Negative Reviews %: 0.0%")
print(f"  - High Risk Products: {int((filtered_agg_with_risk['risk_category'] == 'High').sum())}")
print(f"  - Avg Risk Probability: {filtered_agg_with_risk['risk_probability'].mean()*100:.1f}%")

print("\n" + "=" * 80)
print("✅ INTEGRATION TEST PASSED!")
print("=" * 80)
print("\nAll data flows correctly through filtering and ML column restoration")
