"""Downstream Groq connector for product-level insights.

This module is intentionally isolated from scoring, aggregation, and ML code.
It only consumes already-computed aggregated product metrics and returns
optional insight columns for dashboard display.
"""

import json
import os
from typing import Any, Dict, Optional

import pandas as pd
import requests

from utils.cache import get_cache
from utils.logger import log_event, log_warning

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "qwen/qwen3-32b"


def _safe_float(value: Any) -> float:
    """Convert values to float without raising."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_llm_payload(row: pd.Series) -> Dict[str, Any]:
    """Create the downstream LLM payload from aggregated metrics only."""
    payload = {
        "product": str(row.get("product", "Unknown")),
        "total_reviews": int(_safe_float(row.get("total_reviews", 0))),
        "avg_rating": round(_safe_float(row.get("avg_rating", 0.0)), 3),
        "negative_ratio": round(_safe_float(row.get("negative_ratio", 0.0)), 4),
        "total_impact": round(_safe_float(row.get("total_impact", 0.0)), 4),
        "total_revenue_at_risk": round(_safe_float(row.get("total_revenue_at_risk", 0.0)), 2),
        "final_score": round(_safe_float(row.get("final_score", 0.0)), 4),
        "quadrant": str(row.get("quadrant", "Unknown")),
        "priority": str(row.get("priority", "Unknown")),
        "action": str(row.get("action", "Unknown")),
    }

    if "risk_probability" in row.index:
        payload["risk_probability"] = round(_safe_float(row.get("risk_probability", 0.0)), 4)
    if "risk_category" in row.index:
        payload["risk_category"] = str(row.get("risk_category", "Unknown"))

    return payload


def _fallback_insight(payload: Dict[str, Any]) -> Dict[str, str]:
    """Generate a deterministic fallback insight without any network call."""
    revenue = payload.get("total_revenue_at_risk", 0.0)
    negative_ratio = payload.get("negative_ratio", 0.0)
    risk_probability = payload.get("risk_probability", 0.0)
    action = payload.get("action", "Monitor")

    summary = (
        f"{payload['product']} is in {payload['quadrant']} with priority "
        f"{payload['priority']} and final score {payload['final_score']:.3f}."
    )
    driver = (
        f"Revenue at risk is INR {revenue:,.0f}, negative ratio is {negative_ratio:.1%}, "
        f"and ML risk probability is {risk_probability:.1%}."
    )
    recommendation = f"Recommended action remains: {action}."

    return {
        "llm_summary": summary,
        "llm_driver": driver,
        "llm_recommendation": recommendation,
        "llm_source": "rule_based",
        "llm_payload": json.dumps(payload, sort_keys=True),
    }


def _call_groq(payload: Dict[str, Any], api_key: str) -> Dict[str, str]:
    """Call Groq using aggregated product metrics only."""
    system_prompt = (
        "You are a product analytics assistant. "
        "Use only the provided aggregated metrics. "
        "Do not infer from raw reviews, customer text, or hidden data. "
        "Return only valid JSON with keys summary, driver, recommendation."
    )

    user_prompt = (
        "Analyze this product using aggregated metrics only and return JSON.\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )

    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 300,
        },
        timeout=20,
    )
    response.raise_for_status()

    raw_content = response.json()["choices"][0]["message"]["content"].strip()
    parsed = json.loads(raw_content)

    return {
        "llm_summary": str(parsed.get("summary", "")).strip(),
        "llm_driver": str(parsed.get("driver", "")).strip(),
        "llm_recommendation": str(parsed.get("recommendation", "")).strip(),
        "llm_source": "groq",
        "llm_payload": json.dumps(payload, sort_keys=True),
    }


def enrich_products_with_llm_insights(
    product_df: pd.DataFrame,
    api_key: Optional[str] = None,
    max_products: int = 5,
) -> pd.DataFrame:
    """Attach downstream LLM insights to the top products.

    The returned DataFrame keeps all existing columns unchanged and only adds:
    llm_summary, llm_driver, llm_recommendation, llm_source, llm_payload
    """
    if product_df is None or product_df.empty:
        return product_df

    enriched_df = product_df.copy()
    new_columns = [
        "llm_summary",
        "llm_driver",
        "llm_recommendation",
        "llm_source",
        "llm_payload",
    ]
    for column in new_columns:
        if column not in enriched_df.columns:
            enriched_df[column] = ""

    resolved_key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
    cache = get_cache()

    max_products = max(0, min(int(max_products), len(enriched_df)))
    if max_products == 0:
        return enriched_df

    ranked_df = enriched_df.sort_values("final_score", ascending=False).head(max_products)

    for row_index, row in ranked_df.iterrows():
        payload = _build_llm_payload(row)
        cache_key = f"llm_product_insight::{json.dumps(payload, sort_keys=True)}"
        cached = cache.get(cache_key)

        if cached is None:
            try:
                if resolved_key:
                    cached = _call_groq(payload, resolved_key)
                    log_event("LLM_OUTPUT_READY", {"product": payload["product"], "source": "groq"})
                else:
                    cached = _fallback_insight(payload)
                    log_event("LLM_OUTPUT_READY", {"product": payload["product"], "source": "rule_based"})
            except Exception as exc:
                log_warning("LLM_INSIGHT_FAILED", str(exc), {"product": payload["product"]})
                cached = _fallback_insight(payload)

            cache.set(cache_key, cached)

        for column in new_columns:
            enriched_df.at[row_index, column] = cached.get(column, "")

    return enriched_df
