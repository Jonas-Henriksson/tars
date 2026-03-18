"""Morning news brief — external business events relevant to role and company.

Pulls in recent news and events relevant to:
- SKF and bearing industry
- Key competitors and market trends
- Supply chain and manufacturing sector
- Technology trends in industrial automation

Classifies by relevance, impact, and need-to-react.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent / "morning_news_cache.json"

# News search queries organized by category
_NEWS_CATEGORIES = {
    "company": {
        "label": "SKF & Industry",
        "queries": [
            "SKF Group news",
            "bearing industry market news",
            "SKF competitors Schaeffler Timken NTN NSK",
        ],
        "icon": "building",
    },
    "market": {
        "label": "Market & Economy",
        "queries": [
            "European manufacturing sector news",
            "industrial sector economic outlook",
            "global supply chain disruptions",
        ],
        "icon": "chart",
    },
    "technology": {
        "label": "Technology & Innovation",
        "queries": [
            "predictive maintenance manufacturing technology",
            "industrial IoT automation news",
            "AI manufacturing industry applications",
        ],
        "icon": "cpu",
    },
    "sustainability": {
        "label": "Sustainability & ESG",
        "queries": [
            "manufacturing sustainability ESG regulations Europe",
            "circular economy industrial sector",
        ],
        "icon": "leaf",
    },
}

_CLASSIFY_PROMPT = """\
You are a news analyst for the CEO of SKF, a global bearing and industrial company.

Classify these news items by relevance and required action. Return ONLY valid JSON.

NEWS ITEMS:
{news_items}

For each item, assess:
- relevance: "high" (directly affects SKF/industry), "medium" (relevant context), "low" (tangential)
- impact: "high" (could affect strategy/operations), "medium" (worth monitoring), "low" (informational)
- action: "react" (needs CEO attention/decision), "monitor" (track development), "note" (awareness only)
- summary: 1-sentence executive summary (max 20 words)
- category: company|market|technology|sustainability

Only include items rated medium or high relevance. Skip low-relevance items entirely.

Return JSON array:
[{{
  "title": "Original title",
  "summary": "Brief executive summary",
  "relevance": "high|medium",
  "impact": "high|medium|low",
  "action": "react|monitor|note",
  "category": "company|market|technology|sustainability",
  "source": "source name"
}}]
"""


def _load_cache() -> dict[str, Any]:
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"items": [], "generated_at": None, "date": None}


def _save_cache(data: dict[str, Any]) -> None:
    _CACHE_FILE.write_text(json.dumps(data, indent=2, default=str))


def _get_llm_client():
    try:
        from config import ANTHROPIC_API_KEY
        if not ANTHROPIC_API_KEY:
            return None
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception:
        return None


async def _search_news(query: str) -> list[dict[str, str]]:
    """Search for recent news using DuckDuckGo."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query + " news 2026", "format": "json", "no_html": "1"},
            )
            data = resp.json()
            results = []
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:120],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                    })
            if data.get("Abstract"):
                results.insert(0, {
                    "title": data.get("Heading", query),
                    "snippet": data["Abstract"][:300],
                    "url": data.get("AbstractURL", ""),
                })
            return results
    except Exception as e:
        logger.warning("News search failed for '%s': %s", query, e)
        return []


async def generate_morning_brief() -> dict[str, Any]:
    """Generate the morning news brief.

    Searches for recent news, classifies by relevance and impact,
    and returns structured brief for the CEO.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check cache — only regenerate once per day
    cache = _load_cache()
    if cache.get("date") == today and cache.get("items"):
        return {
            "items": cache["items"],
            "generated_at": cache["generated_at"],
            "cached": True,
            "categories": {k: v["label"] for k, v in _NEWS_CATEGORIES.items()},
        }

    # Gather news from all categories
    all_items = []
    for cat_key, cat_info in _NEWS_CATEGORIES.items():
        for query in cat_info["queries"][:2]:  # limit queries per category
            results = await _search_news(query)
            for r in results:
                r["category"] = cat_key
                r["category_label"] = cat_info["label"]
            all_items.extend(results)

    if not all_items:
        result = {
            "items": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
            "message": "No news results available",
            "categories": {k: v["label"] for k, v in _NEWS_CATEGORIES.items()},
        }
        return result

    # Classify with LLM
    client = _get_llm_client()
    classified_items = []

    if client:
        news_text = "\n".join(
            f"- [{item.get('category', '')}] {item['title']}" +
            (f"\n  {item['snippet'][:200]}" if item.get("snippet") else "")
            for item in all_items[:20]
        )
        prompt = _CLASSIFY_PROMPT.format(news_items=news_text)

        try:
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            classified_items = json.loads(text)
        except Exception as e:
            logger.warning("News classification failed: %s", e)

    if not classified_items:
        # Fall back to unclassified items
        classified_items = [
            {
                "title": item["title"][:100],
                "summary": item.get("snippet", "")[:100],
                "relevance": "medium",
                "impact": "medium",
                "action": "note",
                "category": item.get("category", "market"),
                "source": item.get("url", ""),
            }
            for item in all_items[:10]
        ]

    # Sort: react first, then monitor, then note. High relevance first.
    action_order = {"react": 0, "monitor": 1, "note": 2}
    relevance_order = {"high": 0, "medium": 1, "low": 2}
    classified_items.sort(key=lambda x: (
        action_order.get(x.get("action", "note"), 3),
        relevance_order.get(x.get("relevance", "low"), 3),
    ))

    # Cache the results
    result = {
        "items": classified_items[:15],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
        "date": today,
        "categories": {k: v["label"] for k, v in _NEWS_CATEGORIES.items()},
    }
    _save_cache({"items": classified_items[:15], "generated_at": result["generated_at"], "date": today})

    return result


def get_cached_brief() -> dict[str, Any]:
    """Return cached morning brief without regenerating."""
    cache = _load_cache()
    return {
        "items": cache.get("items", []),
        "generated_at": cache.get("generated_at"),
        "cached": True,
        "categories": {k: v["label"] for k, v in _NEWS_CATEGORIES.items()},
    }
