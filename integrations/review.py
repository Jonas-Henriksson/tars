"""Weekly review — voice-friendly summary of task trends and delegation."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta


def get_weekly_review_voice() -> dict:
    """Get a voice-optimized weekly review summary.

    Pulls from intel and tracked tasks, builds a concise narrative
    suitable for the voice AI to read back.
    """
    from integrations.intel import get_intel
    from integrations.notion_tasks import get_tracked_tasks

    intel = get_intel()
    smart_tasks = intel.get("smart_tasks", [])
    topics = intel.get("topics", {})
    people = intel.get("people", {})

    now = datetime.now(timezone.utc)

    open_tasks = [t for t in smart_tasks if t.get("status") != "done"]
    done_tasks = [t for t in smart_tasks if t.get("status") == "done"]

    # Quadrant distribution
    quadrants = {1: 0, 2: 0, 3: 0, 4: 0}
    for t in open_tasks:
        q = t.get("priority", {}).get("quadrant", 4)
        quadrants[q] = quadrants.get(q, 0) + 1

    # Overdue
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
                        "description": t.get("description", ""),
                        "owner": t.get("owner", ""),
                        "days_overdue": (now - due).days,
                    })
            except (ValueError, TypeError):
                pass
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)

    # Delegation
    delegation = {}
    for t in open_tasks:
        owner = t.get("owner", "Unassigned")
        delegation.setdefault(owner, 0)
        delegation[owner] += 1

    # Tracked tasks stale count
    tracked = get_tracked_tasks()
    stale_count = 0
    for t in tracked.get("tasks", []):
        created = t.get("created_at", "")
        if created:
            try:
                cdt = datetime.fromisoformat(created)
                if cdt.tzinfo is None:
                    cdt = cdt.replace(tzinfo=timezone.utc)
                if (now - cdt).days >= 7:
                    stale_count += 1
            except (ValueError, TypeError):
                pass

    # Build voice summary
    parts = []
    parts.append(f"You have {len(open_tasks)} open tasks and {len(done_tasks)} completed")

    if quadrants[1]:
        parts.append(f"{quadrants[1]} need immediate action")
    if quadrants[2]:
        parts.append(f"{quadrants[2]} scheduled")
    if quadrants[3]:
        parts.append(f"{quadrants[3]} delegated")

    if overdue:
        parts.append(f"{len(overdue)} are overdue")
        worst = overdue[0]
        parts.append(
            f"the most overdue is \"{worst['description'][:60]}\" "
            f"owned by {worst['owner']}, {worst['days_overdue']} days late"
        )

    if stale_count:
        parts.append(f"{stale_count} tracked tasks are stale, open for over a week")

    # Delegation summary
    delegated_others = {k: v for k, v in delegation.items() if k != "Me"}
    if delegated_others:
        busiest = max(delegated_others.items(), key=lambda x: x[1])
        parts.append(f"{busiest[0]} has the most tasks with {busiest[1]}")

    return {
        "voice_summary": ". ".join(parts) + ".",
        "open": len(open_tasks),
        "done": len(done_tasks),
        "quadrants": quadrants,
        "overdue_count": len(overdue),
        "overdue": overdue[:5],
        "stale_count": stale_count,
        "delegation": delegation,
        "top_topics": dict(sorted(topics.items(), key=lambda x: -x[1])[:5]),
    }
