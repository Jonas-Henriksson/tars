"""Agile auto-classification engine — Opus-powered hierarchy generation.

Analyzes all smart tasks extracted from Notion meeting transcriptions and
auto-generates the full agile hierarchy:

    Theme → Initiative → Epic → User Story → Task

Key features:
- Builds a topic knowledge map from historical Notion page data
- Uses Claude Opus for complex semantic grouping and gap-fill
- Proposes missing tasks/stories/epics for complete delivery
- Normalizes grammar (capitalization, concise titles)
- Respects manual overrides — tasks manually moved by users are preserved
- Marks all auto-generated items with source="auto" for visual distinction
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_INTEL_FILE = Path(__file__).parent.parent / "notion_intel.json"


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output, ignoring preamble and markdown."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find the first { and last } to extract the JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise json.JSONDecodeError("No JSON object found in response", text, 0)


def _get_opus_client():
    """Get Anthropic client for Opus calls."""
    try:
        from config import ANTHROPIC_API_KEY
        if not ANTHROPIC_API_KEY:
            return None
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        logger.warning("Cannot initialize Anthropic client: %s", e)
        return None


# ---------------------------------------------------------------------------
# Phase 0: Historical context retrieval
# ---------------------------------------------------------------------------

def _build_knowledge_map(intel: dict) -> dict[str, dict]:
    """Build a topic knowledge map from all scanned Notion pages.

    For each unique topic/project across all pages, compiles:
    - First/last mention dates
    - Mention count
    - Page summaries with dates
    - People involved
    - Related topics

    This ensures the classifier can connect a new task to discussions
    from months ago that had no explicit task created at the time.
    """
    page_index = intel.get("page_index", {})
    knowledge_map: dict[str, dict] = {}

    for page_id, page_info in page_index.items():
        page_date = page_info.get("last_edited_time", page_info.get("scanned_at", ""))
        page_title = page_info.get("title", "")
        page_summary = page_info.get("summary", "")
        page_topics = page_info.get("topics", [])
        page_projects = page_info.get("projects", [])
        page_people = page_info.get("people", [])

        # Combine topics and projects as knowledge map keys
        keys = set()
        for t in page_topics:
            # Handle hierarchical topics like "supply-chain/optimization"
            keys.add(t.split("/")[0] if "/" in t else t)
        for p in page_projects:
            keys.add(p)

        for key in keys:
            if not key or len(key) < 2:
                continue

            if key not in knowledge_map:
                knowledge_map[key] = {
                    "first_mentioned": page_date,
                    "last_mentioned": page_date,
                    "mention_count": 0,
                    "page_summaries": [],
                    "people_involved": set(),
                    "related_topics": set(),
                }

            entry = knowledge_map[key]
            entry["mention_count"] += 1
            if page_date and page_date < entry["first_mentioned"]:
                entry["first_mentioned"] = page_date
            if page_date and page_date > entry["last_mentioned"]:
                entry["last_mentioned"] = page_date

            if page_summary:
                entry["page_summaries"].append({
                    "date": page_date[:10] if page_date else "",
                    "title": page_title,
                    "summary": page_summary[:200],
                })

            for person in page_people:
                if isinstance(person, str):
                    entry["people_involved"].add(person)

            for t in page_topics:
                if t != key:
                    entry["related_topics"].add(t.split("/")[0] if "/" in t else t)

    # Convert sets to sorted lists for JSON serialization
    for entry in knowledge_map.values():
        entry["people_involved"] = sorted(entry["people_involved"])
        entry["related_topics"] = sorted(entry["related_topics"])
        # Keep only most recent 5 page summaries per topic to manage context size
        entry["page_summaries"] = sorted(
            entry["page_summaries"], key=lambda x: x.get("date", ""), reverse=True
        )[:5]

    return knowledge_map


def _compact_knowledge_map(km: dict, max_entries: int = 50) -> str:
    """Serialize knowledge map to compact string for Opus context.

    Limits to top entries by mention count to fit context window.
    """
    if not km:
        return "No historical context available."

    # Sort by mention count, take top entries
    sorted_entries = sorted(km.items(), key=lambda x: x[1]["mention_count"], reverse=True)
    top_entries = sorted_entries[:max_entries]

    lines = []
    for topic, info in top_entries:
        summaries_text = "; ".join(
            f"{s['date']}: {s['summary']}" for s in info["page_summaries"][:3]
        )
        people = ", ".join(info["people_involved"][:5])
        lines.append(
            f"- {topic} (mentioned {info['mention_count']}x, "
            f"{info['first_mentioned'][:10]}–{info['last_mentioned'][:10]}): "
            f"People: {people or 'unknown'}. "
            f"Context: {summaries_text or 'no summary'}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 1: Theme + Initiative discovery
# ---------------------------------------------------------------------------

_PHASE1_PROMPT = """\
You are analyzing {count} tasks extracted from meeting notes for a team.
Your job is to organize them into an agile hierarchy.

HISTORICAL CONTEXT:
Below is a knowledge map of topics discussed across all meetings in the
organization. Use this to understand the full history behind each topic.
A task about "SAP readiness" may seem isolated, but if SAP was discussed
extensively 6 months ago, that historical context should inform how you
group and prioritize it. Connect new tasks to historical threads.

{topic_knowledge_map}

RULES:
- Create Themes (highest level strategic areas, 3-8 typically)
- Create Initiatives under themes (strategic goals/projects)
- Use the historical context to connect tasks to broader organizational
  themes even if the task description alone seems narrow
- Mark tasks as "operational" if they are admin, hiring, vendor management,
  recurring ops, or don't belong to a strategic initiative
- Mark tasks as "unclassified" if you're not confident where they belong
- Only group tasks when you have REASONABLE CONFIDENCE they relate
- A task can only belong to one initiative
- Also propose new initiatives if the historical context reveals strategic
  areas that have tasks but no explicit initiative yet

GRAMMAR:
- Capitalize first letter of all theme and initiative titles
- Make titles concise, meaningful, and professional
- No trailing punctuation on titles

Return ONLY valid JSON (no markdown, no explanation):
{{"themes": [{{"title": "...", "description": "..."}}], "initiatives": [{{"title": "...", "description": "...", "theme_index": 0, "task_ids": [...], "proposed": false}}], "proposed_initiatives": [{{"title": "...", "description": "...", "theme_index": 0, "rationale": "..."}}], "operational_task_ids": [...], "unclassified_task_ids": [...]}}

TASKS:
{tasks_json}
"""


# ---------------------------------------------------------------------------
# Phase 2: Epic + Story breakdown + gap-fill
# ---------------------------------------------------------------------------

_PHASE2_PROMPT = """\
You are breaking down this initiative into Epics and User Stories,
AND identifying what's missing for complete delivery.

Initiative: {initiative_title}
Description: {initiative_description}

HISTORICAL CONTEXT for this initiative's topic area:
{relevant_context}

Tasks assigned to this initiative:
{tasks_json}

RULES:
- Group related tasks into Epics (large bodies of work)
- Within each Epic, create User Stories that represent user-facing value
- Link each task to the most appropriate User Story via task_ids
- Write stories in "As a [role], I want [goal], so that [benefit]" format when possible
- Use historical context to inform story descriptions — include background from prior meetings
- Some tasks may not fit any story — leave them as unlinked_task_ids on the epic

GAP-FILL (critical):
- Think through what is required to COMPLETE this initiative end-to-end
- If tasks exist for "build" but not "test" or "deploy", propose those missing tasks
- If an obvious epic or story is missing to cover the full delivery, propose it
- Mark all proposed items clearly so users can approve or dismiss them
- Be pragmatic — only propose items that genuinely add value, not boilerplate

GRAMMAR:
- Capitalize first letter of all titles
- Make titles concise and meaningful
- No trailing punctuation on titles
- Consistent tense and style across all items

Return ONLY valid JSON (no markdown, no explanation):
{{"epics": [{{"title": "...", "description": "...", "stories": [{{"title": "...", "description": "...", "task_ids": [...]}}], "unlinked_task_ids": [...], "proposed_stories": [{{"title": "...", "description": "...", "rationale": "..."}}]}}], "proposed_epics": [{{"title": "...", "description": "...", "rationale": "...", "proposed_stories": [{{"title": "...", "description": "..."}}]}}], "proposed_tasks": [{{"description": "...", "rationale": "...", "epic_title": "...", "story_title": "..."}}]}}
"""


# ---------------------------------------------------------------------------
# Grammar normalization
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Normalize a title: capitalize first letter, strip trailing punctuation."""
    if not title:
        return title
    title = title.strip()
    # Remove trailing period, colon, semicolon
    title = title.rstrip(".:;,")
    # Capitalize first letter
    if title and title[0].islower():
        title = title[0].upper() + title[1:]
    return title


def _normalize_description(desc: str) -> str:
    """Normalize a description: capitalize first letter."""
    if not desc:
        return desc
    desc = desc.strip()
    if desc and desc[0].islower():
        desc = desc[0].upper() + desc[1:]
    return desc


# ---------------------------------------------------------------------------
# Main classification engine
# ---------------------------------------------------------------------------

async def classify_tasks(
    force_reclassify: bool = False,
    on_progress: Optional[Callable[[dict], Any]] = None,
) -> dict:
    """Run agile auto-classification on all smart tasks.

    Args:
        force_reclassify: If True, also reclassify tasks with manual_override.
        on_progress: Optional callback for progress updates.

    Returns:
        Summary dict with counts of themes, initiatives, epics, stories created.
    """
    client = _get_opus_client()
    if client is None:
        return {"error": "No Anthropic API key configured. Cannot run classification."}

    # Load intel data
    if not _INTEL_FILE.exists():
        return {"error": "No intel data found. Run a Notion scan first."}

    try:
        intel = json.loads(_INTEL_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Failed to load intel data: {e}"}

    all_tasks = intel.get("smart_tasks", [])
    if not all_tasks:
        return {"error": "No tasks found. Run a Notion scan first."}

    # Filter tasks for classification
    tasks_to_classify = []
    for t in all_tasks:
        if t.get("status") == "done":
            continue
        if t.get("manual_override") and not force_reclassify:
            continue
        tasks_to_classify.append(t)

    if not tasks_to_classify:
        return {"message": "No tasks to classify (all are done or manually overridden)."}

    def _emit(msg: dict) -> None:
        if on_progress:
            result = on_progress(msg)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)

    _emit({"status": "started", "phase": "context", "message": "Building historical context..."})

    # Phase 0: Build knowledge map
    knowledge_map = _build_knowledge_map(intel)
    km_text = _compact_knowledge_map(knowledge_map)

    _emit({"status": "processing", "phase": "phase1",
           "message": f"Analyzing {len(tasks_to_classify)} tasks with Opus..."})

    # Phase 1: Theme + Initiative discovery
    compact_tasks = []
    for t in tasks_to_classify:
        compact_tasks.append({
            "id": t["id"],
            "description": t.get("description", ""),
            "owner": t.get("owner", ""),
            "topics": t.get("topics", []),
        })

    phase1_prompt = _PHASE1_PROMPT.format(
        count=len(compact_tasks),
        topic_knowledge_map=km_text,
        tasks_json=json.dumps(compact_tasks, indent=None),
    )

    try:
        phase1_result = await asyncio.to_thread(
            client.messages.create,
            model="claude-opus-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": phase1_prompt}],
        )
        phase1_text = phase1_result.content[0].text.strip()
        logger.info("Phase 1 raw response (first 200 chars): %s", phase1_text[:200])
        phase1_data = _extract_json(phase1_text)
    except json.JSONDecodeError as e:
        logger.error("Phase 1: Opus returned invalid JSON: %s", e)
        return {"error": f"Classification failed — Opus returned invalid JSON in Phase 1: {e}"}
    except Exception as e:
        logger.error("Phase 1 API call failed: %s", e)
        return {"error": f"Classification failed — API error: {e}"}

    # Apply Phase 1 results
    from integrations.themes import create_theme
    from integrations.initiatives import create_initiative
    from integrations.epics import create_epic, create_story

    themes_created = []
    for t_data in phase1_data.get("themes", []):
        result = create_theme(
            title=_normalize_title(t_data.get("title", "")),
            description=_normalize_description(t_data.get("description", "")),
            source="auto",
        )
        themes_created.append(result.get("theme", {}))

    initiatives_created = []
    initiative_task_map: dict[str, list[str]] = {}  # initiative_id -> [task_ids]

    for i_data in phase1_data.get("initiatives", []):
        theme_idx = i_data.get("theme_index", 0)
        theme_id = themes_created[theme_idx]["id"] if theme_idx < len(themes_created) else ""

        result = create_initiative(
            title=_normalize_title(i_data.get("title", "")),
            description=_normalize_description(i_data.get("description", "")),
            theme_id=theme_id,
            source="auto",
        )
        init = result.get("initiative", {})
        initiatives_created.append(init)
        initiative_task_map[init["id"]] = i_data.get("task_ids", [])

    # Also create proposed initiatives
    for pi_data in phase1_data.get("proposed_initiatives", []):
        theme_idx = pi_data.get("theme_index", 0)
        theme_id = themes_created[theme_idx]["id"] if theme_idx < len(themes_created) else ""

        result = create_initiative(
            title=_normalize_title(pi_data.get("title", "")),
            description=_normalize_description(pi_data.get("description", "")),
            theme_id=theme_id,
            source="auto",
        )
        initiatives_created.append(result.get("initiative", {}))

    # Update task classifications
    task_id_set = {t["id"] for t in tasks_to_classify}
    operational_ids = set(phase1_data.get("operational_task_ids", []))
    unclassified_ids = set(phase1_data.get("unclassified_task_ids", []))

    for task in all_tasks:
        tid = task["id"]
        if tid not in task_id_set:
            continue
        if task.get("manual_override") and not force_reclassify:
            continue

        if tid in operational_ids:
            task["classification"] = "operational"
            task["confidence"] = 0.8
        elif tid in unclassified_ids:
            task["classification"] = "unclassified"
            task["confidence"] = 0.0
        else:
            task["classification"] = "strategic"
            task["confidence"] = 0.7

    # Phase 2: Break each initiative into epics + stories
    epics_created = 0
    stories_created = 0
    proposed_tasks_created = 0

    for i_idx, init in enumerate(initiatives_created):
        init_id = init.get("id", "")
        init_task_ids = initiative_task_map.get(init_id, [])
        if not init_task_ids:
            continue

        _emit({
            "status": "processing", "phase": "phase2",
            "message": f"Breaking down initiative {i_idx + 1}/{len(initiatives_created)}: {init.get('title', '')}",
            "current": i_idx + 1, "total": len(initiatives_created),
        })

        # Gather tasks for this initiative
        init_tasks = []
        for t in tasks_to_classify:
            if t["id"] in init_task_ids:
                init_tasks.append({
                    "id": t["id"],
                    "description": t.get("description", ""),
                    "owner": t.get("owner", ""),
                })

        if not init_tasks:
            continue

        # Build relevant context from knowledge map
        init_title_words = set(init.get("title", "").lower().split())
        relevant_context_parts = []
        for topic, info in knowledge_map.items():
            if topic.lower() in init_title_words or any(
                w in topic.lower() for w in init_title_words if len(w) > 3
            ):
                for s in info.get("page_summaries", [])[:3]:
                    relevant_context_parts.append(
                        f"- {s['date']}: {s['title']} — {s['summary']}"
                    )
        relevant_context = "\n".join(relevant_context_parts[:10]) or "No specific historical context."

        phase2_prompt = _PHASE2_PROMPT.format(
            initiative_title=init.get("title", ""),
            initiative_description=init.get("description", ""),
            relevant_context=relevant_context,
            tasks_json=json.dumps(init_tasks, indent=None),
        )

        try:
            phase2_result = await asyncio.to_thread(
                client.messages.create,
                model="claude-opus-4-20250514",
                max_tokens=8192,
                messages=[{"role": "user", "content": phase2_prompt}],
            )
            phase2_text = phase2_result.content[0].text.strip()
            phase2_data = _extract_json(phase2_text)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Phase 2 failed for initiative '%s': %s", init.get("title"), e)
            continue

        # Create epics and stories
        for e_data in phase2_data.get("epics", []):
            epic_result = create_epic(
                title=_normalize_title(e_data.get("title", "")),
                description=_normalize_description(e_data.get("description", "")),
                initiative_id=init_id,
                source="auto",
            )
            epic = epic_result.get("epic", {})
            epic_id = epic.get("id", "")
            epics_created += 1

            # Create stories within this epic
            for s_data in e_data.get("stories", []):
                story_result = create_story(
                    epic_id=epic_id,
                    title=_normalize_title(s_data.get("title", "")),
                    description=_normalize_description(s_data.get("description", "")),
                    source="auto",
                )
                story = story_result.get("story", {})
                story_id = story.get("id", "")
                stories_created += 1

                # Link tasks to this story
                for tid in s_data.get("task_ids", []):
                    for task in all_tasks:
                        if task["id"] == tid:
                            task["story_id"] = story_id
                            task["confidence"] = 0.8
                            break

            # Handle unlinked tasks — link directly to epic (no story)
            for tid in e_data.get("unlinked_task_ids", []):
                for task in all_tasks:
                    if task["id"] == tid:
                        task["confidence"] = 0.5
                        break

            # Create proposed stories
            for ps_data in e_data.get("proposed_stories", []):
                create_story(
                    epic_id=epic_id,
                    title=_normalize_title(ps_data.get("title", "")),
                    description=_normalize_description(ps_data.get("description", "")),
                    source="auto",
                )
                stories_created += 1

        # Create proposed epics
        for pe_data in phase2_data.get("proposed_epics", []):
            pe_result = create_epic(
                title=_normalize_title(pe_data.get("title", "")),
                description=_normalize_description(pe_data.get("description", "")),
                initiative_id=init_id,
                source="auto",
            )
            pe = pe_result.get("epic", {})
            pe_id = pe.get("id", "")
            epics_created += 1

            for ps_data in pe_data.get("proposed_stories", []):
                create_story(
                    epic_id=pe_id,
                    title=_normalize_title(ps_data.get("title", "")),
                    description=_normalize_description(ps_data.get("description", "")),
                    source="auto",
                )
                stories_created += 1

        # Create proposed gap-fill tasks
        for pt_data in phase2_data.get("proposed_tasks", []):
            from integrations.intel import _load_intel, _save_intel
            import uuid

            new_task = {
                "id": uuid.uuid4().hex[:8],
                "description": _normalize_description(pt_data.get("description", "")),
                "owner": "",
                "delegated": False,
                "source_title": f"Auto-generated for: {init.get('title', '')}",
                "source_url": "",
                "source_page_id": "",
                "source_context": pt_data.get("rationale", ""),
                "topics": [],
                "follow_up_date": "",
                "priority": {"urgent": False, "important": True, "quadrant": 2, "quadrant_label": "Schedule"},
                "status": "open",
                "steps": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "story_id": "",
                "classification": "strategic",
                "manual_override": False,
                "override_at": "",
                "confidence": 0.0,
                "source": "auto",
            }
            all_tasks.append(new_task)
            proposed_tasks_created += 1

    # Phase 3: Grammar normalization on existing task descriptions
    _emit({"status": "processing", "phase": "grammar", "message": "Normalizing grammar..."})

    for task in all_tasks:
        desc = task.get("description", "")
        if desc:
            task["description"] = _normalize_description(desc)

    # Save updated intel
    intel["smart_tasks"] = all_tasks
    _INTEL_FILE.write_text(json.dumps(intel, indent=2, default=str))

    summary = {
        "status": "complete",
        "themes_created": len(themes_created),
        "initiatives_created": len(initiatives_created),
        "epics_created": epics_created,
        "stories_created": stories_created,
        "proposed_tasks_created": proposed_tasks_created,
        "tasks_classified": len(tasks_to_classify),
        "operational_count": len(operational_ids),
        "unclassified_count": len(unclassified_ids),
        "strategic_count": len(tasks_to_classify) - len(operational_ids) - len(unclassified_ids),
    }

    _emit({"status": "complete", **summary})
    logger.info("Classification complete: %s", summary)
    return summary
