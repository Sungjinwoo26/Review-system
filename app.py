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
from processing.ml.features_ml import prepare_ml_features
from processing.ml.train import train_risk_model, get_feature_importance
from processing.ml.predict import predict_risk, get_risk_summary
from llm import enrich_products_with_llm_insights
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
    # ML model state
    if 'ml_model_dict' not in st.session_state:
        st.session_state.ml_model_dict = None
    if 'ml_features' not in st.session_state:
        st.session_state.ml_features = None


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
    Render KPI cards showing high-level business metrics including ML risk predictions
    
    Args:
        review_df: Review-level data with scoring
        product_df: Product-level aggregated data (with risk_probability from ML)
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
    
    # ML-based metric: High-risk products count
    high_risk_count = 0
    if 'risk_category' in product_df.columns:
        high_risk_count = int((product_df['risk_category'] == 'High').sum())
    
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
    print(f"  - High Risk Products (ML): {high_risk_count}")
    
    # Display KPI cards (5-column layout)
    col1, col2, col3, col4, col5 = st.columns(5)
    
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
    
    with col5:
        st.metric(
            "🚨 High Risk Products",
            high_risk_count,
            delta="≥70% confidence"
        )


def render_filters(raw_df: pd.DataFrame) -> Tuple[List[str], Tuple, float, float]:
    """
    Render filter bar for dynamic data filtering
    
    Args:
        raw_df: Raw unfiltered dataframe
    
    Returns:
        Tuple of (selected_products, date_range, severity_threshold, risk_threshold)
    """
    if raw_df is None or raw_df.empty:
        return [], None, 0.2, 0.0
    
    st.subheader("🔍 Filter Data")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Product filter
    with col1:
        available_products = get_available_products(raw_df)
        selected_products = st.multiselect(
            "📦 Select Products",
            options=available_products,
            default=available_products,
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
            value=0.0,
            step=0.05,
            help="Minimum issue severity to include (0 = show all reviews)"
        )
    
    # ML Risk threshold filter (NEW)
    with col4:
        risk_threshold = st.slider(
            "🤖 ML Risk Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
            help="Minimum predicted risk probability to show"
        )
    
    return selected_products, date_range, severity_threshold, risk_threshold


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
    Render product ranking table with ML risk predictions
    
    Args:
        aggregated_df: Product-level aggregated data (with risk_probability from ML)
    """
    if aggregated_df is None or aggregated_df.empty:
        st.warning("No data available for product ranking")
        return
    
    # Prepare display columns
    display_df = aggregated_df.copy()
    
    # Select and order columns - include ML risk metrics
    cols_to_display = [
        'product', 'total_reviews', 'avg_rating', 'negative_ratio',
        'final_score', 'total_revenue_at_risk', 'quadrant',
        'risk_probability', 'risk_category'
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
    
    # Format risk probability as percentage with color indicators
    if 'risk_probability' in display_df.columns:
        display_df['Risk %'] = (display_df['risk_probability'] * 100).round(1).astype(str) + '%'
        # Create a visual indicator using emoji based on risk category
        if 'risk_category' in display_df.columns:
            display_df['Risk Status'] = display_df['risk_category'].apply(
                lambda x: '🟢 Low' if x == 'Low' else ('🟡 Medium' if x == 'Medium' else '🔴 High')
            )
            # Reorder to show Risk Status with Risk %
            cols_to_show = []
            for col in available_cols:
                cols_to_show.append(col)
            # Move risk columns to the end for visibility
            if 'risk_probability' in cols_to_show:
                cols_to_show.remove('risk_probability')
            if 'risk_category' in cols_to_show:
                cols_to_show.remove('risk_category')
            display_df = display_df[cols_to_show + ['Risk %', 'Risk Status']]
    
    # Display table
    st.subheader("🎯 Product Ranking by Priority (with ML Risk Predictions)")
    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(400, 50 * len(display_df)),
        hide_index=True
    )


def render_risk_distribution(aggregated_df: pd.DataFrame) -> None:
    """
    Render ML risk probability distribution visualization
    
    Args:
        aggregated_df: Product-level aggregated data with risk_probability
    """
    if aggregated_df is None or aggregated_df.empty or 'risk_probability' not in aggregated_df.columns:
        st.warning("No risk probability data available")
        return
    
    # Create bins for risk categories
    bins = [0, 0.3, 0.7, 1.0]
    labels = ['Low (0-30%)', 'Medium (30-70%)', 'High (70-100%)']
    
    aggregated_df_copy = aggregated_df.copy()
    aggregated_df_copy['risk_bin'] = pd.cut(
        aggregated_df_copy['risk_probability'],
        bins=bins,
        labels=labels,
        include_lowest=True
    )
    
    # Count by risk category
    risk_counts = aggregated_df_copy['risk_bin'].value_counts().sort_index()
    
    # Create bar chart
    fig = go.Figure()
    
    colors = ['#2ecc71', '#f1c40f', '#e74c3c']  # Green, Yellow, Red
    
    fig.add_trace(go.Bar(
        x=risk_counts.index.astype(str),
        y=risk_counts.values,
        marker=dict(color=colors),
        text=risk_counts.values,
        textposition='auto',
        hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
    ))
    
    fig.update_layout(
        title="📊 ML Risk Distribution by Category",
        xaxis_title="Risk Category",
        yaxis_title="Number of Products",
        height=400,
        showlegend=False,
        plot_bgcolor='rgba(240,240,240,0.5)'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_feature_importance(model_dict: Optional[Dict]) -> None:
    """
    Render feature importance from trained ML model (if available)
    
    Args:
        model_dict: Dictionary returned from train_risk_model (contains model and scaler)
    """
    if model_dict is None:
        st.info("⏳ Feature importance will be available after data loads")
        return
    
    try:
        importance_df = get_feature_importance(model_dict)
        
        if importance_df is None or importance_df.empty:
            st.warning("Could not extract feature importance")
            return
        
        # Get top 5 features
        top_features = importance_df.head(5)
        
        # Create horizontal bar chart
        fig = go.Figure()
        
        # Color based on positive/negative coefficient
        colors = ['#e74c3c' if x > 0 else '#3498db' for x in top_features['coefficient']]
        
        fig.add_trace(go.Bar(
            y=top_features['feature'],
            x=top_features['coefficient'],
            orientation='h',
            marker=dict(color=colors),
            text=top_features['coefficient'].round(3),
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Coefficient: %{x:.3f}<extra></extra>'
        ))
        
        fig.update_layout(
            title="🧠 Top Risk Drivers (Feature Importance)",
            xaxis_title="Coefficient (Impact on Risk Probability)",
            yaxis_title="Feature Name",
            height=350,
            showlegend=False,
            plot_bgcolor='rgba(240,240,240,0.5)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Legend
        st.caption("🔴 Red = Increases Risk | 🔵 Blue = Decreases Risk")
        
    except Exception as e:
        st.warning(f"Could not display feature importance: {str(e)}")


def render_ml_insights(aggregated_df: pd.DataFrame) -> None:
    """
    Render ML-powered insights and recommendations
    
    Args:
        aggregated_df: Product-level aggregated data with risk metrics
    """
    if aggregated_df is None or aggregated_df.empty:
        return
    
    st.subheader("💡 ML-Powered Insights")
    
    col1, col2, col3 = st.columns(3)
    
    # Insight 1: High-risk products that are NOT in Fire-Fight quadrant
    with col1:
        if 'risk_probability' in aggregated_df.columns and 'quadrant' in aggregated_df.columns:
            hidden_risks = aggregated_df[
                (aggregated_df['risk_probability'] > 0.7) & 
                (aggregated_df['quadrant'] != 'The Fire-Fight')
            ]
            
            st.metric(
                "🎯 Hidden Risks Detected",
                len(hidden_risks),
                delta="Predicted but not yet flagged" if len(hidden_risks) > 0 else "None"
            )
    
    # Insight 2: Average risk across quadrants
    with col2:
        if 'risk_probability' in aggregated_df.columns:
            avg_risk = aggregated_df['risk_probability'].mean()
            st.metric(
                "📊 Portfolio Risk",
                f"{avg_risk*100:.1f}%",
                delta="Average across all products"
            )
    
    # Insight 3: High-risk products in VIP segment
    with col3:
        if 'risk_probability' in aggregated_df.columns and 'total_revenue_at_risk' in aggregated_df.columns:
            high_risk_revenue = aggregated_df[aggregated_df['risk_probability'] > 0.7]['total_revenue_at_risk'].sum()
            st.metric(
                "💰 Revenue at Risk (High-Risk Products)",
                f"₹{high_risk_revenue:,.0f}",
                delta="In predicted high-risk products"
            )


def render_enhanced_kpis(review_df: pd.DataFrame, product_df: pd.DataFrame) -> None:
    """
    Render enhanced KPI cards with ML metrics
    
    Args:
        review_df: Review-level data
        product_df: Product-level data with ML predictions
    """
    if review_df is None or product_df is None or product_df.empty:
        return
    
    # Validate ML output
    if 'risk_probability' not in product_df.columns:
        product_df['risk_probability'] = 0
    if 'risk_category' not in product_df.columns:
        product_df['risk_category'] = 'Low'
    
    # Calculate metrics
    total_revenue_at_risk = safe_divide(
        product_df['total_revenue_at_risk'].sum() if 'total_revenue_at_risk' in product_df.columns else 0,
        1,
        default=0.0
    )
    
    total_reviews = len(review_df)
    
    # DEBUG: Check is_negative column
    has_is_negative = 'is_negative' in review_df.columns
    negative_count = 0
    if has_is_negative:
        negative_count = review_df['is_negative'].sum()
        print(f"[DEBUG] is_negative column found: {negative_count} negatives in {total_reviews} reviews")
    else:
        print(f"[DEBUG] is_negative column NOT found. Available columns: {review_df.columns.tolist()}")
    
    negative_pct = safe_divide(
        negative_count,
        total_reviews,
        default=0.0
    ) * 100
    
    # ML metrics
    high_risk_count = int((product_df['risk_category'] == 'High').sum())
    medium_risk_count = int((product_df['risk_category'] == 'Medium').sum())
    avg_risk_prob = float(product_df['risk_probability'].mean())
    
    # Find top risk product
    product_col = None
    for col in ['product', 'product_name', 'product_id']:
        if col in product_df.columns:
            product_col = col
            break
    
    top_product = "N/A"
    if not product_df.empty and product_col and 'final_score' in product_df.columns:
        top_idx = product_df['final_score'].idxmax()
        top_product = product_df.loc[top_idx, product_col]
    
    # Display KPI cards (5-column layout)
    col1, col2, col3, col4, col5 = st.columns(5)
    
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
            "🚨 High Risk Products",
            high_risk_count,
            delta=f"({high_risk_count} of {len(product_df)})"
        )
    
    with col5:
        st.metric(
            "📊 Avg Risk Probability",
            f"{avg_risk_prob*100:.1f}%",
            delta="ML predicted likelihood"
        )


# ===== UTILITY FUNCTIONS =====

def show_error(message: str) -> None:
    """Show error message and stop execution"""
    st.error(f"❌ {message}")
    st.stop()


def apply_llm_insights(aggregated_df: pd.DataFrame, groq_api_key: str = "") -> pd.DataFrame:
    """
    Apply downstream LLM insights to already-aggregated product metrics.

    This function does not alter scoring, aggregation, or ML outputs.
    """
    if aggregated_df is None or aggregated_df.empty:
        return aggregated_df

    ml_snapshot = []
    if 'risk_probability' in aggregated_df.columns:
        ml_snapshot = aggregated_df[['product', 'risk_probability', 'risk_category']].head(5).to_dict('records')
    print(f"\n[DEBUG] ML Output Checkpoint: {ml_snapshot}")

    agg_cols = [
        col for col in [
            'product', 'total_reviews', 'avg_rating', 'negative_ratio',
            'total_impact', 'total_revenue_at_risk', 'final_score',
            'quadrant', 'priority', 'action'
        ] if col in aggregated_df.columns
    ]
    print(f"[DEBUG] Aggregated Metrics Checkpoint: {aggregated_df[agg_cols].head(5).to_dict('records')}")

    llm_df = enrich_products_with_llm_insights(
        aggregated_df,
        api_key=groq_api_key,
        max_products=5
    )

    llm_input_snapshot = []
    llm_output_snapshot = []
    if 'llm_payload' in llm_df.columns:
        llm_input_snapshot = llm_df.loc[llm_df['llm_payload'] != '', ['product', 'llm_payload']].head(3).to_dict('records')
    if 'llm_summary' in llm_df.columns:
        llm_output_snapshot = llm_df.loc[llm_df['llm_summary'] != '', ['product', 'llm_source', 'llm_summary']].head(3).to_dict('records')
    print(f"[DEBUG] LLM Input Checkpoint: {llm_input_snapshot}")
    print(f"[DEBUG] LLM Output Checkpoint: {llm_output_snapshot}")

    return llm_df


def render_llm_insights(aggregated_df: pd.DataFrame) -> None:
    """Render downstream LLM insights without changing core metrics."""
    if aggregated_df is None or aggregated_df.empty:
        return

    if 'llm_summary' not in aggregated_df.columns:
        st.info("Add a Groq API key in the sidebar to generate LLM insights, or use the rule-based fallback for top products.")
        return

    insight_df = aggregated_df[aggregated_df['llm_summary'] != ''].copy()
    if insight_df.empty:
        st.info("Add a Groq API key in the sidebar to generate LLM insights, or use the rule-based fallback for top products.")
        return

    st.subheader("LLM Insights")
    for _, row in insight_df.head(5).iterrows():
        source = row.get('llm_source', 'unknown')
        with st.expander(f"{row.get('product', 'Unknown')} ({source})", expanded=False):
            st.write(f"**Summary:** {row.get('llm_summary', '')}")
            st.write(f"**Driver:** {row.get('llm_driver', '')}")
            st.write(f"**Recommendation:** {row.get('llm_recommendation', '')}")


def render_debug_checkpoints(review_df: pd.DataFrame, aggregated_df: pd.DataFrame) -> None:
    """Render lightweight debug checkpoints for validation."""
    with st.expander("Debug Checkpoints", expanded=False):
        st.write("**ML outputs**")
        ml_cols = [col for col in ['product', 'risk_probability', 'risk_category'] if col in aggregated_df.columns]
        if ml_cols:
            st.dataframe(aggregated_df[ml_cols].head(10), use_container_width=True, hide_index=True)
        else:
            st.write("ML output columns not available.")

        st.write("**Aggregated metrics**")
        agg_cols = [
            col for col in [
                'product', 'total_reviews', 'avg_rating', 'negative_ratio',
                'total_revenue_at_risk', 'final_score', 'quadrant', 'priority', 'action'
            ] if col in aggregated_df.columns
        ]
        st.dataframe(aggregated_df[agg_cols].head(10), use_container_width=True, hide_index=True)

        st.write("**LLM input**")
        llm_input_cols = [col for col in ['product', 'llm_payload'] if col in aggregated_df.columns]
        if len(llm_input_cols) == 2:
            st.dataframe(
                aggregated_df.loc[aggregated_df['llm_payload'] != '', llm_input_cols].head(5),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("LLM input payload not generated yet.")

        st.write("**LLM output**")
        llm_output_cols = [col for col in ['product', 'llm_source', 'llm_summary', 'llm_recommendation'] if col in aggregated_df.columns]
        if len(llm_output_cols) >= 3:
            st.dataframe(
                aggregated_df.loc[aggregated_df['llm_summary'] != '', llm_output_cols].head(5),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("LLM output not generated yet.")


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


def apply_ml_predictions(aggregated_df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply ML risk prediction model to aggregated product data.
    
    Process:
    1. Prepare ML features from aggregated metrics
    2. Train Logistic Regression model (if not cached)
    3. Generate risk probability predictions
    4. Add predictive columns to dataframe
    
    Error Handling:
    - If ML fails, returns dataframe with default risk_probability = 0
    - Graceful degradation to ensure system continues operating
    - Logs warnings but doesn't break pipeline
    
    Args:
        aggregated_df: Product-level DataFrame from aggregation pipeline
    
    Returns:
        Enhanced DataFrame with risk_probability, risk_category, high_risk_predicted columns
    """
    
    try:
        # Step 1: Prepare ML features
        ml_df, features = prepare_ml_features(aggregated_df)
        
        if ml_df is None or ml_df.empty:
            raise ValueError("Feature preparation returned empty dataframe")
        
        # Step 2: Train model
        # Note: We train on each batch to adapt to current data
        # In production, you'd cache/persist the model
        model_dict = train_risk_model(ml_df, features, quantile=0.75)
        
        if model_dict is None:
            raise ValueError("Model training failed")
        
        # Cache model in session state for later use (e.g., feature importance display)
        st.session_state.ml_model_dict = model_dict
        st.session_state.ml_features = features
        
        # Step 3: Generate predictions
        ml_df = predict_risk(model_dict, ml_df)
        
        # Step 4: Merge predictions back to aggregated dataframe
        # Keep only product identifier and ML columns
        ml_predictions = ml_df[['product', 'risk_probability', 'risk_category', 'high_risk_predicted']].copy()
        
        # Merge back to original dataframe
        aggregated_df = aggregated_df.merge(
            ml_predictions,
            on='product',
            how='left'
        )
        
        # Fill any missing predictions with defaults (graceful degradation)
        aggregated_df['risk_probability'] = aggregated_df['risk_probability'].fillna(0)
        aggregated_df['high_risk_predicted'] = aggregated_df['high_risk_predicted'].fillna(0).astype(int)
        aggregated_df['risk_category'] = aggregated_df['risk_category'].fillna('Low')
        
        # Log success
        log_event("ML_PREDICTIONS_COMPLETE", {
            'products': len(aggregated_df),
            'high_risk_count': int((aggregated_df['risk_category'] == 'High').sum()),
            'avg_risk_probability': float(aggregated_df['risk_probability'].mean())
        })
        
        return aggregated_df
    
    except Exception as e:
        # Graceful degradation: add default columns and continue
        log_warning("ML_PREDICTION_FAILED", f"Risk prediction failed: {str(e)}")
        
        # Add default columns if they don't exist
        if 'risk_probability' not in aggregated_df.columns:
            aggregated_df['risk_probability'] = 0.0
        if 'high_risk_predicted' not in aggregated_df.columns:
            aggregated_df['high_risk_predicted'] = 0
        if 'risk_category' not in aggregated_df.columns:
            aggregated_df['risk_category'] = 'Low'
        
        return aggregated_df


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

        st.subheader("LLM Settings")
        groq_api_key = st.text_input(
            "Groq API Key (Optional)",
            type="password",
            help="Used only for downstream product insights after ML and aggregation."
        )

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
                st.session_state.data_fetched = True
                st.session_state.last_refresh = datetime.now()
            
            # Apply ML risk predictions
            with st.spinner("🤖 Generating risk predictions..."):
                aggregated_df = apply_ml_predictions(aggregated_df)

            # Apply downstream LLM insights
            with st.spinner("🧠 Generating downstream product insights..."):
                aggregated_df = apply_llm_insights(aggregated_df, groq_api_key)
                st.session_state.aggregated_data = aggregated_df
            
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
    selected_products, date_range, severity_threshold, risk_threshold = render_filters_result
    
    # DEBUG: Show filter state
    print(f"\n[DEBUG] Filter Application:")
    print(f"  - Selected products: {selected_products}")
    print(f"  - Date range: {date_range}")
    print(f"  - Severity threshold: {severity_threshold}")
    print(f"  - Risk threshold (ML): {risk_threshold}")
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
        
        # CRITICAL FIX: Restore ML columns from original aggregated_df
        # When re-aggregating, we lose the ML predictions, so merge them back
        ml_columns = ['risk_probability', 'risk_category', 'high_risk_predicted']
        if all(col in aggregated_df.columns for col in ml_columns):
            ml_data = aggregated_df[['product'] + ml_columns].copy()
            filtered_agg = filtered_agg.merge(ml_data, on='product', how='left')
            # Fill any missing ML values with defaults
            filtered_agg['risk_probability'] = filtered_agg['risk_probability'].fillna(0.0)
            filtered_agg['risk_category'] = filtered_agg['risk_category'].fillna('Low')
            filtered_agg['high_risk_predicted'] = filtered_agg['high_risk_predicted'].fillna(0).astype(int)

    else:
        filtered_agg = aggregated_df
    
    # Step 3b: Apply ML risk threshold filter
    if risk_threshold > 0:
        if 'risk_probability' in filtered_agg.columns:
            pre_risk_filter = len(filtered_agg)
            filtered_agg = filtered_agg[filtered_agg['risk_probability'] >= risk_threshold]
            print(f"  - After risk filter: {len(filtered_agg)} products (filtered {pre_risk_filter - len(filtered_agg)})")
            
            # Also filter reviews to match the remaining products
            product_col = None
            for col in ['product', 'product_name', 'product_id']:
                if col in filtered_df.columns and col in filtered_agg.columns:
                    product_col = col
                    break
            
            if product_col:
                filtered_df = filtered_df[filtered_df[product_col].isin(filtered_agg[product_col])]
                print(f"  - Filtered reviews: {len(filtered_df)} reviews from {len(filtered_agg)} products")

    filtered_agg = apply_llm_insights(filtered_agg, groq_api_key)
    
    # Step 4: Render enhanced KPI cards with ML metrics
    st.divider()
    st.subheader("📊 Key Performance Indicators")
    render_enhanced_kpis(filtered_df, filtered_agg)
    
    # Step 5: Render quadrant visualization
    st.divider()
    st.subheader("📈 Prioritization Analysis")
    render_quadrant(filtered_agg)
    
    # Step 6: Render ML risk distribution chart
    st.divider()
    st.subheader("📊 ML Risk Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        render_risk_distribution(filtered_agg)
    
    with col2:
        render_feature_importance(st.session_state.ml_model_dict)
    
    # Step 7: Render ML insights
    st.divider()
    render_ml_insights(filtered_agg)
    
    # Step 8: Render downstream LLM insights
    st.divider()
    render_llm_insights(filtered_agg)

    # Step 9: Render ranking table
    st.divider()
    render_table(filtered_agg)

    # Step 10: Render debug checkpoints
    st.divider()
    render_debug_checkpoints(filtered_df, filtered_agg)
    
    # Step 11: Additional details (optional tabs)
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
