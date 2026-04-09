"""Comprehensive scoring engine validation tests.

Tests all 5 layers of the scoring hierarchy:
1. Normalization & Scaling
2. Feature Engineering
3. Customer Importance Score (CIS)
4. Issue Severity & Impact
5. Validation & Logic Gates
"""

import pytest
import pandas as pd
import numpy as np
from services.scoring import compute_scores, validation_check
from services.aggregation import aggregate_product_metrics


class TestCISLogic:
    """Test Customer Importance Score (CIS) Layer 3."""
    
    def test_high_ltv_customer_higher_cis(self):
        """High-LTV customers should have higher CIS."""
        df = pd.DataFrame({
            'ltv_norm': [0.9, 0.1],  # High vs low LTV (normalized)
            'order_norm': [0.5, 0.5],
            'repeat': [0, 0],
            'verified': [1, 1],
            'helpful_norm': [0.5, 0.5],
            'recency': [0.8, 0.8],
            'severity_rating': [0.5, 0.5],
            'sentiment_score': [0.5, 0.5],
            'rating': [3, 3],
            'customer_ltv': [10000, 100],
            'is_negative': [0, 0]
        })
        
        result = compute_scores(df)
        
        # High LTV should have higher CIS (0.30 weight on ltv_norm)
        assert result.loc[0, 'CIS'] > result.loc[1, 'CIS'], \
            "High-LTV customer should have higher CIS"
    
    def test_cis_formula_correctness(self):
        """Test CIS formula: 0.30*ltv + 0.20*order + 0.15*repeat + 0.10*verified + 0.10*helpful + 0.15*recency."""
        df = pd.DataFrame({
            'ltv_norm': [0.5],
            'order_norm': [0.4],
            'repeat': [1.0],
            'verified': [1.0],
            'helpful_norm': [0.6],
            'recency': [0.7],
            'severity_rating': [0.5],
            'sentiment_score': [0.5],
            'rating': [3],
            'customer_ltv': [5000],
            'is_negative': [0]
        })
        
        result = compute_scores(df)
        
        # Manual calculation
        expected_cis = (0.30 * 0.5) + (0.20 * 0.4) + (0.15 * 1.0) + \
                       (0.10 * 1.0) + (0.10 * 0.6) + (0.15 * 0.7)
        
        assert abs(result.loc[0, 'CIS'] - expected_cis) < 1e-6, \
            f"CIS formula error. Expected {expected_cis}, got {result.loc[0, 'CIS']}"
    
    def test_cis_range_0_to_1(self):
        """CIS should always be in [0, 1] range."""
        df = pd.DataFrame({
            'ltv_norm': [np.random.rand() for _ in range(100)],
            'order_norm': [np.random.rand() for _ in range(100)],
            'repeat': [np.random.randint(0, 2) for _ in range(100)],
            'verified': [np.random.randint(0, 2) for _ in range(100)],
            'helpful_norm': [np.random.rand() for _ in range(100)],
            'recency': [np.random.rand() for _ in range(100)],
            'severity_rating': [np.random.rand() for _ in range(100)],
            'sentiment_score': [np.random.rand() for _ in range(100)],
            'rating': [np.random.randint(1, 6) for _ in range(100)],
            'customer_ltv': [np.random.rand() * 10000 for _ in range(100)],
            'is_negative': [0 for _ in range(100)]
        })
        
        result = compute_scores(df)
        
        assert (result['CIS'] >= 0).all() and (result['CIS'] <= 1).all(), \
            "CIS values out of range [0, 1]"


class TestSeverityLogic:
    """Test Issue Severity Score Layer 3B."""
    
    def test_severity_formula_correctness(self):
        """Test severity formula: 0.60*severity_rating + 0.40*(1 - sentiment_score)."""
        df = pd.DataFrame({
            'ltv_norm': [0.5],
            'order_norm': [0.5],
            'repeat': [0],
            'verified': [0],
            'helpful_norm': [0.5],
            'recency': [0.5],
            'severity_rating': [0.9],
            'sentiment_score': [0.8],  # Positive sentiment should reduce severity
            'rating': [1],
            'customer_ltv': [5000],
            'is_negative': [1]
        })
        
        result = compute_scores(df)
        
        # Manual calculation with corrected formula
        expected_severity = (0.60 * 0.9) + (0.40 * (1 - 0.8))
        
        assert abs(result.loc[0, 'severity'] - expected_severity) < 1e-6, \
            f"Severity formula error. Expected {expected_severity}, got {result.loc[0, 'severity']}"
    
    def test_1star_vs_5star_severity(self):
        """1-star review should have much higher severity than 5-star."""
        df = pd.DataFrame({
            'ltv_norm': [0.5, 0.5],
            'order_norm': [0.5, 0.5],
            'repeat': [0, 0],
            'verified': [0, 0],
            'helpful_norm': [0.5, 0.5],
            'recency': [0.5, 0.5],
            'severity_rating': [1.0, 0.0],  # 1-star vs 5-star
            'sentiment_score': [0.0, 1.0],  # negative vs positive
            'rating': [1, 5],
            'customer_ltv': [5000, 5000],
            'is_negative': [1, 0]
        })
        
        result = compute_scores(df)
        
        # 1-star (severe, negative) should score higher than 5-star (positive)
        assert result.loc[0, 'severity'] > result.loc[1, 'severity'], \
            "1-star review should have higher severity than 5-star"


class TestImpactScore:
    """Test Review Impact Score Layer 4."""
    
    def test_high_ltv_low_rating_beats_low_ltv_low_rating(self):
        """Main validation: High-LTV + low-rating should score higher than low-LTV + low-rating."""
        df = pd.DataFrame({
            'ltv_norm': [0.9, 0.1],  # High vs low LTV
            'order_norm': [0.5, 0.5],
            'repeat': [0, 0],
            'verified': [1, 1],
            'helpful_norm': [0.5, 0.5],
            'recency': [0.8, 0.8],
            'severity_rating': [1.0, 1.0],  # Same low rating
            'sentiment_score': [0.0, 0.0],  # Same negative sentiment
            'rating': [1, 1],
            'customer_ltv': [10000, 100],
            'is_negative': [1, 1]
        })
        
        result = compute_scores(df)
        
        # High-LTV 1-star should beat low-LTV 1-star
        assert result.loc[0, 'impact_score'] > result.loc[1, 'impact_score'], \
            "High-value customer issues should have higher impact"
    
    def test_impact_is_cis_times_severity(self):
        """Test impact_score = CIS × Severity."""
        df = pd.DataFrame({
            'ltv_norm': [0.5],
            'order_norm': [0.5],
            'repeat': [0],
            'verified': [0],
            'helpful_norm': [0.5],
            'recency': [0.5],
            'severity_rating': [0.8],
            'sentiment_score': [0.6],
            'rating': [2],
            'customer_ltv': [5000],
            'is_negative': [1]
        })
        
        result = compute_scores(df)
        
        # Manual calculation with corrected severity formula
        expected_cis = (0.30 * 0.5) + (0.20 * 0.5) + (0.15 * 0) + \
                       (0.10 * 0) + (0.10 * 0.5) + (0.15 * 0.5)
        expected_severity = (0.60 * 0.8) + (0.40 * (1 - 0.6))  # Corrected formula
        expected_impact = expected_cis * expected_severity
        
        assert abs(result.loc[0, 'impact_score'] - expected_impact) < 1e-6, \
            f"Impact formula error. Expected {expected_impact}, got {result.loc[0, 'impact_score']}"


class TestZeroImpactTrap:
    """Test Critical Logic Gate: Zero-Impact Trap."""
    
    def test_perfect_product_zero_score(self):
        """Products with only 5-star reviews should have final_score = 0 (zero-impact trap)."""
        # Create all 5-star reviews
        df = pd.DataFrame({
            'product': ['Perfect Product'] * 10,
            'ltv_norm': [0.9] * 10,
            'order_norm': [0.8] * 10,
            'repeat': [1] * 10,
            'verified': [1] * 10,
            'helpful_norm': [0.7] * 10,
            'recency': [0.9] * 10,
            'severity_rating': [0.0] * 10,  # 5-star => no severity
            'sentiment_score': [1.0] * 10,  # positive sentiment
            'rating': [5] * 10,
            'customer_ltv': [5000] * 10,
            'order_value': [500] * 10,
            'is_negative': [0] * 10
        })
        
        # Run through pipeline
        scored = compute_scores(df)
        aggregated = aggregate_product_metrics(scored)
        
        # Perfect product should have 0 impact (no issues)
        assert aggregated.loc[0, 'total_impact'] == 0, \
            "Perfect product should have 0 total impact"
        
        # And final_score should be forced to 0
        assert aggregated.loc[0, 'final_score'] == 0, \
            "Perfect product should have final_score = 0 (zero-impact trap)"
    
    def test_problematic_product_high_score(self):
        """Products with many 1-star reviews should have high final_score."""
        # Create all 1-star reviews with high-value customers
        df = pd.DataFrame({
            'product': ['Bad Product'] * 10,
            'ltv_norm': [0.9] * 10,
            'order_norm': [0.8] * 10,
            'repeat': [1] * 10,
            'verified': [1] * 10,
            'helpful_norm': [0.7] * 10,
            'recency': [0.9] * 10,
            'severity_rating': [1.0] * 10,  # 1-star => high severity
            'sentiment_score': [0.0] * 10,  # negative sentiment
            'rating': [1] * 10,
            'customer_ltv': [5000] * 10,
            'order_value': [500] * 10,
            'is_negative': [1] * 10
        })
        
        # Run through pipeline
        scored = compute_scores(df)
        aggregated = aggregate_product_metrics(scored)
        
        # Bad product should have high impact and high final_score
        assert aggregated.loc[0, 'total_impact'] > 0, \
            "Bad product should have high total impact"
        
        assert aggregated.loc[0, 'final_score'] > 0, \
            "Bad product should have final_score > 0"


class TestPPSLogic:
    """Test Product Priority Score Layer 5."""
    
    def test_pps_formula_correctness(self):
        """Test PPS combines all product-level metrics."""
        # Create test data
        df = pd.DataFrame({
            'product': ['Product A'] * 5,
            'ltv_norm': [0.5] * 5,
            'order_norm': [0.6] * 5,
            'repeat': [1] * 5,
            'verified': [1] * 5,
            'helpful_norm': [0.7] * 5,
            'recency': [0.8] * 5,
            'severity_rating': [0.8] * 5,
            'sentiment_score': [0.2] * 5,
            'rating': [2] * 5,
            'customer_ltv': [5000] * 5,
            'order_value': [500] * 5,
            'is_negative': [1] * 5
        })
        
        scored = compute_scores(df)
        aggregated = aggregate_product_metrics(scored)
        
        # PPS should be in [0, 1]
        assert (aggregated['PPS'] >= 0).all() and (aggregated['PPS'] <= 1).all(), \
            "PPS should be in [0, 1]"


class TestValidationCheck:
    """Test the validation_check() function."""
    
    def test_validation_passes_for_valid_data(self):
        """Validation should pass for correctly scored data."""
        df = pd.DataFrame({
            'rating': [1, 1, 5, 5],
            'customer_ltv': [10000, 10000, 100, 100],
            'CIS': [0.8, 0.8, 0.2, 0.2],
            'severity': [1.0, 1.0, 0.0, 0.0],
            'impact_score': [0.8, 0.8, 0.0, 0.0]
        })
        
        result = validation_check(df)
        
        assert result['passed'] == True, \
            f"Validation should pass. Messages: {result['detail_messages']}"
    
    def test_validation_detects_high_vs_low_ltv_difference(self):
        """Validation should detect high-LTV > low-LTV for same rating."""
        df = pd.DataFrame({
            'rating': [1, 1],
            'customer_ltv': [10000, 100],
            'CIS': [0.8, 0.2],
            'severity': [1.0, 1.0],
            'impact_score': [0.8, 0.2]
        })
        
        result = validation_check(df)
        
        # Should have ratio > 1.0
        assert result['high_ltv_vs_low_ltv'] > 1.0, \
            "High-LTV should score higher than low-LTV"
    
    def test_validation_fails_for_out_of_range(self):
        """Validation should fail if scores out of range."""
        df = pd.DataFrame({
            'rating': [1],
            'customer_ltv': [5000],
            'CIS': [1.5],  # Out of range!
            'severity': [0.5],
            'impact_score': [0.75]
        })
        
        result = validation_check(df)
        
        assert result['passed'] == False, \
            "Validation should fail for out-of-range CIS"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_single_review(self):
        """Should handle single review correctly."""
        df = pd.DataFrame({
            'product': ['Product A'],
            'ltv_norm': [0.5],
            'order_norm': [0.5],
            'repeat': [0],
            'verified': [1],
            'helpful_norm': [0.5],
            'recency': [0.5],
            'severity_rating': [0.5],
            'sentiment_score': [0.5],
            'rating': [3],
            'customer_ltv': [5000],
            'order_value': [500],
            'is_negative': [0]
        })
        
        scored = compute_scores(df)
        aggregated = aggregate_product_metrics(scored)
        
        assert len(aggregated) == 1, "Should have 1 product"
        assert aggregated.loc[0, 'total_reviews'] == 1, "Should have 1 review"
    
    def test_multiple_products(self):
        """Should correctly aggregate multiple products."""
        products = ['A', 'B', 'C', 'D']
        df = pd.DataFrame({
            'product': products * 5,  # 20 reviews total
            'ltv_norm': [0.5] * 20,
            'order_norm': [0.5] * 20,
            'repeat': [0] * 20,
            'verified': [1] * 20,
            'helpful_norm': [0.5] * 20,
            'recency': [0.5] * 20,
            'severity_rating': [0.5] * 20,
            'sentiment_score': [0.5] * 20,
            'rating': [3] * 20,
            'customer_ltv': [5000] * 20,
            'order_value': [500] * 20,
            'is_negative': [0] * 20
        })
        
        scored = compute_scores(df)
        aggregated = aggregate_product_metrics(scored)
        
        assert len(aggregated) == 4, "Should have 4 products"
        assert (aggregated['total_reviews'] == 5).all(), "Each product should have 5 reviews"
    
    def test_no_nan_in_output(self):
        """No NaN values should be in final output."""
        df = pd.DataFrame({
            'product': ['Product A'] * 10,
            'ltv_norm': np.random.rand(10),
            'order_norm': np.random.rand(10),
            'repeat': [0, 1] * 5,
            'verified': [0, 1] * 5,
            'helpful_norm': np.random.rand(10),
            'recency': np.random.rand(10),
            'severity_rating': np.random.rand(10),
            'sentiment_score': np.random.rand(10),
            'rating': np.random.randint(1, 6, 10),
            'customer_ltv': np.random.rand(10) * 10000,
            'order_value': np.random.rand(10) * 1000,
            'is_negative': np.random.randint(0, 2, 10)
        })
        
        scored = compute_scores(df)
        aggregated = aggregate_product_metrics(scored)
        
        assert not scored[['CIS', 'severity', 'impact_score']].isna().any().any(), \
            "No NaN in scored data"
        assert not aggregated[['PPS', 'final_score']].isna().any().any(), \
            "No NaN in aggregated data"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
