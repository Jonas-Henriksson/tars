"""Auto-populate epics, user stories, and people from intelligence data.

Analyzes existing smart tasks, tracked tasks, and page index to suggest
and create epics and user stories, grouping related work into coherent
deliverables. Also enriches people profiles from intel context.
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# LLM-powered epic/story generation
# -----------------------------------------------------------------------

_EPIC_PROMPT = """\
You are an agile project manager organizing work into epics and user stories.

Below are tasks grouped by topic. Analyze them and create epics (large bodies of work)
with user stories (specific deliverables) that logically organize these tasks.

TASKS BY TOPIC:
{tasks_by_topic}

EXISTING EPICS (avoid duplicates):
{existing_epics}

HISTORICAL CONTEXT (from past discussions and meetings):
{historical_context}

Use this historical context to create richer epics that reference past decisions,
incorporate specific details (names, timelines, technical choices), and connect to
previously discussed work that may not have been formalized as tasks yet.

EXTERNAL BEST PRACTICES (industry frameworks and methodologies for these topics):
{best_practices}

Leverage these best practices to:
- Structure epics around proven frameworks and methodologies
- Include industry-standard KPIs in acceptance criteria
- Reference specific frameworks (e.g., "Kotter's 8-step model", "SCOR framework") in descriptions
- Suggest stories that align with best-practice implementation steps

Rules:
- Each epic should represent a cohesive body of work (not a single task)
- Only create epics where there are 2+ related tasks that form a larger initiative
- User stories should follow "As a [role], I want [goal] so that [benefit]" when possible
- Assign owner based on who owns most tasks in that group
- Set realistic priorities: high (business-critical), medium (important), low (nice-to-have)
- Skip tasks that are purely operational/routine (e.g. "review email", "attend meeting")
- Use the topic as context but give epics specific, actionable titles

Return ONLY valid JSON array of epics:
[{{
  "title": "Epic title",
  "description": "Brief description of the body of work",
  "owner": "Person name",
  "priority": "high|medium|low",
  "quarter": "Q1 2026",
  "stories": [
    {{
      "title": "User story title",
      "description": "As a..., I want..., so that...",
      "owner": "Person name",
      "size": "XS|S|M|L|XL",
      "priority": "high|medium|low",
      "linked_task_descriptions": ["task description that maps to this story"]
    }}
  ]
}}]

Return an empty array [] if no meaningful epics can be created.
"""

_PEOPLE_PROMPT = """\
Analyze these person mentions from business documents and infer their role,
organization, and relationship to the CEO.

PERSON DATA:
{person_data}

For each person, return your best inference. Only include people where you can
make a reasonable guess. Skip people with insufficient context.

Return ONLY valid JSON array:
[{{
  "name": "Full Name",
  "role": "Inferred role/title",
  "organization": "Department or company",
  "relationship": "direct_report|peer|external|board|stakeholder"
}}]
"""




async def auto_populate_epics() -> dict[str, Any]:
    """Analyze existing tasks and create epics/stories from them.

    Groups tasks by topic, uses LLM to identify coherent epics,
    then creates them via the epics module.
    """
    from integrations.intel import _load_intel
    from integrations.notion_tasks import _load_tasks
    from integrations.epics import create_epic, create_story, get_epics, link_task_to_story

    from integrations.manual_changes import get_deleted_epic_ids, get_deleted_story_ids

    intel = _load_intel()
    tracked = _load_tasks()
    smart_tasks = intel.get("smart_tasks", [])

    # Get existing epics and deleted IDs to avoid duplicates and re-creation
    existing = get_epics()
    existing_titles = {e["title"].lower() for e in existing.get("epics", [])}
    deleted_epic_ids = get_deleted_epic_ids()
    deleted_story_ids = get_deleted_story_ids()

    # Include existing + manually deleted epics in the "don't recreate" list
    existing_titles_str = "\n".join(f"- {e['title']}" for e in existing.get("epics", [])) or "(none)"

    # Group tasks by topic
    tasks_by_topic: dict[str, list[dict]] = defaultdict(list)

    for task in smart_tasks:
        if task.get("status") == "done":
            continue
        topics = task.get("topics", ["general"])
        desc = task.get("description", "")
        owner = task.get("owner", "Unassigned")
        for topic in topics:
            tasks_by_topic[topic].append({
                "id": task.get("id", ""),
                "description": desc,
                "owner": owner,
                "priority": task.get("priority", ""),
            })

    for task in tracked:
        if task.get("completed") or task.get("status") == "done":
            continue
        topic = task.get("topic", "general")
        tasks_by_topic[topic].append({
            "id": task.get("id", ""),
            "description": task.get("description", ""),
            "owner": task.get("owner", "Unassigned"),
            "priority": "",
        })

    # Filter out topics with too few tasks (need at least 2 for a meaningful epic)
    eligible_topics = {t: tasks for t, tasks in tasks_by_topic.items()
                       if len(tasks) >= 2 and t != "general"}

    if not eligible_topics:
        return {
            "message": "Not enough related tasks to create epics",
            "epics_created": 0,
            "stories_created": 0,
        }

    # Build prompt
    tasks_text = ""
    for topic, tasks in eligible_topics.items():
        tasks_text += f"\n## {topic}\n"
        for t in tasks[:15]:  # cap per topic to control prompt size
            tasks_text += f"- [{t['owner']}] {t['description']}\n"

    # Inject historical context from context repository
    try:
        from integrations.context_repository import get_related_context
        historical_context = get_related_context(topics=list(eligible_topics.keys()), max_chars=3000)
    except Exception:
        historical_context = ""

    # Inject relevant best practices from external knowledge
    try:
        from integrations.knowledge_enrichment import search_best_practices
        bp_results = []
        for topic in eligible_topics.keys():
            bp_results.extend(search_best_practices(topic))
        # Deduplicate by title
        seen_titles = set()
        unique_bp = []
        for bp in bp_results:
            t = bp.get("title", "")
            if t not in seen_titles:
                seen_titles.add(t)
                unique_bp.append(bp)
        best_practices_text = "\n\n".join(
            f"**{bp['title']}**\n{bp['content'][:500]}"
            for bp in unique_bp[:3]
        ) if unique_bp else ""
    except Exception:
        best_practices_text = ""

    prompt = _EPIC_PROMPT.format(
        tasks_by_topic=tasks_text,
        existing_epics=existing_titles_str,
        historical_context=historical_context or "(no historical context available)",
        best_practices=best_practices_text or "(no external best practices available yet)",
    )

    from llm import llm_call
    raw = await llm_call("epic_generation", prompt, max_tokens=3000)
    if not raw:
        return {"error": "LLM unavailable", "epics_created": 0, "stories_created": 0}

    try:
        suggested_epics = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON for epic generation")
        return {"error": "LLM returned invalid response", "epics_created": 0, "stories_created": 0}

    # Create the epics and stories
    epics_created = 0
    stories_created = 0
    results = []

    # Build task description -> id map for linking
    desc_to_id: dict[str, str] = {}
    for task in smart_tasks + tracked:
        desc = task.get("description", "").lower().strip()
        tid = task.get("id", "")
        if desc and tid:
            desc_to_id[desc] = tid

    for epic_data in suggested_epics:
        title = epic_data.get("title", "").strip()
        if not title or title.lower() in existing_titles:
            continue

        epic_result = create_epic(
            title=title,
            description=epic_data.get("description", ""),
            owner=epic_data.get("owner", ""),
            priority=epic_data.get("priority", "medium"),
            quarter=epic_data.get("quarter", ""),
        )

        epic_id = epic_result.get("epic", {}).get("id", "")
        if not epic_id:
            continue

        epics_created += 1
        existing_titles.add(title.lower())

        for story_data in epic_data.get("stories", []):
            story_title = story_data.get("title", "").strip()
            if not story_title:
                continue

            story_result = create_story(
                epic_id=epic_id,
                title=story_title,
                description=story_data.get("description", ""),
                owner=story_data.get("owner", ""),
                size=story_data.get("size", "M"),
                priority=story_data.get("priority", "medium"),
            )

            story_id = story_result.get("story", {}).get("id", "")
            if story_id:
                stories_created += 1

                # Try to link original tasks to the story
                for linked_desc in story_data.get("linked_task_descriptions", []):
                    linked_lower = linked_desc.lower().strip()
                    # Fuzzy match against task descriptions
                    for desc_key, task_id in desc_to_id.items():
                        if linked_lower in desc_key or desc_key in linked_lower:
                            try:
                                link_task_to_story(story_id, task_id)
                            except Exception:
                                pass
                            break

        results.append({"title": title, "stories": len(epic_data.get("stories", []))})

    return {
        "message": f"Created {epics_created} epics with {stories_created} stories",
        "epics_created": epics_created,
        "stories_created": stories_created,
        "epics": results,
    }


async def auto_enrich_people() -> dict[str, Any]:
    """Analyze intel data to enrich people profiles with inferred roles.

    Uses page context, task assignments, and meeting patterns to infer
    each person's role, organization, and relationship.
    """
    from integrations.people import get_all_people, update_person
    from integrations.intel import _load_intel
    from integrations.manual_changes import get_edited_people

    intel = _load_intel()
    people_intel = intel.get("people", {})
    page_index = intel.get("page_index", {})
    smart_tasks = intel.get("smart_tasks", [])
    existing_people = get_all_people()
    manually_edited = get_edited_people()

    # Find people who need enrichment (no role set, not manually edited)
    needs_enrichment = []
    for name, count in people_intel.items():
        person = existing_people.get(name, {})
        # Skip if already has a role OR was manually edited (respect manual changes)
        if person.get("role") and count >= 2:
            continue
        if name in manually_edited and person.get("role"):
            continue
        if count < 2:
            # Gather context for this person
            context_pages = []
            for _pid, page in page_index.items():
                page_people = [p.lower() for p in page.get("people", [])]
                if name.lower() in " ".join(page_people):
                    context_pages.append(page.get("title", ""))

            tasks_owned = [t["description"] for t in smart_tasks
                          if t.get("owner", "").lower() == name.lower()][:5]

            needs_enrichment.append({
                "name": name,
                "mentions": count,
                "pages": context_pages[:5],
                "tasks": tasks_owned,
            })

    if not needs_enrichment:
        return {"message": "All people profiles are already enriched", "updated": 0}

    # Use LLM to infer roles
    person_text = json.dumps(needs_enrichment[:20], indent=2)
    prompt = _PEOPLE_PROMPT.format(person_data=person_text)

    from llm import llm_call
    raw = await llm_call("people_enrichment", prompt, max_tokens=2000)
    if not raw:
        return {"error": "LLM unavailable", "updated": 0}

    try:
        inferred = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "LLM returned invalid response", "updated": 0}

    updated = 0
    for person in inferred:
        name = person.get("name", "")
        if not name:
            continue
        try:
            # Only fill in EMPTY fields — never overwrite manual edits
            existing = existing_people.get(name, {})
            is_manual = name in manually_edited
            updates = {}
            if person.get("role") and not existing.get("role"):
                updates["role"] = person["role"]
            if person.get("organization") and not existing.get("organization"):
                updates["organization"] = person["organization"]
            if person.get("relationship") and not existing.get("relationship"):
                updates["relationship"] = person["relationship"]
            if updates:
                update_person(name, **updates)
                updated += 1
        except Exception as e:
            logger.warning("Failed to update person %s: %s", name, e)

    return {
        "message": f"Enriched {updated} people profiles",
        "updated": updated,
    }
