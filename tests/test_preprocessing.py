"""
Unit tests for preprocessing module
"""
import pytest
import pandas as pd
import numpy as np
from services.preprocessing import preprocess_data


@pytest.fixture
def sample_data():
    """Create sample review data for testing"""
    return pd.DataFrame({
        'customer_ltv': [100, 200, np.nan, 500],
        'order_value': [50, np.nan, 75, 100],
        'helpful_votes': [5, 10, 0, np.nan],
        'days_since_purchase': [10, 20, np.nan, 45],
        'is_repeat_customer': [True, False, True, False],
        'verified_purchase': [True, True, False, True]
    })


def test_missing_values_filled(sample_data):
    """Test that missing values are properly filled"""
    result = preprocess_data(sample_data)
    
    assert not result['customer_ltv'].isna().any()
    assert not result['order_value'].isna().any()
    assert not result['helpful_votes'].isna().any()
    assert not result['days_since_purchase'].isna().any()


def test_log_scaling_applied(sample_data):
    """Test that log scaling is applied"""
    result = preprocess_data(sample_data)
    
    assert 'ltv_log' in result.columns
    assert 'order_value_log' in result.columns
    
    # Values should be positive after log transformation
    assert (result['ltv_log'] >= 0).all()
    assert (result['order_value_log'] >= 0).all()


def test_normalization_boundaries(sample_data):
    """Test that normalized values are between 0 and 1"""
    result = preprocess_data(sample_data)
    
    for col in ['ltv_norm', 'order_norm', 'helpful_norm']:
        assert (result[col] >= 0).all()
        assert (result[col] <= 1).all()


def test_boolean_encoding(sample_data):
    """Test that boolean fields are encoded as 0/1"""
    result = preprocess_data(sample_data)
    
    assert set(result['repeat'].unique()).issubset({0, 1})
    assert set(result['verified'].unique()).issubset({0, 1})
    assert result['repeat'].dtype in [np.int64, np.int32, int]


def test_no_nans_in_output(sample_data):
    """Test that no NaN values remain in output"""
    result = preprocess_data(sample_data)
    
    assert not result.isna().any().any(), "Found NaN values in output"


def test_empty_dataframe():
    """Test handling of empty dataframe"""
    empty_df = pd.DataFrame({
        'customer_ltv': [],
        'order_value': [],
        'helpful_votes': [],
        'days_since_purchase': [],
        'is_repeat_customer': [],
        'verified_purchase': []
    })
    
    result = preprocess_data(empty_df)
    assert len(result) == 0
    assert 'ltv_norm' in result.columns


def test_all_nulls():
    """Test handling when all values are null"""
    null_df = pd.DataFrame({
        'customer_ltv': [None, None],
        'order_value': [None, None],
        'helpful_votes': [None, None],
        'days_since_purchase': [None, None],
        'is_repeat_customer': [None, None],
        'verified_purchase': [None, None]
    })
    
    result = preprocess_data(null_df)
    
    # Should fill with defaults, not remain null
    assert not result.isna().any().any()
