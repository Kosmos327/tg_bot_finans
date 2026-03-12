"""
settings_service.py – Parse "Настройки" sheet and expose reference data + role mapping.

Sheet format (block layout)
----------------------------
Each logical section is introduced by a header enclosed in square brackets,
e.g. "[Статусы сделок]".  Values follow on subsequent rows (one per row, in
column A).  A completely empty row or the next section header ends the section.

The roles section uses a pipe-delimited table format:

    [Роли пользователей]
    telegram_user_id | full_name | role | active
    123456789 | Иван Петров | manager | TRUE
    987654321 | Анна Смирнова | accountant | TRUE

Public API
----------
load_statuses()            → List[str]
load_business_directions() → List[str]
load_clients()             → List[str]
load_managers()            → List[str]
load_vat_types()           → List[str]
load_sources()             → List[str]
load_roles_mapping()       → List[dict]
get_user_role(user_id)     → str   ("no_access" if unknown/inactive)
is_user_active(user_id)    → bool
load_all_settings()        → dict  (all sections combined)
"""

import logging
from typing import Dict, List, Optional

from backend.services.sheets_service import (
    SheetsError,
    SheetNotFoundError,
    SHEET_SETTINGS,
    get_worksheet,
)
from backend.services.permissions import ALLOWED_ROLES, NO_ACCESS_ROLE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping: sheet section headers → internal keys
# ---------------------------------------------------------------------------

# Each entry: (section_header_text, internal_key, is_table)
_SECTION_DEFS = [
    ("[Статусы сделок]", "statuses", False),
    ("[Направления бизнеса]", "business_directions", False),
    ("[Клиенты]", "clients", False),
    ("[Менеджеры]", "managers", False),
    ("[Наличие НДС]", "vat_types", False),
    ("[Источники]", "sources", False),
    ("[Роли пользователей]", "roles_mapping", True),
]

# Quick lookup: canonical header text → (key, is_table)
_SECTION_LOOKUP: Dict[str, tuple] = {
    hdr: (key, is_tbl) for hdr, key, is_tbl in _SECTION_DEFS
}

# Default fallback values when a section is empty / missing
_DEFAULTS: Dict[str, List[str]] = {
    "statuses": ["Новая", "В работе", "Завершена", "Отменена", "Приостановлена"],
    "business_directions": ["Разработка", "Консалтинг", "Дизайн", "Маркетинг", "Другое"],
    "clients": [],
    "managers": [],
    "vat_types": ["С НДС", "Без НДС"],
    "sources": ["Рекомендация", "Сайт", "Реклама", "Холодный звонок", "Другое"],
    "roles_mapping": [],
}

# ---------------------------------------------------------------------------
# Core parser (pure function – easy to unit-test with synthetic data)
# ---------------------------------------------------------------------------

# All known section header texts for end-of-section detection
_ALL_SECTION_HEADERS = frozenset(_SECTION_LOOKUP.keys())


def parse_settings_sheet(all_values: List[List[str]]) -> Dict[str, list]:
    """
    Parse the raw 2-D list returned by ``worksheet.get_all_values()`` and
    return a dict with one key per section.

    Parameters
    ----------
    all_values:
        List of rows; each row is a list of cell strings.

    Returns
    -------
    dict with keys: statuses, business_directions, clients, managers,
                    vat_types, sources, roles_mapping
    """
    result: Dict[str, list] = {key: [] for _, key, _ in _SECTION_DEFS}

    current_key: Optional[str] = None
    current_is_table: bool = False
    table_headers: Optional[List[str]] = None

    for row in all_values:
        # Normalise: strip whitespace from every cell
        cells = [c.strip() for c in row]
        first_cell = cells[0] if cells else ""

        # ── Section header detection ──────────────────────────────────────
        if first_cell in _ALL_SECTION_HEADERS:
            current_key, current_is_table = _SECTION_LOOKUP[first_cell]
            table_headers = None  # reset table headers for new section
            continue

        # ── Outside any section ───────────────────────────────────────────
        if current_key is None:
            continue

        # ── Empty row → end of current section ───────────────────────────
        if not any(cells):
            current_key = None
            current_is_table = False
            table_headers = None
            continue

        # ── Table section (roles_mapping) ─────────────────────────────────
        if current_is_table:
            # Pipe-delimited values
            parts = [p.strip() for p in first_cell.split("|")]
            # Also check if values span multiple columns
            if len(parts) == 1 and len([c for c in cells if c]) > 1:
                parts = [c for c in cells if c]

            if table_headers is None:
                # First row after section header is the column header row
                table_headers = [p.lower().replace(" ", "_") for p in parts]
                continue

            if len(parts) < len(table_headers):
                # Pad short rows
                parts += [""] * (len(table_headers) - len(parts))

            entry = dict(zip(table_headers, parts))
            result[current_key].append(entry)
            continue

        # ── Simple list section ───────────────────────────────────────────
        value = first_cell
        if value:
            result[current_key].append(value)

    return result


# ---------------------------------------------------------------------------
# Public loader functions
# ---------------------------------------------------------------------------


def _load_section(key: str) -> list:
    """Load a single section from the settings sheet with fallback defaults."""
    try:
        ws = get_worksheet(SHEET_SETTINGS)
        all_values = ws.get_all_values()
        parsed = parse_settings_sheet(all_values)
        data = parsed.get(key, [])
        if not data:
            logger.warning("Settings section '%s' is empty; using defaults.", key)
            return list(_DEFAULTS.get(key, []))
        return data
    except SheetNotFoundError:
        logger.warning("Sheet '%s' not found; using defaults for '%s'.", SHEET_SETTINGS, key)
        return list(_DEFAULTS.get(key, []))
    except SheetsError as exc:
        logger.error("Failed to load settings section '%s': %s", key, exc)
        return list(_DEFAULTS.get(key, []))


def load_statuses() -> List[str]:
    return _load_section("statuses")


def load_business_directions() -> List[str]:
    return _load_section("business_directions")


def load_clients() -> List[str]:
    return _load_section("clients")


def load_managers() -> List[str]:
    return _load_section("managers")


def load_vat_types() -> List[str]:
    return _load_section("vat_types")


def load_sources() -> List[str]:
    return _load_section("sources")


def load_roles_mapping() -> List[dict]:
    """
    Return the list of role-mapping entries from the "[Роли пользователей]"
    section.  Each entry is a dict with at least:
        telegram_user_id, full_name, role, active
    """
    raw = _load_section("roles_mapping")
    normalised: List[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        user_id = str(entry.get("telegram_user_id", "")).strip()
        role = str(entry.get("role", "")).strip().lower()
        active_raw = str(entry.get("active", "")).strip().upper()

        if not user_id:
            logger.warning("Skipping malformed role row (missing telegram_user_id): %s", entry)
            continue
        if role not in ALLOWED_ROLES:
            logger.warning(
                "Unknown role '%s' for user %s; skipping.", role, user_id
            )
            continue

        normalised.append(
            {
                "telegram_user_id": user_id,
                "full_name": str(entry.get("full_name", "")).strip(),
                "role": role,
                "active": active_raw in {"TRUE", "1", "YES", "ДА", "ACTIVE"},
            }
        )
    return normalised


def _build_roles_index() -> Dict[str, dict]:
    """Return a dict keyed by telegram_user_id for fast look-up."""
    return {entry["telegram_user_id"]: entry for entry in load_roles_mapping()}


def get_user_role(telegram_user_id: str) -> str:
    """
    Return the role string for *telegram_user_id*.
    Returns NO_ACCESS_ROLE ("no_access") if the user is not found or inactive.
    """
    index = _build_roles_index()
    entry = index.get(str(telegram_user_id))
    if entry is None:
        return NO_ACCESS_ROLE
    if not entry.get("active", False):
        return NO_ACCESS_ROLE
    return entry.get("role", NO_ACCESS_ROLE)


def is_user_active(telegram_user_id: str) -> bool:
    """Return True if the user exists in the roles table and is active."""
    index = _build_roles_index()
    entry = index.get(str(telegram_user_id))
    return bool(entry and entry.get("active", False))


def get_user_full_name(telegram_user_id: str) -> str:
    """Return the user's full name from the roles table, or empty string."""
    index = _build_roles_index()
    entry = index.get(str(telegram_user_id))
    return entry.get("full_name", "") if entry else ""


def load_all_settings() -> dict:
    """
    Load all sections from the settings sheet in a single round-trip.
    Returns a dict with all section keys.
    """
    try:
        ws = get_worksheet(SHEET_SETTINGS)
        all_values = ws.get_all_values()
        parsed = parse_settings_sheet(all_values)

        def _with_defaults(key: str) -> list:
            data = parsed.get(key, [])
            if not data:
                return list(_DEFAULTS.get(key, []))
            return data

        return {
            "statuses": _with_defaults("statuses"),
            "business_directions": _with_defaults("business_directions"),
            "clients": _with_defaults("clients"),
            "managers": _with_defaults("managers"),
            "vat_types": _with_defaults("vat_types"),
            "sources": _with_defaults("sources"),
        }
    except (SheetNotFoundError, SheetsError) as exc:
        logger.error("Failed to load all settings: %s", exc)
        return {k: list(v) for k, v in _DEFAULTS.items() if k != "roles_mapping"}
