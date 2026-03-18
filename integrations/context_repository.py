"""Context Repository — captures and persists rich Opus-synthesized digests of Notion pages.

Every scanned Notion page produces a context entry: a 300-600 word synthesized
digest capturing discussions, decisions, rationale, open questions, and action
intent.  Entries are tagged with topics, people, and projects for fast retrieval.

The repository enables:
- Historical context injection into epic generation prompts
- Agent queries about past discussions and decisions
- Re-evaluation of existing epics when new relevant context surfaces
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CTX_FILE = Path(__file__).parent.parent / "context_repository.json"

# -----------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------

def _load() -> dict[str, Any]:
    if _CTX_FILE.exists():
        try:
            return json.loads(_CTX_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load context repository, starting fresh")
    return {
        "entries": {},
        "topic_index": {},
        "person_index": {},
        "page_to_entry": {},
        "stats": {"total_entries": 0, "last_updated": None},
    }


def _save(data: dict[str, Any]) -> None:
    data["stats"]["total_entries"] = len(data.get("entries", {}))
    data["stats"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    _CTX_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _rebuild_indexes(data: dict[str, Any]) -> None:
    """Rebuild topic_index and person_index from entries."""
    topic_idx: dict[str, list[str]] = {}
    person_idx: dict[str, list[str]] = {}
    page_map: dict[str, str] = {}

    for entry_id, entry in data.get("entries", {}).items():
        for t in entry.get("topics", []):
            topic_idx.setdefault(t, []).append(entry_id)
        for p in entry.get("people", []):
            person_idx.setdefault(p, []).append(entry_id)
        pid = entry.get("page_id")
        if pid:
            page_map[pid] = entry_id

    data["topic_index"] = topic_idx
    data["person_index"] = person_idx
    data["page_to_entry"] = page_map


def _content_hash(content: str) -> str:
    """SHA-256 of first 8000 chars, return first 8 hex digits."""
    return hashlib.sha256(content[:8000].encode()).hexdigest()[:8]


# -----------------------------------------------------------------------
# LLM Prompt
# -----------------------------------------------------------------------

_CONTEXT_SYNTHESIS_PROMPT = """\
You are synthesizing a Notion page into a rich context entry for a corporate knowledge repository.
This entry will be stored permanently and retrieved months later when related topics arise.

Page title: {title}
Page date: {page_date}
Page content:
{content}

Already extracted metadata:
- Topics: {topics}
- People: {people}
- Decisions: {decisions}

Create a CONTEXT DIGEST that captures:
1. **Background & Situation**: What prompted this discussion/document? What's the context?
2. **Key Discussions**: What was discussed, debated, or analyzed? Include specifics.
3. **Decisions & Rationale**: What was decided and WHY? Include reasoning.
4. **Open Questions & Risks**: What remains unresolved? What risks were identified?
5. **Action Intent**: What actions or directions were indicated, even if not formalized as tasks?
6. **Relationships**: How does this connect to other projects, teams, or initiatives?

Write 300-600 words. Be specific and factual — include names, numbers, dates, and technical details.
Do NOT be generic. This digest must be useful to someone 3 months from now who needs to recall
what was discussed and decided here.

Return ONLY the digest text, no JSON wrapping.
"""

_RELEVANCE_CHECK_PROMPT = """\
You are reviewing whether new context information is relevant to an existing epic.

EXISTING EPIC:
Title: {epic_title}
Description: {epic_description}
Stories: {story_titles}

NEW CONTEXT (from recent Notion page scans):
{new_context}

Questions:
1. Does this new context contain information that should update the epic description?
2. Does it suggest new user stories that should be added?
3. Does it change the priority or scope of the epic?

Return ONLY valid JSON:
{{"action": "update", "reason": "brief explanation", "suggested_description_addition": "text to append to epic description or empty", "suggested_stories": ["new story title 1"]}}

or

{{"action": "skip", "reason": "brief explanation", "suggested_description_addition": "", "suggested_stories": []}}
"""


# -----------------------------------------------------------------------
# Core synthesis
# -----------------------------------------------------------------------

async def synthesize_context_entry(
    page_id: str,
    title: str,
    content: str,
    page_url: str,
    page_date: str,
    llm_meta: dict,
) -> dict | None:
    """Synthesize and store a context entry for a Notion page.

    Reuses already-extracted LLM metadata (topics, people, decisions) to avoid
    duplicate LLM calls.  Only the context digest is a new LLM call.

    Returns the entry dict, or None if synthesis fails.
    """
    data = _load()
    chash = _content_hash(content)

    # Skip if entry already exists with same content hash
    existing_id = data.get("page_to_entry", {}).get(page_id)
    if existing_id:
        existing = data["entries"].get(existing_id, {})
        if existing.get("content_hash") == chash:
            logger.debug("Context entry for '%s' unchanged (hash %s), skipping", title, chash)
            return existing

    from llm import llm_call

    prompt = _CONTEXT_SYNTHESIS_PROMPT.format(
        title=title,
        page_date=page_date or "unknown",
        content=content[:8000],
        topics=", ".join(llm_meta.get("topics", [])),
        people=", ".join(llm_meta.get("people", [])),
        decisions=json.dumps(llm_meta.get("decisions", []), default=str),
    )

    digest = await llm_call("context_synthesis", prompt, max_tokens=1500)
    if not digest:
        logger.warning("Context synthesis failed for '%s'", title)
        return None

    entry_id = existing_id or f"ctx_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    entry = {
        "id": entry_id,
        "page_id": page_id,
        "page_title": title,
        "page_url": page_url,
        "context_digest": digest,
        "topics": llm_meta.get("topics", []),
        "people": llm_meta.get("people", []),
        "organizations": llm_meta.get("organizations", []),
        "projects": llm_meta.get("projects", []),
        "decisions": llm_meta.get("decisions", []),
        "tags": llm_meta.get("tags", []),
        "source_date": page_date,
        "created_at": data["entries"].get(entry_id, {}).get("created_at", now),
        "updated_at": now,
        "content_hash": chash,
    }

    data["entries"][entry_id] = entry
    _rebuild_indexes(data)
    _save(data)

    logger.info("Context entry %s for '%s' (%d words)", "updated" if existing_id else "created", title, len(digest.split()))
    return entry


# -----------------------------------------------------------------------
# Retrieval
# -----------------------------------------------------------------------

def get_context_entry(entry_id: str) -> dict | None:
    """Get a single context entry by ID."""
    return _load().get("entries", {}).get(entry_id)


def get_context_for_page(page_id: str) -> dict | None:
    """Get context entry for a Notion page."""
    data = _load()
    entry_id = data.get("page_to_entry", {}).get(page_id)
    if entry_id:
        return data["entries"].get(entry_id)
    return None


def query_by_topics(topics: list[str], max_results: int = 10) -> list[dict]:
    """Return entries matching any given topic, sorted by topic overlap then recency."""
    data = _load()
    idx = data.get("topic_index", {})
    entry_ids: dict[str, int] = {}
    for t in topics:
        for eid in idx.get(t, []):
            entry_ids[eid] = entry_ids.get(eid, 0) + 1

    entries = []
    for eid, overlap in entry_ids.items():
        e = data["entries"].get(eid)
        if e:
            entries.append((overlap, e.get("source_date", ""), e))

    entries.sort(key=lambda x: (-x[0], x[1]), reverse=False)
    # Sort: highest overlap first, then most recent
    entries.sort(key=lambda x: (-x[0], ""), reverse=False)
    return [e for _, _, e in entries[:max_results]]


def query_by_people(people: list[str], max_results: int = 10) -> list[dict]:
    """Return entries mentioning any of the given people."""
    data = _load()
    idx = data.get("person_index", {})
    seen: set[str] = set()
    results: list[dict] = []
    for p in people:
        for eid in idx.get(p, []):
            if eid not in seen:
                seen.add(eid)
                e = data["entries"].get(eid)
                if e:
                    results.append(e)
    # Sort by source_date descending
    results.sort(key=lambda e: e.get("source_date", ""), reverse=True)
    return results[:max_results]


def search_context(query: str, max_results: int = 10) -> list[dict]:
    """Keyword search across context_digest, page_title, topics, people, projects."""
    data = _load()
    query_lower = query.lower()
    terms = query_lower.split()
    scored: list[tuple[int, dict]] = []

    for entry in data.get("entries", {}).values():
        searchable = " ".join([
            entry.get("context_digest", ""),
            entry.get("page_title", ""),
            " ".join(entry.get("topics", [])),
            " ".join(entry.get("people", [])),
            " ".join(entry.get("projects", [])),
        ]).lower()

        score = sum(1 for t in terms if t in searchable)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: (-x[0], x[1].get("source_date", "")))
    return [e for _, e in scored[:max_results]]


def get_related_context(
    topics: list[str] | str = "",
    people: list[str] | str = "",
    exclude_page_ids: list[str] | None = None,
    max_results: int = 5,
    max_chars: int = 4000,
) -> str:
    """Return a formatted text block of related context for LLM prompt injection.

    Accepts topics/people as either lists or comma-separated strings (for API use).
    """
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split(",") if t.strip()]
    if isinstance(people, str):
        people = [p.strip() for p in people.split(",") if p.strip()]

    exclude = set(exclude_page_ids or [])

    # Gather candidates from topics and people
    seen: set[str] = set()
    candidates: list[tuple[int, dict]] = []

    data = _load()
    idx_t = data.get("topic_index", {})
    idx_p = data.get("person_index", {})

    # Topic matches (primary, scored by overlap)
    entry_scores: dict[str, int] = {}
    for t in topics:
        for eid in idx_t.get(t, []):
            entry_scores[eid] = entry_scores.get(eid, 0) + 2  # weight 2 for topics

    for p in people:
        for eid in idx_p.get(p, []):
            entry_scores[eid] = entry_scores.get(eid, 0) + 1  # weight 1 for people

    for eid, score in entry_scores.items():
        e = data["entries"].get(eid)
        if e and e.get("page_id") not in exclude and eid not in seen:
            seen.add(eid)
            candidates.append((score, e))

    candidates.sort(key=lambda x: (-x[0], x[1].get("source_date", "")))
    selected = [e for _, e in candidates[:max_results]]

    if not selected:
        return ""

    # Format output
    parts: list[str] = ["## Related Historical Context\n"]
    total_chars = 0

    for entry in selected:
        digest = entry.get("context_digest", "")
        # Truncate individual digests if needed
        if total_chars + len(digest) > max_chars:
            remaining = max_chars - total_chars
            if remaining < 100:
                break
            digest = digest[:remaining] + "..."

        header = f"### {entry.get('page_title', 'Untitled')} ({entry.get('source_date', 'unknown')[:10]})"
        topics_line = f"Topics: {', '.join(entry.get('topics', []))}"
        people_line = f"People: {', '.join(entry.get('people', []))}"

        block = f"{header}\n{digest}\n{topics_line}\n{people_line}\n"
        parts.append(block)
        total_chars += len(digest)

    return "\n".join(parts)


def get_stats() -> dict:
    """Return summary statistics about the context repository."""
    data = _load()
    entries = data.get("entries", {})

    topic_counts: dict[str, int] = {}
    for entry in entries.values():
        for t in entry.get("topics", []):
            topic_counts[t] = topic_counts.get(t, 0) + 1

    dates = [e.get("source_date", "") for e in entries.values() if e.get("source_date")]
    dates.sort()

    return {
        "total_entries": len(entries),
        "topics": topic_counts,
        "date_range": {
            "earliest": dates[0] if dates else None,
            "latest": dates[-1] if dates else None,
        },
        "last_updated": data.get("stats", {}).get("last_updated"),
    }


# -----------------------------------------------------------------------
# Epic re-evaluation
# -----------------------------------------------------------------------

async def check_context_relevance() -> dict:
    """Compare recent context entries against existing epics for relevance.

    If new context is topically relevant to an existing epic, call Opus to
    evaluate whether the epic should be updated.  Respects manual_changes
    registry — skips manually edited epics.

    Returns dict with flagged_epics and updates_applied counts.
    """
    from integrations.epics import get_epics, update_epic
    from integrations.manual_changes import get_edited_epic_ids
    from llm import llm_call

    data = _load()
    entries = data.get("entries", {})
    edited_ids = get_edited_epic_ids()

    if not entries:
        return {"message": "No context entries available", "flagged_epics": 0, "updates_applied": 0}

    epics = get_epics()
    if not epics:
        return {"message": "No epics to evaluate", "flagged_epics": 0, "updates_applied": 0}

    # Find entries updated in the last 24 hours (recent context)
    cutoff = datetime.now(timezone.utc).isoformat()[:10]  # today
    recent_entries = [
        e for e in entries.values()
        if (e.get("updated_at", "") or "")[:10] >= cutoff
    ]

    if not recent_entries:
        return {"message": "No recent context entries to check", "flagged_epics": 0, "updates_applied": 0}

    # Build topic-to-entry map for recent entries
    recent_topics: dict[str, list[dict]] = {}
    for e in recent_entries:
        for t in e.get("topics", []):
            recent_topics.setdefault(t, []).append(e)

    flagged = 0
    updated = 0

    for epic in epics:
        epic_id = epic.get("id", "")
        if epic_id in edited_ids:
            continue

        # Check topic overlap
        epic_topics = set()
        for story in epic.get("stories", []):
            epic_topics.update(story.get("topics", []))
        # Also check epic title words against topics
        title_words = set(epic.get("title", "").lower().split())

        relevant_entries: list[dict] = []
        for t, ents in recent_topics.items():
            t_lower = t.lower().replace("/", " ")
            if t in epic_topics or any(w in t_lower for w in title_words if len(w) > 3):
                relevant_entries.extend(ents)

        if not relevant_entries:
            continue

        flagged += 1

        # Build context block from relevant entries
        context_block = "\n\n".join(
            f"**{e.get('page_title', '')}** ({e.get('source_date', '')[:10]})\n{e.get('context_digest', '')[:500]}"
            for e in relevant_entries[:3]
        )

        story_titles = ", ".join(s.get("title", "") for s in epic.get("stories", []))

        prompt = _RELEVANCE_CHECK_PROMPT.format(
            epic_title=epic.get("title", ""),
            epic_description=epic.get("description", ""),
            story_titles=story_titles,
            new_context=context_block,
        )

        raw = await llm_call("context_relevance_check", prompt, max_tokens=500)
        if not raw:
            continue

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from relevance check for epic '%s'", epic.get("title"))
            continue

        if result.get("action") == "update":
            addition = result.get("suggested_description_addition", "").strip()
            if addition:
                new_desc = epic.get("description", "") + "\n\n" + addition
                update_epic(epic_id, description=new_desc)
                updated += 1
                logger.info("Updated epic '%s' with new context: %s", epic.get("title"), result.get("reason"))

            # Add suggested stories
            for story_title in result.get("suggested_stories", []):
                if story_title:
                    from integrations.epics import create_story
                    create_story(
                        epic_id=epic_id,
                        title=story_title,
                        description=f"Suggested from context: {result.get('reason', '')}",
                        owner=epic.get("owner", "Unassigned"),
                    )
                    logger.info("Added story '%s' to epic '%s'", story_title, epic.get("title"))

    msg = f"Checked {len(epics)} epics against {len(recent_entries)} recent context entries"
    return {"message": msg, "flagged_epics": flagged, "updates_applied": updated}


# -----------------------------------------------------------------------
# Smart context summaries for tasks, stories, and epics
# -----------------------------------------------------------------------

_ITEM_SUMMARY_PROMPT = """\
You are creating a rich background summary for a {item_type} in a project management system.
This summary helps the user understand the full context behind this item — not just what it says,
but WHY it exists, what discussions led to it, and what they should know before acting on it.

ITEM:
Type: {item_type}
Title: {title}
Description: {description}

SOURCE PAGE CONTEXT:
{source_context}

RELATED HISTORICAL CONTEXT (from other discussions and meetings on similar topics):
{related_context}

Create a concise but informative background summary (150-300 words) that covers:
1. **What this is about**: Plain-language explanation of what this item involves
2. **Background**: What discussions, decisions, or events led to this item
3. **Key people**: Who is involved and what their role/stake is
4. **Connected work**: How this relates to other initiatives, projects, or past decisions
5. **Things to know**: Risks, open questions, or important context the user should be aware of

Be specific — use names, dates, and details from the context. Skip sections that have no relevant info.
Return ONLY the summary text, no JSON wrapping.
"""

_SMART_STEPS_PROMPT = """\
You are generating practical action steps for a task based on its description and
the rich historical context from the organization's knowledge base.

TASK:
Description: {description}
Owner: {owner}
Topics: {topics}

SOURCE PAGE CONTEXT (the meeting/document where this task originated):
{source_context}

RELATED CONTEXT (from other discussions and meetings on similar topics):
{related_context}

Generate 4-7 specific, actionable steps for completing this task. Steps should:
- Be informed by the actual context (reference specific people, systems, documents, decisions)
- Be practical and ordered logically
- Include any coordination or dependencies evident from the context
- Be concise (one line each)

Return ONLY a numbered list:
1. First step
2. Second step
...
"""


async def generate_item_summary(
    item_type: str,
    title: str,
    description: str,
    topics: list[str] | None = None,
    people: list[str] | None = None,
    source_page_id: str | None = None,
) -> dict:
    """Generate a smart context summary for a task, epic, or story.

    Queries the context repository for related entries and calls Opus
    to synthesize a background summary specific to this item.
    """
    from llm import llm_call

    # Get source page context if available
    source_context = ""
    if source_page_id:
        entry = get_context_for_page(source_page_id)
        if entry:
            source_context = entry.get("context_digest", "")

    # Get related context from other entries
    related_context = get_related_context(
        topics=topics or [],
        people=people or [],
        exclude_page_ids=[source_page_id] if source_page_id else None,
        max_results=3,
        max_chars=2000,
    )

    prompt = _ITEM_SUMMARY_PROMPT.format(
        item_type=item_type,
        title=title,
        description=description or "(no description)",
        source_context=source_context or "(no source page context available)",
        related_context=related_context or "(no related context available)",
    )

    summary_text = await llm_call("item_context_summary", prompt, max_tokens=800)
    if not summary_text:
        return {"summary": "", "related_entries": [], "generated_at": None}

    # Collect IDs of related entries used
    related_ids = []
    if source_page_id:
        data = _load()
        eid = data.get("page_to_entry", {}).get(source_page_id)
        if eid:
            related_ids.append(eid)

    return {
        "summary": summary_text,
        "related_entries": related_ids,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def generate_smart_steps(
    description: str,
    owner: str = "",
    topics: list[str] | None = None,
    source_page_id: str | None = None,
    source_context_snippet: str = "",
) -> str | None:
    """Generate context-aware action steps for a task using the context repository.

    Returns a numbered list string, or None if generation fails (caller should
    fall back to heuristic steps).
    """
    from llm import llm_call

    # Get source page context
    source_context = source_context_snippet
    if source_page_id:
        entry = get_context_for_page(source_page_id)
        if entry:
            source_context = entry.get("context_digest", "")

    # Get related context
    related_context = get_related_context(
        topics=topics or [],
        exclude_page_ids=[source_page_id] if source_page_id else None,
        max_results=2,
        max_chars=1500,
    )

    # Only call LLM if we have some context to work with
    if not source_context and not related_context:
        return None

    prompt = _SMART_STEPS_PROMPT.format(
        description=description,
        owner=owner or "Unassigned",
        topics=", ".join(topics or []),
        source_context=source_context or "(no source context)",
        related_context=related_context or "(no related context)",
    )

    return await llm_call("smart_steps", prompt, max_tokens=500)
