"""
managers_service.py – CRUD operations for the 'managers' sheet.

Sheet columns:
  manager_id | manager_name | role | created_at

Public API
----------
get_managers()                              → List[dict]
add_manager(manager_name, role)             → dict
update_manager(manager_id, name, role)      → dict | None
delete_manager(manager_id)                 → bool
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.services.sheets_service import (
    SHEET_MANAGERS,
    SheetsError,
    get_or_create_worksheet,
    get_header_map,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()

MANAGERS_HEADERS: List[str] = ["manager_id", "manager_name", "role", "created_at"]


def _ensure_headers(ws) -> None:
    """Write the canonical header row if the sheet is empty."""
    try:
        existing = ws.row_values(1)
        if not any(c.strip() for c in existing):
            ws.append_row(MANAGERS_HEADERS, value_input_option="USER_ENTERED")
            logger.info("Created managers header row.")
    except Exception as exc:
        logger.warning("Could not ensure managers headers: %s", exc)


def _row_to_dict(header_map: Dict[str, int], row: List[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for col_name, idx in header_map.items():
        result[col_name] = row[idx] if idx < len(row) else ""
    return result


def get_managers() -> List[dict]:
    """Return all managers from the managers sheet."""
    try:
        ws = get_or_create_worksheet(SHEET_MANAGERS)
    except SheetsError as exc:
        logger.error("Could not access managers sheet: %s", exc)
        return []

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    if not header_map:
        return []

    all_rows = ws.get_all_values()
    managers: List[dict] = []
    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        if not any(c.strip() for c in row):
            continue
        entry = _row_to_dict(header_map, row)
        if entry.get("manager_id") and entry.get("manager_name"):
            managers.append(entry)
    return managers


def add_manager(manager_name: str, role: str = "manager") -> dict:
    """Append a new manager to the managers sheet. Returns the created record."""
    manager_name = manager_name.strip()
    if not manager_name:
        raise ValueError("manager_name cannot be empty")

    try:
        ws = get_or_create_worksheet(SHEET_MANAGERS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access managers sheet: {exc}") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)

    with _lock:
        manager_id = str(uuid.uuid4())[:8]
        created_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        row_data = {
            "manager_id": manager_id,
            "manager_name": manager_name,
            "role": role,
            "created_at": created_at,
        }

        max_idx = max(header_map.values(), default=len(MANAGERS_HEADERS) - 1)
        row: List = [""] * (max_idx + 1)
        for col_name, idx in header_map.items():
            row[idx] = row_data.get(col_name, "")

        ws.append_row(row, value_input_option="USER_ENTERED")

    return row_data


def update_manager(
    manager_id: str,
    manager_name: Optional[str] = None,
    role: Optional[str] = None,
) -> Optional[dict]:
    """Update manager_name and/or role for a given manager_id. Returns updated record or None."""
    if manager_name is not None:
        manager_name = manager_name.strip()
        if not manager_name:
            raise ValueError("manager_name cannot be empty")

    try:
        ws = get_or_create_worksheet(SHEET_MANAGERS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access managers sheet: {exc}") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    if not header_map:
        return None

    all_rows = ws.get_all_values()
    id_col = header_map.get("manager_id")
    name_col = header_map.get("manager_name")
    role_col = header_map.get("role")
    if id_col is None:
        return None

    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        row_id = row[id_col] if id_col < len(row) else ""
        if row_id == manager_id:
            current_name = row[name_col] if name_col is not None and name_col < len(row) else ""
            current_role = row[role_col] if role_col is not None and role_col < len(row) else ""

            new_name = manager_name if manager_name is not None else current_name
            new_role = role if role is not None else current_role

            if name_col is not None:
                ws.update_cell(i + 1, name_col + 1, new_name)
            if role_col is not None:
                ws.update_cell(i + 1, role_col + 1, new_role)

            return {"manager_id": manager_id, "manager_name": new_name, "role": new_role}

    return None


def delete_manager(manager_id: str) -> bool:
    """Delete a manager by manager_id. Returns True if deleted, False if not found."""
    try:
        ws = get_or_create_worksheet(SHEET_MANAGERS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access managers sheet: {exc}") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    if not header_map:
        return False

    all_rows = ws.get_all_values()
    id_col = header_map.get("manager_id")
    if id_col is None:
        return False

    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        row_id = row[id_col] if id_col < len(row) else ""
        if row_id == manager_id:
            ws.delete_rows(i + 1)
            return True

    return False
