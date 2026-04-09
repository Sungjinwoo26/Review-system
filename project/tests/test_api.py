"""
Unit tests for API integration (mock-based)
"""
import pytest
from unittest.mock import patch, MagicMock
from services.ingestion import fetch_reviews
from utils.error_handler import APIError


@patch('services.ingestion.requests.get')
def test_fetch_reviews_success(mock_get):
    """Test successful API data fetch"""
    # Mock API response
    mock_response = MagicMock()
    mock_response.json.side_effect = [
        {
            'data': [
                {
                    'rating': 4,
                    'review_text': 'Good product',
                    'customer_ltv': 100,
                    'order_value': 50,
                    'days_since_purchase': 10,
                    'helpful_votes': 5,
                    'is_repeat_customer': True,
                    'verified_purchase': True
                }
            ]
        },
        {'data': []}  # Empty response to stop pagination
    ]
    mock_get.return_value = mock_response
    
    result = fetch_reviews()
    
    assert len(result) == 1
    assert result.iloc[0]['rating'] == 4


@patch('services.ingestion.requests.get')
def test_fetch_reviews_pagination(mock_get):
    """Test pagination through multiple pages"""
    mock_response = MagicMock()
    mock_response.json.side_effect = [
        {'data': [{'rating': 5, 'review_text': 'Great', 'customer_ltv': 100, 'order_value': 50, 'days_since_purchase': 10, 'helpful_votes': 5, 'is_repeat_customer': True, 'verified_purchase': True}]},
        {'data': [{'rating': 4, 'review_text': 'Good', 'customer_ltv': 200, 'order_value': 75, 'days_since_purchase': 20, 'helpful_votes': 10, 'is_repeat_customer': False, 'verified_purchase': True}]},
        {'data': []}  # Stop pagination
    ]
    mock_get.return_value = mock_response
    
    result = fetch_reviews()
    
    assert len(result) == 2
    assert mock_get.call_count == 3  # 2 pages + 1 empty


@patch('services.ingestion.requests.get')
def test_fetch_reviews_api_failure(mock_get):
    """Test handling of API failure"""
    mock_get.side_effect = Exception("Connection timeout")
    
    with pytest.raises(Exception):
        fetch_reviews()


@patch('services.ingestion.requests.get')
def test_fetch_reviews_empty_response(mock_get):
    """Test handling of empty API response"""
    mock_response = MagicMock()
    mock_response.json.return_value = {'data': []}
    mock_get.return_value = mock_response
    
    result = fetch_reviews()
    
    assert len(result) == 0


@patch('services.ingestion.requests.get')
def test_fetch_reviews_missing_columns(mock_get):
    """Test handling when required columns are missing"""
    mock_response = MagicMock()
    mock_response.json.side_effect = [
        {
            'data': [
                {
                    'rating': 4,
                    'customer_ltv': 100
                    # Missing required fields
                }
            ]
        },
        {'data': []}
    ]
    mock_get.return_value = mock_response
    
    result = fetch_reviews()
    
    # Should still return dataframe even with partial data
    assert len(result) == 1
