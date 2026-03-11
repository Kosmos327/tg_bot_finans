"""
Google Sheets service.

Handles all interactions with the "Финанс.xlsx" Google Spreadsheet
using the gspread library authenticated via a service account.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from config.config import settings

logger = logging.getLogger(__name__)

# OAuth scopes required for read/write access to Sheets
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Sheet names
SHEET_DEALS = "Учёт сделок"
SHEET_SETTINGS = "Настройки"
SHEET_LOG = "Журнал действий"

# Column indices (1-based) for "Учёт сделок"
COL_ID = 1           # A – ID сделки
COL_STATUS = 2       # B – Статус сделки
COL_DIRECTION = 3    # C – Направление бизнеса
COL_CLIENT = 4       # D – Клиент
COL_MANAGER = 5      # E – Менеджер
COL_AMOUNT = 6       # F – Начислено с НДС
COL_VAT = 7          # G – Наличие НДС
COL_PAID = 8         # H – Оплачено
COL_DATE_START = 9   # I – Дата начала проекта
COL_DATE_END = 10    # J – Дата окончания проекта
COL_DATE_ACT = 11    # K – Дата выставления акта
COL_VAR_EXP1 = 12   # L – Переменный расход 1
COL_VAR_EXP2 = 13   # M – Переменный расход 2
COL_BONUS_PCT = 14  # N – Бонус менеджера %
COL_BONUS_PAID = 15 # O – Бонус менеджера выплачено
COL_OVERHEAD = 16   # P – Общепроизводственный расход
COL_SOURCE = 17     # Q – Источник
COL_DOC_LINK = 18   # R – Документ/ссылка
COL_COMMENT = 19    # S – Комментарий


def _get_client() -> gspread.Client:
    """Create an authenticated gspread client using a service account."""
    creds = Credentials.from_service_account_file(
        settings.google_credentials_file, scopes=_SCOPES
    )
    return gspread.authorize(creds)


def _open_sheet(client: gspread.Client, sheet_name: str) -> gspread.Worksheet:
    spreadsheet = client.open(settings.spreadsheet_name)
    return spreadsheet.worksheet(sheet_name)


def _next_deal_id(ws: gspread.Worksheet) -> str:
    """
    Determine the next sequential deal ID by counting existing data rows.
    Returns a string like 'DEAL-000001'.
    """
    all_values = ws.get_all_values()
    # Row 0 is the header; data starts from row 1
    data_rows = len(all_values) - 1 if len(all_values) > 1 else 0
    next_number = data_rows + 1
    return f"DEAL-{next_number:06d}"


def create_deal(deal_data: dict[str, Any]) -> str:
    """
    Append a new deal row to the 'Учёт сделок' sheet and log the action.

    Args:
        deal_data: Dict with deal fields.

    Returns:
        The generated deal ID string.
    """
    client = _get_client()
    ws = _open_sheet(client, SHEET_DEALS)

    deal_id = _next_deal_id(ws)

    row = [""] * 19
    row[COL_ID - 1] = deal_id
    row[COL_STATUS - 1] = deal_data.get("status", "")
    row[COL_DIRECTION - 1] = deal_data.get("business_direction", "")
    row[COL_CLIENT - 1] = deal_data.get("client", "")
    row[COL_MANAGER - 1] = deal_data.get("manager", "")
    row[COL_AMOUNT - 1] = deal_data.get("amount_with_vat", "")
    row[COL_VAT - 1] = deal_data.get("vat_type", "")
    row[COL_PAID - 1] = ""
    row[COL_DATE_START - 1] = deal_data.get("start_date", "")
    row[COL_DATE_END - 1] = deal_data.get("end_date", "")
    row[COL_DATE_ACT - 1] = ""
    row[COL_VAR_EXP1 - 1] = ""
    row[COL_VAR_EXP2 - 1] = ""
    row[COL_BONUS_PCT - 1] = ""
    row[COL_BONUS_PAID - 1] = ""
    row[COL_OVERHEAD - 1] = ""
    row[COL_SOURCE - 1] = deal_data.get("source", "")
    row[COL_DOC_LINK - 1] = deal_data.get("document_link", "")
    row[COL_COMMENT - 1] = deal_data.get("comment", "")

    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info("Deal created: %s", deal_id)

    # Write action log
    _log_action(
        client=client,
        telegram_user_id=deal_data.get("telegram_user_id", ""),
        action="create_deal",
        deal_id=deal_id,
    )

    return deal_id


def get_deals_by_manager(manager_name: str) -> list[dict[str, Any]]:
    """
    Return all deals where the manager column matches `manager_name`.
    """
    client = _get_client()
    ws = _open_sheet(client, SHEET_DEALS)
    all_rows = ws.get_all_values()

    if not all_rows:
        return []

    headers = all_rows[0]
    deals: list[dict[str, Any]] = []

    for row in all_rows[1:]:
        # Pad short rows
        while len(row) < len(headers):
            row.append("")
        row_dict = dict(zip(headers, row))
        if row_dict.get("Менеджер", "") == manager_name:
            deals.append(row_dict)

    return deals


def get_settings() -> dict[str, list[str]]:
    """
    Read reference data from the 'Настройки' sheet.

    Expected layout: each column has a header in row 1 and values below.
    """
    client = _get_client()
    ws = _open_sheet(client, SHEET_SETTINGS)
    all_rows = ws.get_all_values()

    if not all_rows:
        return {}

    headers = all_rows[0]
    result: dict[str, list[str]] = {h: [] for h in headers if h}

    for row in all_rows[1:]:
        for idx, header in enumerate(headers):
            if not header:
                continue
            value = row[idx] if idx < len(row) else ""
            if value:
                result[header].append(value)

    return result


def _log_action(
    client: gspread.Client,
    telegram_user_id: int | str,
    action: str,
    deal_id: str,
) -> None:
    """Append a row to the 'Журнал действий' sheet."""
    try:
        ws = _open_sheet(client, SHEET_LOG)
        ws.append_row(
            [
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                str(telegram_user_id),
                action,
                deal_id,
            ],
            value_input_option="USER_ENTERED",
        )
    except Exception:
        logger.exception("Failed to write action log for deal %s", deal_id)
