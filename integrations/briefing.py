"""Daily briefing — pulls calendar, tasks, and unread emails in one shot."""
from __future__ import annotations

import logging
from typing import Any

from integrations.calendar import get_events
from integrations.mail import get_messages
from integrations.tasks import get_tasks

logger = logging.getLogger(__name__)


async def get_briefing() -> dict[str, Any]:
    """Get a daily briefing: today's events, pending tasks, and unread emails.

    Returns:
        Dict with "calendar", "tasks", and "email" sections.
    """
    # Fetch all three in parallel-ish (they're all async)
    calendar_data = await get_events(days=1, max_results=10)
    tasks_data = await get_tasks(max_results=10)
    email_data = await get_messages(unread_only=True, max_results=10)

    return {
        "calendar": {
            "events": calendar_data["events"],
            "count": calendar_data["count"],
        },
        "tasks": {
            "items": tasks_data["tasks"],
            "count": tasks_data["count"],
        },
        "email": {
            "unread": email_data["messages"],
            "count": email_data["count"],
        },
    }
