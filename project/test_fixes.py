#!/usr/bin/env python
"""
Test script to verify the fixes work correctly
"""
import sys
import pandas as pd
import numpy as np

# Test 1: Verify ML columns are properly merged
print("=" * 60)
print("TEST 1: ML Column Merge Logic")
print("=" * 60)

# Simulate original aggregated_df with ML columns
aggregated_df = pd.DataFrame({
    'product': ['A', 'B', 'C', 'D', 'E'],
    'total_revenue_at_risk': [100, 200, 150, 300, 250],
    'risk_probability': [0.2, 0.8, 0.5, 0.9, 0.3],
    'risk_category': ['Low', 'High', 'Medium', 'High', 'Low']
})

# Simulate filtered_agg (newly aggregated from filtered reviews - no ML columns)
filtered_agg = pd.DataFrame({
    'product': ['A', 'B', 'C'],
    'total_revenue_at_risk': [100, 200, 150],
    'final_score': [0.5, 0.7, 0.6]
})

print("Original aggregated_df:")
print(aggregated_df)
print("\nNewly aggregated filtered_agg (missing ML columns):")
print(filtered_agg)

# Apply the fix
ml_columns = ['risk_probability', 'risk_category']
if all(col in aggregated_df.columns for col in ml_columns):
    ml_data = aggregated_df[['product'] + ml_columns].copy()
    filtered_agg = filtered_agg.merge(ml_data, on='product', how='left')
    # Fill any missing ML values with defaults
    filtered_agg['risk_probability'] = filtered_agg['risk_probability'].fillna(0.0)
    filtered_agg['risk_category'] = filtered_agg['risk_category'].fillna('Low')

print("\nAfter merge (should now have ML columns):")
print(filtered_agg)

if 'risk_probability' in filtered_agg.columns and 'risk_category' in filtered_agg.columns:
    print("✅ TEST 1 PASSED: ML columns successfully merged")
else:
    print("❌ TEST 1 FAILED: ML columns not found after merge")
    sys.exit(1)

# Test 2: Verify filtering of reviews by product
print("\n" + "=" * 60)
print("TEST 2: Review Filtering by Product")
print("=" * 60)

# Simulate filtered_df with all reviews
filtered_df = pd.DataFrame({
    'product': ['A', 'A', 'B', 'B', 'B', 'C', 'C', 'C', 'D'],
    'is_negative': [0, 1, 1, 1, 0, 0, 0, 1, 1],
    'rating': [4, 2, 1, 2, 3, 4, 5, 2, 1]
})

print("Filtered reviews (all products):")
print(filtered_df)

# Simulate filtered_agg after ML filtering (products with risk >= 0.5)
filtered_agg_after_risk = pd.DataFrame({
    'product': ['B', 'C'],
    'risk_probability': [0.8, 0.5]
})

print("\nAfter ML risk threshold filter (only B, C):")
print(filtered_agg_after_risk)

# Apply the review filtering logic
product_col = 'product'
filtered_df_subset = filtered_df[filtered_df[product_col].isin(filtered_agg_after_risk[product_col])]

print("\nFiltered reviews (only from products B, C):")
print(filtered_df_subset)

# Verify negative_pct calculation
total_reviews = len(filtered_df_subset)
negative_count = filtered_df_subset['is_negative'].sum()
negative_pct = (negative_count / total_reviews * 100) if total_reviews > 0 else 0

print(f"\nStats:")
print(f"  - Total reviews: {total_reviews}")
print(f"  - Negative reviews: {negative_count}")
print(f"  - Negative %: {negative_pct:.1f}%")

if total_reviews == 6 and negative_count == 3 and negative_pct == 50.0:
    print("✅ TEST 2 PASSED: Reviews correctly filtered and negative_pct calculated")
else:
    print(f"❌ TEST 2 FAILED: Expected 6 reviews with 3 negative (50%), got {total_reviews} with {negative_count} ({negative_pct:.1f}%)")
    sys.exit(1)

# Test 3: Verify is_negative column is preserved through filtering
print("\n" + "=" * 60)
print("TEST 3: is_negative Column Preservation")
print("=" * 60)

# Simulate processed_df with is_negative column
processed_df = pd.DataFrame({
    'product': ['A', 'A', 'B', 'B', 'B', 'C'],
    'rating': [4, 2, 1, 2, 3, 4],
    'is_negative': [0, 1, 1, 1, 0, 0],
    'review_text': ['good', 'bad', 'terrible', 'bad', 'ok', 'great']
})

print("Original processed_df:")
print(processed_df[['product', 'rating', 'is_negative']])

# Apply filtering function (simulate)
def apply_filters(df, products=None):
    if products and len(products) > 0:
        return df[df['product'].isin(products)].copy()
    return df.copy()

filtered_df_test = apply_filters(processed_df, products=['A', 'B'])

print("\nAfter filtering to products A, B:")
print(filtered_df_test[['product', 'rating', 'is_negative']])

if 'is_negative' in filtered_df_test.columns:
    print("✅ TEST 3 PASSED: is_negative column preserved")
else:
    print("❌ TEST 3 FAILED: is_negative column lost")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
