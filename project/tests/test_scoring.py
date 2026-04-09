"""
Unit tests for scoring module
"""
import pytest
import pandas as pd
import numpy as np
from services.scoring import compute_scores


@pytest.fixture
def sample_featured_data():
    """Create sample data with all required features"""
    return pd.DataFrame({
        'ltv_norm': [0.2, 0.5, 0.8, 0.9],
        'order_norm': [0.3, 0.4, 0.7, 0.5],
        'helpful_norm': [0.1, 0.5, 0.9, 0.3],
        'repeat': [0, 1, 1, 0],
        'verified': [0, 1, 1, 1],
        'severity_rating': [0.8, 0.4, 0.2, 0.1],
        'recency': [0.9, 0.6, 0.4, 0.2],
        'sentiment_score': [0.0, 0.5, 1.0, 0.5]
    })


def test_cis_exists(sample_featured_data):
    """Test CIS column is created"""
    result = compute_scores(sample_featured_data)
    
    assert 'CIS' in result.columns


def test_cis_boundaries(sample_featured_data):
    """Test CIS values are between 0 and 1"""
    result = compute_scores(sample_featured_data)
    
    assert (result['CIS'] >= 0).all()
    assert (result['CIS'] <= 1).all()


def test_cis_formula_weighting(sample_featured_data):
    """Test that high-value customers get higher CIS"""
    result = compute_scores(sample_featured_data)
    
    # Customer 4 has high ltv_norm and order_norm
    # Customer 1 has low ltv_norm and order_norm
    customer_4_cis = result.iloc[3]['CIS']
    customer_1_cis = result.iloc[0]['CIS']
    
    assert customer_4_cis > customer_1_cis


def test_severity_score_exists(sample_featured_data):
    """Test severity column is created"""
    result = compute_scores(sample_featured_data)
    
    assert 'severity' in result.columns


def test_severity_boundaries(sample_featured_data):
    """Test severity values are between 0 and 1"""
    result = compute_scores(sample_featured_data)
    
    assert (result['severity'] >= 0).all()
    assert (result['severity'] <= 1).all()


def test_impact_score_exists(sample_featured_data):
    """Test impact_score column is created"""
    result = compute_scores(sample_featured_data)
    
    assert 'impact_score' in result.columns


def test_impact_score_boundaries(sample_featured_data):
    """Test impact_score values are between 0 and 1"""
    result = compute_scores(sample_featured_data)
    
    assert (result['impact_score'] >= 0).all()
    assert (result['impact_score'] <= 1).all()


def test_impact_score_formula(sample_featured_data):
    """Test impact_score = CIS × severity"""
    result = compute_scores(sample_featured_data)
    
    # Manually calculate for first row
    cis = result.iloc[0]['CIS']
    severity = result.iloc[0]['severity']
    impact = result.iloc[0]['impact_score']
    
    expected_impact = cis * severity
    assert abs(impact - expected_impact) < 0.01  # Allow small float differences


def test_high_cis_high_severity_high_impact(sample_featured_data):
    """Test that high CIS + high severity = high impact"""
    # Create a scenario with high importance customer + severe issue
    high_impact_df = pd.DataFrame({
        'ltv_norm': [0.9],
        'order_norm': [0.9],
        'helpful_norm': [0.8],
        'repeat': [1],
        'verified': [1],
        'severity_rating': [0.9],
        'recency': [0.95],
        'sentiment_score': [0.0]
    })
    
    result = compute_scores(high_impact_df)
    
    # Should have high impact
    assert result.iloc[0]['impact_score'] > 0.5


def test_low_cis_high_severity_moderate_impact(sample_featured_data):
    """Test that low CIS + high severity = moderate impact"""
    low_cis_df = pd.DataFrame({
        'ltv_norm': [0.1],
        'order_norm': [0.1],
        'helpful_norm': [0.1],
        'repeat': [0],
        'verified': [0],
        'severity_rating': [0.9],
        'recency': [0.1],
        'sentiment_score': [0.0]
    })
    
    result = compute_scores(low_cis_df)
    
    # Should have lower impact than high_cis scenario
    assert result.iloc[0]['impact_score'] < 0.4


def test_no_nans_in_output(sample_featured_data):
    """Test no NaN values in output"""
    result = compute_scores(sample_featured_data)
    
    assert not result[['CIS', 'severity', 'impact_score']].isna().any().any()


def test_empty_dataframe():
    """Test with empty dataframe"""
    empty_df = pd.DataFrame({
        'ltv_norm': [],
        'order_norm': [],
        'helpful_norm': [],
        'repeat': [],
        'verified': [],
        'severity_rating': [],
        'recency': [],
        'sentiment_score': []
    })
    
    result = compute_scores(empty_df)
    assert len(result) == 0
    assert 'impact_score' in result.columns
