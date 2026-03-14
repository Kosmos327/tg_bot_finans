"""
billing_service.py – CRUD operations for billing_msk / billing_nsk / billing_ekb sheets.

Supports two sheet formats:

Old format (p1/p2 period columns):
  client_name, p1_shipments_amount, p1_units, p1_storage_amount, p1_pallets,
  p1_returns_amount, p1_returns_trips, p1_extra_services, p1_penalties,
  p1_total_without_penalties, p1_total_with_penalties,
  p2_shipments_amount, ... (same pattern)

New format (VAT-aware single-period columns):
  client, period,
  shipments_with_vat, shipments_vat, shipments_without_vat,
  storage_with_vat, storage_vat, storage_without_vat,
  returns_pickup_with_vat, returns_pickup_vat, returns_pickup_without_vat,
  returns_trips_count,
  additional_services_with_vat, additional_services_vat, additional_services_without_vat,
  penalties,
  total_without_vat, total_vat, total_with_vat,
  payment_status

Format detection is automatic based on header row.

Automatic calculations (new format, fixed 20% VAT):
  *_without_vat = *_with_vat / 1.2
  *_vat         = *_with_vat - *_without_vat
  total_without_vat = shipments_without_vat + storage_without_vat
                    + returns_pickup_without_vat + additional_services_without_vat
                    - penalties
  total_vat     = sum of all *_vat fields
  total_with_vat = total_without_vat + total_vat

Public API
----------
get_billing_entries(warehouse)               → List[dict]
get_billing_entry(warehouse, client_name)    → dict | None
upsert_billing_entry(warehouse, entry_data, user, role) → dict
mark_payment(deal_id, payment_amount, user, role) → bool
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.sheets_service import (
    BILLING_SHEETS,
    MissingHeaderError,
    SheetsError,
    SheetNotFoundError,
    get_worksheet,
    get_header_map,
    safe_float,
)
from backend.services.journal_service import append_journal_entry

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Column definitions – OLD format (p1/p2 period-based)
# ---------------------------------------------------------------------------

BILLING_HEADERS: List[str] = [
    "client_name",
    "p1_shipments_amount", "p1_units", "p1_storage_amount", "p1_pallets",
    "p1_returns_amount", "p1_returns_trips", "p1_extra_services", "p1_penalties",
    "p1_total_without_penalties", "p1_total_with_penalties",
    "p2_shipments_amount", "p2_units", "p2_storage_amount", "p2_pallets",
    "p2_returns_amount", "p2_returns_trips", "p2_extra_services", "p2_penalties",
    "p2_total_without_penalties", "p2_total_with_penalties",
]

# Fields that are auto-calculated in old format
_CALC_FIELDS_OLD = frozenset({
    "p1_total_without_penalties", "p1_total_with_penalties",
    "p2_total_without_penalties", "p2_total_with_penalties",
})

_SUM_FIELDS_P1 = [
    "p1_shipments_amount", "p1_storage_amount",
    "p1_returns_amount", "p1_extra_services",
]
_SUM_FIELDS_P2 = [
    "p2_shipments_amount", "p2_storage_amount",
    "p2_returns_amount", "p2_extra_services",
]

# ---------------------------------------------------------------------------
# Column definitions – NEW format (VAT-aware single-period)
# ---------------------------------------------------------------------------

BILLING_HEADERS_V2: List[str] = [
    "client",
    "month",
    "period",
    "input_mode",
    "shipments_with_vat",
    "shipments_vat",
    "shipments_without_vat",
    "units_count",
    "storage_with_vat",
    "storage_vat",
    "storage_without_vat",
    "pallets_count",
    "returns_pickup_with_vat",
    "returns_pickup_vat",
    "returns_pickup_without_vat",
    "returns_trips_count",
    "additional_services_with_vat",
    "additional_services_vat",
    "additional_services_without_vat",
    "penalties",
    "total_without_vat",
    "total_vat",
    "total_with_vat",
    "payment_status",
    "payment_amount",
    "payment_date",
]

# Calculated columns in new format (re-computed from input)
_CALC_FIELDS_V2 = frozenset({
    "shipments_vat", "shipments_without_vat",
    "storage_vat", "storage_without_vat",
    "returns_pickup_vat", "returns_pickup_without_vat",
    "additional_services_vat", "additional_services_without_vat",
    "total_without_vat", "total_vat", "total_with_vat",
})

# Input-mode constants (full names as per updated sheet spec)
INPUT_MODE_WITH_VAT = "Новый (с НДС)"
INPUT_MODE_WITHOUT_VAT = "Новый (без НДС)"
INPUT_MODE_OLD = "Старый (p1/p2)"

# Backward-compat aliases accepted from older clients / sheets (lowercase for matching)
_INPUT_MODE_WITHOUT_VAT_ALIASES_LOWER = frozenset({"без ндс", "новый (без ндс)"})
_INPUT_MODE_OLD_ALIAS_LOWER = INPUT_MODE_OLD.lower()

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _is_new_format(header_map: Dict[str, int]) -> bool:
    """Return True if the sheet uses the new VAT-aware billing format."""
    return "shipments_with_vat" in header_map or "client" in header_map


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_sheet_name(warehouse: str) -> str:
    """Return the sheet name for the given warehouse key (msk/nsk/ekb)."""
    key = warehouse.strip().lower()
    sheet_name = BILLING_SHEETS.get(key)
    if not sheet_name:
        raise ValueError(
            f"Unknown warehouse '{warehouse}'. Must be one of: "
            + ", ".join(sorted(BILLING_SHEETS.keys()))
        )
    return sheet_name


def _calc_totals(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate old-format totals (p1/p2) in-place.
    Returns the same dict.
    """
    for prefix, sum_fields, total_key, with_key, pen_key in [
        ("p1", _SUM_FIELDS_P1, "p1_total_without_penalties",
         "p1_total_with_penalties", "p1_penalties"),
        ("p2", _SUM_FIELDS_P2, "p2_total_without_penalties",
         "p2_total_with_penalties", "p2_penalties"),
    ]:
        total = sum(safe_float(row_dict.get(f, 0)) for f in sum_fields)
        penalties = safe_float(row_dict.get(pen_key, 0))
        row_dict[total_key] = round(total, 2)
        row_dict[with_key] = round(total - penalties, 2)
    return row_dict


# Fixed VAT rate for billing calculations (20% as per Russian tax law)
BILLING_VAT_RATE = 0.20


def _calc_billing_totals_v2(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate new-format billing totals.

    input_mode controls VAT handling:
      "Новый (с НДС)" (default) – entered values are WITH VAT; auto-calc VAT breakdown (20% rate)
      "Новый (без НДС)"          – entered values are WITHOUT VAT; vat=0, total_with_vat=total_without_vat
      "Старый (p1/p2)"           – preserve existing without_vat/vat breakdown; just sum totals

    Backward-compat aliases ("с НДС", "без НДС") are also accepted.

    Totals (per problem spec):
      total_without_vat = sum(without_vat for all services) - penalties
      total_vat         = sum(vat for all services)
      total_with_vat    = total_without_vat + total_vat

    Returns the same dict (modified in-place).
    """
    input_mode_raw = str(row_dict.get("input_mode") or INPUT_MODE_WITH_VAT).strip()
    input_mode_lower = input_mode_raw.lower()
    services = ["shipments", "storage", "returns_pickup", "additional_services"]

    # Resolve to canonical mode using aliases for backward compat
    if input_mode_lower in _INPUT_MODE_WITHOUT_VAT_ALIASES_LOWER or input_mode_lower == INPUT_MODE_WITHOUT_VAT.lower():
        canonical_mode = INPUT_MODE_WITHOUT_VAT
    elif input_mode_lower == _INPUT_MODE_OLD_ALIAS_LOWER:
        canonical_mode = INPUT_MODE_OLD
    else:
        # Default: "Новый (с НДС)" — also covers legacy "с НДС"
        canonical_mode = INPUT_MODE_WITH_VAT

    if canonical_mode == INPUT_MODE_OLD:
        # "Старый (p1/p2)": use old-style p1/p2 calculation via _calc_totals.
        # For rows stored in new-format sheets with this mode, just calculate
        # totals from already-broken-down values without re-splitting VAT.
        penalties = safe_float(row_dict.get("penalties", 0))
        total_without_vat = round(
            sum(safe_float(row_dict.get(f"{svc}_without_vat", 0)) for svc in services)
            - penalties,
            2,
        )
        total_vat = round(
            sum(safe_float(row_dict.get(f"{svc}_vat", 0)) for svc in services),
            2,
        )
        total_with_vat = round(total_without_vat + total_vat, 2)
        row_dict["total_without_vat"] = total_without_vat
        row_dict["total_vat"] = total_vat
        row_dict["total_with_vat"] = total_with_vat
        return row_dict

    if canonical_mode == INPUT_MODE_WITHOUT_VAT:
        # Values are already without VAT; no VAT is added.
        # We store the same value in both *_with_vat and *_without_vat fields
        # so that downstream code reading *_without_vat gets the correct amount.
        for svc in services:
            without_vat = safe_float(row_dict.get(f"{svc}_with_vat", 0))
            row_dict[f"{svc}_without_vat"] = without_vat
            row_dict[f"{svc}_vat"] = 0.0
            # Overwrite *_with_vat to equal *_without_vat (no VAT applied)
            row_dict[f"{svc}_with_vat"] = without_vat
    else:
        # Default: "с НДС" — values entered with VAT, split at 20%
        for svc in services:
            with_vat = safe_float(row_dict.get(f"{svc}_with_vat", 0))
            without_vat = round(with_vat / (1 + BILLING_VAT_RATE), 2)
            vat_amount = round(with_vat - without_vat, 2)
            row_dict[f"{svc}_without_vat"] = without_vat
            row_dict[f"{svc}_vat"] = vat_amount

    penalties = safe_float(row_dict.get("penalties", 0))

    total_without_vat = round(
        sum(safe_float(row_dict.get(f"{svc}_without_vat", 0)) for svc in services)
        - penalties,
        2,
    )
    total_vat = round(
        sum(safe_float(row_dict.get(f"{svc}_vat", 0)) for svc in services),
        2,
    )
    total_with_vat = round(total_without_vat + total_vat, 2)

    row_dict["total_without_vat"] = total_without_vat
    row_dict["total_vat"] = total_vat
    row_dict["total_with_vat"] = total_with_vat

    return row_dict


def _ensure_headers(ws) -> None:
    """Write the canonical header row if the sheet is empty (uses old format for compat)."""
    try:
        existing = ws.row_values(1)
        if not any(c.strip() for c in existing):
            ws.append_row(BILLING_HEADERS, value_input_option="USER_ENTERED")
            logger.info("Created billing header row in '%s'.", ws.title)
    except Exception as exc:
        logger.warning("Could not ensure billing headers in '%s': %s", ws.title, exc)


def _row_to_dict(header_map: Dict[str, int], row: List[str]) -> Dict[str, Any]:
    """Convert a sheet row to a dict keyed by header names."""
    result: Dict[str, Any] = {}
    for col_name, idx in header_map.items():
        val = row[idx] if idx < len(row) else ""
        result[col_name] = val
    return result


def _dict_to_row(header_map: Dict[str, int], data: Dict[str, Any]) -> List:
    """Convert a data dict to a list aligned with *header_map*."""
    max_idx = max(header_map.values(), default=0)
    row: List = [""] * (max_idx + 1)
    for col_name, idx in header_map.items():
        val = data.get(col_name, "")
        row[idx] = "" if val is None else str(val)
    return row


def _get_client_col(header_map: Dict[str, int]) -> Optional[int]:
    """Return the column index for the client identifier (new: 'client', old: 'client_name')."""
    return header_map.get("client") if "client" in header_map else header_map.get("client_name")


def _get_client_key(header_map: Dict[str, int]) -> str:
    """Return the column name used for client identifier."""
    return "client" if "client" in header_map else "client_name"


def _find_row_by_client_period(
    ws, client_name: str, period: str, header_map: Dict[str, int],
    month: str = "",
) -> Optional[int]:
    """
    Return the 1-based row index for the row whose client + month + period columns match.

    When the sheet has a separate 'month' column (new structure), both month and
    period are matched individually.  When there is no 'month' column the combined
    period value (e.g. "2024-01-p1") is matched against the 'period' column as
    before, preserving backward compatibility.

    Falls back to client-only match if no period/month columns exist.
    Returns None if not found.
    """
    client_col_idx = _get_client_col(header_map)
    if client_col_idx is None:
        return None

    month_col_idx = header_map.get("month")
    period_col_idx = header_map.get("period")

    all_rows = ws.get_all_values()
    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        row_client = row[client_col_idx].strip() if client_col_idx < len(row) else ""
        if row_client != client_name.strip():
            continue

        if month_col_idx is not None:
            # New structure: separate month and period columns
            if month:
                row_month = row[month_col_idx].strip() if month_col_idx < len(row) else ""
                if row_month != month.strip():
                    continue
            if period and period_col_idx is not None:
                row_period = row[period_col_idx].strip() if period_col_idx < len(row) else ""
                if row_period != period.strip():
                    continue
        elif period and period_col_idx is not None:
            # Legacy structure: period column stores combined "YYYY-MM-p1" value
            row_period = row[period_col_idx].strip() if period_col_idx < len(row) else ""
            if row_period != period.strip():
                continue

        return i + 1  # 1-based row
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_billing_entry(
    warehouse: str,
    client: str,
    month: Optional[str] = None,
    period: Optional[str] = None,
) -> Optional[dict]:
    """
    Find a billing entry by warehouse + client + optional month + optional period.

    month:  YYYY-MM  (e.g. "2024-01")
    period: "p1", "p2", or None for full-month entries

    For new-format sheets with a separate 'month' column:
      - month and period are matched individually against their respective columns.

    For new-format sheets without a 'month' column (legacy combined period):
      - If period given: match period column against "{month}-{period}" (e.g. "2024-01-p1")
      - If only month given: accept entries whose period column equals month or starts with
        "{month}-"

    For old-format sheets, only client matching is performed (p1/p2 live as column groups).

    Returns the matching row dict or None if not found.
    """
    entries = get_billing_entries(warehouse)
    if not entries:
        return None

    new_fmt = "client" in (entries[0] if entries else {})
    client_key = "client" if new_fmt else "client_name"
    has_month_col = new_fmt and "month" in (entries[0] if entries else {})

    for entry in entries:
        entry_client = entry.get(client_key, "").strip()
        if entry_client.lower() != client.strip().lower():
            continue

        if not new_fmt:
            # Old format: just match by client
            return entry

        # New format: optionally filter by month + period
        if month:
            if has_month_col:
                # Separate month column
                entry_month = entry.get("month", "").strip()
                if entry_month != month.strip():
                    continue
                if period:
                    entry_period = entry.get("period", "").strip()
                    if entry_period != period.strip():
                        continue
            else:
                # Legacy: combined period column stores "YYYY-MM" or "YYYY-MM-p1"
                entry_period = entry.get("period", "").strip()
                if period:
                    expected = f"{month}-{period}"
                    if entry_period != expected:
                        continue
                else:
                    if entry_period != month and not entry_period.startswith(f"{month}-"):
                        continue

        return entry

    return None

def get_billing_entries(warehouse: str) -> List[dict]:
    """Return all billing rows for the given warehouse."""
    sheet_name = _resolve_sheet_name(warehouse)
    try:
        ws = get_worksheet(sheet_name)
    except SheetNotFoundError:
        logger.warning("Billing sheet '%s' not found; returning empty list.", sheet_name)
        return []

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    all_rows = ws.get_all_values()
    new_fmt = _is_new_format(header_map)
    entries: List[dict] = []
    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        if not any(c.strip() for c in row):
            continue  # skip empty rows
        entry = _row_to_dict(header_map, row)
        if new_fmt:
            entry = _calc_billing_totals_v2(entry)
        else:
            entry = _calc_totals(entry)
        entries.append(entry)
    return entries


def get_billing_entry(warehouse: str, client_name: str) -> Optional[dict]:
    """Return the billing row for a specific client in the given warehouse."""
    entries = get_billing_entries(warehouse)
    client_key = "client_name"
    if entries and "client" in entries[0]:
        client_key = "client"
    for e in entries:
        if e.get(client_key, "").strip() == client_name.strip():
            return e
    return None


def upsert_billing_entry(
    warehouse: str,
    entry_data: Dict[str, Any],
    user: str = "",
    role: str = "",
) -> dict:
    """
    Create or update a billing row for the client in *entry_data* for *warehouse*.

    Supports both old format (client_name, p1_*/p2_* fields) and new format
    (client, shipments_with_vat, etc.).

    Auto-calculated totals are computed before writing.
    Journal entry is appended after a successful write.

    Returns the final row dict (with calculated totals).
    """
    sheet_name = _resolve_sheet_name(warehouse)
    try:
        ws = get_worksheet(sheet_name)
    except SheetNotFoundError as exc:
        raise SheetsError(f"Billing sheet '{sheet_name}' not found") from exc

    _ensure_headers(ws)
    header_map = get_header_map(ws)
    new_fmt = _is_new_format(header_map)

    # Determine client name from entry_data (support both 'client' and 'client_name')
    client_name = str(
        entry_data.get("client") or entry_data.get("client_name", "")
    ).strip()
    if not client_name:
        raise ValueError("client (or client_name) is required")

    # Normalise client key to match the sheet's column
    client_key = _get_client_key(header_map)

    if new_fmt:
        # Strip calculated fields; let them be recomputed
        cleaned: Dict[str, Any] = {
            k: v for k, v in entry_data.items()
            if k not in _CALC_FIELDS_V2
        }
        # Ensure the client key is correct for this format
        if "client" not in cleaned and "client_name" in cleaned:
            cleaned["client"] = cleaned.pop("client_name")
        elif "client_name" not in cleaned and "client" in cleaned:
            pass  # already correct
        _calc_billing_totals_v2(cleaned)
    else:
        # Old format: strip old calc fields
        cleaned = {
            k: v for k, v in entry_data.items()
            if k not in _CALC_FIELDS_OLD
        }
        # Ensure client_name key
        if "client_name" not in cleaned and "client" in cleaned:
            cleaned["client_name"] = cleaned.pop("client")
        _calc_totals(cleaned)

    with _lock:
        period_val = str(entry_data.get("period") or "").strip()
        month_val = str(entry_data.get("month") or "").strip()
        has_month_col = "month" in header_map
        if new_fmt:
            if has_month_col:
                row_num = _find_row_by_client_period(
                    ws, client_name, period_val, header_map, month=month_val
                )
            elif period_val:
                row_num = _find_row_by_client_period(
                    ws, client_name, period_val, header_map
                )
            else:
                row_num = _find_row_by_client_period(ws, client_name, "", header_map)
        else:
            row_num = _find_row_by_client_period(ws, client_name, "", header_map)
        row_data = _dict_to_row(header_map, cleaned)

        if row_num is None:
            ws.append_row(row_data, value_input_option="USER_ENTERED")
            action = "create_billing_entry"
        else:
            last_col_letter = _col_letter(len(row_data) - 1)
            ws.update(
                f"A{row_num}:{last_col_letter}{row_num}",
                [row_data],
                value_input_option="USER_ENTERED",
            )
            action = "update_billing_entry"

    append_journal_entry(
        telegram_user_id=user,
        full_name=user,
        user_role=role,
        action=action,
        deal_id=client_name,
        payload_summary=f"warehouse={warehouse} client={client_name}",
    )

    return cleaned


def _col_letter(col_index: int) -> str:
    """Convert a 0-based column index to a spreadsheet column letter."""
    result = ""
    n = col_index + 1
    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result
