"""Intelligence engine — scans Notion to build a profile of the user's work.

Analyzes all accessible Notion pages to extract:
- Topics the user covers and their frequency
- People the user interacts with
- Delegated tasks and follow-up timelines
- Recurring meetings and patterns
- Smart task list with priority matrix (Eisenhower: urgent/important)

Persists intelligence data in notion_intel.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_INTEL_FILE = Path(__file__).parent.parent / "notion_intel.json"


def _load_intel() -> dict:
    if _INTEL_FILE.exists():
        try:
            return json.loads(_INTEL_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return _empty_intel()


def _save_intel(data: dict) -> None:
    _INTEL_FILE.write_text(json.dumps(data, indent=2, default=str))


def _empty_intel() -> dict:
    return {
        "last_scan_at": None,
        "pages_scanned": 0,
        "topics": {},
        "people": {},
        "smart_tasks": [],
        "page_index": {},
        "executive_summary": {},
        "scan_history": [],
    }


# -----------------------------------------------------------------------
# Content analysis helpers
# -----------------------------------------------------------------------

_TOPIC_KEYWORDS = {
    "strategy": ["strategy", "roadmap", "vision", "objective", "okr", "goal", "initiative"],
    "engineering": ["engineering", "technical", "architecture", "api", "deploy", "release", "sprint", "code", "bug", "feature"],
    "product": ["product", "ux", "design", "user story", "prototype", "wireframe", "requirement"],
    "finance": ["budget", "revenue", "cost", "forecast", "invoice", "financial", "p&l"],
    "hiring": ["hiring", "interview", "candidate", "recruitment", "onboarding", "headcount"],
    "operations": ["operations", "process", "workflow", "sop", "compliance", "audit"],
    "sales": ["sales", "pipeline", "deal", "prospect", "customer", "contract", "pricing"],
    "marketing": ["marketing", "campaign", "brand", "content", "launch", "event"],
    "management": ["1:1", "performance", "feedback", "team", "leadership", "delegation"],
    "planning": ["planning", "quarterly", "annual", "timeline", "milestone", "deadline"],
}


def _detect_topics(text: str, title: str) -> list[str]:
    """Detect topic categories from page content and title."""
    combined = (title + " " + text).lower()
    found = []
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            found.append(topic)
    return found or ["general"]


def _extract_people(text: str, title: str) -> list[str]:
    """Extract people mentions from text."""
    people = set()
    # @mentions
    for m in re.findall(r"@([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", text):
        people.add(m.strip())
    # 1:1 title pattern: "1:1 Name" or "1:1 with Name"
    m = re.search(r"1[:\-]1\s+(?:with\s+)?([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", title)
    if m:
        people.add(m.group(1).strip())
    return sorted(people)


# -----------------------------------------------------------------------
# LLM-powered metadata extraction (rich tagging for graph)
# -----------------------------------------------------------------------

_LLM_EXTRACT_PROMPT = """\
Analyze this Notion page and extract structured metadata. Return ONLY valid JSON.

Page title: {title}
Page content:
{content}

Extract:
- people: All person names mentioned (full names preferred, no duplicates)
- organizations: Teams, companies, departments, committees, councils mentioned
- projects: Named projects, initiatives, programs, workstreams
- topics: Hierarchical topic tags (use "/" for hierarchy, e.g. "supply-chain/optimization", "ai/use-cases", "budget/q3-review"). Be specific, not generic.
- decisions: Key decisions made (each with "text" and "by" who decided, if known)
- tags: Obsidian-style category tags for this page (e.g. "meeting/1on1", "review", "planning/quarterly", "escalation")
- summary: 1-2 sentence summary of the page content

Return JSON:
{{"people":[],"organizations":[],"projects":[],"topics":[],"decisions":[],"tags":[],"summary":""}}
"""

_llm_client = None


def _get_llm_client():
    """Lazy-init Anthropic client."""
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    try:
        from config import ANTHROPIC_API_KEY
        if not ANTHROPIC_API_KEY:
            return None
        import anthropic
        _llm_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return _llm_client
    except Exception as e:
        logger.warning("Cannot initialize Anthropic client: %s", e)
        return None


async def _llm_extract_metadata(title: str, content: str) -> dict | None:
    """Use Claude haiku to extract rich metadata from a page.

    Returns structured dict or None if LLM is unavailable.
    Content is truncated to ~4000 chars to keep costs low.
    """
    client = _get_llm_client()
    if client is None:
        return None

    # Truncate long content to control cost
    max_content = 4000
    truncated = content[:max_content] + ("..." if len(content) > max_content else "")

    prompt = _LLM_EXTRACT_PROMPT.format(title=title, content=truncated)

    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Parse JSON — handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(text)

        # Validate expected keys
        defaults = {
            "people": [], "organizations": [], "projects": [],
            "topics": [], "decisions": [], "tags": [], "summary": "",
        }
        for key, default in defaults.items():
            if key not in result:
                result[key] = default

        # Normalize decisions to list of dicts
        normalized_decisions = []
        for d in result.get("decisions", []):
            if isinstance(d, str):
                normalized_decisions.append({"text": d, "by": ""})
            elif isinstance(d, dict):
                normalized_decisions.append({"text": d.get("text", ""), "by": d.get("by", "")})
        result["decisions"] = normalized_decisions

        return result

    except json.JSONDecodeError as e:
        logger.warning("LLM returned invalid JSON for '%s': %s", title, e)
        return None
    except Exception as e:
        logger.warning("LLM extraction failed for '%s': %s", title, e)
        return None


def _extract_source_context(text: str, description: str, window: int = 300) -> str:
    """Extract surrounding text around where a task was found in the source.

    Returns up to `window` chars of context around the task description.
    """
    text_lower = text.lower()
    desc_lower = description.lower()[:60]
    idx = text_lower.find(desc_lower)

    if idx == -1:
        # Try partial match with first few words
        words = description.split()[:4]
        partial = " ".join(words).lower()
        idx = text_lower.find(partial)

    if idx == -1:
        # Try matching each significant word (3+ chars) to find the best line
        sig_words = [w.lower() for w in description.split() if len(w) >= 3]
        if sig_words:
            best_line = ""
            best_score = 0
            for line in text.split("\n"):
                ll = line.lower()
                score = sum(1 for w in sig_words if w in ll)
                if score > best_score:
                    best_score = score
                    best_line = line.strip()
            # Require at least half the significant words to match
            if best_score >= max(1, len(sig_words) // 2) and best_line:
                idx = text_lower.find(best_line.lower())

    if idx == -1:
        # Fallback: return first chunk of content as generic context
        if len(text.strip()) > 20:
            snippet = text.strip()[:window]
            if len(text.strip()) > window:
                snippet += "..."
            return snippet
        return ""

    start = max(0, idx - window // 2)
    end = min(len(text), idx + len(description) + window // 2)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _suggest_steps(description: str, source_context: str, topics: list[str],
                   owner: str = "", delegated: bool = False) -> str:
    """Generate suggested action steps based on task description and context.

    Uses heuristics and keyword matching to produce practical steps.
    """
    desc_lower = description.lower()
    ctx_lower = (source_context or "").lower()
    combined = desc_lower + " " + ctx_lower
    steps = []

    # --- Pattern-based step generation ---

    # Presentation / slide / deck tasks
    if any(kw in desc_lower for kw in ["presentation", "slide", "deck", "ppt"]):
        steps = [
            "Gather latest data and inputs from stakeholders",
            "Draft slide structure and key messages",
            "Create/update slides with visuals and data",
            "Review with stakeholders for feedback",
            "Finalize and share with audience",
        ]
    # Meeting preparation
    elif any(kw in desc_lower for kw in ["prepare for", "prep for", "meeting"]):
        steps = [
            "Review agenda and previous meeting notes",
            "Gather updates and data points to share",
            "Prepare talking points or materials",
            "Send pre-read or agenda to participants",
        ]
    # Follow-up tasks
    elif any(kw in desc_lower for kw in ["follow up", "follow-up", "check in", "check-in"]):
        person = owner if delegated else ""
        if not person:
            # Try to extract person name from description
            m = re.search(r"(?:with|from)\s+([A-Z][a-z]+)", description)
            if m:
                person = m.group(1)
        steps = [
            f"Reach out to {person or 'the relevant person'} for status update",
            "Review any shared documents or deliverables",
            "Document outcome and next steps",
            "Set follow-up reminder if still pending",
        ]
    # Review / feedback tasks
    elif any(kw in desc_lower for kw in ["review", "feedback", "approve"]):
        steps = [
            "Read through the document/deliverable thoroughly",
            "Note questions, concerns, and suggestions",
            "Share consolidated feedback with the author",
            "Confirm revisions if needed",
        ]
    # Share / send / distribute
    elif any(kw in desc_lower for kw in ["share", "send", "distribute", "forward"]):
        steps = [
            "Ensure the document/material is finalized",
            "Identify recipients and distribution channel",
            "Share with a brief context message",
            "Confirm receipt if needed",
        ]
    # Update / modify / change
    elif any(kw in desc_lower for kw in ["update", "modify", "revise", "change", "incorporate"]):
        steps = [
            "Review current version and identify what needs updating",
            "Gather new inputs or data",
            "Make the required changes",
            "Review and validate the updates",
            "Share updated version with stakeholders",
        ]
    # Collaborate / align / work with
    elif any(kw in desc_lower for kw in ["collaborate", "align", "work with", "partner", "sync with"]):
        # Extract people names from description
        people = re.findall(r"(?:with|and)\s+([A-Z][a-z]+)", description)
        people_str = ", ".join(people) if people else "key stakeholders"
        steps = [
            f"Reach out to {people_str} to align on goals and scope",
            "Agree on roles, responsibilities, and timeline",
            "Set up a working session or shared workspace",
            "Draft initial structure or framework together",
            "Review progress and finalize deliverables",
        ]
    # Organize / coordinate / plan
    elif any(kw in desc_lower for kw in ["organize", "coordinate", "plan", "schedule", "set up", "arrange"]):
        steps = [
            "Define scope, participants, and logistics",
            "Send invites or reserve resources",
            "Prepare agenda or materials",
            "Confirm attendance and final details",
        ]
    # Escalation tasks
    elif any(kw in desc_lower for kw in ["escalat", "raise", "flag", "alert"]):
        steps = [
            "Document the issue with supporting details",
            "Identify the right escalation path / person",
            "Communicate the escalation clearly",
            "Track resolution and follow up",
        ]
    # Ask / request / inquire
    elif any(kw in desc_lower for kw in ["ask", "request", "inquire", "find out", "clarify"]):
        steps = [
            "Formulate clear questions",
            "Reach out to the relevant person(s)",
            "Document the response",
            "Act on the information received",
        ]
    # Expand / extend / add
    elif any(kw in desc_lower for kw in ["expand", "extend", "add", "include", "broaden"]):
        steps = [
            "Review the current scope",
            "Identify what needs to be added",
            "Draft the additional content",
            "Integrate and review the expanded version",
        ]
    # Generic fallback: infer from topic
    elif "strategy" in combined or "roadmap" in combined:
        steps = [
            "Review current strategy/roadmap status",
            "Identify gaps or action items",
            "Draft recommendations or updates",
            "Align with stakeholders",
        ]
    else:
        # Generic task steps
        steps = [
            "Clarify requirements and expected outcome",
            "Gather necessary inputs or information",
            "Complete the task",
            "Review and share results",
        ]

    # Add context-aware refinements
    if "deadline" in combined or "end of" in combined or "by " in combined:
        steps.append("Verify timeline and set intermediate checkpoints")
    if delegated and owner:
        steps.insert(0, f"Confirm expectations and timeline with {owner}")

    return "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))


def _detect_delegations(text: str) -> list[dict]:
    """Detect delegated tasks: items assigned to other people."""
    delegations = []
    seen: set[str] = set()

    # Patterns for @-mention delegations.
    # Use (\w+) for name to avoid non-greedy backtracking issues.
    # Accept optional colon or just space after the name.
    patterns = [
        # "[ ] @Name: task" or "[ ] @Name task"
        re.compile(r"\[[ ]\]\s*@(\w+)[:\s]+(.+)"),
        # "ACTION: @Name task" / "TODO: @Name task"
        re.compile(r"(?:ACTION|TODO|TASK)[:\s]+@(\w+)[:\s]+(.+)", re.IGNORECASE),
        # "• @Name: task" / "- @Name task" / "* @Name task"
        re.compile(r"[•\-\*]\s*@(\w+)[:\s]+(.+)"),
        # "[ ] Name to/will/should verb ..." (non @-mention delegation)
        re.compile(r"\[[ ]\]\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:to|will|should|needs? to)\s+(.{5,})"),
        # "@Name verb ..." on its own line
        re.compile(r"^[•\-\*\s]*@(\w+)\s+(.{6,})$", re.MULTILINE),
    ]

    for pattern in patterns:
        for match in pattern.finditer(text):
            owner = match.group(1).strip()
            desc = match.group(2).strip()
            key = (owner.lower(), desc.lower()[:50])
            if owner and desc and key not in seen:
                seen.add(key)
                delegations.append({"owner": owner, "description": desc})

    return delegations


def _estimate_follow_up_date(text: str, page_date: str) -> str | None:
    """Estimate when to follow up based on context clues."""
    text_lower = text.lower()

    # Explicit date mentions
    date_match = re.search(r"by\s+(\d{4}-\d{2}-\d{2})", text)
    if date_match:
        return date_match.group(1)

    # Relative time expressions
    try:
        base = datetime.fromisoformat(page_date.replace("Z", "+00:00")) if page_date else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        base = datetime.now(timezone.utc)

    if any(w in text_lower for w in ["tomorrow", "asap", "urgent", "immediately"]):
        return (base + timedelta(days=1)).strftime("%Y-%m-%d")
    if any(w in text_lower for w in ["this week", "end of week", "eow", "friday"]):
        days_until_friday = (4 - base.weekday()) % 7 or 7
        return (base + timedelta(days=days_until_friday)).strftime("%Y-%m-%d")
    if any(w in text_lower for w in ["next week", "next monday"]):
        days_until_monday = (7 - base.weekday()) % 7 or 7
        return (base + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
    if any(w in text_lower for w in ["next month", "end of month", "eom"]):
        return (base + timedelta(days=30)).strftime("%Y-%m-%d")

    # Default: follow up in 3 business days for delegated items
    return (base + timedelta(days=3)).strftime("%Y-%m-%d")


def _classify_priority(text: str, is_delegated: bool, age_days: int = 0) -> dict:
    """Classify task using Eisenhower matrix: urgent x important.

    Returns dict with 'urgent', 'important', and 'quadrant'.
    Quadrant 1: Urgent + Important (Do first)
    Quadrant 2: Not urgent + Important (Schedule)
    Quadrant 3: Urgent + Not important (Delegate)
    Quadrant 4: Not urgent + Not important (Eliminate)
    """
    text_lower = text.lower()

    # Urgency signals
    urgent_keywords = ["asap", "urgent", "immediately", "critical", "blocker",
                       "blocked", "deadline", "overdue", "today", "tomorrow",
                       "this week", "eow"]
    urgent = any(kw in text_lower for kw in urgent_keywords) or age_days >= 7

    # Importance signals
    important_keywords = ["strategy", "revenue", "customer", "launch", "decision",
                          "budget", "contract", "leadership", "roadmap", "key",
                          "milestone", "critical path", "risk", "escalat"]
    important = any(kw in text_lower for kw in important_keywords)

    # Delegated items are typically Q3 unless explicitly important
    if is_delegated and not important:
        urgent = urgent or age_days >= 3

    if urgent and important:
        quadrant = 1
        label = "Do first"
    elif not urgent and important:
        quadrant = 2
        label = "Schedule"
    elif urgent and not important:
        quadrant = 3
        label = "Delegate"
    else:
        quadrant = 4
        label = "Eliminate/defer"

    return {
        "urgent": urgent,
        "important": important,
        "quadrant": quadrant,
        "quadrant_label": label,
    }


# -----------------------------------------------------------------------
# Notion page fetcher with pagination
# -----------------------------------------------------------------------

async def _fetch_all_pages(max_pages: int, since: str | None = None) -> list[dict]:
    """Fetch pages from Notion with pagination support.

    Args:
        max_pages: Max pages to return.
        since: ISO 8601 timestamp — only return pages edited after this.
               Results are sorted by last_edited_time desc, so we stop
               paginating once we hit a page older than ``since``.
    """
    import httpx

    from integrations.notion import _format_page, _headers, is_configured
    from integrations.notion import _BASE_URL

    if not is_configured():
        return []

    pages: list[dict] = []
    start_cursor: str | None = None
    batch_size = min(max_pages, 100)
    hit_old_page = False

    async with httpx.AsyncClient(timeout=30) as client:
        while len(pages) < max_pages and not hit_old_page:
            body: dict[str, Any] = {
                "filter": {"value": "page", "property": "object"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                "page_size": batch_size,
            }
            if start_cursor:
                body["start_cursor"] = start_cursor

            try:
                resp = await client.post(
                    f"{_BASE_URL}/search",
                    headers=_headers(),
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.error("Notion search API failed: %s", exc)
                break

            results = data.get("results", [])
            if not results:
                break

            for p in results:
                page = _format_page(p)
                # Stop once we reach pages not edited since last scan
                if since and page.get("last_edited_time", "") <= since:
                    hit_old_page = True
                    break
                pages.append(page)
                if len(pages) >= max_pages:
                    break

            if not data.get("has_more") or not data.get("next_cursor"):
                break
            start_cursor = data["next_cursor"]

    return pages


# -----------------------------------------------------------------------
# Sync intel tasks to tracked tasks (for Tasks page)
# -----------------------------------------------------------------------

def _sync_to_tracked_tasks(new_tasks: list[dict]) -> None:
    """Save intel smart tasks to notion_tracked_tasks.json so the Tasks page shows them."""
    from integrations.notion_tasks import _load_tasks, _save_tasks

    existing = _load_tasks()
    existing_descs = {t["description"].lower()[:50] for t in existing}

    for task in new_tasks:
        if task["description"].lower()[:50] in existing_descs:
            continue
        tracked = {
            "id": task["id"],
            "description": task["description"],
            "owner": task.get("owner", "Unassigned"),
            "topic": task.get("topics", ["General"])[0] if task.get("topics") else "General",
            "source_title": task.get("source_title", ""),
            "source_url": task.get("source_url", ""),
            "source_page_id": task.get("source_page_id", ""),
            "completed": False,
            "status": task.get("status", "open"),
            "followed_up": False,
            "created_at": task.get("created_at", ""),
        }
        existing.append(tracked)
        existing_descs.add(task["description"].lower()[:50])

    _save_tasks(existing)


# -----------------------------------------------------------------------
# Main scan
# -----------------------------------------------------------------------

async def scan_notion(
    max_pages: int = 50,
    full_scan: bool = False,
    on_progress: Optional[Callable[[dict], Any]] = None,
    cancel_event: Optional[asyncio.Event] = None,
) -> dict:
    """Scan Notion pages to build intelligence.

    By default performs an incremental scan — only pages edited since the
    last scan are fetched and processed.  Pass ``full_scan=True`` to
    re-scan everything.

    Args:
        max_pages: Max pages to scan.
        full_scan: If True, ignore last scan timestamp and scan all pages.
        on_progress: Optional async/sync callback receiving progress dicts.
        cancel_event: Optional asyncio.Event; when set, scan stops early.

    Returns:
        Summary of scan results.
    """
    from integrations.notion import get_page_content, is_configured as notion_configured

    if not notion_configured():
        raise RuntimeError("Notion is not configured. Set NOTION_API_KEY in .env.")

    intel = _load_intel()
    now = datetime.now(timezone.utc)

    # Incremental: only fetch pages edited since last scan
    since = None if full_scan else intel.get("last_scan_at")
    pages = await _fetch_all_pages(max_pages, since=since)
    scan_type = "full" if full_scan or not since else "incremental"
    logger.info("Intel scan (%s): fetched %d pages from Notion", scan_type, len(pages))

    topic_counter: Counter = Counter()
    people_counter: Counter = Counter()
    page_index: dict[str, dict] = {}
    new_tasks: list[dict] = []
    existing_task_descs = {t["description"].lower() for t in intel.get("smart_tasks", [])}
    pages_with_content = 0
    errors = 0

    async def _process_page_content(
        title: str, content: str, page_url: str, page_id: str, page_date: str,
    ) -> None:
        """Process a single page's content for topics, people, and tasks."""
        nonlocal pages_with_content

        if not content.strip():
            logger.debug("Intel scan: skipping empty page '%s'", title)
            return
        pages_with_content += 1

        # Check LLM cache — skip extraction if page hasn't changed
        existing_page = intel.get("page_index", {}).get(page_id, {})
        cached_llm = (
            existing_page.get("llm_extracted_at")
            and existing_page.get("last_edited") == page_date
        )

        llm_meta = None
        if not cached_llm:
            llm_meta = await _llm_extract_metadata(title, content)

        if llm_meta:
            # Rich LLM extraction
            topics = llm_meta.get("topics", []) or _detect_topics(content, title)
            people = llm_meta.get("people", []) or _extract_people(content, title)
            projects = llm_meta.get("projects", [])
            organizations = llm_meta.get("organizations", [])
            decisions = llm_meta.get("decisions", [])
            tags = llm_meta.get("tags", [])
            summary = llm_meta.get("summary", "")
            llm_ts = datetime.now(timezone.utc).isoformat()
        elif cached_llm:
            # Use cached LLM data
            topics = existing_page.get("topics", _detect_topics(content, title))
            people = existing_page.get("people", _extract_people(content, title))
            projects = existing_page.get("projects", [])
            organizations = existing_page.get("organizations", [])
            decisions = existing_page.get("decisions", [])
            tags = existing_page.get("tags", [])
            summary = existing_page.get("summary", "")
            llm_ts = existing_page.get("llm_extracted_at", "")
        else:
            # Fallback to regex
            topics = _detect_topics(content, title)
            people = _extract_people(content, title)
            projects = []
            organizations = []
            decisions = []
            tags = []
            summary = ""
            llm_ts = ""

        for t in topics:
            topic_counter[t] += 1
        for p in people:
            people_counter[p] += 1

        # Store per-page metadata for graph visualization
        page_index[page_id] = {
            "title": title,
            "url": page_url,
            "topics": topics,
            "people": people,
            "projects": projects,
            "organizations": organizations,
            "decisions": decisions,
            "tags": tags,
            "summary": summary,
            "last_edited": page_date,
            "llm_extracted_at": llm_ts,
        }

        # Detect delegations -> smart tasks
        delegations = _detect_delegations(content)
        for d in delegations:
            if d["description"].lower() in existing_task_descs:
                continue

            follow_up = _estimate_follow_up_date(d["description"], page_date)
            priority = _classify_priority(d["description"], is_delegated=True)
            source_context = _extract_source_context(content, d["description"])
            suggested_steps = _suggest_steps(
                d["description"], source_context, topics,
                owner=d["owner"], delegated=True,
            )

            task = {
                "id": uuid.uuid4().hex[:8],
                "description": d["description"],
                "owner": d["owner"],
                "delegated": True,
                "source_title": title,
                "source_url": page_url,
                "source_page_id": page_id,
                "source_context": source_context,
                "topics": topics,
                "follow_up_date": follow_up,
                "priority": priority,
                "status": "open",
                "steps": suggested_steps,
                "created_at": now.isoformat(),
            }
            new_tasks.append(task)
            existing_task_descs.add(d["description"].lower())

        # Also detect user's own tasks (not delegated)
        own_tasks = _extract_own_tasks(content, title)
        for ot in own_tasks:
            if ot["description"].lower() in existing_task_descs:
                continue

            follow_up = _estimate_follow_up_date(ot["description"], page_date)
            priority = _classify_priority(ot["description"], is_delegated=False)
            source_context = _extract_source_context(content, ot["description"])
            suggested_steps = _suggest_steps(
                ot["description"], source_context, topics,
                owner="Me", delegated=False,
            )

            task = {
                "id": uuid.uuid4().hex[:8],
                "description": ot["description"],
                "owner": "Me",
                "delegated": False,
                "source_title": title,
                "source_url": page_url,
                "source_page_id": page_id,
                "source_context": source_context,
                "topics": topics,
                "follow_up_date": follow_up,
                "priority": priority,
                "status": "open",
                "steps": suggested_steps,
                "created_at": now.isoformat(),
            }
            new_tasks.append(task)
            existing_task_descs.add(ot["description"].lower())

    async def _emit_progress(current: int, total: int, title: str, status: str = "processing") -> None:
        """Send progress update if callback is set."""
        if on_progress:
            msg = {
                "status": status,
                "current": current,
                "total": total,
                "page_title": title,
                "new_tasks": len(new_tasks),
                "errors": errors,
            }
            result = on_progress(msg)
            if asyncio.iscoroutine(result):
                await result

    total_pages = len(pages)
    await _emit_progress(0, total_pages, "", "started")

    for idx, page in enumerate(pages):
        # Check for cancellation
        if cancel_event and cancel_event.is_set():
            logger.info("Intel scan cancelled after %d/%d pages", idx, total_pages)
            await _emit_progress(idx, total_pages, "", "cancelled")
            break

        page_title = page.get("title", "?")
        await _emit_progress(idx, total_pages, page_title)

        try:
            content_data = await get_page_content(page["id"])
        except Exception as exc:
            logger.warning("Failed to read page %s (%s): %s", page_title, page["id"], exc)
            errors += 1
            continue

        title = content_data.get("title", "")
        content = content_data.get("content", "")
        page_url = page.get("url", "")
        page_date = page.get("last_edited_time", "")

        # Process the main page content (Summary)
        await _process_page_content(title, content, page_url, page["id"], page_date)

        # Process child pages (e.g. Summary, Transcript tabs from meeting tools)
        for child in content_data.get("child_pages", []):
            try:
                child_data = await get_page_content(child["id"])
                child_title = child.get("title", "") or child_data.get("title", "")
                child_content = child_data.get("content", "")
                logger.info("Intel scan: reading child page '%s' of '%s'", child_title, title)
                # Use parent title as source for better context
                source_title = f"{title} > {child_title}" if child_title else title
                await _process_page_content(
                    source_title, child_content, page_url, child["id"], page_date,
                )
            except Exception as exc:
                logger.warning("Failed to read child page %s: %s", child.get("title", "?"), exc)

    # Emit completion progress
    was_cancelled = cancel_event and cancel_event.is_set()
    if not was_cancelled:
        await _emit_progress(total_pages, total_pages, "", "finalizing")

    # Merge into intel
    intel["topics"] = dict(topic_counter.most_common())
    intel["people"] = dict(people_counter.most_common())
    existing_page_index = intel.get("page_index", {})
    existing_page_index.update(page_index)
    intel["page_index"] = existing_page_index
    intel["smart_tasks"] = intel.get("smart_tasks", []) + new_tasks
    intel["pages_scanned"] = len(pages)
    intel["last_scan_at"] = now.isoformat()
    intel["scan_history"].append({
        "at": now.isoformat(),
        "pages": len(pages),
        "new_tasks": len(new_tasks),
        "type": scan_type,
    })
    intel["scan_history"] = intel["scan_history"][-20:]

    # Rebuild executive summary
    intel["executive_summary"] = _build_executive_summary(intel)

    _save_intel(intel)

    # Also save new tasks to the tracked tasks file so the Tasks page shows them
    if new_tasks:
        _sync_to_tracked_tasks(new_tasks)

    return {
        "pages_scanned": len(pages),
        "pages_with_content": pages_with_content,
        "pages_failed": errors,
        "topics_found": len(intel["topics"]),
        "people_found": len(intel["people"]),
        "new_tasks_added": len(new_tasks),
        "total_smart_tasks": len(intel["smart_tasks"]),
        "top_topics": dict(topic_counter.most_common(5)),
        "top_people": dict(people_counter.most_common(5)),
        "executive_summary": intel["executive_summary"],
    }


# Action verbs that signal a task when found at the start of a bullet/line
_ACTION_VERBS = re.compile(
    r"^(update|review|prepare|send|share|create|set up|schedule|follow[\s\-]?up|"
    r"check|finalize|draft|write|submit|complete|plan|organize|coordinate|arrange|"
    r"confirm|reach out|discuss|present|deliver|implement|fix|resolve|assign|"
    r"investigate|research|evaluate|assess|approve|escalate|migrate|deploy|"
    r"configure|test|validate|document|track|monitor|align|prioritize|"
    r"compile|consolidate|refine|iterate|prototype|design|build|launch|"
    r"onboard|train|hire|interview|budget|forecast|invoice|audit|"
    r"analyze|measure|report|communicate|notify|announce|publish|"
    r"integrate|connect|sync|transfer|upgrade|install|provision|"
    r"negotiate|close|renew|extend|cancel|archive|clean[\s\-]?up|"
    r"define|scope|estimate|brainstorm|outline|map|diagram|"
    r"book|reserve|order|purchase|procure|request|file|register|"
    r"enable|disable|grant|revoke|add|remove|move|rename|merge|split)\b",
    re.IGNORECASE,
)


def _extract_own_tasks(text: str, title: str) -> list[dict]:
    """Extract tasks assigned to the user (no @mention, or self-referencing).

    Detects:
    - Unchecked to-do items: ``[ ] task text``
    - TODO/ACTION keywords: ``TODO: task text``
    - Bullet points with action verbs: ``• Update the slide...``
    - Numbered items with action verbs: ``- Review the budget...``
    """
    tasks = []
    seen: set[str] = set()

    def _add(desc: str) -> None:
        desc = desc.strip().rstrip(".").strip()
        if len(desc) < 6:
            return
        if desc.startswith("@"):
            return
        # Skip items that look like delegations (Name to/will/should verb)
        if re.match(r"[A-Z][a-z]+\s+(to|will|should|needs? to)\s+", desc):
            return
        key = desc.lower()[:50]
        if key not in seen:
            seen.add(key)
            tasks.append({"description": desc})

    # Pattern 1: unchecked checkboxes without @mention or name delegation
    for match in re.finditer(r"\[[ ]\]\s*(.{6,})", text):
        _add(match.group(1))

    # Pattern 2: TODO/ACTION lines without @mention
    for match in re.finditer(r"(?:TODO|ACTION)[:\s]+([^@\n]{6,})", text):
        _add(match.group(1))

    # Pattern 3: Bullet points (•) with action verbs
    for match in re.finditer(r"[•]\s+(.{6,})", text):
        desc = match.group(1).strip()
        if _ACTION_VERBS.match(desc):
            _add(desc)

    # Pattern 4: List items (- or *) with action verbs (from numbered_list_item)
    for match in re.finditer(r"^[\-\*]\s+(.{6,})$", text, re.MULTILINE):
        desc = match.group(1).strip()
        if desc.startswith("@"):
            continue  # handled by _detect_delegations
        if _ACTION_VERBS.match(desc):
            _add(desc)

    return tasks


# -----------------------------------------------------------------------
# Executive summary
# -----------------------------------------------------------------------

def _build_executive_summary(intel: dict) -> dict:
    """Build the executive summary from intel data.

    Structures tasks into an Eisenhower matrix and highlights critical items.
    """
    tasks = [t for t in intel.get("smart_tasks", []) if t.get("status") != "done"]
    now = datetime.now(timezone.utc)

    # Recalculate priorities with age
    for task in tasks:
        created = task.get("created_at", "")
        age_days = 0
        if created:
            try:
                age_days = (now - datetime.fromisoformat(created)).days
            except (ValueError, TypeError):
                pass
        task["priority"] = _classify_priority(
            task["description"],
            is_delegated=task.get("delegated", False),
            age_days=age_days,
        )
        task["age_days"] = age_days

    # Eisenhower matrix
    q1 = [t for t in tasks if t["priority"]["quadrant"] == 1]
    q2 = [t for t in tasks if t["priority"]["quadrant"] == 2]
    q3 = [t for t in tasks if t["priority"]["quadrant"] == 3]
    q4 = [t for t in tasks if t["priority"]["quadrant"] == 4]

    # Upcoming follow-ups (next 7 days)
    today = now.strftime("%Y-%m-%d")
    week_out = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    upcoming = [
        t for t in tasks
        if t.get("follow_up_date") and today <= t["follow_up_date"] <= week_out
    ]
    upcoming.sort(key=lambda t: t.get("follow_up_date", ""))

    # Overdue follow-ups
    overdue = [
        t for t in tasks
        if t.get("follow_up_date") and t["follow_up_date"] < today
    ]
    overdue.sort(key=lambda t: t.get("follow_up_date", ""))

    # Delegation summary
    delegated = [t for t in tasks if t.get("delegated")]
    delegation_by_person: dict[str, int] = {}
    for t in delegated:
        delegation_by_person[t.get("owner", "Unknown")] = delegation_by_person.get(t.get("owner", "Unknown"), 0) + 1

    # Topic coverage
    topics = intel.get("topics", {})
    top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:8]

    return {
        "matrix": {
            "q1_do_first": [_summarize_task(t) for t in q1],
            "q2_schedule": [_summarize_task(t) for t in q2],
            "q3_delegate": [_summarize_task(t) for t in q3],
            "q4_defer": [_summarize_task(t) for t in q4],
            "q1_count": len(q1),
            "q2_count": len(q2),
            "q3_count": len(q3),
            "q4_count": len(q4),
        },
        "upcoming_follow_ups": [_summarize_task(t) for t in upcoming[:10]],
        "overdue_follow_ups": [_summarize_task(t) for t in overdue[:10]],
        "delegation_summary": delegation_by_person,
        "top_topics": dict(top_topics),
        "total_open": len(tasks),
        "total_delegated": len(delegated),
        "total_overdue": len(overdue),
    }


def _summarize_task(task: dict) -> dict:
    # Auto-generate steps for tasks that don't have any yet
    steps = (task.get("steps") or "").strip()
    if not steps:
        steps = _suggest_steps(
            task.get("description", ""),
            task.get("source_context", ""),
            task.get("topics", []),
            owner=task.get("owner", ""),
            delegated=task.get("delegated", False),
        )
        # Persist generated steps back to the task so they're saved on next write
        task["steps"] = steps
    return {
        "id": task.get("id"),
        "description": task.get("description", ""),
        "owner": task.get("owner", ""),
        "delegated": task.get("delegated", False),
        "follow_up_date": task.get("follow_up_date"),
        "source_title": task.get("source_title", ""),
        "source_url": task.get("source_url", ""),
        "source_context": task.get("source_context", ""),
        "age_days": task.get("age_days", 0),
        "quadrant": task.get("priority", {}).get("quadrant"),
        "quadrant_label": task.get("priority", {}).get("quadrant_label", ""),
        "topics": task.get("topics", []),
        "status": task.get("status", "open"),
        "steps": steps,
    }


# -----------------------------------------------------------------------
# Query functions
# -----------------------------------------------------------------------

def get_intel() -> dict:
    """Get the full intelligence data."""
    intel = _load_intel()
    if intel.get("smart_tasks"):
        # _build_executive_summary -> _summarize_task may auto-generate steps
        # for tasks that were missing them. Since _summarize_task writes back
        # to the task dict (which is a reference into intel["smart_tasks"]),
        # we save once after rebuilding to persist any generated steps.
        intel["executive_summary"] = _build_executive_summary(intel)
        _save_intel(intel)
    return intel


def build_graph_data() -> dict:
    """Build graph nodes and edges for the relationship visualization.

    Derives relationships from three sources (in priority order):
    1. page_index — per-page people + topic associations from scan
    2. smart_tasks — owner/topic/source_page links
    3. global people/topics dicts — fallback for weight info

    Returns {"nodes": [...], "edges": [...], "tasks": [...]}.
    """
    intel = _load_intel()
    page_index = intel.get("page_index", {})
    tasks = [t for t in intel.get("smart_tasks", []) if t.get("status") != "done"]
    global_people = intel.get("people", {})
    global_topics = intel.get("topics", {})

    nodes: dict[str, dict] = {}
    edge_weights: dict[tuple[str, str, str], int] = {}  # (src, tgt, type) -> weight

    def _add_node(nid: str, label: str, ntype: str, weight: int = 1, **extra: str) -> None:
        if nid in nodes:
            nodes[nid]["weight"] += weight
        else:
            nodes[nid] = {"id": nid, "label": label, "type": ntype, "weight": weight, **extra}

    def _add_edge(src: str, tgt: str, etype: str, weight: int = 1) -> None:
        key = (src, tgt, etype) if src < tgt else (tgt, src, etype)
        edge_weights[key] = edge_weights.get(key, 0) + weight

    # --- Nodes from global dicts ---
    for person, count in global_people.items():
        _add_node(f"person:{person}", person, "person", count)
    for topic, count in global_topics.items():
        if topic == "general":
            continue
        _add_node(f"topic:{topic}", topic, "topic", count)

    # --- Edges + nodes from page_index ---
    for pid, page in page_index.items():
        title = page.get("title", "Untitled")
        # Shorten long titles (e.g., "Parent > Child" -> keep as-is but truncate)
        short = title[:50] + "..." if len(title) > 50 else title
        page_nid = f"page:{pid}"
        _add_node(page_nid, short, "page", 1, url=page.get("url", ""))

        for person in page.get("people", []):
            p_nid = f"person:{person}"
            _add_node(p_nid, person, "person", 0)  # weight added by global dict
            _add_edge(page_nid, p_nid, "mention")

        for topic in page.get("topics", []):
            if topic == "general":
                continue
            t_nid = f"topic:{topic}"
            _add_node(t_nid, topic, "topic", 0)
            _add_edge(page_nid, t_nid, "covers")

        # Derive person<->topic edges from co-occurrence on this page
        for person in page.get("people", []):
            for topic in page.get("topics", []):
                if topic == "general":
                    continue
                _add_edge(f"person:{person}", f"topic:{topic}", "works_on")

        # --- New node types from LLM-enriched data ---

        # Projects
        for project in page.get("projects", []):
            proj_nid = f"project:{project}"
            _add_node(proj_nid, project, "project", 1)
            _add_edge(page_nid, proj_nid, "covers")
            # Link people on this page to the project
            for person in page.get("people", []):
                _add_edge(f"person:{person}", proj_nid, "works_on")

        # Organizations
        for org in page.get("organizations", []):
            org_nid = f"organization:{org}"
            _add_node(org_nid, org, "organization", 1)
            _add_edge(page_nid, org_nid, "covers")
            # Link people on this page to the org (member_of)
            for person in page.get("people", []):
                _add_edge(f"person:{person}", org_nid, "member_of")
            # Link projects on this page to the org (part_of)
            for project in page.get("projects", []):
                _add_edge(f"project:{project}", org_nid, "part_of")

        # Decisions
        for decision in page.get("decisions", []):
            if not isinstance(decision, dict):
                continue
            dec_text = decision.get("text", "")
            if not dec_text:
                continue
            dec_id = dec_text[:60].replace(" ", "_").lower()
            dec_nid = f"decision:{dec_id}"
            short_text = dec_text[:80] + ("..." if len(dec_text) > 80 else "")
            _add_node(dec_nid, short_text, "decision", 1)
            _add_edge(page_nid, dec_nid, "covers")
            # Link the decider
            decided_by = decision.get("by", "")
            if decided_by:
                by_nid = f"person:{decided_by}"
                _add_node(by_nid, decided_by, "person", 0)
                _add_edge(by_nid, dec_nid, "decided")

        # Tags
        for tag in page.get("tags", []):
            tag_nid = f"tag:{tag}"
            _add_node(tag_nid, tag, "tag", 1)
            _add_edge(page_nid, tag_nid, "tagged")

    # --- Edges from smart_tasks (fallback + enrichment) ---
    for task in tasks:
        owner = task.get("owner", "")
        if not owner or owner == "Me":
            continue
        o_nid = f"person:{owner}"
        _add_node(o_nid, owner, "person", 0)

        for topic in task.get("topics", []):
            if topic == "general":
                continue
            t_nid = f"topic:{topic}"
            _add_node(t_nid, topic, "topic", 0)
            _add_edge(o_nid, t_nid, "works_on")

        # Task -> source page link
        sp_id = task.get("source_page_id")
        if sp_id:
            sp_nid = f"page:{sp_id}"
            if sp_nid not in nodes:
                _add_node(sp_nid, task.get("source_title", "Untitled")[:50], "page", 1,
                          url=task.get("source_url", ""))
            _add_edge(o_nid, sp_nid, "mention")

    # --- Build response ---
    edge_list = [
        {"source": s, "target": t, "type": tp, "weight": w}
        for (s, t, tp), w in edge_weights.items()
    ]

    # Include open tasks for sidebar display
    task_summaries = [
        {
            "id": t.get("id"),
            "description": t.get("description", ""),
            "owner": t.get("owner", ""),
            "topics": t.get("topics", []),
            "quadrant": t.get("priority", {}).get("quadrant"),
            "quadrant_label": t.get("priority", {}).get("quadrant_label", ""),
            "follow_up_date": t.get("follow_up_date"),
            "source_title": t.get("source_title", ""),
            "source_page_id": t.get("source_page_id", ""),
        }
        for t in tasks
    ]

    return {
        "nodes": list(nodes.values()),
        "edges": edge_list,
        "tasks": task_summaries,
    }


def get_smart_tasks(owner: str = "", topic: str = "", quadrant: int = 0,
                    include_done: bool = False) -> dict:
    """Get smart tasks with optional filters.

    Args:
        owner: Filter by owner.
        topic: Filter by topic.
        quadrant: Filter by Eisenhower quadrant (1-4), 0 for all.
        include_done: Include completed tasks.
    """
    intel = _load_intel()
    tasks = intel.get("smart_tasks", [])
    now = datetime.now(timezone.utc)

    # Recalculate age and priority
    for task in tasks:
        created = task.get("created_at", "")
        age_days = 0
        if created:
            try:
                age_days = (now - datetime.fromisoformat(created)).days
            except (ValueError, TypeError):
                pass
        task["age_days"] = age_days
        task["priority"] = _classify_priority(
            task["description"],
            is_delegated=task.get("delegated", False),
            age_days=age_days,
        )

    if not include_done:
        tasks = [t for t in tasks if t.get("status") != "done"]
    if owner:
        ol = owner.lower()
        tasks = [t for t in tasks if ol in t.get("owner", "").lower()]
    if topic:
        tl = topic.lower()
        tasks = [t for t in tasks if any(tl in tp.lower() for tp in t.get("topics", []))]
    if quadrant:
        tasks = [t for t in tasks if t.get("priority", {}).get("quadrant") == quadrant]

    # Sort: Q1 first, then Q2, Q3, Q4; within quadrant by follow-up date
    tasks.sort(key=lambda t: (
        t.get("priority", {}).get("quadrant", 4),
        t.get("follow_up_date") or "9999",
    ))

    return {"tasks": [_summarize_task(t) for t in tasks], "count": len(tasks)}


def update_smart_task(
    task_id: str,
    status: str = "",
    follow_up_date: str = "",
    quadrant: int = 0,
    description: str = "",
    owner: str = "",
    steps: str = "",
) -> dict:
    """Update a smart task's fields."""
    intel = _load_intel()
    for task in intel.get("smart_tasks", []):
        if task["id"] == task_id:
            if status:
                task["status"] = status
            if follow_up_date:
                task["follow_up_date"] = follow_up_date
            if quadrant in (1, 2, 3, 4):
                labels = {1: "Do First", 2: "Schedule", 3: "Delegate", 4: "Defer"}
                task["priority"] = {
                    "urgent": quadrant in (1, 3),
                    "important": quadrant in (1, 2),
                    "quadrant": quadrant,
                    "quadrant_label": labels[quadrant],
                }
            if description:
                task["description"] = description
            if owner:
                task["owner"] = owner
            if steps is not None and steps != "":
                task["steps"] = steps
            intel["executive_summary"] = _build_executive_summary(intel)
            _save_intel(intel)
            return {"message": "Task updated.", "task": _summarize_task(task)}
    return {"error": f"Task not found: {task_id}"}


def delete_smart_task(task_id: str) -> dict:
    """Delete a smart task."""
    intel = _load_intel()
    tasks = intel.get("smart_tasks", [])
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(i)
            intel["executive_summary"] = _build_executive_summary(intel)
            _save_intel(intel)
            return {"message": "Task deleted."}
    return {"error": f"Task not found: {task_id}"}
