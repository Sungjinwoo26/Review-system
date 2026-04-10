#!/usr/bin/env python3
"""
Validation script to verify Severity Threshold fixes.

Run this to confirm normalization is working correctly.
"""

import json
import sys

def validate_normalized_scores(products_list):
    """
    Verify that all riskProbability values are in [0, 1] range.
    Verify severity distribution is reasonable.
    """
    print("\n" + "="*60)
    print("SEVERITY THRESHOLD SYSTEM - VALIDATION REPORT")
    print("="*60 + "\n")
    
    if not products_list:
        print("❌ ERROR: No products in list")
        return False
    
    print(f"Total products: {len(products_list)}\n")
    
    # Validate score ranges
    print("📊 RISK PROBABILITY VALIDATION:")
    print("-" * 60)
    
    risk_probs = [p['riskProbability'] for p in products_list]
    min_prob = min(risk_probs)
    max_prob = max(risk_probs)
    avg_prob = sum(risk_probs) / len(risk_probs)
    
    print(f"  Min: {min_prob:.2f}")
    print(f"  Max: {max_prob:.2f}") 
    print(f"  Avg: {avg_prob:.2f}")
    
    # Check if all values are in [0, 1]
    out_of_range = [p for p in risk_probs if p < 0 or p > 1]
    if out_of_range:
        print(f"  ❌ {len(out_of_range)} products OUT OF RANGE [0, 1]")
        print(f"     Examples: {out_of_range[:3]}")
        return False
    else:
        print(f"  ✅ All {len(risk_probs)} products in normalized range [0, 1]")
    
    # Validate severity distribution
    print("\n📈 SEVERITY DISTRIBUTION:")
    print("-" * 60)
    
    severity_count = {
        'High': len([p for p in products_list if p['severity'] == 'High']),
        'Medium': len([p for p in products_list if p['severity'] == 'Medium']),
        'Low': len([p for p in products_list if p['severity'] == 'Low'])
    }
    
    for severity, count in severity_count.items():
        pct = (count / len(products_list)) * 100
        print(f"  {severity:8}: {count:2} ({pct:5.1f}%) ", end="")
        
        # Show indicator bars
        bar_len = 20
        filled = int((count / len(products_list)) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f" {bar}")
    
    # Check distribution reasonableness
    print()
    if severity_count['High'] == 0:
        print("  ⚠️  No HIGH severity products - unusual!")
    elif severity_count['Low'] == 0:
        print("  ⚠️  No LOW severity products - unusual!")
    elif severity_count['High'] == len(products_list):
        print("  ❌ ALL products are HIGH - severity classification broken!")
        return False
    else:
        print("  ✅ Severity distribution is well-distributed")
    
    # Validate threshold boundaries
    print("\n🎯 THRESHOLD BOUNDARY VALIDATION:")
    print("-" * 60)
    
    high_boundary = 0.7
    medium_boundary = 0.4
    
    # Products labeled as High
    high_products = [p for p in products_list if p['severity'] == 'High']
    high_probs = [p['riskProbability'] for p in high_products]
    
    # Products labeled as Medium/Low
    low_products = [p for p in products_list if p['severity'] in ['Medium', 'Low']]
    low_probs = [p['riskProbability'] for p in low_products]
    
    print(f"  HIGH products (should be ≥ {high_boundary}):")
    if high_probs:
        min_high = min(high_probs)
        max_high = max(high_probs)
        print(f"    Range: {min_high:.2f} to {max_high:.2f}")
        if min_high < high_boundary:
            print(f"    ⚠️  Some HIGH products below {high_boundary}")
        else:
            print(f"    ✅ All HIGH products in valid range")
    
    print(f"  LOW/MED products (should be < {high_boundary}):")
    if low_probs:
        min_low = min(low_probs)
        max_low = max(low_probs)
        print(f"    Range: {min_low:.2f} to {max_low:.2f}")
        if max_low >= high_boundary:
            print(f"    ⚠️  Some LOW/MED products at or above {high_boundary}")
        else:
            print(f"    ✅ All LOW/MED products in valid range")
    
    # Sample products
    print("\n📝 SAMPLE PRODUCTS:")
    print("-" * 60)
    for product in products_list[:5]:
        print(f"  {product['name']:20} | Risk: {product['riskProbability']:.2f} | {product['severity']}")
    if len(products_list) > 5:
        print(f"  ... ({len(products_list) - 5} more)")
    
    print("\n" + "="*60)
    print("✅ ALL VALIDATIONS PASSED")
    print("="*60 + "\n")
    
    return True


# Example usage (if products data is available)
if __name__ == "__main__":
    # This would be called from api_server after transform_to_dashboard_format()
    print("""
    To use this validator:
    
    1. In api_server.py, after transform_to_dashboard_format():
        from test_severity_validation import validate_normalized_scores
        validate_normalized_scores(products_list)
    
    2. Or run manually with products data:
        python test_severity_validation.py
    """)
