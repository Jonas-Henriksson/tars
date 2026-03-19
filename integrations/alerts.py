"""Proactive alerts & escalation intelligence.

Analyzes the full TARS data landscape to surface:
- Bottleneck detection (people overloaded with tasks)
- Overdue task escalation
- Calendar conflict detection
- Relationship health scoring
- Risk flags from initiatives and decisions
- Workload imbalance warnings
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Alert sensitivity multiplier: "low" = 1.5x thresholds (fewer alerts),
# "medium" = 1.0x (default), "high" = 0.7x (more alerts)
SENSITIVITY_MULTIPLIERS = {"low": 1.5, "medium": 1.0, "high": 0.7}
_sensitivity = "medium"  # Default

def set_alert_sensitivity(level: str) -> None:
    global _sensitivity
    if level in SENSITIVITY_MULTIPLIERS:
        _sensitivity = level

def _threshold(base: int) -> int:
    return max(1, int(base * SENSITIVITY_MULTIPLIERS.get(_sensitivity, 1.0)))


async def get_alerts() -> dict[str, Any]:
    """Run all proactive alert checks and return prioritized findings.

    This is the main entry point — scans tasks, calendar, people, initiatives,
    and decisions for issues that need executive attention.
    """
    alerts: list[dict] = []

    alerts.extend(_check_bottlenecks())
    alerts.extend(_check_overdue_escalations())
    alerts.extend(await _check_calendar_conflicts())
    alerts.extend(_check_relationship_health())
    alerts.extend(_check_initiative_risks())
    alerts.extend(_check_stale_decisions())
    alerts.extend(_check_orphaned_deliverables())

    # Group related alerts by type
    grouped = _group_alerts(alerts)
    alerts = grouped

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 3))

    # Voice summary
    critical = sum(1 for a in alerts if a.get("severity") == "critical")
    warning = sum(1 for a in alerts if a.get("severity") == "warning")

    parts = []
    if not alerts:
        parts.append("No alerts. Everything looks good")
    else:
        parts.append(f"{len(alerts)} alert{'s' if len(alerts) != 1 else ''}")
        if critical:
            parts.append(f"{critical} critical")
        if warning:
            parts.append(f"{warning} warning{'s' if warning != 1 else ''}")
        # Announce top critical alerts
        for a in alerts[:2]:
            if a.get("severity") == "critical":
                parts.append(a.get("title", ""))

    return {
        "alerts": alerts,
        "count": len(alerts),
        "critical_count": critical,
        "warning_count": warning,
        "voice_summary": ". ".join(parts) + ".",
    }


def _group_alerts(alerts: list[dict]) -> list[dict]:
    """Collapse multiple alerts of the same type into summary alerts."""
    from collections import defaultdict
    by_type = defaultdict(list)
    for a in alerts:
        by_type[a.get("type", "other")].append(a)

    result = []
    for alert_type, group in by_type.items():
        if len(group) <= 2:
            result.extend(group)
        else:
            # Pick the highest severity from the group
            sev_order = {"critical": 0, "warning": 1, "info": 2}
            best_sev = min(group, key=lambda a: sev_order.get(a.get("severity", "info"), 3))["severity"]

            # Build summary
            summary = {
                "type": alert_type,
                "severity": best_sev,
                "title": f"{len(group)} {alert_type.replace('_', ' ')} alerts",
                "detail": "; ".join(a["title"] for a in group[:3]) + (f" and {len(group)-3} more" if len(group) > 3 else ""),
                "children": group,
                "suggested_action": group[0].get("suggested_action", ""),
                "is_group": True,
            }
            result.append(summary)
    return result


def _check_bottlenecks() -> list[dict]:
    """Detect people who are overloaded with tasks."""
    try:
        from integrations.intel import get_intel
        intel = get_intel()
        smart_tasks = intel.get("smart_tasks", [])
    except Exception:
        return []

    # Count open tasks per owner
    owner_counts: dict[str, list[dict]] = {}
    for task in smart_tasks:
        if task.get("status") == "done":
            continue
        owner = task.get("owner", "Unassigned")
        if owner == "Unassigned":
            continue
        owner_counts.setdefault(owner, []).append(task)

    alerts = []
    for owner, tasks in owner_counts.items():
        q1_count = sum(1 for t in tasks if t.get("priority", {}).get("quadrant") == 1)

        if len(tasks) >= _threshold(10):
            alerts.append({
                "type": "bottleneck",
                "severity": "critical",
                "title": f"{owner} is overloaded ({len(tasks)} open tasks)",
                "detail": f"{owner} has {len(tasks)} open tasks"
                          f"{f', including {q1_count} urgent' if q1_count else ''}. "
                          f"Consider redistributing or deprioritizing.",
                "person": owner,
                "task_count": len(tasks),
                "suggested_action": "redistribute_tasks",
            })
        elif len(tasks) >= _threshold(7):
            alerts.append({
                "type": "bottleneck",
                "severity": "warning",
                "title": f"{owner} has high workload ({len(tasks)} tasks)",
                "detail": f"{owner} has {len(tasks)} open tasks. Monitor capacity.",
                "person": owner,
                "task_count": len(tasks),
                "suggested_action": "check_in",
            })

    return alerts


def _check_overdue_escalations() -> list[dict]:
    """Flag tasks that are significantly overdue and need escalation."""
    try:
        from integrations.intel import get_intel
        intel = get_intel()
        smart_tasks = intel.get("smart_tasks", [])
    except Exception:
        return []

    now = datetime.now(timezone.utc)
    alerts = []

    for task in smart_tasks:
        if task.get("status") == "done":
            continue
        fud = task.get("follow_up_date", "")
        if not fud:
            continue
        try:
            due = datetime.fromisoformat(fud)
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            days_overdue = (now - due).days

            if days_overdue >= 14:
                alerts.append({
                    "type": "escalation",
                    "severity": "critical",
                    "title": f"Severely overdue: {task.get('description', '')[:60]}",
                    "detail": f"Task '{task.get('description', '')}' is {days_overdue} days overdue. "
                              f"Owner: {task.get('owner', 'Unassigned')}. Escalate or close.",
                    "owner": task.get("owner", ""),
                    "days_overdue": days_overdue,
                    "task_id": task.get("id"),
                    "suggested_action": "escalate",
                })
            elif days_overdue >= _threshold(10):
                alerts.append({
                    "type": "escalation",
                    "severity": "warning",
                    "title": f"Overdue: {task.get('description', '')[:60]}",
                    "detail": f"Task '{task.get('description', '')}' is {days_overdue} days overdue. "
                              f"Owner: {task.get('owner', 'Unassigned')}.",
                    "owner": task.get("owner", ""),
                    "days_overdue": days_overdue,
                    "task_id": task.get("id"),
                    "suggested_action": "follow_up",
                })
        except (ValueError, TypeError):
            continue

    return alerts


async def _check_calendar_conflicts() -> list[dict]:
    """Detect scheduling conflicts in the calendar."""
    try:
        from integrations.calendar import get_events
        data = await get_events(days=3, max_results=30)
        events = data.get("events", [])
    except Exception:
        return []

    alerts = []

    # Parse events into time ranges
    parsed = []
    for evt in events:
        start = evt.get("start", "")
        end = evt.get("end", "")
        if not start or not end:
            continue
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            parsed.append({
                "subject": evt.get("subject", "Untitled"),
                "start": start_dt,
                "end": end_dt,
            })
        except (ValueError, TypeError):
            continue

    # Check for overlaps
    for i, a in enumerate(parsed):
        for b in parsed[i+1:]:
            if a["start"] < b["end"] and b["start"] < a["end"]:
                alerts.append({
                    "type": "calendar_conflict",
                    "severity": "warning",
                    "title": f"Scheduling conflict: {a['subject']} vs {b['subject']}",
                    "detail": f"'{a['subject']}' ({a['start'].strftime('%H:%M')}-{a['end'].strftime('%H:%M')}) "
                              f"overlaps with '{b['subject']}' ({b['start'].strftime('%H:%M')}-{b['end'].strftime('%H:%M')}) "
                              f"on {a['start'].strftime('%A %b %d')}.",
                    "suggested_action": "reschedule",
                })

    # Check for back-to-back days (no breaks)
    now = datetime.now(timezone.utc)
    today_events = [p for p in parsed if p["start"].date() == now.date()]
    if len(today_events) >= 6:
        total_meeting_hours = sum(
            (e["end"] - e["start"]).total_seconds() / 3600
            for e in today_events
        )
        if total_meeting_hours >= 5:
            alerts.append({
                "type": "calendar_load",
                "severity": "warning",
                "title": f"Heavy meeting day: {len(today_events)} meetings, {total_meeting_hours:.1f}h",
                "detail": f"You have {len(today_events)} meetings today totaling {total_meeting_hours:.1f} hours. "
                          f"Consider blocking focus time or declining non-essential meetings.",
                "suggested_action": "block_focus_time",
            })

    return alerts


def _check_relationship_health() -> list[dict]:
    """Flag relationships that need attention based on interaction patterns."""
    try:
        from integrations.people import get_all_people
        all_people = get_all_people()
        people = all_people.get("people", {})
    except Exception:
        return []

    alerts = []
    now = datetime.now(timezone.utc)

    for name, profile in people.items():
        # Skip people who aren't direct reports or important relationships
        relationship = profile.get("relationship", "").lower()
        has_1on1s = profile.get("has_one_on_ones", False)
        is_important = has_1on1s or "direct" in relationship or "manager" in relationship

        if not is_important:
            continue

        # Check last interaction age
        pages = profile.get("pages", [])
        latest_edit = ""
        for p in pages:
            edited = p.get("last_edited", "")
            if edited > latest_edit:
                latest_edit = edited

        if latest_edit:
            try:
                last_dt = datetime.fromisoformat(latest_edit)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                days_since = (now - last_dt).days

                if days_since >= _threshold(21):
                    alerts.append({
                        "type": "relationship",
                        "severity": "warning" if days_since >= _threshold(30) else "info",
                        "title": f"No recent interaction with {name} ({days_since}d)",
                        "detail": f"Last documented interaction with {name} was {days_since} days ago. "
                                  f"{'They have 1:1s scheduled. ' if has_1on1s else ''}"
                                  f"Consider reaching out.",
                        "person": name,
                        "days_since": days_since,
                        "suggested_action": "schedule_check_in",
                    })
            except (ValueError, TypeError):
                pass

    return alerts


def _check_initiative_risks() -> list[dict]:
    """Flag initiatives that are at risk or off track."""
    try:
        from integrations.initiatives import get_initiatives
        result = get_initiatives()
        initiatives = result.get("initiatives", [])
    except Exception:
        return []

    alerts = []

    for i in initiatives:
        status = i.get("status", "")
        title = i.get("title", "")

        if status == "off_track":
            alerts.append({
                "type": "initiative_risk",
                "severity": "critical",
                "title": f"Initiative off track: {title}",
                "detail": f"'{title}' is off track. Owner: {i.get('owner', 'Unknown')}. "
                          f"{'Quarter: ' + i.get('quarter', '') + '. ' if i.get('quarter') else ''}"
                          f"Review and decide on corrective action.",
                "initiative_id": i.get("id"),
                "suggested_action": "review_initiative",
            })
        elif status == "at_risk":
            alerts.append({
                "type": "initiative_risk",
                "severity": "warning",
                "title": f"Initiative at risk: {title}",
                "detail": f"'{title}' is at risk. Monitor closely and consider intervention.",
                "initiative_id": i.get("id"),
                "suggested_action": "monitor",
            })

    return alerts


def _check_stale_decisions() -> list[dict]:
    """Flag pending decisions that have been waiting too long."""
    try:
        from integrations.decisions import get_decisions
        result = get_decisions(status="pending")
        pending = result.get("decisions", [])
    except Exception:
        return []

    alerts = []
    now = datetime.now(timezone.utc)

    for d in pending:
        created = d.get("created_at", "")
        if not created:
            continue
        try:
            created_dt = datetime.fromisoformat(created)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            days_pending = (now - created_dt).days

            if days_pending >= _threshold(10):
                alerts.append({
                    "type": "stale_decision",
                    "severity": "warning" if days_pending >= _threshold(21) else "info",
                    "title": f"Decision pending {days_pending}d: {d.get('title', '')}",
                    "detail": f"'{d.get('title', '')}' has been pending for {days_pending} days. "
                              f"{'Stakeholders: ' + ', '.join(d.get('stakeholders', [])) + '. ' if d.get('stakeholders') else ''}"
                              f"Make a call or gather more input.",
                    "decision_id": d.get("id"),
                    "days_pending": days_pending,
                    "suggested_action": "decide",
                })
        except (ValueError, TypeError):
            continue

    return alerts


def _check_orphaned_deliverables() -> list[dict]:
    """Flag deliverable tasks that should belong to an epic but don't.

    Uses keyword heuristics to distinguish structured deliverables (build,
    implement, deploy, etc.) from operational/admin work. Only flags when
    a person has 2+ orphaned deliverables to avoid noise.
    """
    try:
        from integrations.team_portfolio import get_team_portfolio
        result = get_team_portfolio()
        portfolio = result.get("portfolio", {})
    except Exception:
        return []

    alerts = []

    for name, member in portfolio.items():
        needs_epic = member.get("needs_epic", [])
        if not needs_epic:
            continue

        # Only alert if there are 2+ orphaned deliverables per person (avoid noise)
        if len(needs_epic) >= 2:
            sample_tasks = ", ".join(
                t.get("description", "")[:50] for t in needs_epic[:3]
            )
            alerts.append({
                "type": "orphaned_deliverable",
                "severity": "warning" if len(needs_epic) >= 4 else "info",
                "title": f"{name} has {len(needs_epic)} deliverable tasks without an epic",
                "detail": f"{name} is working on deliverable tasks that aren't linked "
                          f"to any epic: {sample_tasks}. "
                          f"Consider creating an epic to give these structure and context.",
                "person": name,
                "task_count": len(needs_epic),
                "tasks": [t.get("description", "")[:60] for t in needs_epic[:5]],
                "suggested_action": "create_epic",
            })

    return alerts
