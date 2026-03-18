"""External best-practices knowledge repository.

Pulls in frameworks, methodologies, and best practices from external
sources (web search) based on the topics discussed in meetings and tasks.
Builds a permanent, growing knowledge base of actionable reference material.

Examples:
- S&OP process design best practices
- KPI frameworks for manufacturing
- Change management models (Kotter, ADKAR)
- Supply chain transformation playbooks
- Internal communication frameworks
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KB_FILE = Path(__file__).parent.parent / "best_practices_kb.json"

# Topics mapped to specific search queries for best-practice enrichment
_TOPIC_SEARCH_MAP = {
    "planning": [
        "S&OP process best practices manufacturing",
        "integrated business planning framework",
    ],
    "finance": [
        "financial KPI framework manufacturing industry",
        "rolling forecast best practices",
    ],
    "operations": [
        "operational excellence framework lean manufacturing",
        "supply chain transformation playbook",
    ],
    "engineering": [
        "engineering excellence metrics best practices",
        "DevOps maturity model framework",
    ],
    "people": [
        "change management framework best practices Kotter ADKAR",
        "employee engagement strategy manufacturing",
    ],
    "sales": [
        "B2B sales excellence framework",
        "key account management best practices",
    ],
    "marketing": [
        "B2B marketing strategy framework manufacturing",
        "thought leadership content strategy industrial",
    ],
    "innovation": [
        "innovation management framework stage-gate",
        "R&D portfolio management best practices",
    ],
    "sustainability": [
        "ESG strategy framework manufacturing",
        "circular economy business model design",
    ],
    "customer-success": [
        "customer success framework B2B manufacturing",
        "NPS improvement strategy industrial",
    ],
    "data-analytics": [
        "data-driven decision making framework",
        "manufacturing analytics maturity model",
    ],
    "compliance": [
        "compliance management framework ISO",
        "risk management best practices manufacturing",
    ],
    "partnerships": [
        "strategic partnership framework best practices",
        "supplier relationship management excellence",
    ],
    "strategy": [
        "strategic planning framework industrial company",
        "OKR implementation best practices",
    ],
}

# Custom queries for SKF-specific domains
_SKF_DOMAIN_QUERIES = [
    "bearing industry market trends 2025 2026",
    "industrial automation transformation strategy",
    "predictive maintenance best practices manufacturing",
    "SKF competitor analysis bearing market",
    "supply chain resilience strategy manufacturing Europe",
    "digital transformation manufacturing industry framework",
    "knowledge sharing best practices large organization",
    "internal communication strategy global manufacturing",
]


def _load_kb() -> dict[str, Any]:
    if _KB_FILE.exists():
        try:
            return json.loads(_KB_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"articles": [], "topics_enriched": [], "updated_at": None}


def _save_kb(data: dict[str, Any]) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _KB_FILE.write_text(json.dumps(data, indent=2, default=str))


def _get_llm_client():
    try:
        from config import ANTHROPIC_API_KEY
        if not ANTHROPIC_API_KEY:
            return None
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception:
        return None


_SYNTHESIZE_PROMPT = """\
You are a management consultant creating a concise best-practice brief.

TOPIC: {topic}
SEARCH RESULTS:
{search_results}

Create a structured best-practice brief with:
1. **Framework/Model**: Name the key framework(s) or methodology
2. **Key Principles**: 3-5 core principles (bullet points)
3. **Implementation Steps**: Practical steps for a manufacturing CEO
4. **Common Pitfalls**: 2-3 things to avoid
5. **KPIs to Track**: 3-5 measurable metrics
6. **Sources**: Key thought leaders / publications

Keep it actionable and relevant for a CEO of a global industrial/bearing company.
Be specific, not generic. Under 400 words total.

Return the brief as plain text with markdown formatting.
"""


async def _web_search(query: str) -> list[dict[str, str]]:
    """Search the web for best practices. Returns list of {title, snippet, url}."""
    try:
        import httpx
        # Use a search API if available, otherwise fall back to mock
        # This is designed to work with various search backends
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try DuckDuckGo instant answer API (free, no key)
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1"},
            )
            data = resp.json()
            results = []
            # Related topics
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                    })
            # Abstract
            if data.get("Abstract"):
                results.insert(0, {
                    "title": data.get("Heading", query),
                    "snippet": data["Abstract"],
                    "url": data.get("AbstractURL", ""),
                })
            return results
    except Exception as e:
        logger.warning("Web search failed for '%s': %s", query, e)
        return []


async def enrich_topic(topic: str, custom_queries: list[str] | None = None) -> dict[str, Any]:
    """Research best practices for a specific topic and add to knowledge base.

    Args:
        topic: Topic name (e.g., "operations", "planning")
        custom_queries: Optional custom search queries instead of defaults

    Returns:
        Dict with status and articles added
    """
    kb = _load_kb()

    queries = custom_queries or _TOPIC_SEARCH_MAP.get(topic, [f"{topic} best practices framework"])

    # Gather search results
    all_results = []
    for query in queries[:3]:
        results = await _web_search(query)
        all_results.extend(results)

    if not all_results:
        return {"topic": topic, "status": "no_results", "articles_added": 0}

    # Use LLM to synthesize into actionable brief
    client = _get_llm_client()
    if client is None:
        # Store raw results without synthesis
        article = {
            "topic": topic,
            "title": f"Best Practices: {topic.title()}",
            "content": "\n".join(f"- {r['title']}: {r['snippet']}" for r in all_results),
            "source": "web_search",
            "sources": [r.get("url", "") for r in all_results if r.get("url")],
            "added_at": datetime.now(timezone.utc).isoformat(),
            "type": "best_practice",
        }
        kb["articles"].append(article)
        if topic not in kb["topics_enriched"]:
            kb["topics_enriched"].append(topic)
        _save_kb(kb)
        return {"topic": topic, "status": "added_raw", "articles_added": 1}

    # Synthesize with LLM
    search_text = "\n\n".join(
        f"### {r['title']}\n{r['snippet']}" for r in all_results[:8]
    )
    prompt = _SYNTHESIZE_PROMPT.format(topic=topic, search_results=search_text)

    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        synthesis = response.content[0].text.strip()
    except Exception as e:
        logger.warning("LLM synthesis failed: %s", e)
        synthesis = "\n".join(f"- {r['snippet']}" for r in all_results)

    # Check for duplicates
    existing_titles = {a["title"].lower() for a in kb["articles"]}
    title = f"Best Practices: {topic.replace('-', ' ').title()}"
    if title.lower() in existing_titles:
        title = f"Best Practices: {topic.replace('-', ' ').title()} (Updated)"

    article = {
        "topic": topic,
        "title": title,
        "content": synthesis,
        "source": "web_search + synthesis",
        "sources": [r.get("url", "") for r in all_results if r.get("url")],
        "added_at": datetime.now(timezone.utc).isoformat(),
        "type": "best_practice",
    }

    kb["articles"].append(article)
    if topic not in kb["topics_enriched"]:
        kb["topics_enriched"].append(topic)
    _save_kb(kb)

    return {"topic": topic, "status": "synthesized", "articles_added": 1}


async def enrich_from_intel() -> dict[str, Any]:
    """Automatically enrich knowledge base based on topics found in intelligence data.

    Scans the intel topics and enriches any that haven't been covered yet.
    """
    from integrations.intel import _load_intel

    intel = _load_intel()
    topics = intel.get("topics", {})
    kb = _load_kb()
    already_enriched = set(kb.get("topics_enriched", []))

    # Find topics that need enrichment (exist in intel but not in KB)
    to_enrich = [t for t in topics.keys()
                 if t not in already_enriched and t != "general"]

    if not to_enrich:
        return {"message": "All topics already enriched", "enriched": []}

    results = []
    for topic in to_enrich[:5]:  # Cap at 5 per run to control cost
        result = await enrich_topic(topic)
        results.append(result)

    # Also add SKF-specific domain knowledge if not done
    if "skf_domains" not in already_enriched:
        for query in _SKF_DOMAIN_QUERIES[:3]:
            await enrich_topic("skf_domains", custom_queries=[query])

    return {
        "message": f"Enriched {len(results)} topics",
        "enriched": results,
    }


def get_best_practices(topic: str = "") -> dict[str, Any]:
    """Retrieve best practices from the knowledge base.

    Args:
        topic: Optional topic filter

    Returns:
        Dict with articles list
    """
    kb = _load_kb()
    articles = kb.get("articles", [])

    if topic:
        articles = [a for a in articles if a.get("topic", "").lower() == topic.lower()]

    return {
        "articles": articles,
        "total": len(articles),
        "topics_covered": kb.get("topics_enriched", []),
    }


def search_best_practices(query: str) -> list[dict[str, Any]]:
    """Search best practices knowledge base by keyword."""
    kb = _load_kb()
    q = query.lower()
    results = []

    for article in kb.get("articles", []):
        title = article.get("title", "").lower()
        content = article.get("content", "").lower()
        topic = article.get("topic", "").lower()
        if q in title or q in content or q in topic:
            results.append(article)

    return results
