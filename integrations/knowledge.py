"""Knowledge repository — stores external business context, reports, and news.

Provides a structured store for company intelligence gathered from public
sources (press releases, quarterly reports, annual reports, CMD presentations).
Data persists to knowledge_base.json and is injected into the agent's context.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KB_FILE = Path(__file__).parent.parent / "knowledge_base.json"


def _load() -> dict[str, Any]:
    if _KB_FILE.exists():
        try:
            return json.loads(_KB_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load knowledge base, starting fresh")
    return {"companies": {}, "updated_at": None}


def _save(data: dict[str, Any]) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _KB_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def get_knowledge() -> dict[str, Any]:
    """Return the full knowledge base."""
    return _load()


def get_company(company: str) -> dict[str, Any]:
    """Get all knowledge for a specific company."""
    kb = _load()
    key = company.strip().upper()
    return kb.get("companies", {}).get(key, {})


def add_article(company: str, category: str, article: dict[str, Any]) -> dict[str, Any]:
    """Add a news article / report entry to a company's knowledge.

    Args:
        company: Company name (e.g. "SKF").
        category: One of "news", "quarterly_reports", "annual_reports", "cmd", "strategy".
        article: Dict with at minimum {title, date, content}. Optional: {source_url, summary}.
    """
    kb = _load()
    key = company.strip().upper()

    if key not in kb["companies"]:
        kb["companies"][key] = {
            "name": company.strip(),
            "categories": {},
            "added_at": datetime.now(timezone.utc).isoformat(),
        }

    cats = kb["companies"][key].setdefault("categories", {})
    items = cats.setdefault(category, [])

    # Deduplicate by title
    existing_titles = {item["title"].lower() for item in items}
    if article.get("title", "").lower() in existing_titles:
        return {"status": "duplicate", "title": article["title"]}

    article["added_at"] = datetime.now(timezone.utc).isoformat()
    items.append(article)
    _save(kb)
    return {"status": "added", "title": article["title"], "category": category}


def get_company_summary(company: str) -> str:
    """Build a concise text summary of a company's knowledge for context injection."""
    data = get_company(company)
    if not data:
        return ""

    cats = data.get("categories", {})
    lines = [f"## {data.get('name', company)} — Business Context"]

    for cat_name, items in cats.items():
        label = cat_name.replace("_", " ").title()
        lines.append(f"\n### {label}")
        # Show most recent items (up to 5 per category)
        recent = sorted(items, key=lambda x: x.get("date", ""), reverse=True)[:5]
        for item in recent:
            date = item.get("date", "")
            title = item.get("title", "Untitled")
            summary = item.get("summary", item.get("content", "")[:200])
            lines.append(f"- **{date}** {title}: {summary}")

    return "\n".join(lines)


def search_knowledge(query: str, company: str = "") -> list[dict[str, Any]]:
    """Search knowledge base by keyword."""
    kb = _load()
    query_lower = query.lower()
    results = []

    companies = kb.get("companies", {})
    if company:
        key = company.strip().upper()
        companies = {key: companies[key]} if key in companies else {}

    for _key, comp in companies.items():
        for cat, items in comp.get("categories", {}).items():
            for item in items:
                searchable = " ".join([
                    item.get("title", ""),
                    item.get("content", ""),
                    item.get("summary", ""),
                ]).lower()
                if query_lower in searchable:
                    results.append({**item, "company": comp.get("name", _key), "category": cat})

    return results
