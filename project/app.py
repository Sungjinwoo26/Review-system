"""
Review Intelligence Engine - Streamlit Dashboard
A comprehensive system for analyzing and prioritizing customer reviews
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

from services.ingestion import fetch_reviews
from services.preprocessing import preprocess_data
from services.features import engineer_features
from services.scoring import compute_scores
from services.aggregation import aggregate_product_metrics
from services.decision import make_decisions
from utils.error_handler import ErrorState, APIError
from utils.logger import log_event, log_error, logger
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
    .metric-card { 
        padding: 20px; 
        border-radius: 10px; 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
        color: white;
    }
    .error-banner {
        padding: 15px;
        border-radius: 5px;
        background-color: #fee;
        border-left: 4px solid #f44;
        color: #c33;
    }
    .success-banner {
        padding: 15px;
        border-radius: 5px;
        background-color: #efe;
        border-left: 4px solid #4f4;
        color: #3c3;
    }
    </style>
""", unsafe_allow_html=True)


# ===== CACHE AND STATE MANAGEMENT =====

@st.cache_resource
def init_session_state():
    """Initialize session state"""
    if 'data_fetched' not in st.session_state:
        st.session_state.data_fetched = False
    if 'pipeline_df' not in st.session_state:
        st.session_state.pipeline_df = None
    if 'product_metrics' not in st.session_state:
        st.session_state.product_metrics = None
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = None
    if 'error_state' not in st.session_state:
        st.session_state.error_state = None


# ===== UTILITY FUNCTIONS =====

def show_error_banner(error_state: ErrorState):
    """Display error banner"""
    st.markdown(f"""
        <div class="error-banner">
        <strong>❌ {error_state.error_type}</strong><br/>
        {error_state.message}
        </div>
    """, unsafe_allow_html=True)


def show_success_banner(message: str):
    """Display success banner"""
    st.markdown(f"""
        <div class="success-banner">
        <strong>✅ Success</strong><br/>
        {message}
        </div>
    """, unsafe_allow_html=True)


def run_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run complete data pipeline:
    raw → preprocess → feature engineering → scoring
    """
    try:
        # Step 1: Preprocessing
        st.status("🔄 Preprocessing data...", expanded=False)
        df = preprocess_data(df)
        
        # Step 2: Feature Engineering
        st.status("🔄 Engineering features...", expanded=False)
        df = engineer_features(df)
        
        # Step 3: Scoring
        st.status("🔄 Computing scores...", expanded=False)
        df = compute_scores(df)
        
        return df
        
    except Exception as e:
        log_error("PIPELINE_ERROR", str(e))
        raise


# ===== MAIN APP =====

def main():
    """Main application"""
    init_session_state()
    
    # Header
    st.title("📊 Review Intelligence Engine")
    st.markdown("*Intelligent review analysis and prioritization system*")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Control Panel")
        
        # Refresh button
        col1, col2 = st.columns(2)
        with col1:
            refresh = st.button("🔄 Refresh Data", use_container_width=True)
        with col2:
            clear_cache = st.button("🗑️ Clear Cache", use_container_width=True)
        
        if clear_cache:
            get_cache().clear()
            st.session_state.data_fetched = False
            st.session_state.pipeline_df = None
            st.session_state.product_metrics = None
            st.session_state.last_refresh = None
            st.success("✅ Cache cleared!")
        
        st.divider()
        
        # Status indicator
        st.subheader("📈 System Status")
        if st.session_state.last_refresh:
            st.caption(f"Last updated: {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.caption("No data loaded yet")
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 Data Ingestion",
        "📊 Review Analytics",
        "🎯 Product Priorities",
        "ℹ️ About"
    ])
    
    # ===== TAB 1: DATA INGESTION =====
    with tab1:
        st.header("Data Ingestion & Pipeline")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("**Fetch and process review data**")
        with col2:
            run_pipeline_btn = st.button("🚀 Run Full Pipeline", use_container_width=True, type="primary")
        
        if run_pipeline_btn or (refresh and not st.session_state.data_fetched):
            status_container = st.container()
            
            with status_container:
                with st.spinner("🌐 Fetching reviews from API..."):
                    try:
                        raw_df = fetch_reviews(max_pages=5)  # Limit to 5 pages for MVP
                        
                        if len(raw_df) == 0:
                            st.warning("⚠️ No reviews fetched from API. Check API status.")
                        else:
                            st.success(f"✅ Fetched {len(raw_df)} reviews")
                            
                            # Run pipeline
                            with st.spinner("🔄 Running preprocessing and feature engineering..."):
                                pipeline_df = run_pipeline(raw_df)
                                st.session_state.pipeline_df = pipeline_df
                                st.session_state.data_fetched = True
                                st.session_state.last_refresh = datetime.now()
                                
                                # Create product metrics
                                with st.spinner("📊 Aggregating product metrics..."):
                                    product_metrics = aggregate_product_metrics(pipeline_df)
                                    product_metrics = make_decisions(product_metrics)
                                    st.session_state.product_metrics = product_metrics
                                
                                show_success_banner(f"Pipeline complete! Processed {len(pipeline_df)} reviews across {len(product_metrics)} products.")
                    
                    except APIError as e:
                        st.error(f"❌ API Error: {str(e)}")
                        log_error("API_FETCH_FAILED", str(e))
                    except ValueError as e:
                        st.error(f"❌ Data Validation Error: {str(e)}")
                        log_error("DATA_VALIDATION_FAILED", str(e))
                    except Exception as e:
                        st.error(f"❌ Unexpected Error: {str(e)}")
                        log_error("UNEXPECTED_ERROR", str(e))
        
        # Show data preview
        if st.session_state.data_fetched and st.session_state.pipeline_df is not None:
            st.divider()
            st.subheader("✨ Data Preview")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Reviews", len(st.session_state.pipeline_df))
            with col2:
                neg_count = (st.session_state.pipeline_df['is_negative'] == 1).sum()
                st.metric("Negative Reviews", neg_count)
            with col3:
                avg_rating = st.session_state.pipeline_df['rating'].mean()
                st.metric("Avg Rating", f"{avg_rating:.2f}", delta=f"/{5}")
            
            # Display sample data
            st.subheader("Sample Reviews")
            display_cols = ['rating', 'review_text', 'severity_rating', 'recency', 'is_negative', 'impact_score']
            available_cols = [col for col in display_cols if col in st.session_state.pipeline_df.columns]
            
            st.dataframe(
                st.session_state.pipeline_df[available_cols].head(10),
                use_container_width=True,
                height=300
            )
    
    # ===== TAB 2: REVIEW ANALYTICS =====
    with tab2:
        st.header("Review Analytics & Insights")
        
        if st.session_state.data_fetched and st.session_state.pipeline_df is not None:
            df = st.session_state.pipeline_df
            
            # KPIs
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Reviews Analyzed", len(df))
            with col2:
                st.metric("Avg Impact Score", f"{df['impact_score'].mean():.3f}")
            with col3:
                st.metric("Critical Issues", (df['is_negative'].sum()))
            with col4:
                st.metric("Avg Customer LTV", f"${df['customer_ltv'].mean():.0f}")
            
            st.divider()
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Rating Distribution")
                rating_dist = df['rating'].value_counts().sort_index()
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
                fig = px.histogram(
                    df,
                    x='impact_score',
                    nbins=30,
                    title='Distribution of Review Impact Scores',
                    labels={'impact_score': 'Impact Score', 'count': 'Number of Reviews'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Severity vs Recency")
                fig = px.scatter(
                    df.sample(min(500, len(df))),
                    x='recency',
                    y='severity_rating',
                    size='impact_score',
                    color='is_negative',
                    hover_data=['rating', 'customer_ltv'],
                    labels={'recency': 'Recency Score', 'severity_rating': 'Severity Rating'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Top 10 Highest Impact Reviews")
                top_reviews = df.nlargest(10, 'impact_score')[['rating', 'severity_rating', 'is_negative', 'customer_ltv', 'impact_score']]
                st.dataframe(top_reviews, use_container_width=True)
        
        else:
            st.info("👈 Use the Data Ingestion tab to fetch and process reviews first.")
    
    # ===== TAB 3: PRODUCT PRIORITIES =====
    with tab3:
        st.header("Product Priority Ranking")
        
        if st.session_state.data_fetched and st.session_state.product_metrics is not None:
            metrics = st.session_state.product_metrics
            
            # Overview metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Products Analyzed", len(metrics))
            with col2:
                critical = (metrics['priority'] == 'High').sum()
                st.metric("Critical Priority", critical)
            with col3:
                st.metric("Total Revenue at Risk", f"${metrics['total_revenue_at_risk'].sum():.0f}")
            with col4:
                st.metric("Avg Final Score", f"{metrics['final_score'].mean():.3f}")
            
            st.divider()
            
            # Product priority table
            st.subheader("🎯 Product Priority Matrix")
            
            display_metrics = metrics[[
                'product',
                'total_reviews',
                'avg_rating',
                'negative_ratio',
                'PPS',
                'total_revenue_at_risk',
                'final_score',
                'priority',
                'action'
            ]].copy()
            
            display_metrics = display_metrics.sort_values('final_score', ascending=False)
            
            st.dataframe(
                display_metrics,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Priority Distribution")
                priority_counts = metrics['priority'].value_counts()
                fig = px.pie(
                    values=priority_counts.values,
                    names=priority_counts.index,
                    color=priority_counts.index,
                    color_discrete_map={'High': '#ff6b6b', 'Medium': '#ffd93d', 'Low': '#6bcf7f'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Final Score vs Revenue at Risk")
                fig = px.scatter(
                    metrics,
                    x='final_score',
                    y='total_revenue_at_risk',
                    size='total_reviews',
                    color='priority',
                    hover_data=['product', 'action'],
                    labels={'final_score': 'Final Priority Score', 'total_revenue_at_risk': 'Revenue at Risk ($)'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Action recommendations
            st.divider()
            st.subheader("📋 Recommended Actions")
            
            for action_type in ['Immediate Fix Required', 'Investigate Root Cause', 'Improve Product Experience', 'Respond to Customers', 'Monitor']:
                action_products = metrics[metrics['action'] == action_type]
                
                if len(action_products) > 0:
                    with st.expander(f"🔔 {action_type} ({len(action_products)} products)"):
                        for _, row in action_products.iterrows():
                            st.write(f"""
                            **{row['product']}**
                            - Final Score: {row['final_score']:.3f}
                            - Avg Rating: {row['avg_rating']:.2f}
                            - Reviews: {row['total_reviews']}
                            - Revenue at Risk: ${row['total_revenue_at_risk']:.0f}
                            """)
        else:
            st.info("👈 Use the Data Ingestion tab to fetch and process reviews first.")
    
    # ===== TAB 4: ABOUT =====
    with tab4:
        st.header("About This Application")
        
        st.markdown("""
        ## 🎯 Purpose
        The **Review Intelligence Engine** analyzes customer reviews to identify:
        - Which customers are most valuable
        - Which issues are most severe
        - Which products need immediate attention
        
        ## 🔄 How It Works
        
        1. **Data Ingestion** — Fetches reviews from API with retry logic
        2. **Preprocessing** — Handles missing values, applies log scaling, normalizes features
        3. **Feature Engineering** — Creates severity, recency, and sentiment features
        4. **Scoring** — Computes customer importance and review impact scores
        5. **Aggregation** — Groups reviews by product, computes business metrics
        6. **Decision Making** — Recommends actions based on data
        
        ## 📊 Key Metrics
        
        - **CIS (Customer Importance Score)** — How valuable the customer is (0-1)
        - **Impact Score** — How much the review matters to the business (0-1)
        - **Final Score** — Combined business priority metric
        - **PPS (Product Priority Score)** — Product-level importance
        
        ## 🛡️ Features
        
        ✅ Exponential backoff retry logic for API failures
        ✅ 5-minute smart caching to reduce API calls
        ✅ Comprehensive error handling and logging
        ✅ Data validation at every step
        ✅ Mobile-responsive dashboard
        ✅ Performance-optimized operations
        
        ## 🚀 Deployment Options
        
        **Free Platforms:**
        - **Streamlit Cloud** — Deploy directly on https://streamlit.io
        - **Render** — Free tier with 750 hours/month
        - **Railway** — $5/month free tier
        - **Vercel** — For frontend (if separate)
        - **Netlify** — For frontend (if separate)
        
        ## 🧪 Testing
        
        Run tests with:
        ```bash
        pip install pytest pytest-cov
        pytest tests/ -v --cov=services
        ```
        
        ## 📝 Security Notes
        
        - API endpoints are called server-side
        - No sensitive data exposed in frontend
        - Input data is validated at every step
        - Logging captures errors without exposing sensitive info
        
        ## 📞 Support
        For issues, check the logs or contact the development team.
        """)


if __name__ == "__main__":
    main()
