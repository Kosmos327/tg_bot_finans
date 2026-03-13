"""
deals_service.py – Header-based CRUD operations for the "Учёт сделок" sheet.

Design principles
-----------------
* All column access uses the header row (read once per request), never
  hard-coded positional indexes.
* Deal IDs are generated safely under a threading lock.
* Numeric and date fields are normalised on read and write.
* Filtering is done in Python after a full sheet read (avoids per-row API
  calls; acceptable for typical sheet sizes).

Public API
----------
create_deal(deal_data, telegram_user_id, user_role, full_name) → str (deal_id)
update_deal(deal_id, update_data, telegram_user_id, user_role, full_name) → bool
get_deal_by_id(deal_id) → dict | None
get_all_deals() → List[dict]
get_deals_by_user(manager_name) → List[dict]
get_deals_filtered(filters) → List[dict]

Column map (Russian header → internal field name)
-------------------------------------------------
See DEALS_COLUMN_MAP below.
"""

import logging
import re
import threading
from datetime import date, datetime
from typing import Dict, List, Optional, Union

from backend.services.sheets_service import (
    MissingHeaderError,
    SheetsError,
    SheetNotFoundError,
    SHEET_DEALS,
    get_worksheet,
    get_header_map,
    get_required_column,
    row_to_dict,
    dict_to_row,
    safe_float,
    safe_optional_float,
)
from backend.services.journal_service import append_journal_entry
from backend.services.permissions import filter_update_payload

logger = logging.getLogger(__name__)

# Thread-safe lock for deal ID generation
_deal_id_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Column mapping: Russian sheet header → internal Python field name
# ---------------------------------------------------------------------------

DEALS_COLUMN_MAP: Dict[str, str] = {
    "ID сделки": "deal_id",
    "Статус сделки": "status",
    "Направление бизнеса": "business_direction",
    "Клиент": "client",
    "Менеджер": "manager",
    "Начислено с НДС": "charged_with_vat",
    "Наличие НДС": "vat_type",
    "Оплачено": "paid",
    "Дата начала проекта": "project_start_date",
    "Дата окончания проекта": "project_end_date",
    "Дата выставления акта": "act_date",
    # Legacy expense fields
    "Переменный расход 1": "variable_expense_1",
    "Переменный расход 2": "variable_expense_2",
    "Бонус менеджера %": "manager_bonus_percent",
    "Бонус менеджера выплачено": "manager_bonus_paid",
    "Общепроизводственный расход": "general_production_expense",
    "Источник": "source",
    "Документ/ссылка": "document_link",
    "Комментарий": "comment",
    # New VAT breakdown columns
    "Ставка НДС": "vat_rate",
    "Сумма НДС": "vat_amount",
    "Сумма без НДС": "amount_without_vat",
    # New variable expense 1 VAT breakdown
    "Переменный расход 1 с НДС": "variable_expense_1_with_vat",
    "НДС перем. расход 1": "variable_expense_1_vat",
    "Переменный расход 1 без НДС": "variable_expense_1_without_vat",
    # New variable expense 2 VAT breakdown
    "Переменный расход 2 с НДС": "variable_expense_2_with_vat",
    "НДС перем. расход 2": "variable_expense_2_vat",
    "Переменный расход 2 без НДС": "variable_expense_2_without_vat",
    # New production expense VAT breakdown
    "Производств. расход с НДС": "production_expense_with_vat",
    "НДС производств. расход": "production_expense_vat",
    "Производств. расход без НДС": "production_expense_without_vat",
    # Calculated profitability columns
    "Бонус менеджера сумма": "manager_bonus_amount",
    "Маржинальный доход": "marginal_income",
    "Валовая прибыль": "gross_profit",
    # Metadata
    "Дата создания": "created_at",
}

# Reverse map: internal field name → Russian sheet header
_FIELD_TO_HEADER: Dict[str, str] = {v: k for k, v in DEALS_COLUMN_MAP.items()}

# Ordered list of all sheet headers (for appending full rows)
ORDERED_SHEET_HEADERS: List[str] = list(DEALS_COLUMN_MAP.keys())

# Fields that should be stored/returned as numbers
_NUMERIC_FIELDS = frozenset(
    {
        "charged_with_vat",
        "paid",
        "variable_expense_1",
        "variable_expense_2",
        "manager_bonus_percent",
        "manager_bonus_paid",
        "general_production_expense",
        # New VAT fields
        "vat_rate",
        "vat_amount",
        "amount_without_vat",
        "variable_expense_1_with_vat",
        "variable_expense_1_vat",
        "variable_expense_1_without_vat",
        "variable_expense_2_with_vat",
        "variable_expense_2_vat",
        "variable_expense_2_without_vat",
        "production_expense_with_vat",
        "production_expense_vat",
        "production_expense_without_vat",
        "manager_bonus_amount",
        "marginal_income",
        "gross_profit",
    }
)

# Fields that should be stored as YYYY-MM-DD dates
_DATE_FIELDS = frozenset(
    {"project_start_date", "project_end_date", "act_date"}
)

# Fields that are auto-calculated (computed from other fields; never forced from outside)
_CALC_FIELDS = frozenset(
    {
        "vat_amount",
        "amount_without_vat",
        "variable_expense_1_vat",
        "variable_expense_1_without_vat",
        "variable_expense_2_vat",
        "variable_expense_2_without_vat",
        "production_expense_vat",
        "production_expense_without_vat",
        "marginal_income",
        "gross_profit",
        "manager_bonus_amount",
    }
)

# Required fields for deal creation
_REQUIRED_CREATE_FIELDS = frozenset(
    {"status", "business_direction", "client", "manager", "charged_with_vat", "vat_type",
     "project_start_date", "project_end_date"}
)

# ---------------------------------------------------------------------------
# Deal-ID helpers (pure functions)
# ---------------------------------------------------------------------------

_DEAL_ID_PATTERN = re.compile(r"^DEAL-(\d+)$")


def parse_deal_id_number(deal_id: str) -> Optional[int]:
    """
    Extract the numeric suffix from a DEAL-XXXXXX string.
    Returns None for malformed IDs (safe to call on arbitrary strings).
    """
    if not isinstance(deal_id, str):
        return None
    m = _DEAL_ID_PATTERN.match(deal_id.strip())
    if m:
        return int(m.group(1))
    return None


def format_deal_id(number: int) -> str:
    """Format an integer as DEAL-000001."""
    return f"DEAL-{number:06d}"


def generate_next_deal_id(existing_ids: List[str]) -> str:
    """
    Given a list of existing deal ID strings, return the next sequential ID.
    Malformed IDs are silently ignored.

    >>> generate_next_deal_id(["DEAL-000001", "DEAL-000003", "bad"])
    'DEAL-000004'
    >>> generate_next_deal_id([])
    'DEAL-000001'
    """
    max_num = 0
    for raw_id in existing_ids:
        num = parse_deal_id_number(raw_id)
        if num is not None and num > max_num:
            max_num = num
    return format_deal_id(max_num + 1)


# ---------------------------------------------------------------------------
# Date normalisation (pure function)
# ---------------------------------------------------------------------------

_DATE_INPUT_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
]


def normalise_date(value: str) -> str:
    """
    Attempt to parse *value* as a date and return it in YYYY-MM-DD format.
    Returns the original string on failure (non-destructive).
    """
    if not value or not value.strip():
        return ""
    stripped = value.strip()
    for fmt in _DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(stripped, fmt).date().isoformat()
        except ValueError:
            continue
    return stripped


# ---------------------------------------------------------------------------
# Row conversion helpers
# ---------------------------------------------------------------------------


def _header_map_to_field_map(header_map: Dict[str, int]) -> Dict[str, int]:
    """
    Translate a raw header map (Russian column names → index) into a
    field map (internal Python field names → index).
    Only columns present in DEALS_COLUMN_MAP are included.
    """
    return {
        DEALS_COLUMN_MAP[ru_name]: idx
        for ru_name, idx in header_map.items()
        if ru_name in DEALS_COLUMN_MAP
    }


def _normalise_deal(raw: Dict[str, str]) -> dict:
    """
    Convert a raw dict (keyed by internal field names, values are strings) to
    a properly typed deal dict.
    """
    result = {}
    for field, value in raw.items():
        if field in _NUMERIC_FIELDS:
            result[field] = safe_optional_float(value)
        elif field in _DATE_FIELDS:
            result[field] = value.strip() if value.strip() else None
        else:
            result[field] = value.strip()
    return result


def _deal_row_to_dict(field_map: Dict[str, int], row: List[str]) -> dict:
    """Convert a sheet data row to a normalised deal dict."""
    raw = row_to_dict(field_map, row)  # type: ignore[arg-type]
    return _normalise_deal(raw)


def _deal_dict_to_row(
    header_map: Dict[str, int],
    deal: dict,
) -> List:
    """
    Convert a deal dict (field names → values) to a sheet row using the
    Russian header map.  Each internal field name is first translated to its
    Russian column header before looking it up in header_map.
    """
    # Translate field names → Russian headers
    ru_payload = {
        _FIELD_TO_HEADER[k]: v
        for k, v in deal.items()
        if k in _FIELD_TO_HEADER
    }
    return dict_to_row(header_map, ru_payload, ORDERED_SHEET_HEADERS)


def _validate_required_fields(deal_data: dict) -> None:
    """Raise ValueError if any required field is missing or empty."""
    missing = []
    for field in _REQUIRED_CREATE_FIELDS:
        val = deal_data.get(field)
        if val is None or str(val).strip() == "":
            missing.append(field)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")


def _calculate_deal_financials(payload: dict) -> dict:
    """
    Compute VAT-derived and profitability fields from *payload* in-place.

    Calculations performed (only when required inputs are present):
      amount_without_vat      = charged_with_vat / (1 + vat_rate)
      vat_amount              = charged_with_vat - amount_without_vat

      variable_expense_N_without_vat = variable_expense_N_with_vat / (1 + vat_rate)
      variable_expense_N_vat         = variable_expense_N_with_vat - without_vat

      production_expense_without_vat = production_expense_with_vat / (1 + vat_rate)
      production_expense_vat         = production_expense_with_vat - without_vat

      marginal_income  = amount_without_vat
                        - variable_expense_1_without_vat
                        - variable_expense_2_without_vat
      gross_profit     = marginal_income - production_expense_without_vat
      manager_bonus_amount = gross_profit * manager_bonus_percent / 100

    Returns the same dict (modified in-place).
    """
    charged = safe_float(str(payload.get("charged_with_vat", 0)))
    vat_rate = safe_float(str(payload.get("vat_rate", 0)))

    # VAT breakdown on charged amount.
    # A falsy (0 or absent) vat_rate means no VAT applies → skip breakdown.
    # Only compute when there is a positive VAT rate and a charged amount.
    if charged and vat_rate:
        amount_without_vat = round(charged / (1 + vat_rate), 2)
        payload["amount_without_vat"] = amount_without_vat
        payload["vat_amount"] = round(charged - amount_without_vat, 2)

    # Helper: compute without_vat / vat for a with_vat amount
    def _split_vat(with_vat_val: float) -> tuple:
        if with_vat_val and vat_rate:
            without = round(with_vat_val / (1 + vat_rate), 2)
            vat_a = round(with_vat_val - without, 2)
            return without, vat_a
        return None, None

    # Variable expense 1
    ve1_with = safe_float(str(payload.get("variable_expense_1_with_vat", 0)))
    ve1_without, ve1_vat = _split_vat(ve1_with)
    if ve1_without is not None:
        payload["variable_expense_1_without_vat"] = ve1_without
        payload["variable_expense_1_vat"] = ve1_vat

    # Variable expense 2
    ve2_with = safe_float(str(payload.get("variable_expense_2_with_vat", 0)))
    ve2_without, ve2_vat = _split_vat(ve2_with)
    if ve2_without is not None:
        payload["variable_expense_2_without_vat"] = ve2_without
        payload["variable_expense_2_vat"] = ve2_vat

    # Production expense
    pe_with = safe_float(str(payload.get("production_expense_with_vat", 0)))
    pe_without, pe_vat = _split_vat(pe_with)
    if pe_without is not None:
        payload["production_expense_without_vat"] = pe_without
        payload["production_expense_vat"] = pe_vat

    # Marginal income: needs amount_without_vat to be populated
    amount_no_vat = safe_float(str(payload.get("amount_without_vat", 0)))
    if amount_no_vat:
        ve1_no = safe_float(str(payload.get("variable_expense_1_without_vat", 0)))
        ve2_no = safe_float(str(payload.get("variable_expense_2_without_vat", 0)))
        marginal_income = round(amount_no_vat - ve1_no - ve2_no, 2)
        payload["marginal_income"] = marginal_income

        # Gross profit
        pe_no = safe_float(str(payload.get("production_expense_without_vat", 0)))
        gross_profit = round(marginal_income - pe_no, 2)
        payload["gross_profit"] = gross_profit

        # Manager bonus amount
        bonus_pct = safe_float(str(payload.get("manager_bonus_percent", 0)))
        if bonus_pct:
            payload["manager_bonus_amount"] = round(gross_profit * bonus_pct / 100, 2)

    return payload


def _prepare_deal_payload(deal_data: dict, deal_id: str) -> dict:
    """
    Build a complete deal payload dict with normalised values.
    All optional numeric fields default to 0.0 if not provided;
    optional string fields default to "".
    Auto-calculated fields (VAT breakdown, profitability) are computed here.
    """
    payload = {
        "deal_id": deal_id,
        "status": str(deal_data.get("status", "")).strip(),
        "business_direction": str(deal_data.get("business_direction", "")).strip(),
        "client": str(deal_data.get("client", "")).strip(),
        "manager": str(deal_data.get("manager", "")).strip(),
        "charged_with_vat": safe_float(str(deal_data.get("charged_with_vat", 0))),
        "vat_type": str(deal_data.get("vat_type", "")).strip(),
        "paid": safe_float(str(deal_data.get("paid", 0))),
        "project_start_date": normalise_date(str(deal_data.get("project_start_date", ""))),
        "project_end_date": normalise_date(str(deal_data.get("project_end_date", ""))),
        "act_date": normalise_date(str(deal_data.get("act_date", ""))),
        # Legacy expense fields
        "variable_expense_1": safe_float(str(deal_data.get("variable_expense_1", 0))),
        "variable_expense_2": safe_float(str(deal_data.get("variable_expense_2", 0))),
        "manager_bonus_percent": safe_float(str(deal_data.get("manager_bonus_percent", 0))),
        "manager_bonus_paid": safe_float(str(deal_data.get("manager_bonus_paid", 0))),
        "general_production_expense": safe_float(
            str(deal_data.get("general_production_expense", 0))
        ),
        "source": str(deal_data.get("source", "")).strip(),
        "document_link": str(deal_data.get("document_link", "")).strip(),
        "comment": str(deal_data.get("comment", "")).strip(),
        # New VAT and expense fields (from input, then overridden by auto-calc below)
        "vat_rate": safe_float(str(deal_data.get("vat_rate", 0))),
        "variable_expense_1_with_vat": safe_float(
            str(deal_data.get("variable_expense_1_with_vat", 0))
        ),
        "variable_expense_2_with_vat": safe_float(
            str(deal_data.get("variable_expense_2_with_vat", 0))
        ),
        "production_expense_with_vat": safe_float(
            str(deal_data.get("production_expense_with_vat", 0))
        ),
        # created_at timestamp
        "created_at": str(deal_data.get("created_at", "")).strip()
            or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    # Apply auto-calculations for VAT and profitability
    _calculate_deal_financials(payload)
    return payload


# ---------------------------------------------------------------------------
# Public CRUD functions
# ---------------------------------------------------------------------------


def create_deal(
    deal_data: dict,
    telegram_user_id: str = "",
    user_role: str = "",
    full_name: str = "",
) -> str:
    """
    Validate *deal_data*, generate a new deal ID, append a row to the sheet,
    and write a journal entry.

    Role-based field filtering is applied before persisting: fields outside
    the caller's editable set are silently dropped (accounting fields for a
    manager, etc.).  For the "manager" role the ``manager`` field is always
    overwritten with the caller's own ``full_name`` to prevent impersonation.

    Returns the new deal_id string.
    Raises ValueError for validation errors, SheetsError for sheet failures.
    """
    # Apply role-based field filtering so callers cannot set forbidden fields
    deal_data = filter_update_payload(user_role, deal_data) if user_role else dict(deal_data)

    # Managers must be attributed to themselves
    if user_role == "manager" and full_name:
        deal_data["manager"] = full_name

    _validate_required_fields(deal_data)

    with _deal_id_lock:
        try:
            ws = get_worksheet(SHEET_DEALS)
            header_map = get_header_map(ws)

            # Determine the column index for "ID сделки" to read existing IDs
            deal_id_col = _get_deal_id_column_index(header_map)
            all_rows = ws.get_all_values()
            existing_ids = [
                row[deal_id_col]
                for row in all_rows[1:]  # skip header
                if len(row) > deal_id_col
            ]

            deal_id = generate_next_deal_id(existing_ids)
            payload = _prepare_deal_payload(deal_data, deal_id)
            new_row = _deal_dict_to_row(header_map, payload)

            ws.append_row(new_row, value_input_option="USER_ENTERED")
            logger.info("Created deal %s by user %s", deal_id, telegram_user_id)
        except (SheetNotFoundError, MissingHeaderError, SheetsError):
            raise
        except ValueError:
            raise
        except Exception as exc:
            raise SheetsError(f"Failed to create deal: {exc}") from exc

    # Journal entry (outside lock – failure here must not roll back the deal)
    append_journal_entry(
        telegram_user_id=telegram_user_id,
        full_name=full_name,
        user_role=user_role,
        action="create_deal",
        deal_id=deal_id,
        payload_summary=(
            f"client={deal_data.get('client', '')}, "
            f"status={deal_data.get('status', '')}, "
            f"charged_with_vat={deal_data.get('charged_with_vat', '')}"
        ),
    )
    return deal_id


def update_deal(
    deal_id: str,
    update_data: dict,
    telegram_user_id: str = "",
    user_role: str = "",
    full_name: str = "",
) -> bool:
    """
    Update an existing deal row, enforcing role-based field permissions.

    Only fields allowed for *user_role* (see permissions.py) will be written;
    any forbidden fields are silently dropped and a journal entry is written
    for the rejection.

    Returns True if the deal was found and updated, False if not found.
    """
    # Apply role-based field filtering
    permitted_data = filter_update_payload(user_role, update_data)
    rejected_fields = sorted(set(update_data) - set(permitted_data))

    if rejected_fields:
        logger.warning(
            "Role '%s' attempted to edit forbidden fields %s on deal %s",
            user_role,
            rejected_fields,
            deal_id,
        )
        append_journal_entry(
            telegram_user_id=telegram_user_id,
            full_name=full_name,
            user_role=user_role,
            action="forbidden_edit_attempt",
            deal_id=deal_id,
            changed_fields=rejected_fields,
            payload_summary=f"Rejected fields: {rejected_fields}",
        )

    if not permitted_data:
        logger.info(
            "No permitted fields to update for role '%s' on deal %s", user_role, deal_id
        )
        raise ValueError(
            f"No fields in the request are editable by role '{user_role}'. "
            f"Rejected fields: {rejected_fields}"
        )

    try:
        ws = get_worksheet(SHEET_DEALS)
        header_map = get_header_map(ws)
        field_map = _header_map_to_field_map(header_map)
        all_rows = ws.get_all_values()
    except (SheetNotFoundError, SheetsError):
        raise
    except Exception as exc:
        raise SheetsError(f"Failed to access deals sheet: {exc}") from exc

    deal_id_col = _get_deal_id_column_index(header_map)

    for idx, row in enumerate(all_rows):
        if not row or len(row) <= deal_id_col:
            continue
        if row[deal_id_col].strip() != deal_id:
            continue

        # Found the row; merge update into existing data
        row_number = idx + 1  # 1-based for gspread range update
        current = _deal_row_to_dict(field_map, row)

        # Normalise the incoming update values
        normalised_update = {}
        for field, value in permitted_data.items():
            if value is None:
                continue
            if field in _DATE_FIELDS:
                normalised_update[field] = normalise_date(str(value))
            elif field in _NUMERIC_FIELDS:
                normalised_update[field] = safe_float(str(value))
            else:
                normalised_update[field] = str(value).strip()

        merged = {**current, **normalised_update}
        new_row = _deal_dict_to_row(header_map, merged)

        # Determine range based on actual columns used
        last_col_letter = _col_index_to_letter(len(new_row) - 1)
        try:
            ws.update(
                f"A{row_number}:{last_col_letter}{row_number}",
                [new_row],
                value_input_option="USER_ENTERED",
            )
        except Exception as exc:
            raise SheetsError(f"Failed to write update to sheet: {exc}") from exc

        logger.info("Updated deal %s by user %s", deal_id, telegram_user_id)

        append_journal_entry(
            telegram_user_id=telegram_user_id,
            full_name=full_name,
            user_role=user_role,
            action="update_deal",
            deal_id=deal_id,
            changed_fields=sorted(permitted_data.keys()),
            payload_summary=str({k: permitted_data[k] for k in sorted(permitted_data)}),
        )
        return True

    return False  # deal not found


def get_deal_by_id(deal_id: str) -> Optional[dict]:
    """Return a single normalised deal dict, or None if not found."""
    try:
        ws = get_worksheet(SHEET_DEALS)
        header_map = get_header_map(ws)
        field_map = _header_map_to_field_map(header_map)
        deal_id_col = _get_deal_id_column_index(header_map)
        all_rows = ws.get_all_values()
    except (SheetNotFoundError, SheetsError):
        raise
    except Exception as exc:
        raise SheetsError(f"Failed to read deals sheet: {exc}") from exc

    for row in all_rows[1:]:  # skip header
        if len(row) > deal_id_col and row[deal_id_col].strip() == deal_id:
            return _deal_row_to_dict(field_map, row)
    return None


def get_all_deals() -> List[dict]:
    """Return all deals from the sheet as a list of normalised dicts."""
    return _read_all_deal_rows()


def get_deals_by_user(manager_name: str) -> List[dict]:
    """Return deals where the 'manager' field matches *manager_name*."""
    return get_deals_filtered({"manager": manager_name})


def get_deals_filtered(filters: dict) -> List[dict]:
    """
    Return deals matching all non-None values in *filters*.

    Supported filter keys
    ---------------------
    manager           – exact match on deal['manager']
    client            – exact match on deal['client']
    status            – exact match on deal['status']
    business_direction– exact match on deal['business_direction']
    month             – "YYYY-MM" match on project_start_date
    paid              – True → paid > 0; False → paid == 0 or None
    """
    deals = _read_all_deal_rows()
    result = []
    for deal in deals:
        if _matches_filters(deal, filters):
            result.append(deal)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_all_deal_rows() -> List[dict]:
    """Read and normalise all data rows from the deals sheet."""
    try:
        ws = get_worksheet(SHEET_DEALS)
        header_map = get_header_map(ws)
        field_map = _header_map_to_field_map(header_map)
        deal_id_col = _get_deal_id_column_index(header_map)
        all_rows = ws.get_all_values()
    except (SheetNotFoundError, SheetsError):
        raise
    except Exception as exc:
        raise SheetsError(f"Failed to read deals sheet: {exc}") from exc

    deals = []
    for row in all_rows[1:]:  # skip header row
        if len(row) <= deal_id_col or not row[deal_id_col].strip():
            continue
        deal = _deal_row_to_dict(field_map, row)
        if deal.get("deal_id"):
            deals.append(deal)
    return deals


def _get_deal_id_column_index(header_map: Dict[str, int]) -> int:
    """Return the 0-based index of the 'ID сделки' column."""
    return get_required_column(header_map, "ID сделки")


def _matches_filters(deal: dict, filters: dict) -> bool:
    """Return True if *deal* satisfies all criteria in *filters*."""
    for key, value in filters.items():
        if value is None:
            continue

        if key == "month":
            # Match YYYY-MM against project_start_date
            start = deal.get("project_start_date") or ""
            if not start.startswith(str(value)):
                return False

        elif key == "paid":
            paid_val = deal.get("paid") or 0.0
            if value is True and not (paid_val and paid_val > 0):
                return False
            if value is False and (paid_val and paid_val > 0):
                return False

        else:
            # Exact string match
            deal_val = str(deal.get(key, "")).strip()
            filter_val = str(value).strip()
            if deal_val != filter_val:
                return False

    return True


def _col_index_to_letter(index: int) -> str:
    """Convert a 0-based column index to a spreadsheet column letter (A, B, … Z, AA …)."""
    result = ""
    n = index + 1  # 1-based
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result
