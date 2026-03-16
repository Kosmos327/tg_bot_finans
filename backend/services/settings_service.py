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
    get_or_create_worksheet,
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
    "business_directions": ["ФФ МСК", "ФФ НСК", "ФФ ЕКБ", "ТЛК", "УТЛ"],
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
    except Exception as exc:
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
    Clients and managers are loaded from their dedicated sheets.
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

        settings_data = {
            "statuses": _with_defaults("statuses"),
            "business_directions": _with_defaults("business_directions"),
            "vat_types": _with_defaults("vat_types"),
            "sources": _with_defaults("sources"),
        }
    except (SheetNotFoundError, SheetsError) as exc:
        logger.error("Failed to load settings: %s", exc)
        settings_data = {
            "statuses": list(_DEFAULTS["statuses"]),
            "business_directions": list(_DEFAULTS["business_directions"]),
            "vat_types": list(_DEFAULTS["vat_types"]),
            "sources": list(_DEFAULTS["sources"]),
        }

    # Load clients and managers from their dedicated sheets
    try:
        from backend.services.clients_service import get_clients
        clients_records = get_clients()
        clients = [r["client_name"] for r in clients_records if r.get("client_name")]
        if not clients:
            clients = list(_DEFAULTS.get("clients", []))
    except Exception as exc:
        logger.warning("Failed to load clients from sheet: %s", exc)
        clients = list(_DEFAULTS.get("clients", []))

    try:
        from backend.services.managers_service import get_managers
        managers_records = get_managers()
        managers = [r["manager_name"] for r in managers_records if r.get("manager_name")]
        if not managers:
            managers = list(_DEFAULTS.get("managers", []))
    except Exception as exc:
        logger.warning("Failed to load managers from sheet: %s", exc)
        managers = list(_DEFAULTS.get("managers", []))

    return {
        **settings_data,
        "clients": clients,
        "managers": managers,
    }


# ---------------------------------------------------------------------------
# Section management helpers (add/delete items in simple list sections)
# ---------------------------------------------------------------------------


def _rewrite_settings_sheet(ws, updated_sections: Dict[str, List[str]]) -> None:
    """
    Rewrite the entire settings sheet preserving all sections, but replacing
    the values in *updated_sections*.

    This function reads the current sheet, updates the in-memory representation,
    then clears and rewrites the sheet.
    """
    all_values = ws.get_all_values()
    parsed = parse_settings_sheet(all_values)

    # Merge updates
    for key, values in updated_sections.items():
        parsed[key] = values

    # Build new rows
    rows = []
    for header_text, key, is_table in _SECTION_DEFS:
        if is_table:
            continue  # Don't rewrite roles table via this helper
        values = parsed.get(key, [])
        if not values:
            continue
        rows.append([header_text])
        for val in values:
            rows.append([val])
        rows.append([""])  # blank row between sections

    ws.clear()
    if rows:
        ws.update(rows, value_input_option="USER_ENTERED")


def add_direction(direction: str) -> List[str]:
    """Add a new direction to the settings sheet. Returns updated list."""
    direction = direction.strip()
    if not direction:
        raise ValueError("direction cannot be empty")

    try:
        ws = get_or_create_worksheet(SHEET_SETTINGS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access settings sheet: {exc}") from exc

    all_values = ws.get_all_values()
    parsed = parse_settings_sheet(all_values)
    directions = parsed.get("business_directions", [])
    if not directions:
        directions = list(_DEFAULTS["business_directions"])

    if direction not in directions:
        directions.append(direction)
        _rewrite_settings_sheet(ws, {"business_directions": directions})

    return directions


def delete_direction(direction: str) -> List[str]:
    """Remove a direction from the settings sheet. Returns updated list."""
    try:
        ws = get_or_create_worksheet(SHEET_SETTINGS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access settings sheet: {exc}") from exc

    all_values = ws.get_all_values()
    parsed = parse_settings_sheet(all_values)
    directions = parsed.get("business_directions", [])
    if not directions:
        directions = list(_DEFAULTS["business_directions"])

    directions = [d for d in directions if d != direction]
    _rewrite_settings_sheet(ws, {"business_directions": directions})
    return directions


def add_status(status: str) -> List[str]:
    """Add a new status to the settings sheet. Returns updated list."""
    status = status.strip()
    if not status:
        raise ValueError("status cannot be empty")

    try:
        ws = get_or_create_worksheet(SHEET_SETTINGS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access settings sheet: {exc}") from exc

    all_values = ws.get_all_values()
    parsed = parse_settings_sheet(all_values)
    statuses = parsed.get("statuses", [])
    if not statuses:
        statuses = list(_DEFAULTS["statuses"])

    if status not in statuses:
        statuses.append(status)
        _rewrite_settings_sheet(ws, {"statuses": statuses})

    return statuses


def delete_status(status: str) -> List[str]:
    """Remove a status from the settings sheet. Returns updated list."""
    try:
        ws = get_or_create_worksheet(SHEET_SETTINGS)
    except SheetsError as exc:
        raise SheetsError(f"Could not access settings sheet: {exc}") from exc

    all_values = ws.get_all_values()
    parsed = parse_settings_sheet(all_values)
    statuses = parsed.get("statuses", [])
    if not statuses:
        statuses = list(_DEFAULTS["statuses"])

    statuses = [s for s in statuses if s != status]
    _rewrite_settings_sheet(ws, {"statuses": statuses})
    return statuses


# ---------------------------------------------------------------------------
# Async PostgreSQL implementations (used by routers with AsyncSession)
# ---------------------------------------------------------------------------


async def load_all_settings_pg(db) -> dict:
    """
    Load all settings sections from PostgreSQL.

    Queries deal_statuses, business_directions, vat_types, sources, clients,
    and managers tables.  Falls back to hardcoded defaults on any error.
    """
    from sqlalchemy import select as sa_select
    from app.database.models import (
        DealStatus, BusinessDirection, VatType, Source, Client, Manager,
    )

    async def _fetch_names(model, order_col):
        try:
            result = await db.execute(sa_select(model).order_by(order_col))
            rows = result.scalars().all()
            return [r.name for r in rows if r.name]
        except Exception as exc:
            logger.warning("Failed to load %s from DB: %s", model.__tablename__, exc)
            return []

    statuses = await _fetch_names(DealStatus, DealStatus.name)
    if not statuses:
        statuses = list(_DEFAULTS["statuses"])

    directions = await _fetch_names(BusinessDirection, BusinessDirection.name)
    if not directions:
        directions = list(_DEFAULTS["business_directions"])

    vat_types = await _fetch_names(VatType, VatType.name)
    if not vat_types:
        vat_types = list(_DEFAULTS["vat_types"])

    sources = await _fetch_names(Source, Source.name)
    if not sources:
        sources = list(_DEFAULTS["sources"])

    # Clients: return names
    try:
        result = await db.execute(
            sa_select(Client).order_by(Client.client_name)
        )
        clients = [c.client_name for c in result.scalars().all() if c.client_name]
    except Exception as exc:
        logger.warning("Failed to load clients from DB: %s", exc)
        clients = list(_DEFAULTS["clients"])

    # Managers: return names
    try:
        result = await db.execute(
            sa_select(Manager).order_by(Manager.manager_name)
        )
        managers = [m.manager_name for m in result.scalars().all() if m.manager_name]
    except Exception as exc:
        logger.warning("Failed to load managers from DB: %s", exc)
        managers = list(_DEFAULTS["managers"])

    return {
        "statuses": statuses,
        "business_directions": directions,
        "vat_types": vat_types,
        "sources": sources,
        "clients": clients,
        "managers": managers,
    }


async def load_enriched_settings_pg(db) -> dict:
    """
    Load all reference data from PostgreSQL, enriched with IDs.

    Returns {id, name} objects for each reference item so that the Mini App
    can pass IDs directly to SQL-function-based API endpoints.
    """
    from sqlalchemy import select as sa_select
    from app.database.models import (
        DealStatus, BusinessDirection, VatType, Source, Client, Manager, Warehouse,
    )

    async def _fetch_id_name(model, name_col, order_col):
        try:
            result = await db.execute(sa_select(model).order_by(order_col))
            rows = result.scalars().all()
            return [{"id": r.id, "name": getattr(r, name_col)} for r in rows if getattr(r, name_col, None)]
        except Exception as exc:
            logger.warning("Failed to load %s from DB: %s", model.__tablename__, exc)
            return []

    statuses = await _fetch_id_name(DealStatus, "name", DealStatus.name)
    directions = await _fetch_id_name(BusinessDirection, "name", BusinessDirection.name)
    vat_types = await _fetch_id_name(VatType, "name", VatType.name)
    if not vat_types:
        vat_types = [{"id": 1, "name": "С НДС"}, {"id": 2, "name": "Без НДС"}]
    sources = await _fetch_id_name(Source, "name", Source.name)

    try:
        result = await db.execute(sa_select(Client).order_by(Client.client_name))
        clients = [{"id": c.id, "name": c.client_name} for c in result.scalars().all() if c.client_name]
    except Exception as exc:
        logger.warning("Failed to load clients from DB: %s", exc)
        clients = []

    try:
        result = await db.execute(sa_select(Manager).order_by(Manager.manager_name))
        managers = [{"id": m.id, "name": m.manager_name} for m in result.scalars().all() if m.manager_name]
    except Exception as exc:
        logger.warning("Failed to load managers from DB: %s", exc)
        managers = []

    try:
        result = await db.execute(sa_select(Warehouse).order_by(Warehouse.name))
        warehouses = [{"id": w.id, "name": w.name, "code": w.code} for w in result.scalars().all()]
    except Exception as exc:
        logger.warning("Failed to load warehouses from DB: %s", exc)
        warehouses = []

    return {
        "statuses": statuses,
        "business_directions": directions,
        "vat_types": vat_types,
        "sources": sources,
        "clients": clients,
        "managers": managers,
        "warehouses": warehouses,
    }



    """Return all business directions from PostgreSQL."""
    from sqlalchemy import select as sa_select
    from app.database.models import BusinessDirection

    try:
        result = await db.execute(
            sa_select(BusinessDirection).order_by(BusinessDirection.name)
        )
        names = [r.name for r in result.scalars().all() if r.name]
        return names or list(_DEFAULTS["business_directions"])
    except Exception as exc:
        logger.warning("Failed to load business_directions from DB: %s", exc)
        return list(_DEFAULTS["business_directions"])


async def add_direction_pg(db, direction: str) -> List[str]:
    """Add a new business direction. Returns updated list."""
    from sqlalchemy import select as sa_select
    from app.database.models import BusinessDirection

    direction = direction.strip()
    if not direction:
        raise ValueError("direction cannot be empty")

    try:
        existing = await db.execute(
            sa_select(BusinessDirection).where(BusinessDirection.name == direction)
        )
        if existing.scalar_one_or_none() is None:
            db.add(BusinessDirection(name=direction))
            await db.flush()
            logger.info("Added business direction: %r", direction)
    except Exception as exc:
        logger.error("Failed to add business direction: %s", exc)
        raise

    return await load_business_directions_pg(db)


async def delete_direction_pg(db, direction: str) -> List[str]:
    """Remove a business direction. Returns updated list."""
    from sqlalchemy import select as sa_select, delete as sa_delete
    from app.database.models import BusinessDirection

    try:
        await db.execute(
            sa_delete(BusinessDirection).where(BusinessDirection.name == direction)
        )
        await db.flush()
        logger.info("Deleted business direction: %r", direction)
    except Exception as exc:
        logger.error("Failed to delete business direction: %s", exc)
        raise

    return await load_business_directions_pg(db)


async def load_statuses_pg(db) -> List[str]:
    """Return all deal statuses from PostgreSQL."""
    from sqlalchemy import select as sa_select
    from app.database.models import DealStatus

    try:
        result = await db.execute(sa_select(DealStatus).order_by(DealStatus.name))
        names = [r.name for r in result.scalars().all() if r.name]
        return names or list(_DEFAULTS["statuses"])
    except Exception as exc:
        logger.warning("Failed to load deal_statuses from DB: %s", exc)
        return list(_DEFAULTS["statuses"])


async def add_status_pg(db, status: str) -> List[str]:
    """Add a new deal status. Returns updated list."""
    from sqlalchemy import select as sa_select
    from app.database.models import DealStatus

    status = status.strip()
    if not status:
        raise ValueError("status cannot be empty")

    try:
        existing = await db.execute(
            sa_select(DealStatus).where(DealStatus.name == status)
        )
        if existing.scalar_one_or_none() is None:
            db.add(DealStatus(name=status))
            await db.flush()
            logger.info("Added deal status: %r", status)
    except Exception as exc:
        logger.error("Failed to add deal status: %s", exc)
        raise

    return await load_statuses_pg(db)


async def delete_status_pg(db, status: str) -> List[str]:
    """Remove a deal status. Returns updated list."""
    from sqlalchemy import delete as sa_delete
    from app.database.models import DealStatus

    try:
        await db.execute(sa_delete(DealStatus).where(DealStatus.name == status))
        await db.flush()
        logger.info("Deleted deal status: %r", status)
    except Exception as exc:
        logger.error("Failed to delete deal status: %s", exc)
        raise

    return await load_statuses_pg(db)
