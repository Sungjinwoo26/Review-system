"""
Review Intelligence Engine - Streamlit Dashboard (Production-Grade)
Production-grade dashboard with modular components, state management, and decision-focused UI.

Features:
- Modular component architecture (render_kpis, render_filters, render_quadrant, render_table)
- 4-layer KPI metrics with revenue-at-risk analysis
- Dynamic filtering (Product, Date Range, Severity Threshold)
- Quadrant visualization with threshold lines for prioritization
- Ranked product table for execution decisions
- Session state optimization to prevent unnecessary recomputation
- Comprehensive error handling and empty data management
- 10-day recency plateau, balanced issue severity, 4-layer scoring hierarchy

Required: pandas, numpy, plotly, streamlit, datetime
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, List
import plotly.express as px
import plotly.graph_objects as go

from services.ingestion import fetch_reviews
from services.scoring_engine import (
    apply_scoring_pipeline,
    aggregate_to_products,
    classify_quadrants,
    calculate_revenue_at_risk,
    summary_stats,
    print_summary_stats
)
from services.ingestion import (
    fetch_dynamic_api,
    parse_uploaded_file,
    normalize_schema,
    load_data
)
from utils.error_handler import ErrorState, APIError, safe_divide
from utils.logger import log_event, log_error, log_warning, logger
from utils.cache import get_cache

# Page configuration
st.set_page_config(
    page_title="Review Intelligence Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom styling
st.markdown("""
    <style>
    .kpi-card { 
        padding: 20px; 
        border-radius: 10px; 
        background-color: #f0f2f6;
        border-left: 4px solid #667eea;
    }
    </style>
""", unsafe_allow_html=True)


# ===== STATE MANAGEMENT =====

def init_session_state():
    """Initialize session state - called at app startup"""
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None
    if 'aggregated_data' not in st.session_state:
        st.session_state.aggregated_data = None
    if 'data_fetched' not in st.session_state:
        st.session_state.data_fetched = False
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = None
    if 'filter_state' not in st.session_state:
        st.session_state.filter_state = {
            'products': None,
            'date_range': None,
            'severity_threshold': 0.2
        }
    # Dual input system state
    if 'input_mode' not in st.session_state:
        st.session_state.input_mode = "API"
    if 'api_url' not in st.session_state:
        st.session_state.api_url = "https://mosaicfellowship.in/api/data/cx/reviews"
    if 'api_key' not in st.session_state:
        st.session_state.api_key = ""
    if 'use_default_api' not in st.session_state:
        st.session_state.use_default_api = True


# ===== FILTER FUNCTIONS =====

def get_available_products(df: pd.DataFrame) -> List[str]:
    """Get list of unique products from dataset"""
    if df is None or df.empty:
        return []
    
    # Try multiple possible column names for robustness
    product_col = None
    for col in ['product', 'product_name', 'product_id']:
        if col in df.columns:
            product_col = col
            break
    
    if product_col is None or df[product_col].isna().all():
        return []
    
    # Extract unique products, filter out empty strings and NaN
    products = df[product_col].fillna("Unknown").astype(str).str.strip()
    products = [p for p in products.unique() if p and p != "Unknown"]
    
    if not products:
        return []
    
    return sorted(products)


def get_date_range(df: pd.DataFrame) -> Tuple[datetime, datetime]:
    """Get min and max dates from dataset"""
    if df is None or df.empty or 'review_date' not in df.columns:
        return datetime.now() - timedelta(days=30), datetime.now()
    
    try:
        df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
        min_date = df['review_date'].min()
        max_date = df['review_date'].max()
        
        # Handle NaT values
        if pd.isna(min_date) or pd.isna(max_date):
            return datetime.now() - timedelta(days=30), datetime.now()
        
        return min_date.to_pydatetime(), max_date.to_pydatetime()
    except Exception as e:
        log_warning("DATE_RANGE_ERROR", str(e))
        return datetime.now() - timedelta(days=30), datetime.now()


def apply_filters(
    df: pd.DataFrame,
    products: Optional[List[str]] = None,
    date_range: Optional[Tuple[datetime, datetime]] = None,
    severity_threshold: float = 0.0
) -> pd.DataFrame:
    """
    Apply filters to dataset
    
    Args:
        df: Input dataframe
        products: List of products to include (None = all)
        date_range: Tuple of (start_date, end_date) or None
        severity_threshold: Minimum severity threshold (0.0-1.0)
    
    Returns:
        Filtered dataframe
    """
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()
    
    filtered_df = df.copy()
    
    # Product filter - try multiple possible column names
    if products and len(products) > 0:
        product_col = None
        for col in ['product', 'product_name', 'product_id']:
            if col in filtered_df.columns:
                product_col = col
                break
        
        if product_col:
            filtered_df = filtered_df[filtered_df[product_col].isin(products)]
    
    # Date range filter
    if date_range and len(date_range) == 2 and 'review_date' in filtered_df.columns:
        start_date, end_date = date_range
        filtered_df['review_date'] = pd.to_datetime(filtered_df['review_date'], errors='coerce')
        filtered_df = filtered_df[
            (filtered_df['review_date'] >= start_date) &
            (filtered_df['review_date'] <= end_date)
        ]
    
    # Severity threshold filter
    if severity_threshold > 0.0 and 'issue_severity' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['issue_severity'] >= severity_threshold]
    
    return filtered_df


# ===== MODULAR RENDER FUNCTIONS =====

@st.cache_data
def render_kpis(review_df: pd.DataFrame, product_df: pd.DataFrame) -> None:
    """
    Render KPI cards showing high-level business metrics
    
    Args:
        review_df: Review-level data with scoring
        product_df: Product-level aggregated data
    """
    # Compute metrics
    total_revenue_at_risk = safe_divide(
        product_df['total_revenue_at_risk'].sum() if 'total_revenue_at_risk' in product_df.columns else 0,
        1,
        default=0.0
    )
    
    total_reviews = len(review_df)
    
    negative_pct = safe_divide(
        (review_df['is_negative'].sum() if 'is_negative' in review_df.columns else 0),
        total_reviews,
        default=0.0
    ) * 100
    
    # Find product column name (could be 'product' or 'product_name')
    product_col = None
    for col in ['product', 'product_name', 'product_id']:
        if col in product_df.columns:
            product_col = col
            break
    
    # Find top risk product
    top_product = "N/A"
    if not product_df.empty and product_col and 'final_score' in product_df.columns:
        top_idx = product_df['final_score'].idxmax()
        top_product = product_df.loc[top_idx, product_col]
    
    # DEBUG: Log KPI calculation
    print(f"\n[DEBUG] KPI Calculation:")
    print(f"  - Total Revenue at Risk: ₹{total_revenue_at_risk:,.2f}")
    print(f"  - Total Reviews: {total_reviews}")
    print(f"  - Negative %: {negative_pct:.1f}%")
    print(f"  - Top Product: {top_product}")
    
    # Display KPI cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Revenue at Risk",
            f"₹{total_revenue_at_risk:,.0f}",
            delta="All products" if total_revenue_at_risk > 0 else None
        )
    
    with col2:
        st.metric(
            "Total Reviews",
            f"{total_reviews:,}",
            delta="Analyzed data"
        )
    
    with col3:
        st.metric(
            "% Negative Reviews",
            f"{negative_pct:.1f}%",
            delta="Rating ≤ 2"
        )
    
    with col4:
        st.metric(
            "Top Risk Product",
            top_product,
            delta="Highest priority"
        )


def render_filters(raw_df: pd.DataFrame) -> Tuple[List[str], Tuple, float]:
    """
    Render filter bar for dynamic data filtering
    
    Args:
        raw_df: Raw unfiltered dataframe
    
    Returns:
        Tuple of (selected_products, date_range, severity_threshold)
    """
    if raw_df is None or raw_df.empty:
        return [], None, 0.2
    
    st.subheader("🔍 Filter Data")
    
    col1, col2, col3 = st.columns(3)
    
    # Product filter
    with col1:
        available_products = get_available_products(raw_df)
        selected_products = st.multiselect(
            "📦 Select Products",
            options=available_products,
            default=available_products if len(available_products) <= 5 else available_products[:5],
            help="Select which products to analyze"
        )
    
    # Date range filter
    with col2:
        use_date_filter = st.checkbox("📅 Filter by Date", value=False)
        date_range = None
        
        if use_date_filter:
            min_date, max_date = get_date_range(raw_df)
            col_start, col_end = st.columns(2)
            
            with col_start:
                start_date = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
            
            with col_end:
                end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)
            
            # Validate date range
            if start_date <= end_date:
                date_range = (datetime.combine(start_date, datetime.min.time()),
                             datetime.combine(end_date, datetime.max.time()))
            else:
                st.warning("Start date must be before end date")
    
    # Severity threshold filter
    with col3:
        severity_threshold = st.slider(
            "⚠️ Severity Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.2,
            step=0.05,
            help="Minimum issue severity to include"
        )
    
    return selected_products, date_range, severity_threshold


def render_quadrant(aggregated_df: pd.DataFrame) -> None:
    """
    Render quadrant visualization for prioritization
    
    Args:
        aggregated_df: Product-level aggregated data with scores
    """
    if aggregated_df is None or aggregated_df.empty:
        st.warning("No data available for quadrant visualization")
        return
    
    # Verify required columns
    required_cols = ['negative_ratio', 'total_revenue_at_risk', 'final_score', 'product', 'quadrant']
    missing_cols = [col for col in required_cols if col not in aggregated_df.columns]
    
    if missing_cols:
        st.error(f"Missing columns for quadrant chart: {missing_cols}")
        return
    
    # Calculate thresholds (75th percentile)
    x_threshold = aggregated_df['negative_ratio'].quantile(0.75)
    y_threshold = aggregated_df['total_revenue_at_risk'].quantile(0.75)
    
    # Create scatter plot
    fig = go.Figure()
    
    # Add data points
    fig.add_trace(go.Scatter(
        x=aggregated_df['negative_ratio'],
        y=aggregated_df['total_revenue_at_risk'],
        mode='markers',
        marker=dict(
            size=aggregated_df['final_score'] * 30,  # Scale score to size
            color=aggregated_df['final_score'],
            colorscale='RdYlGn_r',
            showscale=True,
            colorbar=dict(title="Final Score"),
            line=dict(width=2, color='white')
        ),
        text=aggregated_df['product'] + '<br>' +
             'Negative Ratio: ' + (aggregated_df['negative_ratio'] * 100).round(1).astype(str) + '%' + '<br>' +
             'Revenue at Risk: ₹' + aggregated_df['total_revenue_at_risk'].round(0).astype(str) + '<br>' +
             'Quadrant: ' + aggregated_df['quadrant'].astype(str) + '<br>' +
             'Final Score: ' + aggregated_df['final_score'].round(3).astype(str),
        hovertemplate='<b>%{customdata}</b><br>%{text}<extra></extra>',
        customdata=aggregated_df['product']
    ))
    
    # Add threshold lines
    fig.add_shape(
        type="line",
        x0=x_threshold, x1=x_threshold,
        y0=0, y1=aggregated_df['total_revenue_at_risk'].max() * 1.1,
        line=dict(color="blue", width=2, dash="dash"),
        name=f"Neg. Ratio 75th: {x_threshold:.2%}"
    )
    
    fig.add_shape(
        type="line",
        x0=0, x1=aggregated_df['negative_ratio'].max() * 1.1,
        y0=y_threshold, y1=y_threshold,
        line=dict(color="red", width=2, dash="dash"),
        name=f"Revenue Risk 75th: ₹{y_threshold:,.0f}"
    )
    
    # Add quadrant labels
    quadrant_labels = [
        {"x": aggregated_df['negative_ratio'].max() * 0.25, "y": aggregated_df['total_revenue_at_risk'].max() * 0.75, "text": "The VIP Nudge", "color": "orange"},
        {"x": aggregated_df['negative_ratio'].max() * 0.75, "y": aggregated_df['total_revenue_at_risk'].max() * 0.75, "text": "The Fire-Fight", "color": "red"},
        {"x": aggregated_df['negative_ratio'].max() * 0.25, "y": aggregated_df['total_revenue_at_risk'].max() * 0.25, "text": "The Noise", "color": "green"},
        {"x": aggregated_df['negative_ratio'].max() * 0.75, "y": aggregated_df['total_revenue_at_risk'].max() * 0.25, "text": "Slow Burn", "color": "yellow"},
    ]
    
    for quad in quadrant_labels:
        fig.add_annotation(
            x=quad["x"], y=quad["y"],
            text=quad["text"],
            showarrow=False,
            font=dict(size=12, color=quad["color"]),
            opacity=0.3
        )
    
    # Update layout
    fig.update_layout(
        title="📊 Product Priority Quadrant Matrix",
        xaxis_title="Negative Ratio (Criticism Intensity)",
        yaxis_title="Revenue at Risk (₹)",
        height=600,
        hovermode='closest',
        plot_bgcolor='rgba(240,240,240,0.5)'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_table(aggregated_df: pd.DataFrame) -> None:
    """
    Render product ranking table
    
    Args:
        aggregated_df: Product-level aggregated data
    """
    if aggregated_df is None or aggregated_df.empty:
        st.warning("No data available for product ranking")
        return
    
    # Prepare display columns
    display_df = aggregated_df.copy()
    
    # Select and order columns
    cols_to_display = [
        'product', 'total_reviews', 'avg_rating', 'negative_ratio',
        'final_score', 'total_revenue_at_risk', 'quadrant'
    ]
    
    available_cols = [col for col in cols_to_display if col in display_df.columns]
    display_df = display_df[available_cols]
    
    # Sort by final_score descending
    if 'final_score' in display_df.columns:
        display_df = display_df.sort_values('final_score', ascending=False)
    
    # Format numeric columns for display
    if 'final_score' in display_df.columns:
        display_df['final_score'] = display_df['final_score'].round(3)
    if 'avg_rating' in display_df.columns:
        display_df['avg_rating'] = display_df['avg_rating'].round(2)
    if 'negative_ratio' in display_df.columns:
        display_df['negative_ratio'] = (display_df['negative_ratio'] * 100).round(1).astype(str) + '%'
    if 'total_revenue_at_risk' in display_df.columns:
        display_df['total_revenue_at_risk'] = '₹' + display_df['total_revenue_at_risk'].round(0).astype(int).astype(str)
    
    # Display table
    st.subheader("🎯 Product Ranking by Priority")
    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(400, 50 * len(display_df)),
        hide_index=True
    )


# ===== UTILITY FUNCTIONS =====

def show_error(message: str) -> None:
    """Show error message and stop execution"""
    st.error(f"❌ {message}")
    st.stop()


def run_pipeline(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run complete scoring pipeline:
    raw → preprocess → features → scoring → aggregation → classification
    
    Returns:
        Tuple of (review_df, product_df) with scoring and decision columns
    """
    try:
        # Validate input
        if df is None or df.empty:
            raise ValueError("Empty input dataframe")
        
        # Step 1: Apply scoring pipeline
        review_df = apply_scoring_pipeline(df)
        
        if not isinstance(review_df, pd.DataFrame) or review_df.empty:
            raise ValueError("Scoring pipeline returned empty or invalid result")
        
        # Step 2: Aggregate to product level
        product_df = aggregate_to_products(review_df)
        
        if not isinstance(product_df, pd.DataFrame) or product_df.empty:
            raise ValueError("Product aggregation returned empty or invalid result")
        
        # Step 3: Classify quadrants
        product_df = classify_quadrants(product_df)
        
        # Add priority column
        product_df['priority'] = product_df['quadrant'].apply(
            lambda q: 'High' if q in ['The Fire-Fight', 'The VIP Nudge'] else 'Low'
        )
        
        # Log completion
        log_event("PIPELINE_COMPLETE", {
            'reviews': len(review_df),
            'products': len(product_df)
        })
        
        return review_df, product_df
        
    except Exception as e:
        log_error("PIPELINE_FAILED", str(e))
        raise


# ===== MAIN APPLICATION =====

def main():
    """Main application with modular dashboard components"""
    
    # Initialize session state
    init_session_state()
    
    # Page configuration
    st.set_page_config(
        page_title="Review Intelligence Engine",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Header
    st.title("📊 Review Intelligence Engine")
    st.markdown("*Intelligent review analysis and prioritization system*")
    
    # Sidebar control panel
    with st.sidebar:
        st.header("⚙️ Control Panel")
        
        # ===== DUAL INPUT SYSTEM UI =====
        st.subheader("📥 Data Source")
        input_mode = st.radio(
            "Select Data Source",
            ["API", "Upload File"],
            key="input_mode_select"
        )
        
        # Conditional input fields based on mode
        if input_mode == "API":
            st.write("**API Configuration**")
            
            use_default = st.checkbox("Use Default API", value=True)
            
            if use_default:
                api_url = "https://mosaicfellowship.in/api/data/cx/reviews"
                st.info(f"📌 Using: `{api_url}`")
            else:
                api_url = st.text_input(
                    "Enter API URL",
                    value="https://",
                    help="Full API endpoint URL"
                )
            
            api_key = st.text_input(
                "API Key (Optional)",
                type="password",
                help="Bearer token for authentication"
            )
            
            uploaded_file = None
            
        else:  # Upload File mode
            st.write("**File Upload**")
            uploaded_file = st.file_uploader(
                "Upload CSV or JSON file",
                type=["csv", "json"],
                help="Select a CSV or JSON file with review data"
            )
            api_url = None
            api_key = None
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            fetch_btn = st.button("🔄 Load Data", use_container_width=True, type="primary")
        with col2:
            clear_btn = st.button("🗑️ Clear Cache", use_container_width=True)
        
        if clear_btn:
            get_cache().clear()
            st.session_state.raw_data = None
            st.session_state.processed_data = None
            st.session_state.aggregated_data = None
            st.session_state.data_fetched = False
            st.session_state.last_refresh = None
            st.success("✅ Cache cleared!")
            st.rerun()
        
        st.divider()
        
        st.subheader("📈 System Status")
        if st.session_state.data_fetched and st.session_state.last_refresh:
            st.success(f"✅ Data loaded\nLast refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
        else:
            st.info("⏳ Waiting for data load")
    
    # ===== EXECUTION FLOW (STRICT ORDER) =====
    
    # Step 1: Load data (state-aware) - using dual input system
    if fetch_btn:
        try:
            # Validate inputs based on mode
            if input_mode == "API":
                if not api_url:
                    show_error("❌ Please enter an API URL")
            else:  # Upload File
                if uploaded_file is None:
                    show_error("❌ Please upload a file")
            
            # Load data using unified loader
            spinner_msg = "🌐 Fetching from API..." if input_mode == "API" else "📥 Parsing uploaded file..."
            with st.spinner(spinner_msg):
                raw_df = load_data(
                    input_mode=input_mode,
                    api_url=api_url,
                    api_key=api_key,
                    uploaded_file=uploaded_file
                )
            
            if raw_df is None or raw_df.empty:
                show_error("❌ No data loaded from source")
            
            st.session_state.raw_data = raw_df
            
            # Run pipeline
            with st.spinner("🔄 Processing pipeline..."):
                processed_df, aggregated_df = run_pipeline(raw_df)
                st.session_state.processed_data = processed_df
                st.session_state.aggregated_data = aggregated_df
                st.session_state.data_fetched = True
                st.session_state.last_refresh = datetime.now()
            
            st.success(f"✅ Loaded {len(raw_df)} reviews across {len(aggregated_df)} products from {input_mode}")
        
        except APIError as e:
            show_error(f"API Error: {str(e)}")
        except ValueError as e:
            show_error(f"Validation Error: {str(e)}")
        except Exception as e:
            log_error("DATA_LOAD_FAILED", str(e))
            show_error(f"Error loading data: {str(e)}")
    
    # Check if data is loaded
    if not st.session_state.data_fetched or st.session_state.processed_data is None:
        st.info("👈 Select a data source and click 'Load Data' to start analysis")
        return
    
    # Retrieve data from state
    raw_df = st.session_state.raw_data
    processed_df = st.session_state.processed_data
    aggregated_df = st.session_state.aggregated_data
    
    # VALIDATION: Show data quality summary
    with st.expander("🔍 Data Quality Check", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Reviews", len(processed_df))
        with col2:
            products = []
            for col in ['product', 'product_name', 'product_id']:
                if col in processed_df.columns:
                    products = processed_df[col].unique().tolist()
                    break
            st.metric("Unique Products", len(products))
        with col3:
            total_ltv = processed_df['customer_ltv'].sum() if 'customer_ltv' in processed_df.columns else 0
            st.metric("Total LTV", f"₹{total_ltv:,.0f}")
        
        # Show available products
        if products:
            st.write("**Available Products:**")
            st.write(", ".join(sorted(products)))
        else:
            st.warning("⚠️ No products found in dataset")
    
    # Step 2: Apply filters
    st.divider()
    render_filters_result = render_filters(raw_df)
    selected_products, date_range, severity_threshold = render_filters_result
    
    # DEBUG: Show filter state
    print(f"\n[DEBUG] Filter Application:")
    print(f"  - Selected products: {selected_products}")
    print(f"  - Date range: {date_range}")
    print(f"  - Severity threshold: {severity_threshold}")
    print(f"  - Pre-filter rows: {len(processed_df)}")
    
    # Apply filters to processed data
    filtered_df = apply_filters(
        processed_df,
        products=selected_products if selected_products else None,
        date_range=date_range,
        severity_threshold=severity_threshold
    )
    
    print(f"  - Post-filter rows: {len(filtered_df)}")
    
    # Check if filtered data is empty
    if filtered_df.empty:
        st.warning("⚠️ No reviews match the selected filters")
        st.stop()
    
    # Step 3: Re-aggregate if filters were applied
    if len(filtered_df) < len(processed_df):
        filtered_agg = aggregate_to_products(filtered_df)
        filtered_agg = classify_quadrants(filtered_agg)
    else:
        filtered_agg = aggregated_df
    
    # Step 4: Render KPI cards
    st.divider()
    st.subheader("📊 Key Performance Indicators")
    render_kpis(filtered_df, filtered_agg)
    
    # Step 5: Render quadrant visualization
    st.divider()
    st.subheader("📈 Prioritization Analysis")
    render_quadrant(filtered_agg)
    
    # Step 6: Render ranking table
    st.divider()
    render_table(filtered_agg)
    
    # Step 7: Additional details (optional tabs)
    st.divider()
    tab1, tab2, tab3 = st.tabs(["📊 Data Preview", "📈 Charts", "ℹ️ About"])
    
    with tab1:
        st.subheader("Review-Level Data Preview")
        cols_to_show = [col for col in ['rating', 'review_text', 'issue_severity', 'is_negative', 'impact_score'] 
                       if col in filtered_df.columns]
        st.dataframe(
            filtered_df[cols_to_show].head(20),
            use_container_width=True,
            height=400
        )
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Rating Distribution")
            if 'rating' in filtered_df.columns:
                rating_dist = filtered_df['rating'].value_counts().sort_index()
                fig = px.bar(
                    x=rating_dist.index,
                    y=rating_dist.values,
                    labels={'x': 'Rating', 'y': 'Count'},
                    color=rating_dist.values,
                    color_continuous_scale='RdYlGn'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Impact Score Distribution")
            if 'impact_score' in filtered_df.columns:
                fig = px.histogram(
                    filtered_df,
                    x='impact_score',
                    nbins=30,
                    labels={'impact_score': 'Impact Score', 'count': 'Frequency'}
                )
                st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.markdown("""
        ## 🎯 About This Dashboard
        
        The **Review Intelligence Engine (RIE)** helps you:
        - Identify high-impact reviews instantly
        - Prioritize products for action
        - Quantify revenue at risk
        - Make data-driven decisions
        
        ### Key Metrics
        - **CIS**: Customer Importance Score (based on LTV)
        - **Impact Score**: Review severity × Customer importance
        - **Final Score**: Product-level priority metric
        - **Revenue at Risk**: Total LTV of negative customer reviews
        
        ### Quadrant Framework
        - **Fire-Fight**: High risk, high impact → Immediate action
        - **VIP Nudge**: Low risk, high impact → Engage key customers
        - **Slow Burn**: High risk, low impact → Monitor
        - **Noise**: Low risk, low impact → Track
        
        ### How It Works
        1. Fetch reviews from API
        2. Validate and preprocess data
        3. Compute customer and review scores
        4. Aggregate to product level
        5. Classify by priority quadrant
        6. Display prioritized recommendations
        """)


if __name__ == "__main__":
    main()
