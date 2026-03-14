"""
journal_service.py - Audit log service.

Google Sheets support has been removed. This module provides stubs
for backward compatibility with existing tests and code.
For production use, see app.services.journal_service.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Union

from backend.services.sheets_service import (
    SheetsError,
    SheetNotFoundError,
    SHEET_JOURNAL,
    SHEET_JOURNAL_NEW,
    get_header_map,
    MissingHeaderError,
)

logger = logging.getLogger(__name__)

JOURNAL_HEADERS: List[str] = [
    "timestamp",
    "telegram_user_id",
    "full_name",
    "user_role",
    "action",
    "deal_id",
    "changed_fields",
    "payload_summary",
]

_NEW_JOURNAL_HEADERS: List[str] = [
    "timestamp",
    "user",
    "role",
    "action",
    "entity",
    "entity_id",
    "details",
]


def get_worksheet(name: str) -> Any:
    """Stub – raises NotImplementedError. Present for patch compatibility."""
    raise NotImplementedError(
        "Google Sheets support has been removed. Use PostgreSQL via app.database."
    )


def _ensure_headers(ws: Any) -> None:
    """
    Write the header row if the sheet is empty, or warn if headers are wrong.

    Kept for backward compatibility with existing tests. Works with real or mock
    worksheet objects that implement row_values() and append_row().
    """
    try:
        existing = ws.row_values(1)
        existing_stripped = [c.strip() for c in existing]

        if not any(existing_stripped):
            ws.append_row(JOURNAL_HEADERS, value_input_option="USER_ENTERED")
            logger.info("Created journal header row.")
            return

        existing_set = set(existing_stripped)
        missing_headers = [h for h in JOURNAL_HEADERS if h not in existing_set]
        if missing_headers:
            logger.warning(
                "Journal sheet has missing or mismatched headers: %s. "
                "Expected: %s. Found: %s.",
                missing_headers,
                JOURNAL_HEADERS,
                existing_stripped,
            )
    except Exception as exc:
        logger.warning("Could not ensure journal headers: %s", exc)


def _serialise(value: Union[str, list, dict, None]) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def append_journal_entry(
    telegram_user_id: str,
    full_name: str = "",
    user_role: str = "",
    action: str = "",
    deal_id: str = "",
    changed_fields: Optional[Union[str, list]] = None,
    payload_summary: Optional[Union[str, dict]] = None,
) -> None:
    """
    Stub - previously wrote to Google Sheets journal.
    Now logs to application logger only.
    For production use, call app.services.journal_service.log_action instead.
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "JOURNAL: timestamp=%s user=%s role=%s action=%s deal_id=%s",
        timestamp,
        telegram_user_id,
        user_role,
        action,
        deal_id,
    )


def append_new_journal_entry(
    user: str,
    role: str,
    action: str,
    entity: str,
    entity_id: str = "",
    details: str = "",
) -> None:
    """
    Stub - previously wrote to new-format Google Sheets journal.
    Now logs to application logger only.
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "JOURNAL_NEW: timestamp=%s user=%s role=%s action=%s entity=%s entity_id=%s",
        timestamp,
        user,
        role,
        action,
        entity,
        entity_id,
    )
