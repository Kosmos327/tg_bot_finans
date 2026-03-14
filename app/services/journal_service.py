"""
Journal service — writes audit entries to the journal_entries table.

Every create/update/delete action should call log_action().
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import JournalEntry

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    user_id: str | int | None = None,
    role_name: str | None = None,
    entity: str | None = None,
    entity_id: str | int | None = None,
    details: str | None = None,
) -> None:
    """
    Append one audit record to the journal_entries table.

    Parameters
    ----------
    db:        Async database session.
    action:    Short action name, e.g. "create_deal", "delete_manager".
    user_id:   Telegram user ID or username.
    role_name: Role at the time of the action.
    entity:    Entity type, e.g. "manager", "client", "deal".
    entity_id: Affected entity ID.
    details:   Human-readable summary of what changed.
    """
    try:
        entry = JournalEntry(
            user_id=str(user_id) if user_id is not None else None,
            role_name=role_name,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
        )
        db.add(entry)
        await db.flush()
        logger.debug(
            "Journal entry written: action=%s entity=%s entity_id=%s user=%s",
            action,
            entity,
            entity_id,
            user_id,
        )
    except Exception as exc:
        logger.warning("Failed to write journal entry: %s", exc)
