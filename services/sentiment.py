# services/sentiment.py
"""
AI-powered sentiment analysis for RIE v2.0
- Uses Groq with qwen/qwen3-32b
- Strong prompt to prevent <think> tags
- Loads API key from .env
- Supports batching + caching
"""

import os
import re
import requests
from typing import List, Optional
from dotenv import load_dotenv

from utils.logger import log_event, log_warning, get_logger
from utils.cache import get_cache

logger = get_logger("sentiment")

# Load environment variables
load_dotenv()

# ================== CONFIG ==================
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "qwen/qwen3-32b"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

CACHE_TTL = 7200  # 2 hours


def _batch_sentiment_groq(texts: List[str]) -> List[float]:
    """Batch sentiment analysis using Groq with strict prompt"""
    if not GROQ_API_KEY or not texts:
        log_warning("GROQ_KEY_MISSING", "GROQ_API_KEY not found in .env file")
        return [0.0] * len(texts)

    cache = get_cache()
    cache_key = f"batch_sent_groq_{hash(tuple(sorted(t[:200] for t in texts)))}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Truncate reviews to avoid token limit issues
    truncated = [t[:700] if isinstance(t, str) else "" for t in texts]

    # Strong system prompt to prevent thinking tags
    system_prompt = (
        "You are an expert sentiment analyst. "
        "For every review, respond with ONLY a single number between -1.0 and +1.0. "
        "Do not output any text, explanations, reasoning, <think> tags, or extra formatting. "
        "One number per review, one per line. Be extremely concise."
    )

    user_prompt = "\n---\n".join(truncated)

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
                "temperature": 0.0,      # Very low for consistent output
                "max_tokens": 1024,
                "stop": ["\n\n"]         # Helps prevent rambling
            },
            timeout=18
        )
        response.raise_for_status()

        raw_output = response.json()["choices"][0]["message"]["content"].strip()

        # Parse numbers from output
        scores = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            # Extract first floating point number
            match = re.search(r"[-+]?\d*\.\d+|\d+", line)
            if match:
                score = float(match.group())
                scores.append(max(-1.0, min(1.0, score)))
            else:
                scores.append(0.0)

        # Fill missing scores if any
        while len(scores) < len(texts):
            scores.append(0.0)

        cache.set(cache_key, scores)
        log_event("BATCH_SENTIMENT_SUCCESS", {"model": GROQ_MODEL, "count": len(texts)})
        return scores

    except Exception as e:
        log_warning("GROQ_BATCH_FAILED", str(e))
        return [0.0] * len(texts)


def get_ai_sentiment(review_text: str) -> float:
    """Get sentiment score for a single review."""
    if not review_text or not isinstance(review_text, str) or not review_text.strip():
        return 0.0

    cache = get_cache()
    cache_key = f"sent_single_{hash(review_text[:500])}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    score = _batch_sentiment_groq([review_text])[0]
    cache.set(cache_key, score)
    return score


def sentiment_to_pipeline_score(raw_score: float) -> float:
    return max(0.0, min(1.0, (raw_score + 1.0) / 2.0))


def has_groq_key() -> bool:
    return bool(GROQ_API_KEY and GROQ_API_KEY.strip())