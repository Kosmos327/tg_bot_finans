"""
clients_service.py – CRUD operations for the 'clients' sheet.

Sheet columns:
  client_id | client_name | created_at

Public API
----------
get_clients()                      → List[dict]
add_client(client_name)            → dict
update_client(client_id, name)     → dict | None
delete_client(client_id)           → bool
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.services.sheets_service import (
    SHEET_CLIENTS,
    SheetsError,
    get_or_create_worksheet,
    get_header_map,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()

CLIENTS_HEADERS: List[str] = ["client_id", "client_name", "created_at"]


def _ensure_headers(ws) -> None:
    """Write the canonical header row if the sheet is empty."""
    try:
        existing = ws.row_values(1)
        if not any(c.strip() for c in existing):
            ws.append_row(CLIENTS_HEADERS, value_input_option="USER_ENTERED")
            logger.info("Created clients header row.")
    except Exception as exc:
        logger.warning("Could not ensure clients headers: %s", exc)


def _row_to_dict(header_map: Dict[str, int], row: List[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for col_name, idx in header_map.items():
        result[col_name] = row[idx] if idx < len(row) else ""
    return result


def get_clients() -> List[dict]:
    """Return all clients from the clients sheet."""
    try:
        ws = get_or_create_worksheet(SHEET_CLIENTS)
    except SheetsError as exc:
        logger.error("Could not access clients sheet: %s", exc)
        return []

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    if not header_map:
        return []

    all_rows = ws.get_all_values()
    clients: List[dict] = []
    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        if not any(c.strip() for c in row):
            continue
        entry = _row_to_dict(header_map, row)
        if entry.get("client_id") and entry.get("client_name"):
            clients.append(entry)
    return clients


def add_client(client_name: str) -> dict:
    """Append a new client to the clients sheet. Returns the created record."""
    client_name = client_name.strip()
    if not client_name:
        raise ValueError("client_name cannot be empty")

    try:
        ws = get_or_create_worksheet(SHEET_CLIENTS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access clients sheet: {exc}") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)

    with _lock:
        client_id = str(uuid.uuid4())[:8]
        created_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        row_data = {
            "client_id": client_id,
            "client_name": client_name,
            "created_at": created_at,
        }

        max_idx = max(header_map.values(), default=len(CLIENTS_HEADERS) - 1)
        row: List = [""] * (max_idx + 1)
        for col_name, idx in header_map.items():
            row[idx] = row_data.get(col_name, "")

        ws.append_row(row, value_input_option="USER_ENTERED")

    return row_data


def update_client(client_id: str, client_name: str) -> Optional[dict]:
    """Update the client_name for a given client_id. Returns updated record or None."""
    client_name = client_name.strip()
    if not client_name:
        raise ValueError("client_name cannot be empty")

    try:
        ws = get_or_create_worksheet(SHEET_CLIENTS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access clients sheet: {exc}") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    if not header_map:
        return None

    all_rows = ws.get_all_values()
    id_col = header_map.get("client_id")
    name_col = header_map.get("client_name")
    if id_col is None or name_col is None:
        return None

    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        row_id = row[id_col] if id_col < len(row) else ""
        if row_id == client_id:
            # Update the name column (1-indexed row, 1-indexed col)
            ws.update_cell(i + 1, name_col + 1, client_name)
            return {"client_id": client_id, "client_name": client_name}

    return None


def delete_client(client_id: str) -> bool:
    """Delete a client by client_id. Returns True if deleted, False if not found."""
    try:
        ws = get_or_create_worksheet(SHEET_CLIENTS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access clients sheet: {exc}") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    if not header_map:
        return False

    all_rows = ws.get_all_values()
    id_col = header_map.get("client_id")
    if id_col is None:
        return False

    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        row_id = row[id_col] if id_col < len(row) else ""
        if row_id == client_id:
            ws.delete_rows(i + 1)
            return True

    return False
