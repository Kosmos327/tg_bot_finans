import logging
import threading
from datetime import datetime
from typing import Any, List, Optional

import gspread
from google.oauth2.service_account import Credentials

from config.config import settings

logger = logging.getLogger(__name__)

# Lock to prevent race conditions in sequential deal ID generation
_deal_id_lock = threading.Lock()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

SHEET_DEALS = "Учёт сделок"
SHEET_SETTINGS = "Настройки"
SHEET_JOURNAL = "Журнал действий"

# Row 1 is header in "Учёт сделок"
DEALS_HEADER_ROW = 1

# Column index mapping (1-based) for "Учёт сделок"
COL_DEAL_ID = 1        # A
COL_STATUS = 2         # B
COL_DIRECTION = 3      # C
COL_CLIENT = 4         # D
COL_MANAGER = 5        # E
COL_CHARGED_VAT = 6    # F
COL_VAT_TYPE = 7       # G
COL_PAID = 8           # H
COL_START_DATE = 9     # I
COL_END_DATE = 10      # J
COL_ACT_DATE = 11      # K
COL_VAR_EXP1 = 12      # L
COL_VAR_EXP2 = 13      # M
COL_BONUS_PCT = 14     # N
COL_BONUS_PAID = 15    # O
COL_GENERAL_EXP = 16   # P
COL_SOURCE = 17        # Q
COL_DOC_LINK = 18      # R
COL_COMMENT = 19       # S


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        settings.google_service_account_file,
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    client = _get_client()
    return client.open_by_key(settings.google_sheets_spreadsheet_id)


def load_settings() -> dict:
    """Load reference data from 'Настройки' sheet."""
    try:
        spreadsheet = _get_spreadsheet()
        ws = spreadsheet.worksheet(SHEET_SETTINGS)
        all_values = ws.get_all_values()

        settings_data: dict = {
            "statuses": [],
            "business_directions": [],
            "clients": [],
            "managers": [],
            "vat_types": [],
            "sources": [],
        }

        # Parse settings sheet: column A = key, column B+ = values
        for row in all_values:
            if not row or not row[0]:
                continue
            key = row[0].strip().lower()
            values = [v.strip() for v in row[1:] if v.strip()]

            if "статус" in key:
                settings_data["statuses"] = values
            elif "направлени" in key:
                settings_data["business_directions"] = values
            elif "клиент" in key:
                settings_data["clients"] = values
            elif "менеджер" in key:
                settings_data["managers"] = values
            elif "ндс" in key:
                settings_data["vat_types"] = values
            elif "источник" in key:
                settings_data["sources"] = values

        # Provide defaults if sheet is empty or not configured
        if not settings_data["statuses"]:
            settings_data["statuses"] = [
                "Новая", "В работе", "Завершена", "Отменена", "Приостановлена"
            ]
        if not settings_data["business_directions"]:
            settings_data["business_directions"] = [
                "Разработка", "Консалтинг", "Дизайн", "Маркетинг", "Другое"
            ]
        if not settings_data["vat_types"]:
            settings_data["vat_types"] = ["С НДС", "Без НДС"]
        if not settings_data["sources"]:
            settings_data["sources"] = [
                "Рекомендация", "Сайт", "Реклама", "Холодный звонок", "Другое"
            ]

        return settings_data
    except Exception as exc:
        logger.error("Failed to load settings from Google Sheets: %s", exc)
        # Return defaults on error
        return {
            "statuses": ["Новая", "В работе", "Завершена", "Отменена"],
            "business_directions": ["Разработка", "Консалтинг", "Дизайн", "Другое"],
            "clients": [],
            "managers": [],
            "vat_types": ["С НДС", "Без НДС"],
            "sources": ["Рекомендация", "Сайт", "Реклама", "Другое"],
        }


def _get_next_deal_id(ws: gspread.Worksheet) -> str:
    """Generate the next sequential deal ID."""
    all_ids = ws.col_values(COL_DEAL_ID)
    max_num = 0
    for cell_val in all_ids[1:]:  # skip header
        if cell_val and cell_val.startswith("DEAL-"):
            try:
                num = int(cell_val.split("-")[1])
                if num > max_num:
                    max_num = num
            except (IndexError, ValueError):
                pass
    return f"DEAL-{max_num + 1:06d}"


def create_deal(deal_data: dict) -> str:
    """Append a new deal row to 'Учёт сделок'. Returns the new deal_id."""
    with _deal_id_lock:
        spreadsheet = _get_spreadsheet()
        ws = spreadsheet.worksheet(SHEET_DEALS)

        deal_id = _get_next_deal_id(ws)

        row = [
            deal_id,
            deal_data.get("status", ""),
            deal_data.get("business_direction", ""),
            deal_data.get("client", ""),
            deal_data.get("manager", ""),
            deal_data.get("charged_with_vat", ""),
            deal_data.get("vat_type", ""),
            deal_data.get("paid", ""),
            deal_data.get("project_start_date", ""),
            deal_data.get("project_end_date", ""),
            deal_data.get("act_date", ""),
            deal_data.get("variable_expense_1", ""),
            deal_data.get("variable_expense_2", ""),
            deal_data.get("manager_bonus_percent", ""),
            deal_data.get("manager_bonus_paid", ""),
            deal_data.get("general_production_expense", ""),
            deal_data.get("source", ""),
            deal_data.get("document_link", ""),
            deal_data.get("comment", ""),
        ]

        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Created deal %s", deal_id)
        return deal_id


def get_user_deals(manager_name: Optional[str] = None) -> List[dict]:
    """
    Return deals from the sheet. Optionally filter by manager name.
    Returns list of deal dicts.
    """
    spreadsheet = _get_spreadsheet()
    ws = spreadsheet.worksheet(SHEET_DEALS)
    all_rows = ws.get_all_values()

    if len(all_rows) <= 1:
        return []

    deals = []
    for row in all_rows[1:]:  # skip header
        # Pad row to 19 columns
        while len(row) < 19:
            row.append("")

        deal = _row_to_dict(row)
        if not deal["deal_id"]:
            continue
        if manager_name and deal["manager"] != manager_name:
            continue
        deals.append(deal)

    return deals


def get_deal_by_id(deal_id: str) -> Optional[dict]:
    """Return a single deal dict by deal_id, or None if not found."""
    spreadsheet = _get_spreadsheet()
    ws = spreadsheet.worksheet(SHEET_DEALS)
    all_rows = ws.get_all_values()

    for row in all_rows[1:]:
        while len(row) < 19:
            row.append("")
        if row[0] == deal_id:
            return _row_to_dict(row)
    return None


def update_deal(deal_id: str, update_data: dict) -> bool:
    """
    Update an existing deal row. Returns True on success.
    """
    spreadsheet = _get_spreadsheet()
    ws = spreadsheet.worksheet(SHEET_DEALS)
    all_rows = ws.get_all_values()

    for idx, row in enumerate(all_rows):
        if row and row[0] == deal_id:
            row_number = idx + 1  # 1-based
            current = _row_to_dict(row)
            # Merge updates
            merged = {**current, **{k: v for k, v in update_data.items() if v is not None}}
            new_row = _dict_to_row(merged)
            ws.update(
                f"A{row_number}:S{row_number}",
                [new_row],
                value_input_option="USER_ENTERED",
            )
            logger.info("Updated deal %s", deal_id)
            return True
    return False


def append_journal_entry(
    telegram_user_id: str,
    action: str,
    deal_id: str = "",
    payload_summary: str = "",
) -> None:
    """Append a log entry to 'Журнал действий'."""
    try:
        spreadsheet = _get_spreadsheet()
        ws = spreadsheet.worksheet(SHEET_JOURNAL)
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row(
            [timestamp, telegram_user_id, action, deal_id, payload_summary],
            value_input_option="USER_ENTERED",
        )
    except Exception as exc:
        logger.warning("Failed to append journal entry: %s", exc)


def _row_to_dict(row: list) -> dict:
    def _safe(idx: int) -> str:
        try:
            return row[idx]
        except IndexError:
            return ""

    def _safe_float(idx: int) -> Optional[float]:
        val = _safe(idx)
        if val == "":
            return None
        try:
            return float(val)
        except ValueError:
            return None

    return {
        "deal_id": _safe(0),
        "status": _safe(1),
        "business_direction": _safe(2),
        "client": _safe(3),
        "manager": _safe(4),
        "charged_with_vat": _safe_float(5),
        "vat_type": _safe(6),
        "paid": _safe_float(7),
        "project_start_date": _safe(8),
        "project_end_date": _safe(9),
        "act_date": _safe(10),
        "variable_expense_1": _safe_float(11),
        "variable_expense_2": _safe_float(12),
        "manager_bonus_percent": _safe_float(13),
        "manager_bonus_paid": _safe_float(14),
        "general_production_expense": _safe_float(15),
        "source": _safe(16),
        "document_link": _safe(17),
        "comment": _safe(18),
    }


def _dict_to_row(deal: dict) -> list:
    def _v(key: str) -> Any:
        val = deal.get(key, "")
        return val if val is not None else ""

    return [
        _v("deal_id"),
        _v("status"),
        _v("business_direction"),
        _v("client"),
        _v("manager"),
        _v("charged_with_vat"),
        _v("vat_type"),
        _v("paid"),
        _v("project_start_date"),
        _v("project_end_date"),
        _v("act_date"),
        _v("variable_expense_1"),
        _v("variable_expense_2"),
        _v("manager_bonus_percent"),
        _v("manager_bonus_paid"),
        _v("general_production_expense"),
        _v("source"),
        _v("document_link"),
        _v("comment"),
    ]
