"""
Unit tests for feature engineering module
"""
import pytest
import pandas as pd
import numpy as np
from services.features import engineer_features


@pytest.fixture
def sample_preprocessed_data():
    """Create sample preprocessed data"""
    return pd.DataFrame({
        'rating': [1, 2, 4, 5],
        'days_since_purchase': [5, 15, 30, 60],
        'sentiment': ['negative', 'neutral', 'positive', 'positive'],
        'ltv_norm': [0.5, 0.7, 0.3, 0.9],
        'order_norm': [0.6, 0.4, 0.8, 0.5]
    })


def test_severity_rating_boundaries(sample_preprocessed_data):
    """Test severity_rating is between 0 and 1"""
    result = engineer_features(sample_preprocessed_data)
    
    assert 'severity_rating' in result.columns
    assert (result['severity_rating'] >= 0).all()
    assert (result['severity_rating'] <= 1).all()


def test_severity_rating_formula(sample_preprocessed_data):
    """Test severity_rating formula: (5 - rating) / 4"""
    result = engineer_features(sample_preprocessed_data)
    
    # Rating 5 should have lowest severity (0)
    # Rating 1 should have highest severity (1)
    assert result.loc[result['rating'] == 5, 'severity_rating'].values[0] < 0.1
    assert result.loc[result['rating'] == 1, 'severity_rating'].values[0] > 0.9


def test_recency_score_boundaries(sample_preprocessed_data):
    """Test recency is between 0 and 1"""
    result = engineer_features(sample_preprocessed_data)
    
    assert 'recency' in result.columns
    assert (result['recency'] >= 0).all()
    assert (result['recency'] <= 1).all()


def test_recency_recent_higher(sample_preprocessed_data):
    """Test that more recent reviews have higher recency scores"""
    result = engineer_features(sample_preprocessed_data)
    
    # 5 days should have higher recency than 60 days
    recent = result.loc[result['days_since_purchase'] == 5, 'recency'].values[0]
    old = result.loc[result['days_since_purchase'] == 60, 'recency'].values[0]
    
    assert recent > old


def test_sentiment_mapping(sample_preprocessed_data):
    """Test sentiment score mapping"""
    result = engineer_features(sample_preprocessed_data)
    
    assert 'sentiment_score' in result.columns
    
    # Check sentiment mapping
    assert result.loc[result['sentiment'] == 'positive', 'sentiment_score'].values[0] == 1.0
    assert result.loc[result['sentiment'] == 'neutral', 'sentiment_score'].values[0] == 0.5
    assert result.loc[result['sentiment'] == 'negative', 'sentiment_score'].values[0] == 0.0


def test_sentiment_default_when_missing():
    """Test default sentiment score when column missing"""
    df = pd.DataFrame({
        'rating': [3],
        'days_since_purchase': [20]
    })
    
    result = engineer_features(df)
    
    # Should default to 0.5
    assert result['sentiment_score'].values[0] == 0.5


def test_negative_flag(sample_preprocessed_data):
    """Test is_negative flag"""
    result = engineer_features(sample_preprocessed_data)
    
    assert 'is_negative' in result.columns
    
    # Rating 1 and 2 should be marked as negative
    assert result.loc[result['rating'] == 1, 'is_negative'].values[0] == 1
    assert result.loc[result['rating'] == 2, 'is_negative'].values[0] == 1
    
    # Rating 4 and 5 should not be marked as negative
    assert result.loc[result['rating'] == 4, 'is_negative'].values[0] == 0
    assert result.loc[result['rating'] == 5, 'is_negative'].values[0] == 0


def test_no_nans_in_features(sample_preprocessed_data):
    """Test that no NaN values in output"""
    result = engineer_features(sample_preprocessed_data)
    
    assert not result[['severity_rating', 'recency', 'sentiment_score', 'is_negative']].isna().any().any()


def test_empty_dataframe():
    """Test with empty dataframe"""
    empty_df = pd.DataFrame({
        'rating': [],
        'days_since_purchase': []
    })
    
    result = engineer_features(empty_df)
    assert len(result) == 0
    assert 'severity_rating' in result.columns
