# Error Handling Implementation Guide

## Overview

This guide extends the error handling system to the **Scoring Pipeline** and **UI Layer** to complete the production-ready architecture.

---

## Phase 1: Scoring Engine Error Handling

### Current Status
- ✅ `utils/error_handler.py` - Complete with custom exceptions
- ✅ `utils/logger.py` - Complete with structured logging
- ✅ `services/ingestion.py` - Complete with retry logic
- ⏳ `services/scoring_engine.py` - NEEDS error handling
- ⏳ `services/data_robustness.py` - NEEDS error handling
- ⏳ `app.py` - NEEDS UI error handling

---

## Scoring Engine Enhancement Plan

### File: `services/scoring_engine.py`

**Goal**: Wrap all computation functions with error handling

#### Implementation Steps

**Step 1: Add Error Handling Imports**

```python
# At top of services/scoring_engine.py
from utils.error_handler import (
    catch_and_log, 
    assert_schema, 
    safe_divide,
    ScoringError
)
from utils.logger import logger, log_error, log_performance
```

**Step 2: Wrap Core Scoring Functions**

```python
# Before: Original function
def compute_cis(review):
    """Compute Customer Impact Score"""
    # existing implementation
    
# After: Add error handling
@catch_and_log(
    default_return=0.0,  # Return neutral score on error
    error_type="CIS_COMPUTATION_ERROR",
    log_level="error"
)
def compute_cis(review):
    """Compute Customer Impact Score with error handling"""
    try:
        # existing implementation
        pass
    except KeyError as e:
        logger.error(f"Missing field in review: {e}")
        raise DataError(f"Cannot compute CIS - missing field: {e}")
    except Exception as e:
        logger.exception("Unexpected error in CIS computation")
        raise ScoringError(f"CIS computation failed: {e}")
```

**Step 3: Add Validation at Pipeline Entry**

```python
def apply_scoring_pipeline(df):
    """Apply scoring pipeline with validation and error handling"""
    
    # Validate input
    try:
        assert_schema(
            df,
            required_columns=['rating', 'customer_ltv', 'days_since_review'],
            context="Scoring pipeline"
        )
        assert_not_empty(df, context="Scoring pipeline")
    except DataError as e:
        logger.error(f"Validation failed: {e}")
        return df  # Return unchanged, partially scored data
    
    # Apply scoring stages with error tracking
    errors = []
    warnings = []
    
    try:
        df['cis_score'] = df.apply(compute_cis, axis=1)
    except Exception as e:
        logger.error(f"CIS scoring failed: {e}")
        errors.append(f"CIS computation: {e}")
        df['cis_score'] = 0.0
        warnings.append("Using default CIS scores")
    
    try:
        df['severity_score'] = df.apply(compute_impact_score, axis=1)
    except Exception as e:
        logger.error(f"Severity scoring failed: {e}")
        errors.append(f"Severity computation: {e}")
        df['severity_score'] = 0.5
        warnings.append("Using default Severity scores")
    
    try:
        df['priority_score'] = df.apply(compute_product_priority_score, axis=1)
    except Exception as e:
        logger.error(f"Priority scoring failed: {e}")
        errors.append(f"Priority computation: {e}")
        df['priority_score'] = 0.5
        warnings.append("Using default Priority scores")
    
    try:
        df['final_score'] = df.apply(compute_final_score, axis=1)
    except Exception as e:
        logger.error(f"Final scoring failed: {e}")
        errors.append(f"Final score computation: {e}")
        df['final_score'] = 0.5
        warnings.append("Using default Final scores")
    
    # Log summary
    if errors:
        log_error(
            "PIPELINE_PARTIAL_FAILURE",
            f"Scoring pipeline completed with {len(errors)} errors",
            {"errors": errors, "warnings": warnings}
        )
    else:
        logger.info("Scoring pipeline completed successfully")
    
    return df
```

**Step 4: Add Safe Aggregation**

```python
@catch_and_log(
    default_return={},
    error_type="AGGREGATION_ERROR"
)
def aggregate_to_products(df):
    """Aggregate scores to products with error handling"""
    
    try:
        assert_not_empty(df, context="Product aggregation")
    except DataError as e:
        logger.error(str(e))
        return {}
    
    try:
        # existing aggregation logic
        aggregated = {}
        for product in df['product_name'].unique():
            try:
                product_data = df[df['product_name'] == product]
                aggregated[product] = {
                    'avg_score': product_data['final_score'].mean(),
                    'total_ltv': product_data['customer_ltv'].sum(),
                    'review_count': len(product_data)
                }
            except Exception as e:
                logger.warning(f"Failed to aggregate {product}: {e}")
                continue
        
        return aggregated
        
    except Exception as e:
        logger.exception("Aggregation pipeline failed")
        return {}
```

**Step 5: Add Safe Classification**

```python
@catch_and_log(
    default_return=None,
    error_type="CLASSIFICATION_ERROR"
)
def classify_quadrants(product_scores):
    """Classify products by quadrant with error handling"""
    
    try:
        # existing classification logic
        classification = {}
        
        for product, score in product_scores.items():
            try:
                quadrant = _determine_quadrant(score)
                classification[product] = quadrant
            except Exception as e:
                logger.warning(f"Cannot classify {product}: {e}")
                classification[product] = 'Unknown'
        
        return classification
        
    except Exception as e:
        logger.exception("Quadrant classification failed")
        return None
```

---

## Phase 2: UI Error Handling

### File: `app.py`

**Goal**: Wrap all data operations with try-catch and user-friendly error messages

#### Implementation Steps

**Step 1: Add Error Handling Imports**

```python
# At top of app.py
import streamlit as st
from utils.error_handler import ErrorState, safe_get_nested
from utils.logger import logger, log_error, log_performance
```

**Step 2: Safe Session State Access**

```python
# ALREADY DONE ✓ - Just verify:

def init_session_state():
    # NO @st.cache_resource decorator
    if "data_fetched" not in st.session_state:
        st.session_state.data_fetched = False
    if "pipeline_df" not in st.session_state:
        st.session_state.pipeline_df = None
    # ... more initializations

# Always use safe access:
if st.session_state.get("data_fetched", False):
    df = st.session_state.get("pipeline_df")
#  NOT: if st.session_state.data_fetched:
```

**Step 3: Safe Data Fetching**

```python
def safe_fetch_and_process():
    """Fetch and process data with comprehensive error handling"""
    
    try:
        st.info("📥 Fetching reviews...")
        
        # Fetch with timeout
        reviews_df, fetch_metrics = fetch_reviews_safe()
        
        if reviews_df.empty:
            st.error("""
                ❌ No reviews fetched. Possible issues:
                - API server is down
                - Rate limit exceeded
                - Network connection problem
                
                Please check your internet connection and try again.
            """)
            logger.error("Empty DataFrame returned from API")
            return None
        
        st.success(f"✅ Loaded {len(reviews_df)} reviews")
        
        # Process with error handling
        st.info("🔄 Processing data...")
        
        processed_df, process_report = robust_data_pipeline(
            reviews_df,
            include_report=True
        )
        
        if not process_report.get("success", False):
            st.warning("⚠️ Data processing had issues (continuing with available data)")
            for issue in process_report.get("warnings", []):
                st.warning(f"  • {issue}")
        
        st.session_state.pipeline_df = processed_df
        st.session_state.data_fetched = True
        st.success("✅ Ready to analyze")
        
        return processed_df
        
    except Exception as e:
        logger.exception("Data fetch and processing failed")
        st.error("""
            ❌ Fatal error processing data.
            
            This has been logged and our team will investigate.
            Please try again later.
        """)
        return None
```

**Step 4: Safe Tab Content**

```python
with tab1:  # Data Ingestion Tab
    st.subheader("📊 Data Ingestion")
    
    try:
        if st.button("Fetch & Process Reviews"):
            df = safe_fetch_and_process()
            
    except KeyError as e:
        logger.error(f"Missing column: {e}")
        st.error(f"⚠️ Data format issue: missing {str(e)}")
    except MemoryError:
        logger.error("Out of memory")
        st.error("❌ Too much data. Try reducing max_pages.")
    except Exception as e:
        logger.exception("Tab1 error")
        st.error("❌ Unexpected error. Please try again.")

with tab2:  # Review Analytics Tab
    st.subheader("📈 Review Analytics")
    
    try:
        df = st.session_state.get("pipeline_df")
        
        if df is None or df.empty:
            st.info("No data loaded. Please fetch data first.")
        else:
            # Display analytics
            col1, col2, col3 = st.columns(3)
            
            try:
                with col1:
                    st.metric("Total Reviews", len(df))
                with col2:
                    avg_score = safe_divide(
                        df['final_score'].sum(),
                        len(df),
                        default=0.0
                    )
                    st.metric("Avg Score", f"{avg_score:.2f}")
                with col3:
                    total_ltv = df['customer_ltv'].sum()
                    st.metric("Total LTV", f"${total_ltv:,.0f}")
            except Exception as e:
                logger.warning(f"Metrics display error: {e}")
                st.warning("⚠️ Could not display some metrics")
            
            # Visualizations
            try:
                st.plotly_chart(visualize_score_distribution(df))
            except Exception as e:
                logger.warning(f"Visualization error: {e}")
                st.warning("⚠️ Could not render visualization")
                
    except Exception as e:
        logger.exception("Tab2 error")
        st.error("❌ Analytics display failed")

with tab3:  # Product Priorities Tab
    st.subheader("🎯 Product Priorities")
    
    try:
        df = st.session_state.get("pipeline_df")
        
        if df is None or df.empty:
            st.info("No data loaded. Please fetch data first.")
        else:
            try:
                # Aggregate and classify
                product_scores = aggregate_to_products(df)
                quadrants = classify_quadrants(product_scores)
                
                if not product_scores:
                    st.warning("⚠️ No products available")
                else:
                    # Display priority table
                    priority_data = []
                    for product, scores in product_scores.items():
                        try:
                            priority_data.append({
                                'Product': product,
                                'Score': f"{scores.get('avg_score', 0):.2f}",
                                'LTV at Risk': f"${scores.get('total_ltv', 0):,.0f}",
                                'Reviews': scores.get('review_count', 0),
                                'Priority': quadrants.get(product, 'Unknown')
                            })
                        except Exception as e:
                            logger.warning(f"Error processing {product}: {e}")
                            continue
                    
                    if priority_data:
                        st.dataframe(priority_data)
                    else:
                        st.warning("⚠️ No valid products to display")
                        
            except Exception as e:
                logger.warning(f"Product aggregation error: {e}")
                st.warning("⚠️ Could not load product priorities")
                
    except Exception as e:
        logger.exception("Tab3 error")
        st.error("❌ Products display failed")
```

**Step 5: Add Error Summary Display**

```python
def display_error_summary():
    """Display summary of system health"""
    
    with st.sidebar:
        st.subheader("📊 System Status")
        
        try:
            # Check log file for recent errors
            if os.path.exists("review_system.log"):
                with open("review_system.log", "r") as f:
                    lines = f.readlines()
                
                # Count recent errors (last 100 lines)
                recent_lines = lines[-100:]
                error_count = sum(1 for l in recent_lines if "ERROR" in l)
                warning_count = sum(1 for l in recent_lines if "WARNING" in l)
                
                if error_count > 10:
                    st.error(f"⚠️ {error_count} recent errors")
                elif warning_count > 5:
                    st.warning(f"⚠️ {warning_count} recent warnings")
                else:
                    st.success("✅ System healthy")
                    
        except Exception as e:
            logger.debug(f"Could not read log file: {e}")
            st.info("Status: Unknown")
```

---

## Phase 3: Integration Testing

### File: `tests/test_error_handling_integration.py` (NEW)

```python
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from services.ingestion import fetch_reviews_safe
from services.scoring_engine import apply_scoring_pipeline
from utils.error_handler import APIError, DataError, ScoringError

class TestAPIErrorHandling:
    """Test API layer error handling"""
    
    @patch('requests.get')
    def test_api_timeout_retry(self, mock_get):
        """Test that API timeouts trigger retries"""
        from requests.exceptions import Timeout
        
        # Fail twice, succeed on third
        mock_get.side_effect = [
            Timeout(),
            Timeout(),
            MagicMock(status_code=200, json=lambda: {'data': [{'id': 1}]})
        ]
        
        result = fetch_reviews_safe(max_pages=1)
        
        # Should succeed after retries
        assert not result.empty
        assert mock_get.call_count == 3
    
    @patch('requests.get')
    def test_api_server_error_retry(self, mock_get):
        """Test that 5xx errors trigger retries"""
        mock_get.return_value = MagicMock(
            status_code=500,
            raise_for_status=MagicMock(side_effect=Exception("500"))
        )
        
        result = fetch_reviews_safe(max_pages=1)
        
        # Should return empty DataFrame on failure
        assert isinstance(result, pd.DataFrame)
        assert result.empty
    
    @patch('requests.get')
    def test_api_client_error_no_retry(self, mock_get):
        """Test that 4xx errors don't retry"""
        mock_get.return_value = MagicMock(
            status_code=404,
            raise_for_status=MagicMock(side_effect=Exception("404"))
        )
        
        result = fetch_reviews_safe(max_pages=1)
        
        # Should fail immediately, not retry
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestScoringErrorHandling:
    """Test scoring pipeline error handling"""
    
    def test_missing_column_handling(self):
        """Test scoring pipeline with missing column"""
        df = pd.DataFrame({
            'rating': [4, 5, 3],
            # Missing 'customer_ltv' column
        })
        
        result = apply_scoring_pipeline(df)
        
        # Should handle gracefully
        assert isinstance(result, pd.DataFrame)
        # Should have attempted to add scored columns
    
    def test_mismatched_types_handling(self):
        """Test scoring with unexpected data types"""
        df = pd.DataFrame({
            'rating': ['high', 'low', 'medium'],  # Should be numeric
            'customer_ltv': [100, 200, 300],
            'days_since_review': [5, 10, 15],
            'product_name': ['A', 'B', 'C']
        })
        
        result = apply_scoring_pipeline(df)
        
        # Should handle type errors gracefully
        assert isinstance(result, pd.DataFrame)
    
    def test_empty_dataframe_handling(self):
        """Test scoring with empty DataFrame"""
        df = pd.DataFrame()
        
        result = apply_scoring_pipeline(df)
        
        # Should return empty DataFrame
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestDataValidationErrors:
    """Test data validation error handling"""
    
    def test_nan_heavy_dataset(self):
        """Test processing dataset with many NaNs"""
        df = pd.DataFrame({
            'rating': [None, 5, None, 3],
            'sentiment_score': [None, None, 0.8, None],
            'customer_ltv': [100, 200, None, 400],
            'product_name': ['A', 'B', 'C', 'D']
        })
        
        from services.data_robustness import robust_data_pipeline
        result, report = robust_data_pipeline(df, include_report=True)
        
        # Should handle NaNs appropriately
        assert not result.isnull().all().any()  # No all-null columns
        assert report['success'] or len(report.get('warnings', [])) > 0


class TestGracefulDegradation:
    """Test graceful degradation on partial failures"""
    
    def test_partial_api_failure(self):
        """Test system continues with partial data on API failure"""
        from services.data_robustness import robust_data_pipeline
        
        # Simulate partial API response
        df = pd.DataFrame({
            'rating': [4, 5],
            'customer_ltv': [100, 200],
            'product_name': ['A', 'B']
        })
        
        result, report = robust_data_pipeline(df)
        
        # Should process what's available
        assert len(result) > 0
        assert not result.empty
    
    def test_scoring_with_bad_records(self):
        """Test that bad records don't stop entire pipeline"""
        df = pd.DataFrame({
            'rating': [4, None, 5, 'invalid'],
            'customer_ltv': [100, 200, 300, 400],
            'product_name': ['A', 'B', 'C', 'D'],
            'days_since_review': [5, 10, 15, float('inf')]
        })
        
        result = apply_scoring_pipeline(df)
        
        # Should have processed what it could
        assert isinstance(result, pd.DataFrame)
        assert 'final_score' in result.columns
```

---

## Implementation Checklist

### Scoring Engine Enhancement
- [ ] Add error handling imports to scoring_engine.py
- [ ] Wrap compute_cis() with @catch_and_log
- [ ] Wrap compute_impact_score() with @catch_and_log
- [ ] Wrap compute_product_priority_score() with @catch_and_log
- [ ] Wrap compute_final_score() with @catch_and_log
- [ ] Update apply_scoring_pipeline() with stage-by-stage error tracking
- [ ] Update aggregate_to_products() with error handling
- [ ] Update classify_quadrants() with error handling
- [ ] Test all scoring functions with invalid inputs

### UI Error Handling
- [ ] Add error handling imports to app.py
- [ ] Create safe_fetch_and_process() function
- [ ] Wrap Tab1 (Data Ingestion) with try-catch
- [ ] Wrap Tab2 (Review Analytics) with try-catch
- [ ] Wrap Tab3 (Product Priorities) with try-catch
- [ ] Add display_error_summary() to sidebar
- [ ] Test UI with each tab containing data
- [ ] Test UI with empty data
- [ ] Test UI with corrupted data

### Testing
- [ ] Create tests/test_error_handling_integration.py
- [ ] Test API timeout retries
- [ ] Test API 5xx error retries
- [ ] Test API 4xx no-retry behavior
- [ ] Test scoring with missing columns
- [ ] Test scoring with type mismatches
- [ ] Test partial API failures
- [ ] Test full error scenarios

---

## Success Criteria

✅ **All error scenarios handled**:
- API timeouts → Retry with backoff
- Network failures → Retry with backoff
- Invalid data → Skip/default
- Missing columns → Add with defaults
- Type mismatches → Coerce/skip
- Partial failures → Continue with available data

✅ **User experience**:
- No raw exceptions in UI
- Clear, actionable error messages
- System continues operating on partial failures
- Status indicators show system health

✅ **Debugging capability**:
- All errors logged with full context
- Log file shows complete error history
- Metrics available for performance analysis
- Easy to trace failures through layers

✅ **Test coverage**:
- All error paths have tests
- Integration tests for realistic scenarios
- Tests pass with 100% coverage of error handling code

