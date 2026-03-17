"""Notion integration — search pages, read content, query databases.

Uses the official notion-client SDK with async support.
Requires NOTION_API_KEY set in .env (create at notion.so/my-integrations).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from config import NOTION_API_KEY

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def is_configured() -> bool:
    """Check if Notion API key is set."""
    return bool(NOTION_API_KEY)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _extract_text(rich_text: list[dict]) -> str:
    """Extract plain text from Notion rich_text array."""
    return "".join(item.get("plain_text", "") for item in rich_text)


def _extract_block_text(block: dict) -> str:
    """Extract text content from a single block."""
    block_type = block.get("type", "")
    data = block.get(block_type, {})
    rich_text = data.get("rich_text", [])
    text = _extract_text(rich_text)

    if block_type in ("heading_1", "heading_2", "heading_3"):
        level = block_type[-1]
        return f"{'#' * int(level)} {text}"
    elif block_type == "bulleted_list_item":
        return f"• {text}"
    elif block_type == "numbered_list_item":
        return f"- {text}"
    elif block_type == "to_do":
        checked = data.get("checked", False)
        mark = "x" if checked else " "
        return f"[{mark}] {text}"
    elif block_type == "toggle":
        return f"▸ {text}"
    elif block_type == "divider":
        return "---"
    elif block_type == "code":
        return f"```\n{text}\n```"
    elif text:
        return text
    return ""


def _format_page(page: dict) -> dict[str, Any]:
    """Format a Notion page object into a clean dict."""
    props = page.get("properties", {})
    title = ""
    for prop in props.values():
        if prop.get("type") == "title":
            title = _extract_text(prop.get("title", []))
            break

    return {
        "id": page["id"],
        "title": title,
        "url": page.get("url", ""),
        "created_time": page.get("created_time", ""),
        "last_edited_time": page.get("last_edited_time", ""),
    }


async def search_pages(query: str, max_results: int = 10) -> dict:
    """Search Notion pages by keyword.

    Args:
        query: Search text.
        max_results: Max pages to return.

    Returns:
        Dict with pages list and count.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE_URL}/search",
            headers=_headers(),
            json={
                "query": query,
                "filter": {"value": "page", "property": "object"},
                "page_size": max_results,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    pages = [_format_page(p) for p in data.get("results", [])]
    return {"pages": pages, "count": len(pages)}


async def get_page_content(page_id: str) -> dict:
    """Read the full content of a Notion page.

    Args:
        page_id: The Notion page ID.

    Returns:
        Dict with page title, content text, and blocks.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    async with httpx.AsyncClient(timeout=30) as client:
        # Get page metadata
        page_resp = await client.get(
            f"{_BASE_URL}/pages/{page_id}",
            headers=_headers(),
        )
        page_resp.raise_for_status()
        page_data = page_resp.json()
        page_info = _format_page(page_data)

        # Get page blocks (content)
        blocks_resp = await client.get(
            f"{_BASE_URL}/blocks/{page_id}/children",
            headers=_headers(),
            params={"page_size": 100},
        )
        blocks_resp.raise_for_status()
        blocks_data = blocks_resp.json()

    blocks = blocks_data.get("results", [])
    lines = []
    for block in blocks:
        text = _extract_block_text(block)
        if text:
            lines.append(text)

    return {
        "id": page_info["id"],
        "title": page_info["title"],
        "url": page_info["url"],
        "content": "\n".join(lines),
        "block_count": len(blocks),
    }


async def query_database(database_id: str, filter_obj: dict | None = None,
                         max_results: int = 50) -> dict:
    """Query a Notion database.

    Args:
        database_id: The database ID.
        filter_obj: Optional Notion filter object.
        max_results: Max rows to return.

    Returns:
        Dict with entries list and count.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    body: dict[str, Any] = {"page_size": max_results}
    if filter_obj:
        body["filter"] = filter_obj

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE_URL}/databases/{database_id}/query",
            headers=_headers(),
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    entries = []
    for page in data.get("results", []):
        entry = _format_page(page)
        # Extract all text/select/date properties
        props = page.get("properties", {})
        entry["properties"] = _extract_properties(props)
        entries.append(entry)

    return {"entries": entries, "count": len(entries)}


def _extract_properties(props: dict) -> dict[str, Any]:
    """Extract readable values from Notion properties."""
    result = {}
    for name, prop in props.items():
        ptype = prop.get("type", "")
        if ptype == "title":
            result[name] = _extract_text(prop.get("title", []))
        elif ptype == "rich_text":
            result[name] = _extract_text(prop.get("rich_text", []))
        elif ptype == "select":
            sel = prop.get("select")
            result[name] = sel["name"] if sel else None
        elif ptype == "multi_select":
            result[name] = [s["name"] for s in prop.get("multi_select", [])]
        elif ptype == "date":
            d = prop.get("date")
            result[name] = d["start"] if d else None
        elif ptype == "checkbox":
            result[name] = prop.get("checkbox", False)
        elif ptype == "number":
            result[name] = prop.get("number")
        elif ptype == "people":
            result[name] = [
                p.get("name", p.get("id", ""))
                for p in prop.get("people", [])
            ]
        elif ptype == "email":
            result[name] = prop.get("email")
        elif ptype == "status":
            s = prop.get("status")
            result[name] = s["name"] if s else None
        elif ptype == "url":
            result[name] = prop.get("url")
    return result


async def list_databases(max_results: int = 20) -> dict:
    """List all databases shared with the integration.

    Returns:
        Dict with databases list and count.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE_URL}/search",
            headers=_headers(),
            json={
                "filter": {"value": "database", "property": "object"},
                "page_size": max_results,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    databases = []
    for db in data.get("results", []):
        title = _extract_text(db.get("title", []))
        databases.append({
            "id": db["id"],
            "title": title,
            "url": db.get("url", ""),
        })

    return {"databases": databases, "count": len(databases)}
