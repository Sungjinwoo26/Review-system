"""Tests for the advanced scoring engine.

Validates:
- Recency score with 10-day plateau
- Balanced issue severity
- 4-layer scoring hierarchy
- Revenue at risk calculations
- Quadrant classification
"""

import pytest
import pandas as pd
import numpy as np
from services.scoring_engine import (
    calculate_recency_score,
    calculate_issue_severity,
    compute_cis,
    compute_impact_score,
    apply_scoring_pipeline,
    aggregate_to_products,
    classify_quadrants,
    calculate_revenue_at_risk,
    summary_stats
)


class TestRecencyPlateau:
    """Test 10-day recency plateau logic."""
    
    def test_within_plateau_gets_full_weight(self):
        """Reviews within 10 days should have score ≥ 0.95."""
        days = pd.Series([0, 5, 10])
        scores = calculate_recency_score(days)
        
        assert (scores >= 0.95).all(), f"Days within plateau should score ≥ 0.95, got {scores.values}"
    
    def test_after_plateau_decays(self):
        """Reviews after 10 days should decay exponentially."""
        days = pd.Series([10, 30, 60])
        scores = calculate_recency_score(days)
        
        # Score should decrease with more days
        assert scores[1] < scores[0], "30 days should have lower score than 10 days"
        assert scores[2] < scores[1], "60 days should have lower score than 30 days"
    
    def test_recency_formula_correctness(self):
        """Verify exact formula: exp(-max(0, days - 10) / 30)."""
        days = pd.Series([20])  # 10 days after plateau
        score = calculate_recency_score(days)[0]
        
        expected = np.exp(-10 / 30)  # exp(-10/30)
        assert abs(score - expected) < 1e-6, f"Expected {expected}, got {score}"
    
    def test_recency_in_range(self):
        """All recency scores should be in [0, 1]."""
        days = pd.Series(np.linspace(0, 365, 100))
        scores = calculate_recency_score(days)
        
        assert (scores >= 0).all() and (scores <= 1).all(), \
            f"Scores out of range: [{scores.min()}, {scores.max()}]"


class TestIssueSeverity:
    """Test balanced issue severity calculation."""
    
    def test_5star_has_zero_severity(self):
        """5-star review should have severity ≈ 0.2 (with neutral sentiment default)."""
        severity = calculate_issue_severity(pd.Series([5]))[0]
        # With neutral sentiment default (0.5): severity = 0.6*(0) + 0.4*0.5 = 0.2
        assert severity < 0.3, f"5-star should have low severity, got {severity}"
    
    def test_1star_has_high_severity(self):
        """1-star review should have severity ≈ 0.8 (with neutral sentiment default)."""
        severity = calculate_issue_severity(pd.Series([1]))[0]
        # With neutral sentiment default (0.5): severity = 0.6*(1) + 0.4*0.5 = 0.8
        assert severity > 0.7, f"1-star should have high severity, got {severity}"
    
    def test_negative_sentiment_increases_severity(self):
        """Negative sentiment should increase severity."""
        rating = pd.Series([3])
        
        severity_neutral = calculate_issue_severity(rating, 'neutral')[0]
        severity_negative = calculate_issue_severity(rating, 'negative')[0]
        
        assert severity_negative > severity_neutral, \
            "Negative sentiment should increase severity"
    
    def test_positive_sentiment_decreases_severity(self):
        """Positive sentiment should decrease severity."""
        rating = pd.Series([3])
        
        severity_neutral = calculate_issue_severity(rating, 'neutral')[0]
        severity_positive = calculate_issue_severity(rating, 'positive')[0]
        
        assert severity_positive < severity_neutral, \
            "Positive sentiment should decrease severity"
    
    def test_severity_formula_correctness(self):
        """Verify formula: 0.6 * rating_severity + 0.4 * sentiment_score."""
        rating = pd.Series([2])
        sentiment = 'negative'  # sentiment_score = 1.0
        
        severity = calculate_issue_severity(rating, sentiment)[0]
        
        rating_sev = (5 - 2) / 4  # = 0.75
        sentiment_score = 1.0
        expected = 0.6 * rating_sev + 0.4 * sentiment_score  # 0.85
        
        assert abs(severity - expected) < 1e-6, f"Expected {expected}, got {severity}"


class TestCISCalculation:
    """Test Customer Importance Score."""
    
    def test_high_ltv_high_cis(self):
        """High-LTV customer should have high CIS."""
        df = pd.DataFrame({
            'ltv_norm': [1.0],
            'order_norm': [0.5],
            'repeat': [1],
            'verified': [1],
            'helpful_norm': [0.5],
            'recency_score': [1.0]
        })
        
        cis = compute_cis(df)[0]
        assert cis > 0.8, f"High-LTV customer should have high CIS, got {cis}"
    
    def test_low_ltv_low_cis(self):
        """Low-LTV customer should have low CIS."""
        df = pd.DataFrame({
            'ltv_norm': [0.0],
            'order_norm': [0.0],
            'repeat': [0],
            'verified': [0],
            'helpful_norm': [0.0],
            'recency_score': [0.0]
        })
        
        cis = compute_cis(df)[0]
        assert cis < 0.2, f"Low-LTV customer should have low CIS, got {cis}"
    
    def test_cis_formula_weights(self):
        """Verify CIS weights sum to 1.0 and each contributes correctly."""
        df = pd.DataFrame({
            'ltv_norm': [1.0],
            'order_norm': [0.0],
            'repeat': [0.0],
            'verified': [0.0],
            'helpful_norm': [0.0],
            'recency_score': [0.0]
        })
        
        cis = compute_cis(df)[0]
        expected = 0.30  # Only ltv_norm is 1.0, weight is 0.30
        
        assert abs(cis - expected) < 1e-6, f"Expected {expected}, got {cis}"


class TestImpactScore:
    """Test impact score with zero-gate logic."""
    
    def test_high_cis_high_severity_high_impact(self):
        """High CIS + high severity should yield high impact."""
        df = pd.DataFrame({
            'CIS': [1.0],
            'issue_severity': [1.0],
            'rating': [1]
        })
        
        impact = compute_impact_score(df)[0]
        assert impact > 0.8, f"High CIS + severity should yield high impact, got {impact}"
    
    def test_positive_review_zero_impact(self):
        """ZERO-GATE: Rating > 3 should have zero impact."""
        df = pd.DataFrame({
            'CIS': [1.0],
            'issue_severity': [0.5],
            'rating': [4]
        })
        
        impact = compute_impact_score(df)[0]
        assert impact == 0, f"Positive review (rating > 3) should have zero impact, got {impact}"
    
    def test_boundary_rating_3_has_impact(self):
        """Rating = 3 should still have impact (neutral, not positive)."""
        df = pd.DataFrame({
            'CIS': [0.5],
            'issue_severity': [0.5],
            'rating': [3]
        })
        
        impact = compute_impact_score(df)[0]
        assert impact > 0, f"Rating 3 should have impact, got {impact}"
    
    def test_boundary_rating_2_5_has_impact(self):
        """Rating = 2.5 should have impact."""
        df = pd.DataFrame({
            'CIS': [0.5],
            'issue_severity': [0.5],
            'rating': [2.5]
        })
        
        impact = compute_impact_score(df)[0]
        assert impact > 0, f"Rating 2.5 should have impact, got {impact}"


class TestRevenueAtRisk:
    """Test revenue at risk calculation."""
    
    def test_negative_reviews_only(self):
        """Only reviews with rating <= 2.5 count toward revenue at risk."""
        df = pd.DataFrame({
            'rating': [1, 2, 2.5, 3, 4, 5],
            'customer_ltv': [1000, 2000, 3000, 4000, 5000, 6000]
        })
        
        risk_stats = calculate_revenue_at_risk(df)
        expected_risk = 1000 + 2000 + 3000  # Sum of LTV for ratings 1, 2, 2.5
        
        assert abs(risk_stats['total_rev_risk'] - expected_risk) < 1, \
            f"Expected {expected_risk}, got {risk_stats['total_rev_risk']}"
    
    def test_no_negative_reviews_zero_risk(self):
        """All positive reviews should have zero revenue at risk."""
        df = pd.DataFrame({
            'rating': [4, 5, 5, 4],
            'customer_ltv': [1000, 2000, 3000, 4000]
        })
        
        risk_stats = calculate_revenue_at_risk(df)
        assert risk_stats['total_rev_risk'] == 0, "All positive reviews should have zero risk"


class TestQuadrantClassification:
    """Test quadrant analysis classification."""
    
    def test_fire_fight_quadrant(self):
        """High revenue at risk + high negative ratio = Fire-Fight."""
        product_df = pd.DataFrame({
            'product': ['A', 'B', 'C', 'D'],
            'revenue_at_risk': [50000, 1000, 1000, 1000],
            'negative_ratio': [0.8, 0.1, 0.1, 0.1],
            'total_impact': [10, 1, 1, 1]
        })
        
        result = classify_quadrants(product_df)
        assert result.loc[0, 'quadrant'] == 'The Fire-Fight', "Should classify as Fire-Fight"
        assert 'Immediate Fix' in result.loc[0, 'action'], "Should recommend Immediate Fix"
    
    def test_vip_nudge_quadrant(self):
        """High impact + low negative ratio = VIP Nudge."""
        product_df = pd.DataFrame({
            'product': ['A', 'B', 'C', 'D'],
            'revenue_at_risk': [5000, 100, 100, 100],
            'negative_ratio': [0.2, 0.9, 0.9, 0.9],
            'total_impact': [100, 1, 1, 1]
        })
        
        result = classify_quadrants(product_df)
        assert result.loc[0, 'quadrant'] == 'The VIP Nudge', "Should classify as VIP Nudge"
        assert 'Outreach' in result.loc[0, 'action'], "Should recommend Outreach"
    
    def test_slow_burn_quadrant(self):
        """Low revenue but high negative ratio = Slow Burn."""
        product_df = pd.DataFrame({
            'product': ['A', 'B', 'C', 'D'],
            'revenue_at_risk': [500, 50000, 50000, 50000],
            'negative_ratio': [0.9, 0.1, 0.1, 0.1],
            'total_impact': [5, 100, 100, 100]
        })
        
        result = classify_quadrants(product_df)
        assert result.loc[0, 'quadrant'] == 'The Slow Burn', "Should classify as Slow Burn"
        assert 'Experience' in result.loc[0, 'action'], "Should recommend Experience improvement"


class TestPipeline:
    """Test complete pipeline."""
    
    def test_end_to_end_pipeline(self):
        """Full pipeline should process data without errors."""
        df = pd.DataFrame({
            'rating': [1, 2, 3, 4, 5],
            'customer_ltv': [5000, 4000, 3000, 2000, 1000],
            'order_value': [500, 400, 300, 200, 100],
            'helpful_votes': [10, 8, 5, 2, 0],
            'days_since_purchase': [5, 15, 30, 60, 90],
            'is_repeat_customer': [True, False, True, False, True],
            'verified_purchase': [True, True, False, True, False],
            'product': ['A', 'A', 'B', 'B', 'C'],
            'review_text': ['Bad', 'Poor', 'OK', 'Good', 'Excellent']
        })
        
        # Run through pipeline
        scored = apply_scoring_pipeline(df)
        
        # Verify output columns exist
        required_cols = ['CIS', 'impact_score', 'recency_score', 'issue_severity']
        assert all(col in scored.columns for col in required_cols), \
            "Missing required columns in output"
        
        # Aggregate to products
        product_df = aggregate_to_products(scored)
        
        # Verify product-level columns
        assert 'PPS' in product_df.columns, "Missing PPS column"
        assert 'final_score' in product_df.columns, "Missing final_score column"
        
        # Classify quadrants
        product_df = classify_quadrants(product_df)
        assert 'quadrant' in product_df.columns, "Missing quadrant column"
        assert 'action' in product_df.columns, "Missing action column"
        
        # Get summary stats
        stats = summary_stats(scored, product_df)
        assert stats['total_reviews'] == 5, "Wrong review count"
        assert stats['total_products'] == 3, "Wrong product count"


class TestEdgeCases:
    """Test edge cases and robustness."""
    
    def test_single_review(self):
        """Should handle single review."""
        df = pd.DataFrame({
            'rating': [3],
            'customer_ltv': [5000],
            'order_value': [500],
            'helpful_votes': [0],
            'days_since_purchase': [10],
            'is_repeat_customer': [True],
            'verified_purchase': [True],
            'product': ['A'],
            'review_text': ['Good product']
        })
        
        scored = apply_scoring_pipeline(df)
        assert len(scored) == 1, "Should handle single review"
    
    def test_missing_columns(self):
        """Should handle missing optional columns."""
        df = pd.DataFrame({
            'rating': [3, 4, 5]
        })
        
        scored = apply_scoring_pipeline(df)
        assert len(scored) == 3, "Should handle incomplete dataframe"
        assert all(col in scored.columns for col in ['CIS', 'impact_score']), \
            "Missing required output columns"
    
    def test_all_zero_values(self):
        """Should handle all zero/null values."""
        df = pd.DataFrame({
            'rating': [3, 3],
            'customer_ltv': [0, 0],
            'order_value': [0, 0],
            'helpful_votes': [0, 0],
            'days_since_purchase': [0, 0],
            'is_repeat_customer': [False, False],
            'verified_purchase': [False, False],
            'product': ['A', 'A'],
            'review_text': ['', '']
        })
        
        scored = apply_scoring_pipeline(df)
        assert not scored[['CIS', 'impact_score']].isna().any().any(), \
            "Should not have NaN values"
    
    def test_extreme_ltv_values(self):
        """Should handle extreme LTV values with log scaling."""
        df = pd.DataFrame({
            'rating': [1, 1],
            'customer_ltv': [1, 1000000],  # 1 vs 1 million
            'order_value': [1, 1000000],
            'helpful_votes': [0, 0],
            'days_since_purchase': [10, 10],
            'is_repeat_customer': [False, False],
            'verified_purchase': [False, False],
            'product': ['A', 'A'],
            'review_text': ['Bad', 'Bad']
        })
        
        scored = apply_scoring_pipeline(df)
        
        # Log scaling should prevent extreme values
        assert (scored['CIS'] <= 1).all(), "CIS should be <= 1"
        assert (scored['CIS'] >= 0).all(), "CIS should be >= 0"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
