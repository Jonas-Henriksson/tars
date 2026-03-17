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


async def update_page_title(page_id: str, new_title: str) -> dict:
    """Update a page's title property.

    Args:
        page_id: The Notion page ID.
        new_title: The new title text.

    Returns:
        Dict with updated page info.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    # First, find the title property name
    async with httpx.AsyncClient(timeout=30) as client:
        page_resp = await client.get(
            f"{_BASE_URL}/pages/{page_id}",
            headers=_headers(),
        )
        page_resp.raise_for_status()
        page_data = page_resp.json()

        title_prop_name = None
        for prop_name, prop in page_data.get("properties", {}).items():
            if prop.get("type") == "title":
                title_prop_name = prop_name
                break

        if not title_prop_name:
            return {"error": "Could not find title property on page."}

        resp = await client.patch(
            f"{_BASE_URL}/pages/{page_id}",
            headers=_headers(),
            json={
                "properties": {
                    title_prop_name: {
                        "title": [{"text": {"content": new_title}}],
                    },
                },
            },
        )
        resp.raise_for_status()

    return {"message": f"Title updated to '{new_title}'.", "page_id": page_id}


async def update_block_text(block_id: str, new_text: str, block_type: str = "paragraph") -> dict:
    """Update the text content of a block.

    Args:
        block_id: The block ID.
        new_text: New text content.
        block_type: Block type (paragraph, heading_1, etc.).

    Returns:
        Dict with update confirmation.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{_BASE_URL}/blocks/{block_id}",
            headers=_headers(),
            json={
                block_type: {
                    "rich_text": [{"text": {"content": new_text}}],
                },
            },
        )
        resp.raise_for_status()

    return {"message": "Block updated.", "block_id": block_id}


async def get_page_blocks(page_id: str) -> list[dict]:
    """Get all blocks (with IDs and types) for a page.

    Args:
        page_id: The Notion page ID.

    Returns:
        List of block dicts with id, type, and text content.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE_URL}/blocks/{page_id}/children",
            headers=_headers(),
            params={"page_size": 100},
        )
        resp.raise_for_status()
        data = resp.json()

    blocks = []
    for block in data.get("results", []):
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        text = _extract_text(block_data.get("rich_text", []))
        blocks.append({
            "id": block["id"],
            "type": block_type,
            "text": text,
            "has_children": block.get("has_children", False),
        })
    return blocks


async def get_recently_edited_pages(since: str | None = None,
                                     max_results: int = 20) -> dict:
    """Get pages edited recently, sorted by last_edited_time descending.

    Args:
        since: ISO 8601 timestamp — only return pages edited after this.
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
                "filter": {"value": "page", "property": "object"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                "page_size": max_results,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    pages = [_format_page(p) for p in data.get("results", [])]

    if since:
        pages = [p for p in pages if p["last_edited_time"] > since]

    return {"pages": pages, "count": len(pages)}


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
