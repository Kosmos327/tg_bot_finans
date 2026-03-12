"""Journal router – audit log."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from backend.services import settings_service
from backend.services.permissions import NO_ACCESS_ROLE
from backend.services.sheets_service import (
    SheetsError,
    SheetNotFoundError,
    SHEET_JOURNAL,
    get_worksheet,
    get_header_map,
)
from backend.services.telegram_auth import extract_user_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"])

_JOURNAL_HEADER_FIELDS = [
    "timestamp",
    "telegram_user_id",
    "full_name",
    "user_role",
    "action",
    "deal_id",
    "changed_fields",
    "payload_summary",
]


def _resolve_user(init_data: Optional[str]) -> tuple:
    """Return (user_id, role) from Telegram initData."""
    if not init_data:
        return "", NO_ACCESS_ROLE
    user = extract_user_from_init_data(init_data)
    if not user:
        return "", NO_ACCESS_ROLE
    user_id = str(user.get("id", ""))
    role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
    return user_id, role


@router.get("/recent", response_model=List[Dict[str, Any]])
async def recent_journal(
    limit: int = Query(default=50, le=200, ge=1),
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> List[Dict[str, Any]]:
    """Return recent journal entries. Managers cannot access the journal."""
    user_id, role = _resolve_user(x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    # Managers do not have access to the journal
    if role == "manager":
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        ws = get_worksheet(SHEET_JOURNAL)
        header_map = get_header_map(ws)
        all_rows = ws.get_all_values()
    except SheetNotFoundError as exc:
        logger.warning("Journal sheet not found: %s", exc)
        return []
    except SheetsError as exc:
        logger.error("Error reading journal: %s", exc)
        raise HTTPException(status_code=500, detail="Journal unavailable") from exc

    entries: List[Dict[str, Any]] = []
    for i in range(len(all_rows) - 1, 0, -1):  # iterate from last row, skip header (index 0)
        row = all_rows[i]
        if not any(c.strip() for c in row):
            continue
        entry: Dict[str, Any] = {}
        for field in _JOURNAL_HEADER_FIELDS:
            col_idx = header_map.get(field)
            entry[field] = row[col_idx].strip() if col_idx is not None and col_idx < len(row) else ""
        entries.append(entry)
        if len(entries) >= limit:
            break

    return entries

