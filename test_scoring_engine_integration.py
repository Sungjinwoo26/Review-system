"""Quick test of the scoring engine integration."""

from services.scoring_engine import (
    apply_scoring_pipeline,
    aggregate_to_products,
    classify_quadrants,
    calculate_revenue_at_risk,
    summary_stats,
    print_summary_stats
)
import pandas as pd
import numpy as np

# Test data
print("🧪 Creating test data...")
df = pd.DataFrame({
    'rating': [1, 2, 3, 4, 5] * 20,
    'customer_ltv': [5000, 4000, 3000, 2000, 1000] * 20,
    'order_value': [500, 400, 300, 200, 100] * 20,
    'helpful_votes': [10, 8, 5, 2, 0] * 20,
    'days_since_purchase': [5, 15, 30, 60, 90] * 20,
    'is_repeat_customer': [True, False] * 50,
    'verified_purchase': [True, False] * 50,
    'product': ['A', 'B', 'C'] * 33 + ['D'],
    'review_text': ['Great product!', 'Poor quality', 'Average', 'Good!', 'Excellent!'] * 20
})

print("\n✅ Scoring reviews with engine...")
scored_df = apply_scoring_pipeline(df)
print(f"   • Scored {len(scored_df)} reviews")
print(f"   • CIS range: [{scored_df['CIS'].min():.3f}, {scored_df['CIS'].max():.3f}]")
print(f"   • Impact range: [{scored_df['impact_score'].min():.3f}, {scored_df['impact_score'].max():.3f}]")

print("\n✅ Aggregating to products...")
product_df = aggregate_to_products(scored_df)
print(f"   • Analyzed {len(product_df)} products")
print(f"   • PPS range: [{product_df['PPS'].min():.3f}, {product_df['PPS'].max():.3f}]")

print("\n✅ Classifying quadrants...")
product_df = classify_quadrants(product_df)
quadrant_counts = product_df['quadrant'].value_counts()
for quad, count in quadrant_counts.items():
    print(f"   • {quad}: {count} products")

print("\n✅ Calculating statistics...")
stats = summary_stats(scored_df, product_df)
print_summary_stats(stats)

print("\n🎉 Scoring engine integration successful!")
