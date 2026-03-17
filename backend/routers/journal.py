"""Journal router – audit log."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from backend.models.schemas import JournalEntryNewCreate
from backend.services import settings_service
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    JOURNAL_VIEW_ROLES,
    ALLOWED_ROLES,
    check_role,
)
from backend.services.sheets_service import (
    SheetsError,
    SheetNotFoundError,
    SHEET_JOURNAL,
    SHEET_JOURNAL_NEW,
    get_worksheet,
    get_header_map,
)
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"])

# Legacy journal column fields (old "Журнал действий" sheet)
_LEGACY_JOURNAL_FIELDS = [
    "timestamp",
    "telegram_user_id",
    "full_name",
    "user_role",
    "action",
    "deal_id",
    "changed_fields",
    "payload_summary",
]

# New journal column fields ("journal" sheet)
_NEW_JOURNAL_FIELDS = [
    "timestamp",
    "user",
    "role",
    "action",
    "entity",
    "entity_id",
    "details",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_user(init_data: Optional[str], role_header: Optional[str] = None) -> tuple:
    """Return (user_id, role) from Telegram initData or X-User-Role header.

    When initData is present but the Sheets-based role lookup returns NO_ACCESS_ROLE
    (user migrated to PostgreSQL-only), fall through to the X-User-Role header so
    that authenticated sessions continue to work.

    Returns:
        - (user_id_str, role_code) when resolved via initData + Sheets lookup.
        - ("", role_code) when resolved via X-User-Role header fallback.
        - ("", NO_ACCESS_ROLE) when no auth information can be resolved.
    """
    if init_data:
        user = extract_user_from_init_data(init_data)
        if user:
            user_id = str(user.get("id", ""))
            role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
            if role != NO_ACCESS_ROLE:
                return user_id, role

    if role_header and role_header.strip():
        role = role_header.strip().lower()
        if role in ALLOWED_ROLES:
            return "", role

    return "", NO_ACCESS_ROLE


def _read_journal(sheet_name: str, fields: List[str], limit: int) -> List[Dict[str, Any]]:
    """Read the last *limit* rows from a journal sheet."""
    try:
        ws = get_worksheet(sheet_name)
        header_map = get_header_map(ws)
        all_rows = ws.get_all_values()
    except SheetNotFoundError as exc:
        logger.warning("Journal sheet '%s' not found: %s", sheet_name, exc)
        return []
    except SheetsError as exc:
        logger.error("Error reading journal sheet '%s': %s", sheet_name, exc)
        raise

    entries: List[Dict[str, Any]] = []
    for i in range(len(all_rows) - 1, 0, -1):  # newest first, skip header at index 0
        row = all_rows[i]
        if not any(c.strip() for c in row):
            continue
        entry: Dict[str, Any] = {}
        for field in fields:
            col_idx = header_map.get(field)
            entry[field] = row[col_idx].strip() if col_idx is not None and col_idx < len(row) else ""
        entries.append(entry)
        if len(entries) >= limit:
            break

    return entries


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/recent", response_model=List[Dict[str, Any]])
async def recent_journal(
    limit: int = Query(default=50, le=200, ge=1),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Return recent journal entries from the legacy "Журнал действий" sheet.
    Accessible by: operations_director, accounting, admin.
    """
    user_id, role = _resolve_user(x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not check_role(role, JOURNAL_VIEW_ROLES):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return _read_journal(SHEET_JOURNAL, _LEGACY_JOURNAL_FIELDS, limit)
    except SheetsError as exc:
        raise HTTPException(status_code=500, detail="Journal unavailable") from exc


@router.get("", response_model=List[Dict[str, Any]])
async def list_journal(
    limit: int = Query(default=50, le=200, ge=1),
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """
    Return recent entries from the new 'journal' sheet (timestamp/user/action/entity/entity_id/details).
    Accessible by: operations_director, accounting, admin.
    """
    user_id, role = _resolve_user(x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    if not check_role(role, JOURNAL_VIEW_ROLES):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return _read_journal(SHEET_JOURNAL_NEW, _NEW_JOURNAL_FIELDS, limit)
    except SheetsError as exc:
        raise HTTPException(status_code=500, detail="Journal unavailable") from exc


@router.post("", response_model=Dict[str, Any])
async def write_journal_entry(
    body: JournalEntryNewCreate,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Append one entry to the new 'journal' sheet.
    Callable by any authenticated user (Mini App sends user actions here).
    """
    user_id, role = _resolve_user(x_telegram_init_data, x_user_role)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        ws = get_worksheet(SHEET_JOURNAL_NEW)
    except SheetNotFoundError:
        # Sheet doesn't exist yet – try to create the header row via the old journal
        logger.warning("New journal sheet not found; entry not written.")
        return {"success": False, "detail": "Journal sheet not found"}
    except SheetsError as exc:
        raise HTTPException(status_code=500, detail="Journal unavailable") from exc

    # Ensure headers exist
    try:
        existing = ws.row_values(1)
        if not any(c.strip() for c in existing):
            ws.append_row(_NEW_JOURNAL_FIELDS, value_input_option="USER_ENTERED")
    except Exception:
        pass

    row = [
        timestamp,
        body.user or user_id,
        body.role or role,
        body.action,
        body.entity,
        body.entity_id,
        body.details,
    ]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as exc:
        logger.warning("Failed to append journal entry: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to write journal entry") from exc

    return {"success": True, "timestamp": timestamp}

