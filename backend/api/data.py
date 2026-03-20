"""Data API — tasks, decisions, initiatives, epics, people, alerts.

Consolidates all REST endpoints that were previously in web/server.py.
Uses the unified tool registry for execution.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.auth.middleware import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["data"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------------------
# Pydantic models for request bodies
# ---------------------------------------------------------------------------

class SmartTaskUpdate(BaseModel):
    status: str = ""
    follow_up_date: str = ""
    quadrant: int = 0
    description: str = ""
    owner: str = ""
    steps: str = ""


class StepToTask(BaseModel):
    step_description: str


class TrackedTaskUpdate(BaseModel):
    owner: str | None = None
    topic: str | None = None
    description: str | None = None
    status: str | None = None
    follow_up_date: str | None = None


class DecisionCreate(BaseModel):
    title: str
    rationale: str = ""
    decided_by: str = ""
    stakeholders: list[str] = []
    context: str = ""
    initiative: str = ""
    status: str = "decided"
    linked_type: str = ""
    linked_id: str = ""
    linked_title: str = ""
    source: str = "manual"
    source_page_id: str = ""
    requested_by: str = ""
    requested_from: str = ""
    request_reason: str = ""
    from_workstream: str = ""


class DecisionUpdate(BaseModel):
    status: str | None = None
    rationale: str | None = None
    outcome_notes: str | None = None
    stakeholders: list[str] | None = None
    initiative: str | None = None
    title: str | None = None
    linked_type: str | None = None
    linked_id: str | None = None
    linked_title: str | None = None
    source: str | None = None
    source_page_id: str | None = None
    requested_by: str | None = None
    requested_from: str | None = None
    request_reason: str | None = None
    from_workstream: str | None = None


class NotionDecisionImport(BaseModel):
    decisions: list[dict] = []


class InitiativeCreate(BaseModel):
    title: str
    description: str = ""
    owner: str = ""
    quarter: str = ""
    status: str = "on_track"
    priority: str = "high"
    milestones: list[str] = []
    theme_id: str = ""
    source_title: str = ""
    source_url: str = ""
    source_page_id: str = ""


class InitiativeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    owner: str | None = None
    quarter: str | None = None
    status: str | None = None
    priority: str | None = None
    theme_id: str | None = None


class KeyResultCreate(BaseModel):
    initiative_id: str
    description: str
    target: str = ""
    current: str = ""
    owner: str = ""


class KeyResultUpdate(BaseModel):
    current: str | None = None
    status: str | None = None
    description: str | None = None


class EpicCreate(BaseModel):
    title: str
    description: str = ""
    owner: str = ""
    initiative_id: str = ""
    quarter: str = ""
    priority: str = "high"
    acceptance_criteria: list[str] = []
    source_title: str = ""
    source_url: str = ""
    source_page_id: str = ""


class EpicUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    owner: str | None = None
    status: str | None = None
    priority: str | None = None
    quarter: str | None = None
    initiative_id: str | None = None
    acceptance_criteria: list[str] | None = None


class StoryCreate(BaseModel):
    epic_id: str
    title: str
    description: str = ""
    owner: str = ""
    size: str = "M"
    priority: str = "medium"
    acceptance_criteria: list[str] = []
    source_title: str = ""
    source_url: str = ""
    source_page_id: str = ""


class StoryUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    owner: str | None = None
    status: str | None = None
    priority: str | None = None
    size: str | None = None
    acceptance_criteria: list[str] | None = None


class LinkTask(BaseModel):
    task_id: str


class ThemeCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "active"


class ThemeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class TaskAssign(BaseModel):
    story_id: str = ""
    epic_id: str = ""
    classification: str = ""


class PersonCreate(BaseModel):
    name: str
    role: str = ""
    relationship: str = ""
    organization: str = ""
    notes: str = ""
    email: str = ""


class PersonUpdate(BaseModel):
    role: str | None = None
    relationship: str | None = None
    organization: str | None = None
    notes: str | None = None
    email: str | None = None


# ---------------------------------------------------------------------------
# Intelligence & scanning
# ---------------------------------------------------------------------------

@router.get("/intel")
async def get_intel():
    from integrations.intel import get_intel as _get
    return JSONResponse(_get())


@router.get("/intel/graph")
async def get_intel_graph(max_nodes: int = 500, min_edge_weight: int = 1):
    from integrations.intel import build_graph_data
    return JSONResponse(build_graph_data(max_nodes=max_nodes, min_edge_weight=min_edge_weight))


@router.post("/intel/scan")
async def scan_intel(max_pages: int = 50, full_scan: bool = False):
    from integrations.intel import scan_notion
    result = await scan_notion(max_pages=max_pages, full_scan=full_scan)
    return JSONResponse(result)


_active_scan_cancel: dict[str, asyncio.Event] = {}


@router.post("/intel/scan/stream")
async def scan_intel_stream(max_pages: int = 50, full_scan: bool = False):
    """SSE endpoint for streaming scan progress."""
    from integrations.intel import scan_notion

    scan_id = str(id(asyncio.current_task()))
    cancel_event = asyncio.Event()
    _active_scan_cancel[scan_id] = cancel_event
    progress_queue: asyncio.Queue = asyncio.Queue()

    def on_progress(msg: dict) -> None:
        msg["scan_id"] = scan_id
        progress_queue.put_nowait(msg)

    async def generate():
        try:
            scan_task = asyncio.create_task(
                scan_notion(max_pages=max_pages, full_scan=full_scan,
                            on_progress=on_progress, cancel_event=cancel_event)
            )
            while not scan_task.done():
                try:
                    msg = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"

            while not progress_queue.empty():
                msg = progress_queue.get_nowait()
                yield f"data: {json.dumps(msg)}\n\n"

            result = scan_task.result()
            result["status"] = "complete"
            result["scan_id"] = scan_id
            yield f"data: {json.dumps(result)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'status': 'error', 'message': str(exc)})}\n\n"
        finally:
            _active_scan_cancel.pop(scan_id, None)

    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Scan-Id": scan_id},
    )


@router.post("/intel/scan/cancel")
async def cancel_scan(scan_id: str = ""):
    if scan_id and scan_id in _active_scan_cancel:
        _active_scan_cancel[scan_id].set()
        return {"message": "Scan cancellation requested."}
    if not scan_id and _active_scan_cancel:
        for ev in _active_scan_cancel.values():
            ev.set()
        return {"message": f"Cancelled {len(_active_scan_cancel)} scan(s)."}
    return JSONResponse({"message": "No active scan."}, status_code=404)


# ---------------------------------------------------------------------------
# Smart tasks
# ---------------------------------------------------------------------------

@router.get("/intel/tasks")
async def get_smart_tasks(owner: str = "", topic: str = "", quadrant: int = 0, include_done: bool = False):
    from integrations.intel import get_smart_tasks as _get
    return JSONResponse(_get(owner=owner, topic=topic, quadrant=quadrant, include_done=include_done))


@router.patch("/intel/tasks/{task_id}")
async def update_smart_task(task_id: str, body: SmartTaskUpdate):
    from integrations.intel import update_smart_task as _update
    result = _update(task_id=task_id, status=body.status, follow_up_date=body.follow_up_date,
                     quadrant=body.quadrant, description=body.description, owner=body.owner, steps=body.steps)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.delete("/intel/tasks/{task_id}")
async def delete_smart_task(task_id: str):
    from integrations.intel import delete_smart_task as _delete
    result = _delete(task_id=task_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.post("/intel/tasks/rewrite-titles")
async def rewrite_task_titles():
    from integrations.intel import rewrite_task_titles as _rewrite
    result = await _rewrite()
    if "error" in result:
        return JSONResponse(result, status_code=500)
    return JSONResponse(result)


@router.post("/intel/tasks/{task_id}/create-from-step", status_code=201)
async def create_task_from_step(task_id: str, body: StepToTask):
    """Create a new task from a next-step line, inheriting the parent's agile group."""
    from integrations.intel import create_task_from_step as _create
    result = _create(parent_task_id=task_id, step_description=body.step_description)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Tracked tasks
# ---------------------------------------------------------------------------

@router.get("/tasks")
async def get_tasks(owner: str = "", topic: str = "", status: str = "", include_completed: bool = False):
    from integrations.notion_tasks import get_tracked_tasks
    return JSONResponse(get_tracked_tasks(owner=owner, topic=topic, status=status, include_completed=include_completed))


@router.patch("/tasks/{task_id}")
async def update_tracked_task(task_id: str, body: TrackedTaskUpdate):
    from integrations.notion_tasks import update_task as _update
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    result = _update(task_id=task_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.get("/tasks/owners")
async def get_task_owners():
    from integrations.notion_tasks import get_owner_frequencies
    return JSONResponse(get_owner_frequencies())


# ---------------------------------------------------------------------------
# Briefing & review
# ---------------------------------------------------------------------------

@router.get("/briefing")
async def get_briefing():
    from integrations.briefing_daily import compile_daily_briefing
    briefing = await compile_daily_briefing()
    return JSONResponse(briefing)


@router.get("/review/weekly")
async def get_weekly_review():
    from integrations.intel import get_intel as _get_intel
    from integrations.notion_tasks import get_tracked_tasks as _get_tracked
    from datetime import datetime, timezone, timedelta

    intel = _get_intel()
    smart_tasks = intel.get("smart_tasks", [])
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    open_tasks = [t for t in smart_tasks if t.get("status") != "done"]
    done_tasks = [t for t in smart_tasks if t.get("status") == "done"]
    quadrant_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for t in open_tasks:
        q = t.get("priority", {}).get("quadrant", 4)
        quadrant_counts[q] = quadrant_counts.get(q, 0) + 1

    overdue = []
    for t in open_tasks:
        fud = t.get("follow_up_date", "")
        if fud:
            try:
                due = datetime.fromisoformat(fud)
                if due.tzinfo is None:
                    due = due.replace(tzinfo=timezone.utc)
                if due < now:
                    overdue.append({
                        "id": t.get("id"), "description": t.get("description", ""),
                        "owner": t.get("owner", ""), "follow_up_date": fud,
                        "days_overdue": (now - due).days,
                    })
            except (ValueError, TypeError):
                pass
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)

    delegation = {}
    for t in open_tasks:
        owner = t.get("owner", "Unassigned")
        delegation.setdefault(owner, {"count": 0, "overdue": 0, "tasks": []})
        delegation[owner]["count"] += 1
        delegation[owner]["tasks"].append({
            "description": t.get("description", "")[:80],
            "status": t.get("status"),
            "quadrant": t.get("priority", {}).get("quadrant"),
        })

    tracked_all = _get_tracked(include_completed=True)
    tracked_open = _get_tracked()

    return JSONResponse({
        "period": {"start": week_ago.isoformat(), "end": now.isoformat()},
        "smart_tasks": {
            "total": len(smart_tasks), "open": len(open_tasks), "done": len(done_tasks),
            "quadrants": quadrant_counts, "overdue": overdue, "overdue_count": len(overdue),
        },
        "tracked_tasks": {
            "total": len(tracked_all.get("tasks", [])),
            "open": tracked_open.get("count", 0),
        },
        "delegation": delegation,
        "topics": intel.get("topics", {}),
        "people": intel.get("people", {}),
        "scan_history": intel.get("scan_history", [])[-7:],
    })


# ---------------------------------------------------------------------------
# Meeting review (gating newly added items)
# ---------------------------------------------------------------------------

@router.get("/meeting-review")
async def get_meeting_review(days: int = 3, date: str = ""):
    """Aggregate recently created items across all entity types for review.

    Groups items by their source meeting (via source_title) and resolves
    hierarchy paths so the user can see where each item landed.

    Query params:
      date  – YYYY-MM-DD to show items created on that specific day only.
      days  – fallback: show items created in the last N days (default 3).
    """
    from datetime import datetime, timezone, timedelta, date as date_type
    from integrations.themes import get_themes
    from integrations.initiatives import get_initiatives
    from integrations.epics import get_epics, get_stories
    from integrations.intel import get_smart_tasks
    from integrations.decisions import get_decisions

    now = datetime.now(timezone.utc)

    # Determine filter window
    if date:
        try:
            target_date = date_type.fromisoformat(date)
        except ValueError:
            target_date = now.date()
        day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
    else:
        day_start = now - timedelta(days=days)
        day_end = now + timedelta(days=1)  # include today fully
        target_date = now.date()

    def _in_window(item: dict) -> bool:
        ca = item.get("created_at", "")
        if not ca:
            return False
        try:
            dt = datetime.fromisoformat(ca)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return day_start <= dt < day_end
        except (ValueError, TypeError):
            return False

    # Load all entities
    themes = {t["id"]: t for t in get_themes().get("themes", [])}
    initiatives = {i["id"]: i for i in get_initiatives().get("initiatives", [])}
    epics_list = get_epics().get("epics", [])
    epics = {e["id"]: e for e in epics_list}
    stories_list = get_stories().get("stories", [])
    stories = {s["id"]: s for s in stories_list}
    _task_result = get_smart_tasks(include_done=True)
    tasks_list = _task_result.get("tasks", _task_result.get("smart_tasks", []))
    decisions_list = get_decisions(limit=0).get("decisions", [])

    # Build reverse index: task_id -> story_id from stories' linked_task_ids
    task_to_story: dict[str, str] = {}
    for s in stories_list:
        for tid in s.get("linked_task_ids", []):
            task_to_story[tid] = s["id"]

    # --- derive source_title for entities missing it (propagate from tasks) ---
    from collections import Counter as _Counter

    # Build task source index: task_id -> {source_title, source_url, source_page_id}
    task_source: dict[str, dict] = {}
    for t in tasks_list:
        st = t.get("source_title", "")
        if st:
            task_source[t["id"]] = {
                "source_title": st,
                "source_url": t.get("source_url", ""),
                "source_page_id": t.get("source_page_id", ""),
            }

    def _derive_source(source_titles: list[str], url_map: dict, pid_map: dict) -> dict:
        if not source_titles:
            return {}
        best = _Counter(source_titles).most_common(1)[0][0]
        return {
            "source_title": best,
            "source_url": url_map.get(best, ""),
            "source_page_id": pid_map.get(best, ""),
        }

    # Stories: derive from linked tasks
    story_derived: dict[str, dict] = {}
    for s in stories_list:
        if s.get("source_title"):
            story_derived[s["id"]] = {
                "source_title": s["source_title"],
                "source_url": s.get("source_url", ""),
                "source_page_id": s.get("source_page_id", ""),
            }
            continue
        titles, urls, pids = [], {}, {}
        for tid in s.get("linked_task_ids", []):
            src = task_source.get(tid)
            if src:
                titles.append(src["source_title"])
                urls[src["source_title"]] = src["source_url"]
                pids[src["source_title"]] = src["source_page_id"]
        derived = _derive_source(titles, urls, pids)
        if derived:
            story_derived[s["id"]] = derived
            # Patch in-memory so hierarchy items pick it up
            s["source_title"] = derived["source_title"]
            s["source_url"] = derived["source_url"]
            s["source_page_id"] = derived["source_page_id"]

    # Epics: derive from child stories
    epic_derived: dict[str, dict] = {}
    for e in epics_list:
        if e.get("source_title"):
            epic_derived[e["id"]] = {
                "source_title": e["source_title"],
                "source_url": e.get("source_url", ""),
                "source_page_id": e.get("source_page_id", ""),
            }
            continue
        titles, urls, pids = [], {}, {}
        for s in stories_list:
            if s.get("epic_id") == e["id"]:
                src = story_derived.get(s["id"])
                if src:
                    titles.append(src["source_title"])
                    urls[src["source_title"]] = src["source_url"]
                    pids[src["source_title"]] = src["source_page_id"]
        derived = _derive_source(titles, urls, pids)
        if derived:
            epic_derived[e["id"]] = derived
            e["source_title"] = derived["source_title"]
            e["source_url"] = derived["source_url"]
            e["source_page_id"] = derived["source_page_id"]

    # Initiatives: derive from child epics
    init_derived: dict[str, dict] = {}
    for i_id, init in initiatives.items():
        if init.get("source_title"):
            init_derived[i_id] = {
                "source_title": init["source_title"],
                "source_url": init.get("source_url", ""),
                "source_page_id": init.get("source_page_id", ""),
            }
            continue
        titles, urls, pids = [], {}, {}
        for e in epics_list:
            if e.get("initiative_id") == i_id:
                src = epic_derived.get(e["id"])
                if src:
                    titles.append(src["source_title"])
                    urls[src["source_title"]] = src["source_url"]
                    pids[src["source_title"]] = src["source_page_id"]
        derived = _derive_source(titles, urls, pids)
        if derived:
            init_derived[i_id] = derived
            init["source_title"] = derived["source_title"]
            init["source_url"] = derived["source_url"]
            init["source_page_id"] = derived["source_page_id"]

    # --- hierarchy path helpers ---
    def _path_from_story(story_id: str) -> list[dict]:
        path: list[dict] = []
        s = stories.get(story_id)
        if not s:
            return path
        path.insert(0, {"type": "story", "id": s["id"], "title": s.get("title", "")})
        e = epics.get(s.get("epic_id", ""))
        if e:
            path.insert(0, {"type": "epic", "id": e["id"], "title": e.get("title", "")})
            init = initiatives.get(e.get("initiative_id", ""))
            if init:
                path.insert(0, {"type": "initiative", "id": init["id"], "title": init.get("title", "")})
                th = themes.get(init.get("theme_id", ""))
                if th:
                    path.insert(0, {"type": "theme", "id": th["id"], "title": th.get("title", "")})
        return path

    def _path_from_epic(epic_id: str) -> list[dict]:
        path: list[dict] = []
        e = epics.get(epic_id)
        if not e:
            return path
        path.insert(0, {"type": "epic", "id": e["id"], "title": e.get("title", "")})
        init = initiatives.get(e.get("initiative_id", ""))
        if init:
            path.insert(0, {"type": "initiative", "id": init["id"], "title": init.get("title", "")})
            th = themes.get(init.get("theme_id", ""))
            if th:
                path.insert(0, {"type": "theme", "id": th["id"], "title": th.get("title", "")})
        return path

    def _path_from_initiative(init_id: str) -> list[dict]:
        path: list[dict] = []
        init = initiatives.get(init_id)
        if not init:
            return path
        path.insert(0, {"type": "initiative", "id": init["id"], "title": init.get("title", "")})
        th = themes.get(init.get("theme_id", ""))
        if th:
            path.insert(0, {"type": "theme", "id": th["id"], "title": th.get("title", "")})
        return path

    # --- collect recent items ---
    all_items: list[dict] = []

    # Tasks
    for t in tasks_list:
        if not _in_window(t):
            continue
        sid = t.get("story_id", "") or task_to_story.get(t.get("id", ""), "")
        all_items.append({
            "id": t["id"],
            "entity_type": "tasks",
            "title": t.get("description", ""),
            "owner": t.get("owner", ""),
            "source": t.get("source", "auto"),
            "created_at": t.get("created_at", ""),
            "confidence": t.get("confidence"),
            "source_page_id": t.get("source_page_id", ""),
            "source_title": t.get("source_title", ""),
            "source_url": t.get("source_url", ""),
            "hierarchy_path": _path_from_story(sid) if sid else [],
        })

    # Stories
    for s in stories_list:
        if not _in_window(s):
            continue
        all_items.append({
            "id": s["id"],
            "entity_type": "stories",
            "title": s.get("title", ""),
            "owner": s.get("owner", ""),
            "source": s.get("source", "auto"),
            "created_at": s.get("created_at", ""),
            "confidence": None,
            "source_page_id": s.get("source_page_id", ""),
            "source_title": s.get("source_title", ""),
            "source_url": s.get("source_url", ""),
            "hierarchy_path": _path_from_epic(s.get("epic_id", "")),
        })

    # Epics
    for e in epics_list:
        if not _in_window(e):
            continue
        all_items.append({
            "id": e["id"],
            "entity_type": "epics",
            "title": e.get("title", ""),
            "owner": e.get("owner", ""),
            "source": e.get("source", "auto"),
            "created_at": e.get("created_at", ""),
            "confidence": None,
            "source_page_id": e.get("source_page_id", ""),
            "source_title": e.get("source_title", ""),
            "source_url": e.get("source_url", ""),
            "hierarchy_path": _path_from_initiative(e.get("initiative_id", "")),
        })

    # Initiatives
    for i in get_initiatives().get("initiatives", []):
        if not _in_window(i):
            continue
        all_items.append({
            "id": i["id"],
            "entity_type": "initiatives",
            "title": i.get("title", ""),
            "owner": i.get("owner", ""),
            "source": i.get("source", "auto"),
            "created_at": i.get("created_at", ""),
            "confidence": None,
            "source_page_id": i.get("source_page_id", ""),
            "source_title": i.get("source_title", ""),
            "source_url": i.get("source_url", ""),
            "hierarchy_path": (
                [{"type": "theme", "id": themes[i["theme_id"]]["id"], "title": themes[i["theme_id"]].get("title", "")}]
                if i.get("theme_id") and i["theme_id"] in themes else []
            ),
        })

    # Decisions
    for d in decisions_list:
        if not _in_window(d):
            continue
        # Resolve hierarchy via linked_id if available
        h_path: list[dict] = []
        lt = d.get("linked_type", "")
        lid = d.get("linked_id", "")
        if lt == "initiative" and lid:
            h_path = _path_from_initiative(lid)
        elif lt == "epic" and lid:
            h_path = _path_from_epic(lid)
        elif lt == "story" and lid:
            h_path = _path_from_story(lid)

        all_items.append({
            "id": d["id"],
            "entity_type": "decisions",
            "title": d.get("title", ""),
            "owner": d.get("decided_by", ""),
            "source": d.get("source", "manual"),
            "created_at": d.get("created_at", ""),
            "confidence": None,
            "source_page_id": d.get("source_page_id", ""),
            "source_title": d.get("source_title", ""),
            "source_url": d.get("source_url", ""),
            "hierarchy_path": h_path,
        })

    # --- group by source meeting ---
    # Use source_title as grouping key (smart tasks always have this set to the
    # Notion page name).  Fall back to source_page_id, then "__ungrouped__".
    meetings_map: dict[str, dict] = {}
    for item in all_items:
        key = item.get("source_title") or item.get("source_page_id") or "__ungrouped__"
        if key not in meetings_map:
            meetings_map[key] = {
                "source_page_id": item.get("source_page_id", ""),
                "source_title": item.get("source_title", "") or ("Other items" if key == "__ungrouped__" else ""),
                "source_url": item.get("source_url", ""),
                "items": [],
                "counts": {"auto": 0, "confirmed": 0, "total": 0},
            }
        # Backfill title/url if a later item has it
        if not meetings_map[key]["source_title"] and item.get("source_title"):
            meetings_map[key]["source_title"] = item["source_title"]
        if not meetings_map[key]["source_url"] and item.get("source_url"):
            meetings_map[key]["source_url"] = item["source_url"]

        # Remove transient fields from the item before appending
        clean_item = {k: v for k, v in item.items() if k not in ("source_page_id", "source_title", "source_url")}
        meetings_map[key]["items"].append(clean_item)
        meetings_map[key]["counts"]["total"] += 1
        if item.get("source") == "auto":
            meetings_map[key]["counts"]["auto"] += 1
        else:
            meetings_map[key]["counts"]["confirmed"] += 1

    # Sort meetings by most recent item first; sort items within each by entity hierarchy order
    entity_order = {"initiatives": 0, "epics": 1, "stories": 2, "tasks": 3, "decisions": 4}
    meetings = sorted(meetings_map.values(), key=lambda m: max((i.get("created_at", "") for i in m["items"]), default=""), reverse=True)
    for m in meetings:
        m["items"].sort(key=lambda i: entity_order.get(i.get("entity_type", ""), 9))

    auto_total = sum(m["counts"]["auto"] for m in meetings)
    confirmed_total = sum(m["counts"]["confirmed"] for m in meetings)
    # Count groups that have a real source title (= actual meeting/page sources)
    source_groups = len([m for m in meetings if m["source_title"] and m["source_title"] != "Other items"])

    return JSONResponse({
        "meetings": meetings,
        "summary": {
            "total_items": len(all_items),
            "auto_items": auto_total,
            "confirmed_items": confirmed_total,
            "meetings_count": source_groups,
            "groups_count": len(meetings),
            "date": target_date.isoformat(),
        },
    })


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/completion-trend")
async def completion_trend():
    """Return daily task completion counts for the last 30 days."""
    from integrations.intel import get_intel as _get_intel
    from datetime import datetime, timezone, timedelta

    intel = _get_intel()
    tasks = intel.get("smart_tasks", [])
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    counts: dict[str, int] = {}
    for t in tasks:
        ca = t.get("completed_at", "")
        if ca and ca[:10] >= cutoff:
            counts[ca[:10]] = counts.get(ca[:10], 0) + 1

    days = []
    for i in range(30):
        d = (now - timedelta(days=29 - i)).strftime("%Y-%m-%d")
        days.append({"date": d, "count": counts.get(d, 0)})

    return JSONResponse({"days": days})


# ---------------------------------------------------------------------------
# Meeting prep
# ---------------------------------------------------------------------------

@router.get("/meeting-prep")
async def api_meeting_prep(event_id: str = "", minutes_ahead: int = 480):
    from integrations.meeting_prep import get_meeting_prep
    return JSONResponse(await get_meeting_prep(event_id=event_id, minutes_ahead=minutes_ahead))


@router.get("/meeting-prep/one-on-one/{person_name}")
async def api_one_on_one_prep(person_name: str):
    """Generate a structured 1:1 meeting prep for a specific person."""
    from integrations.people import get_person as _get_person, get_all_people
    from integrations.intel import get_smart_tasks

    person = _get_person(person_name)
    if "error" in person:
        return JSONResponse({"error": f"Person '{person_name}' not found"}, status_code=404)

    # Get tasks owned by this person
    all_tasks = get_smart_tasks(owner=person_name, include_done=False)
    tasks = all_tasks.get("tasks", all_tasks.get("smart_tasks", []))

    # Categorize tasks
    urgent = [t for t in tasks if (t.get("priority", {}).get("quadrant") or t.get("quadrant", 4)) == 1]
    scheduled = [t for t in tasks if (t.get("priority", {}).get("quadrant") or t.get("quadrant", 4)) == 2]
    delegated = [t for t in tasks if (t.get("priority", {}).get("quadrant") or t.get("quadrant", 4)) == 3]
    deferred = [t for t in tasks if (t.get("priority", {}).get("quadrant") or t.get("quadrant", 4)) == 4]

    overdue = [t for t in tasks if t.get("follow_up_date") and t["follow_up_date"] < __import__("datetime").date.today().isoformat()]

    # Recent pages/context
    pages = person.get("pages", [])[:5]
    topics = person.get("topics", [])

    # Build structured prep
    sections = []

    # 1. Opening / Status check
    sections.append({
        "id": "status",
        "title": "Status & Check-in",
        "duration": "5 min",
        "icon": "check",
        "narrative": f"Open with a personal check-in. {person_name} currently has {len(tasks)} open tasks"
                     + (f" ({len(overdue)} overdue)" if overdue else "")
                     + ". Ask how they're feeling about their workload and any recent wins.",
        "items": [
            {"label": "Open tasks", "value": str(len(tasks)), "type": "stat"},
            {"label": "Urgent (Do First)", "value": str(len(urgent)), "type": "stat", "color": "#ef4444" if urgent else None},
            {"label": "Overdue", "value": str(len(overdue)), "type": "stat", "color": "#ef4444" if overdue else None},
        ],
        "questions": [
            "How are things going overall?",
            "Any wins or progress to celebrate since last time?",
        ],
    })

    # 2. Progress review
    progress_items = []
    for t in (urgent + scheduled)[:6]:
        progress_items.append({
            "label": t.get("description", "")[:80],
            "value": t.get("status", "open"),
            "type": "task",
            "priority": t.get("priority", {}).get("label") or f"Q{t.get('quadrant', 4)}",
        })
    sections.append({
        "id": "progress",
        "title": "Progress Review",
        "duration": "10 min",
        "icon": "trending",
        "narrative": f"Review the highest-priority items. {person_name} has {len(urgent)} urgent and {len(scheduled)} scheduled tasks. "
                     + ("Focus on the overdue items first. " if overdue else "")
                     + "Walk through status on each and identify what's blocking progress.",
        "items": progress_items,
        "questions": [
            "What's the status on your top priorities?",
            "Are any of these blocked or at risk?",
            "Do you need any decisions or resources to move forward?",
        ],
    })

    # 3. Blockers & Concerns
    blocker_items = []
    for t in overdue[:4]:
        blocker_items.append({
            "label": t.get("description", "")[:80],
            "value": f"Due {t.get('follow_up_date', '?')}",
            "type": "blocker",
        })
    sections.append({
        "id": "blockers",
        "title": "Blockers & Concerns",
        "duration": "5 min",
        "icon": "alert",
        "narrative": "Surface any impediments."
                     + (f" There are {len(overdue)} overdue items that may indicate blockers." if overdue else " No overdue items — check for hidden concerns.")
                     + " Ask directly about what's slowing them down.",
        "items": blocker_items,
        "questions": [
            "What's the biggest obstacle you're facing right now?",
            "Is anything slowing you down that I can help remove?",
            "Any concerns about upcoming deadlines?",
        ],
    })

    # 4. Decision asks
    sections.append({
        "id": "decisions",
        "title": "Decisions & Asks",
        "duration": "5 min",
        "icon": "scale",
        "narrative": f"Give {person_name} space to raise any decisions they need from you or escalations. "
                     + "This is also the time to align on priorities or re-assign work if needed.",
        "items": [],
        "questions": [
            "Any decisions you need from me?",
            "Anything you'd like to escalate or get alignment on?",
            "Should we re-prioritize anything based on what we've discussed?",
        ],
    })

    # 5. Forward look
    upcoming = [t for t in scheduled[:4]]
    forward_items = [{"label": t.get("description", "")[:80], "value": t.get("follow_up_date", ""), "type": "upcoming"} for t in upcoming]
    sections.append({
        "id": "forward",
        "title": "Forward Look & Next Steps",
        "duration": "5 min",
        "icon": "calendar",
        "narrative": f"Align on what {person_name} will focus on until the next check-in. "
                     + f"They have {len(scheduled)} scheduled tasks coming up."
                     + " Agree on clear next steps and owners.",
        "items": forward_items,
        "questions": [
            "What are your top 3 priorities for the next week?",
            "Is there anything you want to start or stop doing?",
            "When should we check in again?",
        ],
    })

    # Key takeaways (auto-generated highlights)
    takeaways = []
    if overdue:
        takeaways.append({"text": f"{len(overdue)} overdue tasks need attention", "severity": "warning"})
    if len(urgent) > 3:
        takeaways.append({"text": f"Heavy urgent load ({len(urgent)} Do First tasks) — risk of burnout", "severity": "warning"})
    if len(tasks) > 20:
        takeaways.append({"text": f"High task count ({len(tasks)}) — consider reprioritizing", "severity": "info"})
    if len(tasks) == 0:
        takeaways.append({"text": "No open tasks — check if assignments are up to date", "severity": "info"})
    if not takeaways:
        takeaways.append({"text": f"Workload appears balanced ({len(tasks)} tasks, {len(urgent)} urgent)", "severity": "ok"})

    return JSONResponse({
        "person": person_name,
        "role": person.get("role", ""),
        "relationship": person.get("relationship", ""),
        "organization": person.get("organization", ""),
        "total_tasks": len(tasks),
        "topics": topics[:8],
        "sections": sections,
        "takeaways": takeaways,
        "recent_pages": [{"title": p.get("title", ""), "last_edited": p.get("last_edited", "")} for p in pages],
    })


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

@router.get("/decisions")
async def get_decisions(status: str = "", initiative: str = "", stakeholder: str = ""):
    from integrations.decisions import get_decisions as _get
    return JSONResponse(_get(status=status, initiative=initiative, stakeholder=stakeholder))


@router.post("/decisions", status_code=201)
async def create_decision(body: DecisionCreate):
    from integrations.decisions import log_decision
    return JSONResponse(log_decision(
        title=body.title, rationale=body.rationale, decided_by=body.decided_by,
        stakeholders=body.stakeholders, context=body.context, initiative=body.initiative, status=body.status,
        linked_type=body.linked_type, linked_id=body.linked_id, linked_title=body.linked_title,
        source=body.source, source_page_id=body.source_page_id,
        requested_by=body.requested_by, requested_from=body.requested_from,
        request_reason=body.request_reason, from_workstream=body.from_workstream,
    ))


@router.get("/decisions/notion-preview")
async def notion_decision_preview():
    from integrations.decisions import import_notion_decisions
    return JSONResponse(import_notion_decisions())


@router.post("/decisions/notion-import")
async def notion_decision_import(body: NotionDecisionImport):
    from integrations.decisions import commit_notion_import
    return JSONResponse(commit_notion_import(body.decisions))


@router.patch("/decisions/{decision_id}")
async def update_decision(decision_id: str, body: DecisionUpdate):
    from integrations.decisions import update_decision as _update
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields"}, status_code=400)
    result = _update(decision_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.delete("/decisions/{decision_id}")
async def delete_decision(decision_id: str):
    from integrations.decisions import delete_decision
    result = delete_decision(decision_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Initiatives
# ---------------------------------------------------------------------------

@router.get("/initiatives")
async def get_initiatives(status: str = "", owner: str = "", quarter: str = "", priority: str = ""):
    from integrations.initiatives import get_initiatives as _get
    return JSONResponse(_get(status=status, owner=owner, quarter=quarter, priority=priority))


@router.post("/initiatives", status_code=201)
async def create_initiative(body: InitiativeCreate):
    from integrations.initiatives import create_initiative as _create
    return JSONResponse(_create(
        title=body.title, description=body.description, owner=body.owner,
        quarter=body.quarter, status=body.status, priority=body.priority,
        milestones=body.milestones, theme_id=body.theme_id,
        source_title=body.source_title, source_url=body.source_url,
        source_page_id=body.source_page_id,
    ))


@router.patch("/initiatives/{initiative_id}")
async def update_initiative(initiative_id: str, body: InitiativeUpdate):
    from integrations.initiatives import update_initiative as _update
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields"}, status_code=400)
    result = _update(initiative_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.delete("/initiatives/{initiative_id}")
async def delete_initiative(initiative_id: str):
    from integrations.initiatives import delete_initiative
    result = delete_initiative(initiative_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.post("/initiatives/{initiative_id}/milestones/{idx}/complete")
async def complete_milestone(initiative_id: str, idx: int):
    from integrations.initiatives import complete_milestone as _complete
    result = _complete(initiative_id, idx)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.post("/initiatives/key-results", status_code=201)
async def add_key_result(body: KeyResultCreate):
    from integrations.initiatives import add_key_result as _add
    result = _add(initiative_id=body.initiative_id, description=body.description,
                  target=body.target, current=body.current, owner=body.owner)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.patch("/initiatives/key-results/{kr_id}")
async def update_key_result(kr_id: str, body: KeyResultUpdate):
    from integrations.initiatives import update_key_result as _update
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields"}, status_code=400)
    result = _update(kr_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.get("/alerts")
async def get_alerts():
    from integrations.alerts import get_alerts as _get
    return JSONResponse(await _get())


# ---------------------------------------------------------------------------
# Strategic summary
# ---------------------------------------------------------------------------

@router.get("/strategic-summary")
async def strategic_summary():
    result = {}
    try:
        from integrations.initiatives import get_strategic_summary
        result["initiatives"] = get_strategic_summary()
    except Exception:
        result["initiatives"] = {"available": False}
    try:
        from integrations.decisions import get_decision_summary
        result["decisions"] = get_decision_summary()
    except Exception:
        result["decisions"] = {"available": False}
    try:
        from integrations.alerts import get_alerts as _alerts
        result["alerts"] = await _alerts()
    except Exception:
        result["alerts"] = {"available": False}
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Epics & stories
# ---------------------------------------------------------------------------

@router.get("/epics")
async def get_epics(status: str = "", owner: str = "", initiative_id: str = "", quarter: str = "", priority: str = ""):
    from integrations.epics import get_epics
    return JSONResponse(get_epics(status=status, owner=owner, initiative_id=initiative_id, quarter=quarter, priority=priority))


@router.post("/epics", status_code=201)
async def create_epic(body: EpicCreate):
    from integrations.epics import create_epic
    return JSONResponse(create_epic(
        title=body.title, description=body.description, owner=body.owner,
        initiative_id=body.initiative_id, quarter=body.quarter,
        priority=body.priority, acceptance_criteria=body.acceptance_criteria,
        source_title=body.source_title, source_url=body.source_url,
        source_page_id=body.source_page_id,
    ))


@router.patch("/epics/{epic_id}")
async def update_epic(epic_id: str, body: EpicUpdate):
    from integrations.epics import update_epic
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields"}, status_code=400)
    result = update_epic(epic_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.delete("/epics/{epic_id}")
async def delete_epic(epic_id: str):
    from integrations.epics import delete_epic
    result = delete_epic(epic_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.get("/stories")
async def get_stories(epic_id: str = "", owner: str = "", status: str = "", priority: str = "", size: str = ""):
    from integrations.epics import get_stories
    return JSONResponse(get_stories(epic_id=epic_id, owner=owner, status=status, priority=priority, size=size))


@router.post("/stories", status_code=201)
async def create_story(body: StoryCreate):
    from integrations.epics import create_story
    result = create_story(
        epic_id=body.epic_id, title=body.title, description=body.description,
        owner=body.owner, size=body.size, priority=body.priority,
        acceptance_criteria=body.acceptance_criteria,
        source_title=body.source_title, source_url=body.source_url,
        source_page_id=body.source_page_id,
    )
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.patch("/stories/{story_id}")
async def update_story(story_id: str, body: StoryUpdate):
    from integrations.epics import update_story
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields"}, status_code=400)
    result = update_story(story_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.delete("/stories/{story_id}")
async def delete_story(story_id: str):
    from integrations.epics import delete_story
    result = delete_story(story_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.post("/stories/{story_id}/link-task")
async def link_task(story_id: str, body: LinkTask):
    from integrations.epics import link_task_to_story
    result = link_task_to_story(story_id, body.task_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@router.get("/portfolio")
async def team_portfolio(owner: str = "", quarter: str = "", include_done: bool = False):
    from integrations.team_portfolio import get_team_portfolio
    return JSONResponse(get_team_portfolio(owner=owner, quarter=quarter, include_done=include_done))


@router.get("/portfolio/{name}")
async def member_portfolio(name: str, include_done: bool = False):
    from integrations.team_portfolio import get_member_portfolio
    result = get_member_portfolio(name=name, include_done=include_done)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------

@router.get("/themes")
async def get_themes(status: str = ""):
    from integrations.themes import get_themes as _get
    return JSONResponse(_get(status=status))


@router.post("/themes", status_code=201)
async def create_theme(body: ThemeCreate):
    from integrations.themes import create_theme as _create
    return JSONResponse(_create(title=body.title, description=body.description, status=body.status))


@router.patch("/themes/{theme_id}")
async def update_theme(theme_id: str, body: ThemeUpdate):
    from integrations.themes import update_theme as _update
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields"}, status_code=400)
    result = _update(theme_id, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.delete("/themes/{theme_id}")
async def delete_theme(theme_id: str):
    from integrations.themes import delete_theme
    result = delete_theme(theme_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Classification — background job model
# ---------------------------------------------------------------------------

# In-memory job state so classification survives page navigation.
_classify_job: dict = {"running": False, "status": "idle", "progress": {}}


async def _run_classify_background(force: bool = False) -> None:
    """Run classification as a background task, updating _classify_job."""
    from integrations.classifier import classify_tasks

    def on_progress(msg: dict) -> None:
        _classify_job["progress"] = msg
        logger.info("classify progress: %s", msg.get("message", msg.get("phase", "")))

    try:
        logger.info("Background classification started (force=%s)", force)
        result = await classify_tasks(force_reclassify=force, on_progress=on_progress)
        logger.info("Classification result: %s", result)

        if "error" in result:
            _classify_job["progress"] = {"status": "error", "message": result["error"]}
            _classify_job["status"] = "error"
        elif "message" in result and "status" not in result:
            # Early return like "No tasks to classify" — not an error but nothing happened
            _classify_job["progress"] = {"status": "complete", "message": result["message"]}
            _classify_job["status"] = "complete"
        else:
            result["status"] = "complete"
            _classify_job["progress"] = result
            _classify_job["status"] = "complete"
    except Exception as exc:
        logger.exception("Classification background task failed")
        _classify_job["progress"] = {"status": "error", "message": str(exc)}
        _classify_job["status"] = "error"
    finally:
        _classify_job["running"] = False


@router.post("/classify")
async def run_classification(force: bool = False):
    """Start classification as a background job. Returns immediately."""
    if _classify_job["running"]:
        return JSONResponse({"message": "Classification already running.", **_classify_job["progress"]})

    _classify_job["running"] = True
    _classify_job["status"] = "running"
    _classify_job["progress"] = {"status": "started", "phase": "context", "message": "Starting classification..."}

    asyncio.create_task(_run_classify_background(force=force))
    return JSONResponse({"message": "Classification started.", "status": "started"})


@router.get("/classify/status")
async def classify_status():
    """Poll current classification progress. Safe to call from any page."""
    return JSONResponse({
        "running": _classify_job["running"],
        "status": _classify_job["status"],
        **_classify_job["progress"],
    })


@router.post("/classify/stream")
async def classify_stream(force: bool = False):
    """SSE endpoint for streaming classification progress (legacy)."""
    from integrations.classifier import classify_tasks

    progress_queue: asyncio.Queue = asyncio.Queue()

    def on_progress(msg: dict) -> None:
        progress_queue.put_nowait(msg)

    async def generate():
        try:
            classify_task = asyncio.create_task(
                classify_tasks(force_reclassify=force, on_progress=on_progress)
            )
            while not classify_task.done():
                try:
                    msg = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"

            while not progress_queue.empty():
                msg = progress_queue.get_nowait()
                yield f"data: {json.dumps(msg)}\n\n"

            result = classify_task.result()
            result["status"] = "complete"
            yield f"data: {json.dumps(result)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'status': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Approve / dismiss / assign
# ---------------------------------------------------------------------------

@router.post("/approve/{entity_type}/{entity_id}")
async def approve_item(entity_type: str, entity_id: str):
    """Approve an auto-generated item (source: auto → confirmed)."""
    _approve_fns = {
        "themes": ("integrations.themes", "approve_theme"),
        "initiatives": ("integrations.initiatives", "approve_initiative"),
        "epics": ("integrations.epics", "approve_epic"),
        "stories": ("integrations.epics", "approve_story"),
        "tasks": ("integrations.intel", "approve_task"),
    }

    if entity_type not in _approve_fns:
        return JSONResponse({"error": f"Unknown entity type: {entity_type}"}, status_code=400)

    module_name, fn_name = _approve_fns[entity_type]
    import importlib
    mod = importlib.import_module(module_name)
    fn = getattr(mod, fn_name)
    result = fn(entity_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.post("/dismiss/{entity_type}/{entity_id}")
async def dismiss_item(entity_type: str, entity_id: str):
    """Dismiss/delete an auto-generated item."""
    _delete_fns = {
        "themes": ("integrations.themes", "delete_theme"),
        "initiatives": ("integrations.initiatives", "delete_initiative"),
        "epics": ("integrations.epics", "delete_epic"),
        "stories": ("integrations.epics", "delete_story"),
        "tasks": ("integrations.intel", "delete_smart_task"),
    }

    if entity_type not in _delete_fns:
        return JSONResponse({"error": f"Unknown entity type: {entity_type}"}, status_code=400)

    module_name, fn_name = _delete_fns[entity_type]
    import importlib
    mod = importlib.import_module(module_name)
    fn = getattr(mod, fn_name)
    result = fn(entity_id)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.post("/intel/tasks/{task_id}/assign")
async def assign_task_to_story(task_id: str, body: TaskAssign):
    """Move a task to a different story/epic. Sets manual_override=True."""
    from integrations.intel import assign_task
    result = assign_task(
        task_id=task_id,
        story_id=body.story_id,
        classification=body.classification,
    )
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Hierarchy (full tree view)
# ---------------------------------------------------------------------------

@router.get("/hierarchy")
async def get_hierarchy():
    """Get the full agile hierarchy tree: Themes → Initiatives → Epics → Stories → Tasks."""
    from integrations.themes import get_themes
    from integrations.initiatives import get_initiatives
    from integrations.epics import get_epics, get_stories
    from integrations.intel import get_smart_tasks

    themes = get_themes().get("themes", [])
    initiatives = get_initiatives().get("initiatives", [])
    epics_data = get_epics().get("epics", [])
    stories_data = get_stories().get("stories", [])
    _task_result = get_smart_tasks(include_done=True)
    tasks_data = _task_result.get("tasks",
        _task_result.get("smart_tasks", []))

    # Build tree
    tree = []

    # Index by parent
    init_by_theme: dict[str, list] = {}
    for i in initiatives:
        tid = i.get("theme_id", "")
        init_by_theme.setdefault(tid, []).append(i)

    epics_by_init: dict[str, list] = {}
    for e in epics_data:
        iid = e.get("initiative_id", "")
        epics_by_init.setdefault(iid, []).append(e)

    stories_by_epic: dict[str, list] = {}
    for s in stories_data:
        eid = s.get("epic_id", "")
        stories_by_epic.setdefault(eid, []).append(s)

    # Collect all valid story IDs so we can detect dangling references
    all_story_ids = {s["id"] for s in stories_data}

    # Build reverse index: task_id -> story_id from stories' linked_task_ids
    task_to_story_via_linked: dict[str, str] = {}
    for s in stories_data:
        for tid in s.get("linked_task_ids", []):
            task_to_story_via_linked[tid] = s["id"]

    tasks_by_story: dict[str, list] = {}
    orphan_tasks = []
    for t in tasks_data:
        sid = t.get("story_id", "")
        # Primary: task's own story_id matching an existing story
        if sid and sid in all_story_ids:
            tasks_by_story.setdefault(sid, []).append(t)
        # Fallback: story claims this task via linked_task_ids
        elif t.get("id") in task_to_story_via_linked:
            fallback_sid = task_to_story_via_linked[t["id"]]
            tasks_by_story.setdefault(fallback_sid, []).append(t)
        else:
            orphan_tasks.append(t)

    for theme in themes:
        theme_node = {**theme, "type": "theme", "children": []}
        for init in init_by_theme.get(theme["id"], []):
            init_node = {**init, "type": "initiative", "children": []}
            for epic in epics_by_init.get(init["id"], []):
                epic_node = {**epic, "type": "epic", "children": []}
                for story in stories_by_epic.get(epic["id"], []):
                    story_node = {**story, "type": "story", "children": tasks_by_story.get(story["id"], [])}
                    epic_node["children"].append(story_node)
                init_node["children"].append(epic_node)
            theme_node["children"].append(init_node)
        tree.append(theme_node)

    # Unlinked initiatives (no theme)
    for init in init_by_theme.get("", []):
        init_node = {**init, "type": "initiative", "children": []}
        for epic in epics_by_init.get(init["id"], []):
            epic_node = {**epic, "type": "epic", "children": []}
            for story in stories_by_epic.get(epic["id"], []):
                story_node = {**story, "type": "story", "children": tasks_by_story.get(story["id"], [])}
                epic_node["children"].append(story_node)
            init_node["children"].append(epic_node)
        tree.append(init_node)

    # Operational tasks (exclude done from orphan lists)
    operational = [t for t in orphan_tasks if t.get("classification") == "operational"]
    unclassified = [t for t in orphan_tasks if t.get("classification") != "operational"]

    linked_count = sum(len(v) for v in tasks_by_story.values())
    # Count tasks that had a story_id but it didn't match any story
    dangling_count = sum(
        1 for t in orphan_tasks if t.get("story_id", "")
    )

    return JSONResponse({
        "tree": tree,
        "operational_tasks": operational,
        "unclassified_tasks": unclassified,
        "counts": {
            "themes": len(themes),
            "initiatives": len(initiatives),
            "epics": len(epics_data),
            "stories": len(stories_data),
            "tasks": len(tasks_data),
            "linked": linked_count,
            "dangling": dangling_count,
            "operational": len(operational),
            "unclassified": len(unclassified),
        },
    })


# ---------------------------------------------------------------------------
# Backfill source metadata
# ---------------------------------------------------------------------------

@router.post("/backfill-source-metadata")
async def backfill_source_metadata():
    """Backfill source_title on existing entities by tracing linked tasks."""
    from integrations.intel import _load_intel
    from integrations.epics import (
        _load_data as _load_epics, _save_data as _save_epics,
    )
    from integrations.initiatives import (
        _load_data as _load_inits, _save_data as _save_inits,
    )
    from integrations.themes import (
        _load_data as _load_themes, _save_data as _save_themes,
    )
    from collections import Counter

    intel = _load_intel()
    tasks = intel.get("smart_tasks", [])
    task_by_id = {t["id"]: t for t in tasks}

    def _best_source(task_ids: list[str]) -> dict:
        titles: list[str] = []
        url_map: dict[str, str] = {}
        pid_map: dict[str, str] = {}
        for tid in task_ids:
            t = task_by_id.get(tid)
            if not t:
                continue
            st = t.get("source_title", "")
            if st:
                titles.append(st)
                url_map[st] = t.get("source_url", "")
                pid_map[st] = t.get("source_page_id", "")
        if not titles:
            return {}
        best = Counter(titles).most_common(1)[0][0]
        return {
            "source_title": best,
            "source_url": url_map.get(best, ""),
            "source_page_id": pid_map.get(best, ""),
        }

    updated = {"stories": 0, "epics": 0, "initiatives": 0, "themes": 0}

    # --- Stories: use linked_task_ids ---
    epics_db = _load_epics()
    story_source: dict[str, dict] = {}  # story_id -> source info
    for story in epics_db.get("stories", []):
        if story.get("source_title"):
            continue
        linked = story.get("linked_task_ids", [])
        src = _best_source(linked)
        if src:
            story.update(src)
            story_source[story["id"]] = src
            updated["stories"] += 1

    # Also build story_source for stories that already had source_title
    for story in epics_db.get("stories", []):
        if story.get("source_title") and story["id"] not in story_source:
            story_source[story["id"]] = {
                "source_title": story["source_title"],
                "source_url": story.get("source_url", ""),
                "source_page_id": story.get("source_page_id", ""),
            }

    # --- Epics: aggregate from their stories ---
    epic_source: dict[str, dict] = {}
    for epic in epics_db.get("epics", []):
        if epic.get("source_title"):
            continue
        child_stories = [s for s in epics_db.get("stories", []) if s.get("epic_id") == epic["id"]]
        titles: list[str] = []
        url_map: dict[str, str] = {}
        pid_map: dict[str, str] = {}
        for s in child_stories:
            st = s.get("source_title", "")
            if st:
                titles.append(st)
                url_map[st] = s.get("source_url", "")
                pid_map[st] = s.get("source_page_id", "")
        if titles:
            best = Counter(titles).most_common(1)[0][0]
            src = {"source_title": best, "source_url": url_map.get(best, ""), "source_page_id": pid_map.get(best, "")}
            epic.update(src)
            epic_source[epic["id"]] = src
            updated["epics"] += 1

    _save_epics(epics_db)

    # --- Initiatives: aggregate from their epics ---
    inits_db = _load_inits()
    init_source: dict[str, dict] = {}
    for init in inits_db.get("initiatives", []):
        if init.get("source_title"):
            continue
        child_epics = [e for e in epics_db.get("epics", []) if e.get("initiative_id") == init["id"]]
        titles = []
        url_map = {}
        pid_map = {}
        for e in child_epics:
            st = e.get("source_title", "")
            if st:
                titles.append(st)
                url_map[st] = e.get("source_url", "")
                pid_map[st] = e.get("source_page_id", "")
        if titles:
            best = Counter(titles).most_common(1)[0][0]
            src = {"source_title": best, "source_url": url_map.get(best, ""), "source_page_id": pid_map.get(best, "")}
            init.update(src)
            init_source[init["id"]] = src
            updated["initiatives"] += 1

    _save_inits(inits_db)

    # --- Themes: aggregate from their initiatives ---
    themes_db = _load_themes()
    for theme in themes_db.get("themes", []):
        if theme.get("source_title"):
            continue
        child_inits = [i for i in inits_db.get("initiatives", []) if i.get("theme_id") == theme["id"]]
        titles = []
        url_map = {}
        pid_map = {}
        for i in child_inits:
            st = i.get("source_title", "")
            if st:
                titles.append(st)
                url_map[st] = i.get("source_url", "")
                pid_map[st] = i.get("source_page_id", "")
        if titles:
            best = Counter(titles).most_common(1)[0][0]
            theme.update({"source_title": best, "source_url": url_map.get(best, ""), "source_page_id": pid_map.get(best, "")})
            updated["themes"] += 1

    _save_themes(themes_db)

    return JSONResponse({
        "message": "Source metadata backfilled.",
        "updated": updated,
        "tasks_with_source": sum(1 for t in tasks if t.get("source_title")),
        "total_tasks": len(tasks),
    })


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

@router.get("/people")
async def get_people():
    from integrations.people import get_all_people
    return JSONResponse(get_all_people())


@router.get("/people/{name}")
async def get_person(name: str):
    from integrations.people import get_person as _get
    result = _get(name)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


@router.post("/people", status_code=201)
async def add_person(body: PersonCreate):
    from integrations.people import add_person as _add
    fields = {k: v for k, v in body.model_dump().items() if k != "name" and v}
    result = _add(body.name, **fields)
    if "error" in result:
        return JSONResponse(result, status_code=409)
    return JSONResponse(result)


@router.patch("/people/{name}")
async def update_person(name: str, body: PersonUpdate):
    from integrations.people import update_person as _update
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return JSONResponse({"error": "No fields"}, status_code=400)
    return JSONResponse(_update(name, **fields))


@router.delete("/people/{name}")
async def delete_person(name: str):
    from integrations.people import delete_person as _delete
    result = _delete(name)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Settings / status
# ---------------------------------------------------------------------------

@router.get("/settings/status")
async def get_integration_status():
    from config import (
        OPENAI_API_KEY, ANTHROPIC_API_KEY, NOTION_API_KEY,
        MS_CLIENT_ID, MS_TENANT_ID, TELEGRAM_BOT_TOKEN,
    )

    ms_configured = bool(MS_CLIENT_ID and MS_TENANT_ID)
    ms_signed_in = False
    if ms_configured:
        try:
            from integrations.ms_auth import get_token_silent
            ms_signed_in = get_token_silent() is not None
        except Exception:
            pass

    return JSONResponse({
        "microsoft365": {"configured": ms_configured, "signed_in": ms_signed_in, "services": ["Calendar", "Email", "To Do"]},
        "notion": {"configured": bool(NOTION_API_KEY), "services": ["Pages", "Meeting Notes", "Intelligence Scan"]},
        "openai": {"configured": bool(OPENAI_API_KEY), "services": ["Voice (Realtime)", "Whisper", "TTS"]},
        "anthropic": {"configured": bool(ANTHROPIC_API_KEY), "services": ["Intelligence Extraction (Haiku)"]},
        "telegram": {"configured": bool(TELEGRAM_BOT_TOKEN), "services": ["Bot", "Reminders"]},
    })


# ---------------------------------------------------------------------------
# Voice token
# ---------------------------------------------------------------------------

@router.get("/token")
async def get_ephemeral_token():
    """Get an ephemeral token for OpenAI Realtime API."""
    import httpx
    from config import OPENAI_API_KEY
    from web.server import TARS_INSTRUCTIONS, REALTIME_TOOLS

    if not OPENAI_API_KEY:
        return JSONResponse({"error": "OPENAI_API_KEY not configured"}, status_code=500)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini-realtime-preview", "voice": "ash",
                "instructions": TARS_INSTRUCTIONS, "tools": REALTIME_TOOLS,
                "turn_detection": {"type": "server_vad", "threshold": 0.5, "silence_duration_ms": 800},
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

    return JSONResponse({"token": data["client_secret"]["value"], "expires_at": data.get("expires_at")})


# ---------------------------------------------------------------------------
# Tool execution (for voice/external clients)
# ---------------------------------------------------------------------------

class ToolCallRequest(BaseModel):
    name: str
    arguments: dict


@router.post("/tool")
async def execute_tool(req: ToolCallRequest):
    from backend.tools import registry
    result = await registry.execute(req.name, req.arguments)
    if "error" in result:
        return JSONResponse({"error": result["error"]}, status_code=400)
    return JSONResponse({"result": result})
