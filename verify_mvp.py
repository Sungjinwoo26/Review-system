#!/usr/bin/env python3
"""
MVP Verification Script
Verifies that all components are working correctly
Run with: python verify_mvp.py
"""

import sys
import traceback

def run_verification():
    """Run complete MVP verification"""
    
    print("🧪 Running MVP Verification...\n")
    
    try:
        # Step 1: Test data fetch
        print("1️⃣ Testing data fetch...")
        from services.ingestion import fetch_reviews
        raw = fetch_reviews(max_pages=1)
        assert len(raw) > 0, "No data fetched"
        assert 'rating' in raw.columns, "Missing 'rating' column"
        assert 'customer_ltv' in raw.columns, "Missing 'customer_ltv' column"
        print(f"✅ Fetched {len(raw)} reviews\n")
        
        # Step 2: Test preprocessing
        print("2️⃣ Testing preprocessing...")
        from services.preprocessing import preprocess_data
        processed = preprocess_data(raw)
        assert 'ltv_norm' in processed.columns, "Normalization missing"
        assert 'order_norm' in processed.columns, "Order normalization missing"
        assert 'helpful_norm' in processed.columns, "Helpful normalization missing"
        assert 'repeat' in processed.columns, "Repeat encoding missing"
        assert 'verified' in processed.columns, "Verified encoding missing"
        assert not processed[['ltv_norm', 'order_norm', 'helpful_norm', 'repeat', 'verified']].isnull().any().any(), "NaN values found"
        print("✅ Preprocessing passed\n")
        
        # Step 3: Test feature engineering
        print("3️⃣ Testing feature engineering...")
        from services.features import engineer_features
        featured = engineer_features(processed)
        assert 'severity_rating' in featured.columns, "Severity missing"
        assert 'recency' in featured.columns, "Recency missing"
        assert 'sentiment_score' in featured.columns, "Sentiment missing"
        assert 'is_negative' in featured.columns, "Negative flag missing"
        assert (featured['severity_rating'] >= 0).all() and (featured['severity_rating'] <= 1).all(), "Severity out of range"
        assert (featured['recency'] >= 0).all() and (featured['recency'] <= 1).all(), "Recency out of range"
        assert not featured[['severity_rating', 'recency', 'sentiment_score', 'is_negative']].isnull().any().any(), "NaN values found"
        print("✅ Feature engineering passed\n")
        
        # Step 4: Test scoring
        print("4️⃣ Testing scoring...")
        from services.scoring import compute_scores
        scored = compute_scores(featured)
        assert 'CIS' in scored.columns, "CIS missing"
        assert 'severity' in scored.columns, "Severity missing"
        assert 'impact_score' in scored.columns, "Impact score missing"
        assert (scored['CIS'] >= 0).all() and (scored['CIS'] <= 1).all(), "CIS out of range"
        assert (scored['impact_score'] >= 0).all() and (scored['impact_score'] <= 1).all(), "Impact score out of range"
        assert not scored[['CIS', 'severity', 'impact_score']].isnull().any().any(), "NaN values found"
        print("✅ Scoring passed\n")
        
        # Step 5: Test aggregation
        print("5️⃣ Testing aggregation...")
        from services.aggregation import aggregate_product_metrics
        products = aggregate_product_metrics(scored)
        assert len(products) > 0, "No products aggregated"
        assert 'product' in products.columns, "Product column missing"
        assert 'PPS' in products.columns, "PPS missing"
        assert 'final_score' in products.columns, "Final score missing"
        assert 'total_revenue_at_risk' in products.columns, "Revenue at risk missing"
        print(f"✅ Aggregated {len(products)} products\n")
        
        # Step 6: Test decision making
        print("6️⃣ Testing decision making...")
        from services.decision import make_decisions
        decisions = make_decisions(products)
        assert 'action' in decisions.columns, "Action column missing"
        assert 'priority' in decisions.columns, "Priority column missing"
        assert decisions['action'].notna().all(), "Missing actions found"
        assert decisions['priority'].notna().all(), "Missing priorities found"
        assert set(decisions['priority'].unique()).issubset({'High', 'Medium', 'Low'}), "Invalid priority values"
        print("✅ Decision making passed\n")
        
        # Final summary
        print("=" * 50)
        print("✅✅✅ MVP VERIFICATION PASSED ✅✅✅")
        print("=" * 50)
        print(f"\n📊 Pipeline Summary:")
        print(f"   • Reviews processed: {len(scored)}")
        print(f"   • Products analyzed: {len(decisions)}")
        print(f"   • Critical items: {(decisions['priority'] == 'High').sum()}")
        print(f"   • Medium priority: {(decisions['priority'] == 'Medium').sum()}")
        print(f"   • Low priority: {(decisions['priority'] == 'Low').sum()}")
        print(f"\n✨ All systems ready for deployment!")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ ASSERTION FAILED: {str(e)}\n")
        traceback.print_exc()
        return False
    except ImportError as e:
        print(f"\n❌ IMPORT ERROR: {str(e)}")
        print("   Make sure all service modules are installed.\n")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}\n")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)

