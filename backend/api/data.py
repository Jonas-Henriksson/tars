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

router = APIRouter(prefix="/api", tags=["data"])


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


class DecisionUpdate(BaseModel):
    status: str | None = None
    rationale: str | None = None
    outcome_notes: str | None = None
    stakeholders: list[str] | None = None
    initiative: str | None = None
    title: str | None = None


class InitiativeCreate(BaseModel):
    title: str
    description: str = ""
    owner: str = ""
    quarter: str = ""
    status: str = "on_track"
    priority: str = "high"
    milestones: list[str] = []


class InitiativeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    owner: str | None = None
    quarter: str | None = None
    status: str | None = None
    priority: str | None = None


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
async def get_intel(user: CurrentUser = Depends(get_current_user)):
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
# Meeting prep
# ---------------------------------------------------------------------------

@router.get("/meeting-prep")
async def api_meeting_prep(event_id: str = "", minutes_ahead: int = 480):
    from integrations.meeting_prep import get_meeting_prep
    return JSONResponse(await get_meeting_prep(event_id=event_id, minutes_ahead=minutes_ahead))


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
    ))


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
        quarter=body.quarter, status=body.status, priority=body.priority, milestones=body.milestones,
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
