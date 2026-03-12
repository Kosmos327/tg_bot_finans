"""
journal_service.py – Immutable audit log for the "Журнал действий" sheet.

The first row of the sheet is treated as the header row.  If the sheet is
empty the headers are written automatically before the first entry is appended.

Expected columns (created if missing):
  timestamp | telegram_user_id | full_name | user_role | action
  | deal_id | changed_fields | payload_summary

Public API
----------
append_journal_entry(
    telegram_user_id, full_name, user_role, action,
    deal_id="", changed_fields="", payload_summary=""
) → None
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Union

from backend.services.sheets_service import (
    SheetsError,
    SheetNotFoundError,
    SHEET_JOURNAL,
    get_worksheet,
    get_header_map,
    MissingHeaderError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expected journal headers (in order)
# ---------------------------------------------------------------------------

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


def _ensure_headers(ws) -> None:
    """Write the header row if the sheet is completely empty."""
    try:
        existing = ws.row_values(1)
        if not any(c.strip() for c in existing):
            ws.append_row(JOURNAL_HEADERS, value_input_option="USER_ENTERED")
            logger.info("Created journal header row in '%s'.", SHEET_JOURNAL)
    except Exception as exc:
        logger.warning("Could not ensure journal headers: %s", exc)


def _serialise(value: Union[str, list, dict, None]) -> str:
    """Serialise *value* to a compact string suitable for a sheet cell."""
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
    Append one row to the "Журнал действий" audit sheet.

    Parameters
    ----------
    telegram_user_id:  Telegram numeric user ID (as string).
    full_name:         User display name from roles table.
    user_role:         Role at the time of the action.
    action:            Short action name, e.g. "create_deal", "update_deal".
    deal_id:           Affected deal ID (empty if not deal-related).
    changed_fields:    List of field names that were modified, or string.
    payload_summary:   Human-readable or JSON summary of the payload.
    """
    try:
        ws = get_worksheet(SHEET_JOURNAL)
    except SheetNotFoundError as exc:
        logger.error("Journal sheet not found – entry not written: %s", exc)
        return
    except SheetsError as exc:
        logger.error("Cannot access journal sheet: %s", exc)
        return

    _ensure_headers(ws)

    # Build row aligned with JOURNAL_HEADERS
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    row = [
        timestamp,
        str(telegram_user_id),
        full_name or "",
        user_role or "",
        action or "",
        deal_id or "",
        _serialise(changed_fields),
        _serialise(payload_summary),
    ]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.debug(
            "Journal entry written: action=%s deal_id=%s user=%s",
            action,
            deal_id,
            telegram_user_id,
        )
    except Exception as exc:
        logger.warning("Failed to append journal entry: %s", exc)
