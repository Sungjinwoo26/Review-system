from __future__ import annotations
"""
Review Intelligence Engine - Professional Dashboard for Product Managers
"""

import html as _html
import io
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, Optional, List

import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go

from services.ingestion import load_data
from services.scoring_engine import (
    apply_scoring_pipeline,
    aggregate_to_products,
    classify_quadrants,
)
from services.decision import make_decisions
from utils.error_handler import safe_divide
from utils.logger import log_warning

st.set_page_config(
    page_title="Review Intelligence Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

ISSUE_CATEGORIES = {
    "Delivery & Shipping": [
        "delivery", "shipping", "courier", "late", "delay", "arrived", "transit",
        "dispatch", "package", "parcel", "logistics", "not delivered", "missing"
    ],
    "Product Quality": [
        "quality", "broken", "damaged", "defective", "fake", "counterfeit",
        "poor quality", "bad quality", "not working", "stopped working", "malfunction",
        "cheap", "flimsy", "fell apart", "broke"
    ],
    "Packaging": [
        "packaging", "packed", "box", "wrapper", "seal", "open", "tampered",
        "crushed", "dented", "torn", "leaking"
    ],
    "Customer Support": [
        "support", "customer service", "refund", "return", "exchange", "response",
        "helpline", "agent", "complaint", "resolved", "unresponsive", "ignored",
        "no reply", "escalate"
    ],
    "Wrong / Missing Item": [
        "wrong item", "wrong product", "different product", "missing item",
        "incomplete", "not what i ordered", "substituted", "incorrect"
    ],
    "Pricing & Value": [
        "overpriced", "expensive", "not worth", "value for money", "costly",
        "price", "cheaper", "discount", "money back"
    ],
    "App / Website": [
        "app", "website", "glitch", "crash", "loading", "error", "login",
        "checkout", "payment", "interface", "slow", "bug"
    ],
}


def tag_issue_categories(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "Uncategorized"
    text_lower = text.lower()
    matched = [cat for cat, keywords in ISSUE_CATEGORIES.items() if any(kw in text_lower for kw in keywords)]
    return ", ".join(matched) if matched else "Uncategorized"


def enrich_with_categories(df: pd.DataFrame) -> pd.DataFrame:
    text_col = next((c for c in ["review_text", "text", "comment"] if c in df.columns), None)
    if text_col:
        df = df.copy()
        df["issue_category"] = df[text_col].apply(tag_issue_categories)
    return df


def init_session_state():
    for key in ['raw_data', 'processed_data', 'aggregated_data', 'data_fetched', 'last_refresh']:
        if key not in st.session_state:
            st.session_state[key] = None if key != 'data_fetched' else False

init_session_state()

st.title("📊 Review Intelligence Engine")
st.markdown("*Helping Product Managers turn reviews into clear decisions*")

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
    groq_key = st.text_input("Groq API Key (Optional)", type="password", help="Leave empty for rule-based recommendations only")
    st.divider()

    col1, col2 = st.columns(2)
    fetch_btn = col1.button("🔄 Load & Analyze Data", type="primary", use_container_width=True)
    clear_btn = col2.button("🗑️ Clear Cache", use_container_width=True)

    if clear_btn:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def get_available_products(df):
    if df is None or df.empty:
        return []
    for col in ['product', 'product_name', 'product_id']:
        if col in df.columns:
            products = df[col].fillna("Unknown").astype(str).str.strip().unique()
            return sorted([p for p in products if p and p != "Unknown"])
    return []


def get_date_range(df):
    if df is None or df.empty or 'review_date' not in df.columns:
        return datetime.now() - timedelta(days=30), datetime.now()
    try:
        df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
        return df['review_date'].min().to_pydatetime(), df['review_date'].max().to_pydatetime()
    except:
        return datetime.now() - timedelta(days=30), datetime.now()


def apply_filters(df, products=None, date_range=None, severity_threshold=0.0):
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


@st.cache_data
def render_kpis(review_df, product_df):
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
        st.metric("Expected Revenue at Risk", f"₹{total_weighted:,.0f}", delta=f"₹{total_hard:,.0f} Max Exposure", delta_color="inverse")
    with col2:
        st.metric("Total Reviews", f"{total_reviews:,}")
    with col3:
        st.metric("% Negative Reviews", f"{negative_pct:.1f}%")
    with col4:
        st.metric("Top Risk Product", top_product)


def render_filters(raw_df):
    if raw_df is None or raw_df.empty:
        return [], None, 0.2
    st.subheader("🔍 Filter Data")
    col1, col2, col3 = st.columns(3)
    with col1:
        available = get_available_products(raw_df)
        selected_products = st.multiselect("Select Products", options=available, default=available[:5] if available else [])
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
                date_range = (datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time()))
    with col3:
        severity_threshold = st.slider("Severity Threshold", 0.0, 1.0, 0.2, 0.05)
    return selected_products, date_range, severity_threshold


def render_quadrant(aggregated_df):
    if aggregated_df is None or aggregated_df.empty:
        st.warning("No data available for quadrant chart")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=aggregated_df['negative_ratio'],
        y=aggregated_df['total_revenue_at_risk'],
        mode='markers',
        marker=dict(size=aggregated_df['final_score'] * 30, color=aggregated_df['final_score'],
                    colorscale='RdYlGn_r', showscale=True, colorbar=dict(title="Priority Score")),
        text=aggregated_df['product'],
        hovertemplate="<b>%{text}</b><br>Negative Ratio: %{x:.1%}<br>Revenue at Risk: ₹%{y:,.0f}<extra></extra>"
    ))
    fig.update_layout(title="📊 Product Priority Quadrant", xaxis_title="Negative Review Ratio",
                      yaxis_title="Revenue at Risk (₹)", height=600, plot_bgcolor='rgba(240,240,240,0.5)')
    st.plotly_chart(fig, use_container_width=True)


PRIORITY_COLORS = {
    "High":   ("#fee2e2", "#dc2626", "🔴"),
    "Medium": ("#fef9c3", "#ca8a04", "🟡"),
    "Low":    ("#dcfce7", "#16a34a", "🟢"),
}
ACTION_ICONS = {
    "Immediate Fix Required":    "🚨",
    "Investigate Root Cause":    "🔍",
    "Improve Product Experience":"✨",
    "Monitor":                   "👁️",
}


def _parse_ai_insight(row) -> dict:
    import json as _json

    ai_insight = row.get('ai_insight')
    if ai_insight and isinstance(ai_insight, str) and ai_insight.strip():
        try:
            parsed = _json.loads(ai_insight)
            if isinstance(parsed, dict):
                return {
                    "root_cause": str(parsed.get("root_cause", "")).strip(),
                    "action":     str(parsed.get("action", "")).strip(),
                    "impact":     str(parsed.get("impact", "")).strip(),
                    "kpi":        str(parsed.get("kpi", "")).strip(),
                    "raw_fallback": False,
                }
        except Exception:
            pass

    return {
        "root_cause": "Multiple customer complaints detected.",
        "action": str(row.get('action', 'Review patterns and prioritize fixes.')),
        "impact": f"Revenue at risk: ₹{row.get('total_revenue_at_risk', 0):,.0f}",
        "kpi": "Negative review rate & CSAT",
        "raw_fallback": True,
    }


def render_table(aggregated_df):
    if aggregated_df is None or aggregated_df.empty:
        st.warning("No data available")
        return

    # ── Compact summary table ──────────────────────────────────────────────
    st.subheader("🎯 Product Priority Overview")
    display_df = aggregated_df.copy()
    cols_to_display = ['product', 'total_reviews', 'avg_rating', 'total_revenue_at_risk', 'priority', 'action']
    available_cols = [col for col in cols_to_display if col in display_df.columns]
    display_df = display_df[available_cols].rename(columns={
        'product': 'Product', 'total_reviews': 'Reviews', 'avg_rating': 'Avg Rating',
        'total_revenue_at_risk': 'Revenue at Risk', 'priority': 'Priority', 'action': 'Decision'
    })
    if 'Revenue at Risk' in display_df.columns:
        display_df['Revenue at Risk'] = '₹' + display_df['Revenue at Risk'].round(0).astype(int).astype(str)
    if 'Avg Rating' in display_df.columns:
        display_df['Avg Rating'] = display_df['Avg Rating'].round(2)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── AI Insight Cards ───────────────────────────────────────────────────
    st.subheader("🤖 AI Insights by Product")

    if 'ai_insight' not in aggregated_df.columns:
        st.info("No AI insights available — add a Groq API key for better recommendations.")
        return

    top_df = aggregated_df.head(8) if len(aggregated_df) > 8 else aggregated_df

    # Build all cards into one HTML document and render via components.html
    # This avoids st.markdown unsafe_allow_html rendering issues in newer Streamlit versions
    all_cards_html = ""

    for _, row in top_df.iterrows():
        product_name = str(row.get('product', '—'))
        priority = str(row.get('priority', 'Low'))
        action_label = str(row.get('action', 'Monitor'))

        rev_at_risk = float(row.get('total_revenue_at_risk', 0))
        avg_rating = float(row.get('avg_rating', 0))
        total_rev = int(row.get('total_reviews', 0))

        bg, border, dot = PRIORITY_COLORS.get(priority, ("#f3f4f6", "#6b7280", "⚪"))
        action_icon = ACTION_ICONS.get(action_label, "📋")

        rec = _parse_ai_insight(row)

        root_cause_safe = _html.escape(str(rec.get('root_cause', '—')))
        action_safe     = _html.escape(str(rec.get('action', '—')))
        impact_safe     = _html.escape(str(rec.get('impact', '—')))
        kpi_safe        = _html.escape(str(rec.get('kpi', '—')))
        product_safe    = _html.escape(product_name)
        priority_safe   = _html.escape(priority)
        action_label_safe = _html.escape(action_label)

        ai_badge = "<span style='font-size:0.7rem;color:#9ca3af;'>(rule-based)</span>" if rec.get("raw_fallback", True) else ""

        all_cards_html += f"""
        <div style="
            background:{bg};
            border-left: 5px solid {border};
            border-radius: 10px;
            padding: 1.2rem;
            margin-bottom: 1.2rem;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        ">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.5rem;">
                <div>
                    <span style="font-size:1.2rem; font-weight:700; color:#111827;">{product_safe}</span>
                    <span style="
                        font-size:0.75rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;
                        background:{border}22; color:{border}; border-radius:20px; padding:3px 11px; margin-left:8px;
                    ">{dot} {priority_safe}</span>
                </div>
                <div style="font-size:0.82rem; color:#6b7280; text-align:right;">
                    {action_icon} <b>{action_label_safe}</b><br>
                    &#11088; {avg_rating:.1f} &bull; {total_rev:,} reviews &bull; &#8377;{rev_at_risk:,.0f} at risk
                </div>
            </div>

            <hr style="border:none; border-top:1px solid {border}40; margin:0.9rem 0;">

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem 1.5rem;">
                <div>
                    <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{border}; margin-bottom:4px;">
                        &#128269; Root Cause {ai_badge}
                    </div>
                    <div style="font-size:0.9rem; line-height:1.5; color:#1f2937;">{root_cause_safe}</div>
                </div>

                <div>
                    <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{border}; margin-bottom:4px;">
                        &#9989; Recommended Action
                    </div>
                    <div style="font-size:0.9rem; line-height:1.5; color:#1f2937;">{action_safe}</div>
                </div>

                <div>
                    <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{border}; margin-bottom:4px;">
                        &#128200; Expected Impact
                    </div>
                    <div style="font-size:0.9rem; line-height:1.5; color:#1f2937;">{impact_safe}</div>
                </div>

                <div>
                    <div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{border}; margin-bottom:4px;">
                        &#127919; KPI to Track
                    </div>
                    <div style="font-size:0.9rem; font-weight:600; color:{border};">{kpi_safe}</div>
                </div>
            </div>
        </div>
        """

    # Wrap in a full HTML document for components.html
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background: transparent;
            }}
        </style>
    </head>
    <body>
        {all_cards_html}
    </body>
    </html>
    """

    # Calculate dynamic height: ~220px per card
    card_height = max(220 * len(top_df) + 40, 300)
    components.html(full_html, height=card_height, scrolling=False)


# ── TREND OVER TIME ──────────────────────────────────────────────────────────
def render_trend_over_time(review_df):
    if review_df is None or review_df.empty or 'review_date' not in review_df.columns:
        st.info("No date column found — trend chart unavailable.")
        return
    df = review_df.copy()
    df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
    df = df.dropna(subset=['review_date'])
    if df.empty:
        st.info("No valid dates found.")
        return
    df['week'] = df['review_date'].dt.to_period('W').apply(lambda r: r.start_time)
    product_col = next((c for c in ['product', 'product_name', 'product_id'] if c in df.columns), None)
    if not product_col:
        return

    tab_neg, tab_rating, tab_volume = st.tabs(["📉 Negative %", "⭐ Avg Rating", "📦 Review Volume"])

    with tab_neg:
        if 'is_negative' in df.columns:
            trend = df.groupby([product_col, 'week'])['is_negative'].mean().reset_index()
            trend.columns = ['product', 'week', 'negative_pct']
            trend['negative_pct'] *= 100
            top_prods = trend.groupby('product')['negative_pct'].mean().nlargest(8).index.tolist()
            fig = px.line(trend[trend['product'].isin(top_prods)], x='week', y='negative_pct',
                          color='product', title='Negative Review % by Product (Weekly)', markers=True,
                          labels={'week': 'Week', 'negative_pct': 'Negative %', 'product': 'Product'})
            fig.update_layout(yaxis_ticksuffix='%', height=420)
            st.plotly_chart(fig, use_container_width=True)

    with tab_rating:
        if 'rating' in df.columns:
            trend_r = df.groupby([product_col, 'week'])['rating'].mean().reset_index()
            trend_r.columns = ['product', 'week', 'avg_rating']
            top_prods_r = trend_r.groupby('product')['avg_rating'].mean().nsmallest(8).index.tolist()
            fig = px.line(trend_r[trend_r['product'].isin(top_prods_r)], x='week', y='avg_rating',
                          color='product', title='Avg Rating by Product (Weekly — worst 8)', markers=True,
                          labels={'week': 'Week', 'avg_rating': 'Avg Rating', 'product': 'Product'})
            fig.update_layout(yaxis_range=[1, 5], height=420)
            st.plotly_chart(fig, use_container_width=True)

    with tab_volume:
        trend_v = df.groupby([product_col, 'week']).size().reset_index(name='review_count')
        trend_v.columns = ['product', 'week', 'review_count']
        top_prods_v = trend_v.groupby('product')['review_count'].sum().nlargest(8).index.tolist()
        fig = px.bar(trend_v[trend_v['product'].isin(top_prods_v)], x='week', y='review_count',
                     color='product', title='Review Volume by Product (Weekly, top 8)', barmode='stack',
                     labels={'week': 'Week', 'review_count': 'Reviews', 'product': 'Product'})
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)


# ── REVIEW DRILL-DOWN ────────────────────────────────────────────────────────
def render_drilldown(review_df, aggregated_df):
    if review_df is None or review_df.empty:
        st.info("No review data available.")
        return
    product_col = next((c for c in ['product', 'product_name', 'product_id'] if c in review_df.columns), None)
    if not product_col:
        return

    available_products = get_available_products(review_df)
    selected = st.selectbox("Select a product to drill down", options=available_products, key="drilldown_product")
    product_reviews = review_df[review_df[product_col] == selected].copy()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Reviews", len(product_reviews))
    if 'rating' in product_reviews.columns:
        m2.metric("Avg Rating", f"{product_reviews['rating'].mean():.2f} ★")
    if 'is_negative' in product_reviews.columns:
        m3.metric("Negative %", f"{product_reviews['is_negative'].mean() * 100:.1f}%")
    if not aggregated_df.empty and 'product' in aggregated_df.columns:
        row = aggregated_df[aggregated_df['product'] == selected]
        if not row.empty and 'total_revenue_at_risk' in row.columns:
            m4.metric("Revenue at Risk", f"₹{row['total_revenue_at_risk'].values[0]:,.0f}")

    if 'issue_category' in product_reviews.columns:
        st.markdown("**Issue Category Breakdown**")
        all_cats = []
        for cats in product_reviews['issue_category'].dropna():
            all_cats.extend([c.strip() for c in cats.split(",") if c.strip()])
        if all_cats:
            cat_df = pd.Series(all_cats).value_counts().reset_index()
            cat_df.columns = ['Category', 'Count']
            fig = px.bar(cat_df, x='Count', y='Category', orientation='h',
                         color='Count', color_continuous_scale='Reds',
                         title=f'Issue Categories for {selected}')
            fig.update_layout(height=300, showlegend=False, yaxis=dict(autorange='reversed'))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Top Complaints (Worst Reviews)**")
    text_col = next((c for c in ['review_text', 'text', 'comment'] if c in product_reviews.columns), None)
    sort_col = next((c for c in ['rating', 'sentiment_score', 'impact_score'] if c in product_reviews.columns), None)
    if text_col:
        display_cols = [c for c in ['rating', text_col, 'issue_category', 'review_date'] if c in product_reviews.columns]
        worst = product_reviews.sort_values(by=sort_col).head(10) if sort_col else product_reviews.head(10)
        st.dataframe(worst[display_cols].reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.info("No review text column found.")


# ── CATEGORY / ISSUE ANALYSIS ────────────────────────────────────────────────
def render_category_analysis(review_df):
    if review_df is None or review_df.empty or 'issue_category' not in review_df.columns:
        st.info("Category data not available.")
        return
    product_col = next((c for c in ['product', 'product_name', 'product_id'] if c in review_df.columns), None)

    col_left, col_right = st.columns(2)

    with col_left:
        all_cats = []
        for cats in review_df['issue_category'].dropna():
            all_cats.extend([c.strip() for c in cats.split(",") if c.strip()])
        if all_cats:
            cat_df = pd.Series(all_cats).value_counts().reset_index()
            cat_df.columns = ['Category', 'Count']
            fig = px.pie(cat_df, values='Count', names='Category', title='Share of Issue Categories',
                         color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        if product_col:
            exploded = review_df[[product_col, 'issue_category']].copy()
            exploded['issue_category'] = exploded['issue_category'].str.split(', ')
            exploded = exploded.explode('issue_category')
            exploded = exploded[exploded['issue_category'] != 'Uncategorized']
            pivot = exploded.groupby([product_col, 'issue_category']).size().unstack(fill_value=0)
            top10 = pivot.sum(axis=1).nlargest(10).index
            pivot = pivot.loc[top10]
            if not pivot.empty:
                fig = px.imshow(pivot, color_continuous_scale='YlOrRd',
                                title='Complaint Heatmap (Top 10 Products)',
                                labels=dict(x='Issue Category', y='Product', color='Count'), aspect='auto')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)


# ── EXPORT ───────────────────────────────────────────────────────────────────
def build_excel_export(review_df, aggregated_df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        agg = aggregated_df.copy()
        for col in agg.select_dtypes(include='number').columns:
            agg[col] = agg[col].round(3)
        agg.to_excel(writer, sheet_name='Product Summary', index=False)

        text_col = next((c for c in ['review_text', 'text', 'comment'] if c in review_df.columns), None)
        cols = [c for c in ['product', 'rating', text_col, 'issue_category', 'is_negative', 'review_date'] if c and c in review_df.columns]
        review_df[cols].head(2000).to_excel(writer, sheet_name='Review Detail', index=False)

        if 'issue_category' in review_df.columns:
            all_cats = []
            for cats in review_df['issue_category'].dropna():
                all_cats.extend([c.strip() for c in cats.split(",") if c.strip()])
            cat_df = pd.Series(all_cats).value_counts().reset_index()
            cat_df.columns = ['Issue Category', 'Count']
            cat_df.to_excel(writer, sheet_name='Issue Categories', index=False)
    return output.getvalue()


def build_pdf_export(review_df, aggregated_df):
    try:
        from fpdf import FPDF
    except ImportError:
        return b""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Review Intelligence Engine - Report", ln=True, align='C')
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Key Metrics", ln=True)
    pdf.set_font("Helvetica", "", 10)
    total_rev = aggregated_df.get('total_revenue_at_risk', pd.Series([0])).sum() if not aggregated_df.empty else 0
    negative_pct = review_df.get('is_negative', pd.Series([0])).mean() * 100 if 'is_negative' in review_df.columns else 0
    pdf.cell(0, 6, f"Total Reviews: {len(review_df):,}", ln=True)
    pdf.cell(0, 6, f"Revenue at Risk: Rs {total_rev:,.0f}", ln=True)
    pdf.cell(0, 6, f"Negative Review %: {negative_pct:.1f}%", ln=True)
    pdf.cell(0, 6, f"Products Analyzed: {len(aggregated_df)}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Product Priority Summary", ln=True)
    col_labels = ['Product', 'Reviews', 'Avg Rating', 'Rev at Risk (Rs)', 'Priority']
    col_widths = [55, 22, 28, 45, 25]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    for label, width in zip(col_labels, col_widths):
        pdf.cell(width, 7, label, border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 8)

    display_map = [
        ('product', 55), ('total_reviews', 22), ('avg_rating', 28),
        ('total_revenue_at_risk', 45), ('priority', 25)
    ]
    for i, row in aggregated_df.head(30).iterrows():
        pdf.set_fill_color(245, 247, 255) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        for col, width in display_map:
            val = row.get(col, '')
            if col == 'total_revenue_at_risk':
                val = f"{float(val):,.0f}"
            elif col == 'avg_rating':
                val = f"{float(val):.2f}"
            else:
                val = str(val)[:30]
            pdf.cell(width, 6, val, border=1, fill=(i % 2 == 0))
        pdf.ln()

    if 'issue_category' in review_df.columns:
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Issue Category Breakdown", ln=True)
        pdf.set_font("Helvetica", "", 10)
        all_cats = []
        for cats in review_df['issue_category'].dropna():
            all_cats.extend([c.strip() for c in cats.split(",") if c.strip()])
        for cat, count in pd.Series(all_cats).value_counts().items():
            pct = count / len(all_cats) * 100
            pdf.cell(0, 6, f"  {cat}: {count} ({pct:.1f}%)", ln=True)

    return bytes(pdf.output())


def render_export_panel(review_df, aggregated_df):
    st.subheader("📥 Export Report")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Generate Excel Export", use_container_width=True):
            with st.spinner("Building Excel report..."):
                xlsx_bytes = build_excel_export(review_df, aggregated_df)
            st.download_button(
                label="⬇️ Download Excel (.xlsx)",
                data=xlsx_bytes,
                file_name=f"RIE_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    with col2:
        if st.button("📄 Generate PDF Report", use_container_width=True):
            with st.spinner("Building PDF report..."):
                pdf_bytes = build_pdf_export(review_df, aggregated_df)
            if pdf_bytes:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"RIE_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error("PDF generation failed — install fpdf2: pip install fpdf2")


# ── PIPELINE ─────────────────────────────────────────────────────────────────
def run_pipeline(df, groq_key=None):
    review_df = apply_scoring_pipeline(df, groq_key=groq_key)
    review_df = enrich_with_categories(review_df)
    product_df = aggregate_to_products(review_df)
    product_df = classify_quadrants(product_df)
    product_df = make_decisions(product_df, review_df, groq_key=groq_key)
    return review_df, product_df


def show_error(message):
    st.error(f"❌ {message}")
    st.stop()


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    if fetch_btn:
        try:
            with st.spinner("Loading data and analyzing..."):
                raw_df = load_data(input_mode=input_mode, api_url=api_url, api_key=api_key, uploaded_file=uploaded_file)
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

    st.divider()
    selected_products, date_range, severity_threshold = render_filters(raw_df)
    filtered_df = apply_filters(processed_df, selected_products, date_range, severity_threshold)

    if filtered_df.empty:
        st.warning("⚠️ No reviews match your filters")
        st.stop()

    if len(filtered_df) < len(processed_df):
        filtered_agg = aggregate_to_products(filtered_df)
        filtered_agg = classify_quadrants(filtered_agg)
        filtered_agg = make_decisions(filtered_agg, filtered_df, groq_key=st.session_state.get('groq_key'))
    else:
        filtered_agg = aggregated_df

    st.divider()
    st.subheader("📊 Key Performance Indicators")
    render_kpis(filtered_df, filtered_agg)

    st.divider()
    st.subheader("📈 Prioritization Analysis")
    render_quadrant(filtered_agg)

    st.divider()
    render_table(filtered_agg)

    st.divider()
    st.subheader("📅 Trend Over Time")
    render_trend_over_time(filtered_df)

    st.divider()
    st.subheader("🏷️ Issue Category Analysis")
    render_category_analysis(filtered_df)

    st.divider()
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Data Preview", "📈 Charts", "🔍 Review Drill-Down", "📥 Export", "ℹ️ About"
    ])

    with tab1:
        st.subheader("Review Data Preview")
        cols = [c for c in ['product', 'rating', 'review_text', 'issue_severity', 'issue_category'] if c in filtered_df.columns]
        st.dataframe(filtered_df[cols].head(20), use_container_width=True)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            if 'rating' in filtered_df.columns:
                st.subheader("Rating Distribution")
                rating_dist = filtered_df['rating'].value_counts().sort_index()
                fig = px.bar(x=rating_dist.index, y=rating_dist.values, labels={'x': 'Rating', 'y': 'Count'})
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            if 'impact_score' in filtered_df.columns:
                st.subheader("Impact Score Distribution")
                fig = px.histogram(filtered_df, x='impact_score')
                st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("🔍 Review Drill-Down by Product")
        render_drilldown(filtered_df, filtered_agg)

    with tab4:
        render_export_panel(filtered_df, filtered_agg)

    with tab5:
        st.markdown("""
        ### How to Use This Dashboard
        - **KPIs** — Revenue at risk, review count, negative %, top risk product.
        - **Prioritization Quadrant** — Spot products needing immediate action.
        - **Trend Over Time** — Weekly negative %, avg rating, and volume trends.
        - **Issue Category Analysis** — Auto-tagged complaint buckets with a heatmap.
        - **Review Drill-Down** (tab) — Drill into any product to see its worst reviews.
        - **Export** (tab) — Download Excel (3 sheets) or PDF summary report.

        **Recommendation**: Start with products that have high "Revenue at Risk".
        """)


if __name__ == "__main__":
    main()