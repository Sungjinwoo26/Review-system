# services/decision.py
"""
Decision & Recommendation Engine for RIE v2.0
Improved prompt for Qwen3-32B to remove <think> tags
"""

import os
import re
import pandas as pd
import requests
from typing import List, Optional
from dotenv import load_dotenv

from utils.cache import get_cache
from utils.logger import log_event, log_warning, logger

# Load .env file
load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "qwen/qwen3-32b"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def _get_top_complaints(review_df: pd.DataFrame, product_name: str, n: int = 4) -> List[str]:
    if review_df is None or review_df.empty or 'product' not in review_df.columns:
        return []

    product_reviews = review_df[review_df['product'] == product_name].copy()
    if product_reviews.empty:
        return []

    sort_cols = []
    if 'rating' in product_reviews.columns:
        sort_cols.append('rating')
    if 'sentiment_score' in product_reviews.columns:
        sort_cols.append('sentiment_score')

    if not sort_cols:
        return []

    worst_reviews = product_reviews.sort_values(by=sort_cols).head(n)
    text_col = 'review_text' if 'review_text' in worst_reviews.columns else None
    if not text_col:
        return []

    complaints = worst_reviews[text_col].dropna().astype(str).tolist()
    cleaned = []
    for c in complaints:
        c = c.strip()
        if len(c) > 120:
            c = c[:117] + "..."
        if c:
            cleaned.append(c)
    return cleaned


def generate_ai_recommendation(
    product_name: str,
    top_complaints: List[str],
    priority_score: float,
    revenue_at_risk: float = 0.0
) -> str:
    """Generate deep recommendation using Groq with improved prompt for Qwen3"""
    if not top_complaints:
        return "Monitor – No significant complaints detected."

    if not GROQ_API_KEY:
        log_warning("GROQ_KEY_MISSING", "Using fallback recommendation")
        return f"Immediate Fix Required – Revenue at risk: ₹{revenue_at_risk:,.0f}"

    cache = get_cache()
    complaints_hash = hash(tuple(sorted(top_complaints)))
    cache_key = f"deep_rec_{product_name}_{complaints_hash}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    complaints_text = "\n".join([f"• {c}" for c in top_complaints])

    # === STRONG PROMPT TO PREVENT <think> TAGS ===
    system_prompt = """You are a senior e-commerce Product Manager and CX strategist.
You give direct, concise, and actionable executive recommendations.
Rules you MUST follow:
- NEVER output <think>, </think>, or any thinking tags.
- NEVER show your reasoning process.
- NEVER say "I think", "Let me think", or explain how you arrived at the answer.
- Respond only with the final recommendation in plain, professional English.
- Be clear, specific, and business-focused."""

    user_prompt = f"""Product: **{product_name}**
Priority Score: **{priority_score:.3f}**
Revenue at Risk: **₹{revenue_at_risk:,.0f}**

Top customer complaints:
{complaints_text}

Provide a concise executive recommendation that covers:
1. Likely root cause
2. Specific action (who should do what and by when)
3. Expected revenue impact if fixed
4. One important KPI to track
5. No extra formatting, just simple lines, since this is the final output that would be displayed on the site, without any processing.

Be direct and actionable. /no_think"""

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1024
            },
            timeout=20
        )
        response.raise_for_status()
        
        raw_output = response.json()["choices"][0]["message"]["content"].strip()

        # === CLEANUP: Remove any leftover <think> tags ===
        cleaned = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL | re.IGNORECASE).strip()
        cleaned = re.sub(r'^(Let me think|Thinking step by step).*?\n', '', cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Final safety trim
        recommendation = cleaned.strip()

        if not recommendation:
            recommendation = "Immediate action recommended to address customer complaints."

        cache.set(cache_key, recommendation)
        log_event("DEEP_AI_RECOMMENDATION", {"product": product_name, "model": GROQ_MODEL})
        return recommendation

    except Exception as e:
        log_warning("DEEP_RECOMMENDATION_FAILED", str(e))
        return f"Immediate Fix Required – High revenue at risk (₹{revenue_at_risk:,.0f})"


def make_decisions(
    product_df: pd.DataFrame,
    review_df: Optional[pd.DataFrame] = None,
    groq_key: Optional[str] = None,
) -> pd.DataFrame:
    """Main decision function"""
    df = product_df.copy()
    if df.empty:
        return df

    def get_threshold(col, q=0.75):
        if len(df) < 2:
            return df[col].iloc[0] * 0.9 if len(df) > 0 else 0
        return df[col].quantile(q)

    high_rev_threshold = get_threshold('total_revenue_at_risk')
    high_impact_threshold = get_threshold('total_impact')
    high_neg_threshold = get_threshold('negative_ratio')
    low_rating_threshold = get_threshold('avg_rating', 0.25)

    def process_row(row):
        # Rule-based category
        if (row.get('total_revenue_at_risk', 0) >= high_rev_threshold and 
            row.get('negative_ratio', 0) >= high_neg_threshold):
            category = "Immediate Fix Required"
        elif row.get('total_impact', 0) >= high_impact_threshold:
            category = "Investigate Root Cause"
        elif row.get('avg_rating', 5) <= low_rating_threshold:
            category = "Improve Product Experience"
        else:
            category = "Monitor"

        # AI Recommendation
        recommendation = category
        if review_df is not None:
            complaints = _get_top_complaints(review_df, row['product'])
            recommendation = generate_ai_recommendation(
                product_name=row['product'],
                top_complaints=complaints,
                priority_score=row.get('final_score', 0),
                revenue_at_risk=row.get('total_revenue_at_risk', 0)
            )

        return pd.Series([recommendation, category])

    df[['action', 'category']] = df.apply(process_row, axis=1)

    # Priority assignment
    high_score_threshold = df['final_score'].quantile(0.75) if len(df) > 1 else df['final_score'].max()
    df['priority'] = df['final_score'].apply(
        lambda x: "High" if x >= high_score_threshold else 
                  "Medium" if x >= high_score_threshold * 0.5 else "Low"
    )

    return df.sort_values(by='final_score', ascending=False).reset_index(drop=True)


def has_groq_key() -> bool:
    """Helper to check if key is loaded"""
    return bool(GROQ_API_KEY and GROQ_API_KEY.strip())