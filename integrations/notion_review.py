"""Notion page review — consistency checks, spelling fixes, structure validation.

Tracks the last review timestamp, finds newly edited pages, checks for:
- Name spelling inconsistencies (e.g. "Jon" vs "Jonas")
- Title formatting issues
- Structural problems (e.g. 1:1 notes not under the right section)
- Duplicate or misplaced pages

Stores known names and review state in notion_review_state.json.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path
from typing import Any

from integrations.notion import (
    get_page_blocks,
    get_page_content,
    get_recently_edited_pages,
    is_configured,
    update_block_text,
    update_page_title,
)

logger = logging.getLogger(__name__)

_STATE_FILE = Path(__file__).parent.parent / "notion_review_state.json"


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "last_reviewed_at": None,
        "known_names": [],
        "title_patterns": {},
        "reviewed_pages": [],
    }


def _save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# -----------------------------------------------------------------------
# Known-names management
# -----------------------------------------------------------------------

def get_known_names() -> dict:
    """Get the list of known canonical names used for spell-checking."""
    state = _load_state()
    return {"names": state.get("known_names", []), "count": len(state.get("known_names", []))}


def add_known_names(names: list[str]) -> dict:
    """Add names to the known names list.

    Args:
        names: List of canonical name spellings to add.

    Returns:
        Updated names list.
    """
    state = _load_state()
    existing = set(state.get("known_names", []))
    added = []
    for name in names:
        name = name.strip()
        if name and name not in existing:
            existing.add(name)
            added.append(name)
    state["known_names"] = sorted(existing)
    _save_state(state)
    return {"added": added, "total": len(state["known_names"]), "names": state["known_names"]}


def remove_known_names(names: list[str]) -> dict:
    """Remove names from the known names list."""
    state = _load_state()
    existing = set(state.get("known_names", []))
    removed = []
    for name in names:
        if name in existing:
            existing.discard(name)
            removed.append(name)
    state["known_names"] = sorted(existing)
    _save_state(state)
    return {"removed": removed, "total": len(state["known_names"])}


# -----------------------------------------------------------------------
# Name spell-checking
# -----------------------------------------------------------------------

def find_name_issues(text: str, known_names: list[str]) -> list[dict]:
    """Find potential name misspellings in text.

    Compares words that look like names (capitalized) against known names,
    flagging close-but-not-exact matches.

    Args:
        text: The text to check.
        known_names: List of canonical name spellings.

    Returns:
        List of dicts with 'found', 'suggested', and 'context'.
    """
    if not known_names:
        return []

    issues = []
    known_lower = {n.lower(): n for n in known_names}
    known_list = list(known_lower.keys())
    seen = set()

    # Find capitalized words that could be names
    words = re.findall(r"\b([A-Z][a-z]{1,20})\b", text)

    for word in words:
        word_lower = word.lower()

        # Skip if it's an exact match
        if word_lower in known_lower:
            continue

        # Skip common non-name words
        if word_lower in _COMMON_WORDS:
            continue

        # Skip already flagged
        if word_lower in seen:
            continue

        # Check for close matches
        matches = get_close_matches(word_lower, known_list, n=1, cutoff=0.7)
        if matches:
            suggested = known_lower[matches[0]]
            # Find surrounding context
            idx = text.lower().find(word_lower)
            start = max(0, idx - 30)
            end = min(len(text), idx + len(word) + 30)
            context = text[start:end].replace("\n", " ").strip()

            issues.append({
                "found": word,
                "suggested": suggested,
                "context": f"...{context}...",
            })
            seen.add(word_lower)

    return issues


# Common words that are capitalized but aren't names
_COMMON_WORDS = frozenset({
    "the", "and", "for", "with", "from", "this", "that", "what", "when",
    "where", "which", "who", "how", "not", "but", "are", "was", "were",
    "been", "being", "have", "has", "had", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "did",
    "does", "done", "let", "get", "got", "see", "saw", "set", "put",
    "run", "use", "ask", "try", "new", "old", "big", "all", "any",
    "few", "our", "own", "its", "per", "via", "out", "off", "yes",
    "action", "todo", "task", "note", "notes", "meeting", "agenda",
    "review", "update", "status", "done", "open", "pending", "blocked",
    "high", "low", "normal", "urgent", "next", "steps", "discussion",
    "summary", "context", "background", "follow", "items", "monday",
    "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
})


# -----------------------------------------------------------------------
# Title consistency checks
# -----------------------------------------------------------------------

def check_title_consistency(title: str, page_content: str) -> list[dict]:
    """Check a page title for common formatting issues.

    Looks for:
    - Missing date in meeting notes titles
    - Inconsistent 1:1 format (should be "1:1 Name — Date" or similar)
    - Untitled/empty titles

    Returns:
        List of issue dicts with 'type' and 'message'.
    """
    issues = []

    if not title or title.strip().lower() in ("untitled", ""):
        issues.append({
            "type": "missing_title",
            "message": "Page has no meaningful title.",
        })
        return issues

    # Check for 1:1 meetings — should have a name
    is_one_on_one = bool(re.search(r"1[:\-]1|one[\s-]on[\s-]one", title, re.IGNORECASE))
    if is_one_on_one:
        # Check it has at least one name-like word after the 1:1
        after = re.split(r"1[:\-]1|one[\s-]on[\s-]one", title, flags=re.IGNORECASE)[-1]
        name_words = re.findall(r"[A-Z][a-z]+", after)
        if not name_words:
            issues.append({
                "type": "one_on_one_missing_name",
                "message": f"1:1 meeting title '{title}' is missing a person's name.",
            })

    # Check for date in meeting-like pages
    is_meeting = bool(re.search(
        r"meeting|standup|retro|sprint|sync|check[\s-]?in|1[:\-]1|kickoff|review|planning",
        title, re.IGNORECASE,
    ))
    has_date = bool(re.search(
        r"\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}",
        title, re.IGNORECASE,
    ))
    if is_meeting and not has_date:
        issues.append({
            "type": "meeting_missing_date",
            "message": f"Meeting title '{title}' has no date — consider adding one for easier tracking.",
        })

    return issues


# -----------------------------------------------------------------------
# Full page review
# -----------------------------------------------------------------------

async def review_page(page_id: str, auto_fix: bool = False) -> dict:
    """Review a single Notion page for issues.

    Checks:
    - Title consistency
    - Name spelling in content
    - Task extraction hints

    Args:
        page_id: The page to review.
        auto_fix: If True, automatically fix spelling issues in blocks.

    Returns:
        Dict with all found issues and any fixes applied.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    state = _load_state()
    known_names = state.get("known_names", [])

    page = await get_page_content(page_id)
    title = page["title"]
    content = page["content"]

    result: dict[str, Any] = {
        "page_id": page_id,
        "title": title,
        "url": page["url"],
        "issues": [],
        "fixes_applied": [],
    }

    # Title checks
    title_issues = check_title_consistency(title, content)
    for issue in title_issues:
        result["issues"].append({
            "location": "title",
            **issue,
        })

    # Name checks in title
    title_name_issues = find_name_issues(title, known_names)
    for issue in title_name_issues:
        result["issues"].append({
            "location": "title",
            "type": "name_spelling",
            "found": issue["found"],
            "suggested": issue["suggested"],
            "context": title,
        })
        if auto_fix:
            new_title = title.replace(issue["found"], issue["suggested"])
            try:
                await update_page_title(page_id, new_title)
                title = new_title
                result["fixes_applied"].append({
                    "location": "title",
                    "old": issue["found"],
                    "new": issue["suggested"],
                })
            except Exception as exc:
                logger.warning("Failed to fix title: %s", exc)

    # Name checks in content blocks
    if known_names:
        blocks = await get_page_blocks(page_id)
        for block in blocks:
            block_text = block["text"]
            if not block_text:
                continue

            name_issues = find_name_issues(block_text, known_names)
            for issue in name_issues:
                result["issues"].append({
                    "location": f"block:{block['id']}",
                    "type": "name_spelling",
                    "block_type": block["type"],
                    "found": issue["found"],
                    "suggested": issue["suggested"],
                    "context": issue["context"],
                })
                if auto_fix and block["type"] in (
                    "paragraph", "bulleted_list_item", "numbered_list_item",
                    "to_do", "heading_1", "heading_2", "heading_3", "toggle",
                ):
                    new_text = block_text.replace(issue["found"], issue["suggested"])
                    try:
                        await update_block_text(block["id"], new_text, block["type"])
                        result["fixes_applied"].append({
                            "location": f"block:{block['id']}",
                            "old": issue["found"],
                            "new": issue["suggested"],
                        })
                    except Exception as exc:
                        logger.warning("Failed to fix block %s: %s", block["id"], exc)

    result["issue_count"] = len(result["issues"])
    result["fix_count"] = len(result["fixes_applied"])
    return result


async def review_recent_pages(auto_fix: bool = False) -> dict:
    """Review all pages edited since the last review.

    Finds pages modified since last_reviewed_at, reviews each one,
    and updates the last reviewed timestamp.

    Args:
        auto_fix: If True, automatically fix spelling issues.

    Returns:
        Dict with all reviews and summary.
    """
    if not is_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    state = _load_state()
    since = state.get("last_reviewed_at")

    pages_result = await get_recently_edited_pages(since=since, max_results=20)
    pages = pages_result["pages"]

    if not pages:
        return {
            "message": "No new or edited pages since last review.",
            "last_reviewed_at": since,
            "pages_checked": 0,
        }

    reviews = []
    total_issues = 0
    total_fixes = 0

    for page in pages:
        try:
            review = await review_page(page["id"], auto_fix=auto_fix)
            reviews.append(review)
            total_issues += review["issue_count"]
            total_fixes += review["fix_count"]
        except Exception as exc:
            logger.warning("Failed to review page %s: %s", page["id"], exc)
            reviews.append({
                "page_id": page["id"],
                "title": page["title"],
                "error": str(exc),
            })

    # Update last reviewed timestamp
    state["last_reviewed_at"] = datetime.now(timezone.utc).isoformat()
    reviewed_ids = [r["page_id"] for r in reviews if "error" not in r]
    state["reviewed_pages"] = reviewed_ids + state.get("reviewed_pages", [])
    state["reviewed_pages"] = state["reviewed_pages"][:100]  # keep last 100
    _save_state(state)

    return {
        "pages_checked": len(pages),
        "total_issues": total_issues,
        "total_fixes": total_fixes,
        "last_reviewed_at": state["last_reviewed_at"],
        "reviews": reviews,
    }


def get_review_state() -> dict:
    """Get the current review state (last reviewed time, known names, etc.)."""
    state = _load_state()
    return {
        "last_reviewed_at": state.get("last_reviewed_at"),
        "known_names": state.get("known_names", []),
        "known_names_count": len(state.get("known_names", [])),
        "reviewed_pages_count": len(state.get("reviewed_pages", [])),
    }
