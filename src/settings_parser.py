"""
Parser for the "Настройки" (Settings) Google Sheet.

The sheet is organized as named blocks separated by section header rows.
Each block starts with a Russian header and contains value rows beneath it.

Supported blocks (case-insensitive, extra whitespace is stripped):
  - Статусы            -> statuses
  - Направления бизнеса -> business_directions
  - Клиенты            -> clients
  - Менеджеры          -> managers
  - НДС                -> vat_types
  - Источники          -> sources
  - Роли               -> roles  (structured: telegram_user_id, full_name, role, active)

Usage::

    parser = SettingsParser()
    payload = parser.parse(sheet_rows)
    # payload is a dict with keys:
    #   statuses, business_directions, clients, managers,
    #   vat_types, sources, roles
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Block header → payload key mapping.
# Keys are normalised (stripped, lower-cased) Russian section names.
# ---------------------------------------------------------------------------
_BLOCK_HEADER_MAP: dict[str, str] = {
    "статусы": "statuses",
    "направления бизнеса": "business_directions",
    "клиенты": "clients",
    "менеджеры": "managers",
    "ндс": "vat_types",
    "источники": "sources",
    "роли": "roles",
}

# Column names expected in the "Роли" block header row (normalised).
_ROLES_COLUMNS = ("telegram_user_id", "full_name", "role", "active")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise_text(value: Any) -> str:
    """Return *value* as a whitespace-normalised, stripped string.

    ``None`` is treated as an empty string.
    """
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalise_bool(value: Any) -> bool:
    """Convert common truthy string representations to a Python bool."""
    return _normalise_text(value).upper() in {"TRUE", "1", "YES", "ДА", "Y"}


def _normalise_int(value: Any) -> int | None:
    """
    Parse *value* as an integer.

    Returns ``None`` when the value is empty or cannot be parsed.
    """
    text = _normalise_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _is_empty_row(row: list[Any]) -> bool:
    """Return ``True`` when every cell in *row* is blank / whitespace-only."""
    return all(_normalise_text(cell) == "" for cell in row)


def _row_as_header(row: list[Any]) -> str | None:
    """
    If the first non-empty cell of *row* matches a known block header,
    return the normalised header text; otherwise return ``None``.
    """
    for cell in row:
        text = _normalise_text(cell).lower()
        if text in _BLOCK_HEADER_MAP:
            return text
        if text:
            # Non-empty cell that is not a recognised header → not a header row
            break
    return None


# ---------------------------------------------------------------------------
# Block parsers
# ---------------------------------------------------------------------------

def _parse_simple_block(rows: list[list[Any]]) -> list[str]:
    """
    Parse a block whose values are plain text items (one per row,
    first column).  Empty and whitespace-only rows are skipped.
    """
    result: list[str] = []
    for row in rows:
        if _is_empty_row(row):
            continue
        value = _normalise_text(row[0]) if row else ""
        if value:
            result.append(value)
    return result


def _parse_roles_block(rows: list[list[Any]]) -> list[dict[str, Any]]:
    """
    Parse the structured "Роли" block.

    The block may optionally start with a header row whose cells match
    ``_ROLES_COLUMNS`` (used as a visual guide in the spreadsheet).
    Every subsequent non-empty row is interpreted as a role entry with
    columns in the order:
        telegram_user_id | full_name | role | active
    """
    result: list[dict[str, Any]] = []

    for row in rows:
        if _is_empty_row(row):
            continue

        # Detect and skip the optional column-header row inside the block.
        normalised_cells = [_normalise_text(c).lower() for c in row]
        if all(
            col in normalised_cells
            for col in (_ROLES_COLUMNS[0], _ROLES_COLUMNS[2])
        ):
            continue

        # Pad short rows so index access is always safe.
        padded = list(row) + [""] * max(0, len(_ROLES_COLUMNS) - len(row))

        user_id = _normalise_int(padded[0])
        full_name = _normalise_text(padded[1])
        role = _normalise_text(padded[2]).lower()
        active = _normalise_bool(padded[3])

        result.append(
            {
                "telegram_user_id": user_id,
                "full_name": full_name,
                "role": role,
                "active": active,
            }
        )

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SettingsParser:
    """
    Parses rows from the "Настройки" Google Sheet into a structured
    settings payload.

    The parser is intentionally extensible: to support a new block, add
    an entry to ``_BLOCK_HEADER_MAP`` and (if needed) register a custom
    block parser in ``_BLOCK_PARSERS``.
    """

    # Maps payload key → parser callable.
    # Blocks not listed here fall back to ``_parse_simple_block``.
    _BLOCK_PARSERS: dict[str, Any] = {
        "roles": _parse_roles_block,
    }

    def parse(self, rows: list[list[Any]]) -> dict[str, Any]:
        """
        Parse *rows* (a list of rows, each row being a list of cell values)
        into a structured settings dictionary.

        Returns a dict with the following keys (each defaults to an empty
        list if the corresponding block is absent from the sheet):

        * ``statuses``            – list[str]
        * ``business_directions`` – list[str]
        * ``clients``             – list[str]
        * ``managers``            – list[str]
        * ``vat_types``           – list[str]
        * ``sources``             – list[str]
        * ``roles``               – list[dict]
        """
        payload: dict[str, Any] = {key: [] for key in _BLOCK_HEADER_MAP.values()}

        # Group rows into (header_key, [data_rows]) blocks.
        blocks: list[tuple[str, list[list[Any]]]] = []
        current_key: str | None = None
        current_rows: list[list[Any]] = []

        for row in rows:
            if _is_empty_row(row):
                # Blank rows are spacing rows – keep accumulating but skip them
                # when they appear before the first block is identified.
                if current_key is not None:
                    current_rows.append(row)
                continue

            header = _row_as_header(row)
            if header is not None:
                # Save the previous block (if any) and start a new one.
                if current_key is not None:
                    blocks.append((current_key, current_rows))
                current_key = _BLOCK_HEADER_MAP[header]
                current_rows = []
            else:
                if current_key is not None:
                    current_rows.append(row)
                # Rows that appear before any header are silently ignored.

        # Don't forget the last open block.
        if current_key is not None:
            blocks.append((current_key, current_rows))

        # Parse each collected block.
        for key, block_rows in blocks:
            parser = self._BLOCK_PARSERS.get(key, _parse_simple_block)
            payload[key] = parser(block_rows)

        return payload
