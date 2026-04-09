from __future__ import annotations
"""
Review Intelligence Engine - Professional Dashboard for Product Managers
Clean, actionable, and easy to understand
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Optional, List

import plotly.express as px
import plotly.graph_objects as go

# Services
from services.ingestion import load_data
from services.scoring_engine import (
    apply_scoring_pipeline,
    aggregate_to_products,
    classify_quadrants,
)
from services.decision import make_decisions
from utils.error_handler import safe_divide
from utils.logger import log_warning

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Review Intelligence Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Light custom styling (keeps original feel, just cleaner)
st.markdown("""
    <style>
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1e3a8a;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# ====================== SESSION STATE ======================
def init_session_state():
    for key in ['raw_data', 'processed_data', 'aggregated_data', 'data_fetched', 'last_refresh']:
        if key not in st.session_state:
            st.session_state[key] = None if key != 'data_fetched' else False

init_session_state()

# ====================== HEADER ======================
st.title("📊 Review Intelligence Engine")
st.markdown("*Helping Product Managers turn reviews into clear decisions*")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("⚙️ Control Panel")

    st.subheader("📥 Data Source")
    input_mode = st.radio("Select Data Source", ["API", "Upload File"], key="input_mode_select")

    if input_mode == "API":
        use_default = st.checkbox("Use Default API", value=True)
        api_url = "https://mosaicfellowship.in/api/data/cx/reviews" if use_default else st.text_input("API URL", value="https://")
        api_key = st.text_input("API Key (Optional)", type="password")
        uploaded_file = None
    else:
        uploaded_file = st.file_uploader("Upload CSV or JSON file", type=["csv", "json"])
        api_url = None
        api_key = None

    st.divider()

    st.subheader("⚡ AI Insights")
    groq_key = st.text_input(
        "Groq API Key (Optional)",
        type="password",
        help="Leave empty for rule-based recommendations only"
    )

    st.divider()

    col1, col2 = st.columns(2)
    fetch_btn = col1.button("🔄 Load & Analyze Data", type="primary", use_container_width=True)
    clear_btn = col2.button("🗑️ Clear Cache", use_container_width=True)

    if clear_btn:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ====================== HELPER FUNCTIONS ======================
def get_available_products(df: pd.DataFrame) -> List[str]:
    if df is None or df.empty:
        return []
    for col in ['product', 'product_name', 'product_id']:
        if col in df.columns:
            products = df[col].fillna("Unknown").astype(str).str.strip().unique()
            return sorted([p for p in products if p and p != "Unknown"])
    return []

def get_date_range(df: pd.DataFrame) -> Tuple[datetime, datetime]:
    if df is None or df.empty or 'review_date' not in df.columns:
        return datetime.now() - timedelta(days=30), datetime.now()
    try:
        df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
        return df['review_date'].min().to_pydatetime(), df['review_date'].max().to_pydatetime()
    except:
        return datetime.now() - timedelta(days=30), datetime.now()

def apply_filters(df: pd.DataFrame, products=None, date_range=None, severity_threshold=0.0):
    if df is None or df.empty:
        return pd.DataFrame()
    
    filtered = df.copy()
    
    if products and len(products) > 0:
        for col in ['product', 'product_name', 'product_id']:
            if col in filtered.columns:
                filtered = filtered[filtered[col].isin(products)]
                break
    
    if date_range and 'review_date' in filtered.columns:
        start, end = date_range
        filtered['review_date'] = pd.to_datetime(filtered['review_date'], errors='coerce')
        filtered = filtered[(filtered['review_date'] >= start) & (filtered['review_date'] <= end)]
    
    if severity_threshold > 0.0 and 'issue_severity' in filtered.columns:
        filtered = filtered[filtered['issue_severity'] >= severity_threshold]
    
    return filtered

# ====================== RENDER FUNCTIONS (Improved for PMs) ======================
@st.cache_data
def render_kpis(review_df: pd.DataFrame, product_df: pd.DataFrame):
    total_weighted = safe_divide(product_df.get('total_revenue_at_risk', pd.Series(0)).sum(), 1, 0.0)
    total_hard = safe_divide(product_df.get('hard_revenue_risk', pd.Series(0)).sum(), 1, 0.0)
    total_reviews = len(review_df)
    negative_pct = safe_divide(review_df.get('is_negative', pd.Series(0)).sum(), total_reviews, 0.0) * 100

    product_col = next((col for col in ['product', 'product_name', 'product_id'] if col in product_df.columns), None)
    top_product = "N/A"
    if not product_df.empty and product_col and 'final_score' in product_df.columns:
        top_idx = product_df['final_score'].idxmax()
        top_product = product_df.loc[top_idx, product_col]

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Expected Revenue at Risk",
            f"₹{total_weighted:,.0f}",
            delta=f"₹{total_hard:,.0f} Max Exposure",
            delta_color="inverse",
            help="Estimated money we might lose if we don't fix these issues"
        )
    
    with col2:
        st.metric("Total Reviews", f"{total_reviews:,}")
    
    with col3:
        st.metric("% Negative Reviews", f"{negative_pct:.1f}%", help="Reviews rated 1 or 2 stars")
    
    with col4:
        st.metric("Top Risk Product", top_product, help="Product that needs the most attention right now")

def render_filters(raw_df: pd.DataFrame):
    if raw_df is None or raw_df.empty:
        return [], None, 0.2

    st.subheader("🔍 Filter Data")
    col1, col2, col3 = st.columns(3)

    with col1:
        available = get_available_products(raw_df)
        selected_products = st.multiselect("Select Products", options=available, 
                                          default=available[:5] if available else [])

    with col2:
        use_date = st.checkbox("Filter by Date", value=False)
        date_range = None
        if use_date:
            min_date, max_date = get_date_range(raw_df)
            cstart, cend = st.columns(2)
            with cstart:
                start_date = st.date_input("From", value=min_date)
            with cend:
                end_date = st.date_input("To", value=max_date)
            if start_date <= end_date:
                date_range = (datetime.combine(start_date, datetime.min.time()),
                             datetime.combine(end_date, datetime.max.time()))

    with col3:
        severity_threshold = st.slider("Severity Threshold", 0.0, 1.0, 0.2, 0.05,
                                      help="Higher = only show more serious complaints")

    return selected_products, date_range, severity_threshold

def render_quadrant(aggregated_df: pd.DataFrame):
    if aggregated_df is None or aggregated_df.empty:
        st.warning("No data available for quadrant chart")
        return

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=aggregated_df['negative_ratio'],
        y=aggregated_df['total_revenue_at_risk'],
        mode='markers',
        marker=dict(
            size=aggregated_df['final_score'] * 30,
            color=aggregated_df['final_score'],
            colorscale='RdYlGn_r',
            showscale=True,
            colorbar=dict(title="Priority Score")
        ),
        text=aggregated_df['product'],
        hovertemplate="<b>%{text}</b><br>Negative Ratio: %{x:.1%}<br>Revenue at Risk: ₹%{y:,.0f}<extra></extra>"
    ))

    fig.update_layout(
        title="📊 Product Priority Quadrant",
        xaxis_title="Negative Review Ratio (Complaint Intensity)",
        yaxis_title="Revenue at Risk (₹)",
        height=600,
        plot_bgcolor='rgba(240,240,240,0.5)'   # Kept your original background style
    )

    st.plotly_chart(fig, use_container_width=True)

def render_table(aggregated_df: pd.DataFrame):
    if aggregated_df is None or aggregated_df.empty:
        st.warning("No data available for table")
        return

    display_df = aggregated_df.copy()

    # Make columns easier for PMs to understand
    cols_to_display = ['product', 'total_reviews', 'avg_rating', 'total_revenue_at_risk', 'priority', 'action']
    available_cols = [col for col in cols_to_display if col in display_df.columns]
    display_df = display_df[available_cols]

    # Rename for clarity
    display_df = display_df.rename(columns={
        'product': 'Product',
        'total_reviews': 'Total Reviews',
        'avg_rating': 'Average Rating',
        'total_revenue_at_risk': 'Revenue at Risk',
        'priority': 'Priority Level',
        'action': 'Recommended Action'
    })

    # Formatting
    if 'Revenue at Risk' in display_df.columns:
        display_df['Revenue at Risk'] = '₹' + display_df['Revenue at Risk'].round(0).astype(int).astype(str)

    if 'Average Rating' in display_df.columns:
        display_df['Average Rating'] = display_df['Average Rating'].round(2)

    st.subheader("🎯 Recommended Actions by Priority")
    st.dataframe(
        display_df.sort_values(by='Revenue at Risk', ascending=False) if 'Revenue at Risk' in display_df.columns else display_df,
        use_container_width=True,
        hide_index=True
    )

# ====================== PIPELINE ======================
def run_pipeline(df: pd.DataFrame, groq_key: Optional[str] = None):
    review_df = apply_scoring_pipeline(df, groq_key=groq_key)
    product_df = aggregate_to_products(review_df)
    product_df = classify_quadrants(product_df)
    product_df = make_decisions(product_df, review_df, groq_key=groq_key)
    return review_df, product_df

def show_error(message: str):
    st.error(f"❌ {message}")
    st.stop()

# ====================== MAIN ======================
def main():
    if fetch_btn:
        try:
            with st.spinner("Loading data and analyzing..."):
                raw_df = load_data(
                    input_mode=input_mode,
                    api_url=api_url,
                    api_key=api_key,
                    uploaded_file=uploaded_file
                )

                if raw_df is None or raw_df.empty:
                    show_error("No data loaded from source")

                st.session_state.raw_data = raw_df

                processed_df, aggregated_df = run_pipeline(raw_df, groq_key)

                st.session_state.processed_data = processed_df
                st.session_state.aggregated_data = aggregated_df
                st.session_state.data_fetched = True
                st.session_state.last_refresh = datetime.now()
                st.session_state.groq_key = groq_key

            st.success(f"✅ Loaded {len(raw_df):,} reviews across {len(aggregated_df)} products")

        except Exception as e:
            show_error(f"Error loading data: {str(e)}")

    if not st.session_state.data_fetched or st.session_state.processed_data is None:
        st.info("👈 Select data source in sidebar and click 'Load & Analyze Data'")
        st.stop()

    raw_df = st.session_state.raw_data
    processed_df = st.session_state.processed_data
    aggregated_df = st.session_state.aggregated_data

    # Filters
    st.divider()
    selected_products, date_range, severity_threshold = render_filters(raw_df)

    filtered_df = apply_filters(processed_df, selected_products, date_range, severity_threshold)

    if filtered_df.empty:
        st.warning("⚠️ No reviews match your filters")
        st.stop()

    # Re-aggregate if needed
    if len(filtered_df) < len(processed_df):
        filtered_agg = aggregate_to_products(filtered_df)
        filtered_agg = classify_quadrants(filtered_agg)
        filtered_agg = make_decisions(filtered_agg, filtered_df, groq_key=st.session_state.get('groq_key'))
    else:
        filtered_agg = aggregated_df

    # Main sections
    st.divider()
    st.subheader("📊 Key Performance Indicators")
    render_kpis(filtered_df, filtered_agg)

    st.divider()
    st.subheader("📈 Prioritization Analysis")
    render_quadrant(filtered_agg)

    st.divider()
    render_table(filtered_agg)

    # Tabs
    st.divider()
    tab1, tab2, tab3 = st.tabs(["📊 Data Preview", "📈 Charts", "ℹ️ About"])

    with tab1:
        st.subheader("Review Data Preview")
        cols = [c for c in ['product', 'rating', 'review_text', 'issue_severity'] if c in filtered_df.columns]
        st.dataframe(filtered_df[cols].head(20), use_container_width=True)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            if 'rating' in filtered_df.columns:
                st.subheader("Rating Distribution")
                rating_dist = filtered_df['rating'].value_counts().sort_index()
                fig = px.bar(x=rating_dist.index, y=rating_dist.values, labels={'x':'Rating', 'y':'Count'})
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            if 'impact_score' in filtered_df.columns:
                st.subheader("Impact Score Distribution")
                fig = px.histogram(filtered_df, x='impact_score')
                st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.markdown("""
        ### How to Use This Dashboard

        - **Key Performance Indicators**: Shows potential revenue loss and overall sentiment.
        - **Prioritization Analysis**: Visual chart to see which products need attention first.
        - **Recommended Actions**: Practical next steps sorted by importance.

        **Recommendation**: Start with products that have high "Revenue at Risk".
        """)

if __name__ == "__main__":
    main()