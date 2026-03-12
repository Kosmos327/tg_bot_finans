"""
Google Sheets service for tg_bot_finans.

Wraps gspread calls and provides typed accessors for:
  - Учёт сделок  (deals)
  - Настройки    (settings / users / roles)
  - Журнал действий (audit journal)
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials

from backend.config import (
    DEAL_COL_ACT_DATE,
    DEAL_COL_AMOUNT_VAT,
    DEAL_COL_BONUS_PCT,
    DEAL_COL_BONUS_PAID,
    DEAL_COL_CLIENT,
    DEAL_COL_COMMENT,
    DEAL_COL_CREATOR_TG_ID,
    DEAL_COL_DATE_END,
    DEAL_COL_DATE_START,
    DEAL_COL_DIRECTION,
    DEAL_COL_DOCUMENT,
    DEAL_COL_HAS_VAT,
    DEAL_COL_ID,
    DEAL_COL_MANAGER,
    DEAL_COL_PAID,
    DEAL_COL_PROD_EXP,
    DEAL_COL_SOURCE,
    DEAL_COL_STATUS,
    DEAL_COL_VAR_EXP1,
    DEAL_COL_VAR_EXP2,
    DEALS_TOTAL_COLS,
    JOURNAL_COL_ACTION,
    JOURNAL_COL_CHANGED_FIELDS,
    JOURNAL_COL_DEAL_ID,
    JOURNAL_COL_ROLE,
    JOURNAL_COL_SUMMARY,
    JOURNAL_COL_TG_ID,
    JOURNAL_COL_TIMESTAMP,
    SETTINGS_COL_ACTIVE,
    SETTINGS_COL_FULL_NAME,
    SETTINGS_COL_ROLE,
    SETTINGS_COL_TG_ID,
    SHEET_DEALS,
    SHEET_JOURNAL,
    SHEET_SETTINGS,
    SPREADSHEET_ID,
)
from backend.models.schemas import Deal, JournalEntry, SettingsUser

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _col_letter(col_index: int) -> str:
    """Convert a 0-based column index to a spreadsheet column letter (A, B, …, Z, AA, …)."""
    result = ""
    n = col_index + 1
    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _get_client() -> gspread.Client:
    import os
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw_json:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set."
        )
    try:
        service_account_info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON contains invalid JSON."
        ) from exc
    creds = Credentials.from_service_account_info(service_account_info, scopes=_SCOPES)
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    client = _get_client()
    return client.open_by_key(SPREADSHEET_ID)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pad_row(row: List[str], length: int) -> List[str]:
    """Ensure a row has at least `length` elements."""
    return row + [""] * max(0, length - len(row))


def _row_to_deal(row: List[str]) -> Deal:
    row = _pad_row(row, DEALS_TOTAL_COLS)
    return Deal(
        id=row[DEAL_COL_ID],
        status=row[DEAL_COL_STATUS],
        direction=row[DEAL_COL_DIRECTION],
        client=row[DEAL_COL_CLIENT],
        manager=row[DEAL_COL_MANAGER],
        amount_with_vat=row[DEAL_COL_AMOUNT_VAT],
        has_vat=row[DEAL_COL_HAS_VAT],
        paid=row[DEAL_COL_PAID],
        date_start=row[DEAL_COL_DATE_START],
        date_end=row[DEAL_COL_DATE_END],
        act_date=row[DEAL_COL_ACT_DATE],
        var_exp1=row[DEAL_COL_VAR_EXP1],
        var_exp2=row[DEAL_COL_VAR_EXP2],
        bonus_pct=row[DEAL_COL_BONUS_PCT],
        bonus_paid=row[DEAL_COL_BONUS_PAID],
        prod_exp=row[DEAL_COL_PROD_EXP],
        source=row[DEAL_COL_SOURCE],
        document=row[DEAL_COL_DOCUMENT],
        comment=row[DEAL_COL_COMMENT],
        creator_tg_id=row[DEAL_COL_CREATOR_TG_ID] if len(row) > DEAL_COL_CREATOR_TG_ID else "",
    )


def _deal_to_row(deal_data: Dict[str, Any], existing_row: Optional[List[str]] = None) -> List[str]:
    """Convert a dict of deal fields to a spreadsheet row."""
    base = _pad_row(existing_row or [], DEALS_TOTAL_COLS)
    mapping = {
        "status": DEAL_COL_STATUS,
        "direction": DEAL_COL_DIRECTION,
        "client": DEAL_COL_CLIENT,
        "manager": DEAL_COL_MANAGER,
        "amount_with_vat": DEAL_COL_AMOUNT_VAT,
        "has_vat": DEAL_COL_HAS_VAT,
        "paid": DEAL_COL_PAID,
        "date_start": DEAL_COL_DATE_START,
        "date_end": DEAL_COL_DATE_END,
        "act_date": DEAL_COL_ACT_DATE,
        "var_exp1": DEAL_COL_VAR_EXP1,
        "var_exp2": DEAL_COL_VAR_EXP2,
        "bonus_pct": DEAL_COL_BONUS_PCT,
        "bonus_paid": DEAL_COL_BONUS_PAID,
        "prod_exp": DEAL_COL_PROD_EXP,
        "source": DEAL_COL_SOURCE,
        "document": DEAL_COL_DOCUMENT,
        "comment": DEAL_COL_COMMENT,
        "creator_tg_id": DEAL_COL_CREATOR_TG_ID,
    }
    for field, col in mapping.items():
        if field in deal_data and deal_data[field] is not None:
            base[col] = str(deal_data[field])
    return base


# ---------------------------------------------------------------------------
# Settings / Users
# ---------------------------------------------------------------------------

def get_all_settings_users() -> List[SettingsUser]:
    """Return all user records from the Настройки sheet."""
    try:
        ss = _get_spreadsheet()
        ws = ss.worksheet(SHEET_SETTINGS)
        rows = ws.get_all_values()
    except Exception as exc:
        logger.error("Error reading settings sheet: %s", exc)
        return []

    users = []
    for row in rows:
        row = _pad_row(row, 4)
        tg_id = row[SETTINGS_COL_TG_ID].strip()
        if not tg_id or tg_id.lower() in ("telegram_user_id", "id"):
            continue  # skip header / empty
        users.append(
            SettingsUser(
                telegram_id=tg_id,
                full_name=row[SETTINGS_COL_FULL_NAME],
                role=row[SETTINGS_COL_ROLE],
                active=row[SETTINGS_COL_ACTIVE],
            )
        )
    return users


def get_user_info(telegram_id: int) -> Optional[SettingsUser]:
    users = get_all_settings_users()
    for u in users:
        if u.telegram_id == str(telegram_id):
            return u
    return None


def get_user_role(telegram_id: int) -> Optional[str]:
    user = get_user_info(telegram_id)
    if user and user.active.lower() in ("1", "true", "yes", "да"):
        return user.role.strip() or None
    return None


def is_user_active(telegram_id: int) -> bool:
    user = get_user_info(telegram_id)
    if not user:
        return False
    return user.active.lower() in ("1", "true", "yes", "да")


def get_active_users() -> List[SettingsUser]:
    return [u for u in get_all_settings_users() if u.active.lower() in ("1", "true", "yes", "да")]


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

def get_all_deals() -> List[Deal]:
    try:
        ss = _get_spreadsheet()
        ws = ss.worksheet(SHEET_DEALS)
        rows = ws.get_all_values()
    except Exception as exc:
        logger.error("Error reading deals sheet: %s", exc)
        return []

    deals = []
    for row in rows:
        if not row or not row[0].strip():
            continue
        if row[0].strip().lower() in ("id сделки", "id"):
            continue  # header
        try:
            deals.append(_row_to_deal(row))
        except Exception as exc:
            logger.warning("Skipping bad row: %s – %s", row, exc)
    return deals


def get_deals_by_manager(manager_name: str) -> List[Deal]:
    return [d for d in get_all_deals() if d.manager == manager_name]


def get_deals_by_manager_tg_id(tg_id: int) -> List[Deal]:
    """Filter deals where creator_tg_id matches."""
    return [d for d in get_all_deals() if d.creator_tg_id == str(tg_id)]


def get_deal_by_id(deal_id: str) -> Optional[Deal]:
    for d in get_all_deals():
        if d.id == deal_id:
            return d
    return None


def _next_deal_id(ws: gspread.Worksheet) -> str:
    rows = ws.get_all_values()
    ids = []
    for row in rows:
        if row and row[0].strip() and row[0].strip().lower() not in ("id сделки", "id"):
            try:
                ids.append(int(row[0].strip()))
            except ValueError:
                pass
    return str(max(ids) + 1) if ids else "1"


def create_deal(deal_data: Dict[str, Any]) -> Deal:
    ss = _get_spreadsheet()
    ws = ss.worksheet(SHEET_DEALS)
    new_id = _next_deal_id(ws)
    row = _deal_to_row(deal_data)
    row[DEAL_COL_ID] = new_id
    ws.append_row(row, value_input_option="USER_ENTERED")
    deal_data["id"] = new_id
    return _row_to_deal(row)


def update_deal(deal_id: str, deal_data: Dict[str, Any]) -> Optional[Deal]:
    ss = _get_spreadsheet()
    ws = ss.worksheet(SHEET_DEALS)
    rows = ws.get_all_values()
    for idx, row in enumerate(rows, start=1):
        if row and row[0].strip() == deal_id:
            updated_row = _deal_to_row(deal_data, row)
            last_col = _col_letter(DEALS_TOTAL_COLS - 1)
            ws.update(f"A{idx}:{last_col}{idx}", [updated_row])
            return _row_to_deal(updated_row)
    return None


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

def append_journal_entry(
    tg_id: int,
    role: str,
    action: str,
    deal_id: str,
    changed_fields: List[str],
    summary: str,
) -> None:
    try:
        ss = _get_spreadsheet()
        ws = ss.worksheet(SHEET_JOURNAL)
        row = [""] * 7
        row[JOURNAL_COL_TIMESTAMP] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row[JOURNAL_COL_TG_ID] = str(tg_id)
        row[JOURNAL_COL_ROLE] = role
        row[JOURNAL_COL_ACTION] = action
        row[JOURNAL_COL_DEAL_ID] = str(deal_id)
        row[JOURNAL_COL_CHANGED_FIELDS] = ", ".join(changed_fields)
        row[JOURNAL_COL_SUMMARY] = summary
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as exc:
        logger.error("Error appending journal entry: %s", exc)


def get_recent_journal(limit: int = 50) -> List[JournalEntry]:
    try:
        ss = _get_spreadsheet()
        ws = ss.worksheet(SHEET_JOURNAL)
        rows = ws.get_all_values()
    except Exception as exc:
        logger.error("Error reading journal sheet: %s", exc)
        return []

    entries = []
    for row in reversed(rows):
        row = _pad_row(row, 7)
        if not row[JOURNAL_COL_TIMESTAMP].strip():
            continue
        entries.append(
            JournalEntry(
                timestamp=row[JOURNAL_COL_TIMESTAMP],
                telegram_id=row[JOURNAL_COL_TG_ID],
                role=row[JOURNAL_COL_ROLE],
                action=row[JOURNAL_COL_ACTION],
                deal_id=row[JOURNAL_COL_DEAL_ID],
                changed_fields=row[JOURNAL_COL_CHANGED_FIELDS],
                summary=row[JOURNAL_COL_SUMMARY],
            )
        )
        if len(entries) >= limit:
            break
    return entries
