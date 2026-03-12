"""
Configuration and role-permission maps for the tg_bot_finans backend.
"""

import os
from typing import Dict, List

# ---------------------------------------------------------------------------
# Google Sheets configuration
# ---------------------------------------------------------------------------
SPREADSHEET_ID: str = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")

SHEET_DEALS = "Учёт сделок"
SHEET_SETTINGS = "Настройки"
SHEET_JOURNAL = "Журнал действий"

# ---------------------------------------------------------------------------
# Telegram configuration
# ---------------------------------------------------------------------------
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
MINI_APP_URL: str = os.getenv("WEBAPP_URL", "")

# ---------------------------------------------------------------------------
# Role constants
# ---------------------------------------------------------------------------
ROLE_MANAGER = "manager"
ROLE_ACCOUNTANT = "accountant"
ROLE_OPERATIONS_DIRECTOR = "operations_director"
ROLE_HEAD_OF_SALES = "head_of_sales"

ALL_ROLES = [ROLE_MANAGER, ROLE_ACCOUNTANT, ROLE_OPERATIONS_DIRECTOR, ROLE_HEAD_OF_SALES]

ROLE_LABELS_RU: Dict[str, str] = {
    ROLE_MANAGER: "Менеджер",
    ROLE_ACCOUNTANT: "Бухгалтер",
    ROLE_OPERATIONS_DIRECTOR: "Операционный директор",
    ROLE_HEAD_OF_SALES: "Руководитель отдела продаж",
}

# ---------------------------------------------------------------------------
# Deal columns (0-based index → column letter A=0, B=1, …)
# ---------------------------------------------------------------------------
DEAL_COL_ID = 0          # A - ID сделки
DEAL_COL_STATUS = 1      # B - Статус сделки
DEAL_COL_DIRECTION = 2   # C - Направление бизнеса
DEAL_COL_CLIENT = 3      # D - Клиент
DEAL_COL_MANAGER = 4     # E - Менеджер
DEAL_COL_AMOUNT_VAT = 5  # F - Начислено с НДС
DEAL_COL_HAS_VAT = 6     # G - Наличие НДС
DEAL_COL_PAID = 7        # H - Оплачено
DEAL_COL_DATE_START = 8  # I - Дата начала проекта
DEAL_COL_DATE_END = 9    # J - Дата окончания проекта
DEAL_COL_ACT_DATE = 10   # K - Дата выставления акта
DEAL_COL_VAR_EXP1 = 11   # L - Переменный расход 1
DEAL_COL_VAR_EXP2 = 12   # M - Переменный расход 2
DEAL_COL_BONUS_PCT = 13  # N - Бонус менеджера %
DEAL_COL_BONUS_PAID = 14 # O - Бонус менеджера выплачено
DEAL_COL_PROD_EXP = 15   # P - Общепроизводственный расход
DEAL_COL_SOURCE = 16     # Q - Источник
DEAL_COL_DOCUMENT = 17   # R - Документ/ссылка
DEAL_COL_COMMENT = 18    # S - Комментарий

# Extended (not in spreadsheet, stored/inferred internally):
DEAL_COL_CREATOR_TG_ID = 19  # T (optional extra col)

DEALS_TOTAL_COLS = 20  # total columns we manage (A-T)

# ---------------------------------------------------------------------------
# Field-level edit permissions per role
# ---------------------------------------------------------------------------
ALL_DEAL_FIELDS: List[str] = [
    "status", "direction", "client", "manager",
    "amount_with_vat", "has_vat",
    "paid",
    "date_start", "date_end", "act_date",
    "var_exp1", "var_exp2",
    "bonus_pct", "bonus_paid", "prod_exp",
    "source", "document", "comment",
    "creator_tg_id",
]

ROLE_EDITABLE_FIELDS: Dict[str, List[str]] = {
    ROLE_MANAGER: [
        "status", "direction", "client",
        "amount_with_vat", "has_vat",
        "date_start", "date_end",
        "source", "document", "comment",
    ],
    ROLE_ACCOUNTANT: [
        "paid", "act_date",
        "var_exp1", "var_exp2",
        "bonus_pct", "bonus_paid", "prod_exp",
        "comment",
    ],
    ROLE_OPERATIONS_DIRECTOR: ALL_DEAL_FIELDS,
    ROLE_HEAD_OF_SALES: [
        "status", "direction", "client", "manager",
        "amount_with_vat", "has_vat",
        "date_start", "date_end",
        "source", "document", "comment",
    ],
}

# Settings sheet columns (0-based)
SETTINGS_COL_TG_ID = 0
SETTINGS_COL_FULL_NAME = 1
SETTINGS_COL_ROLE = 2
SETTINGS_COL_ACTIVE = 3

# Journal columns (0-based)
JOURNAL_COL_TIMESTAMP = 0
JOURNAL_COL_TG_ID = 1
JOURNAL_COL_ROLE = 2
JOURNAL_COL_ACTION = 3
JOURNAL_COL_DEAL_ID = 4
JOURNAL_COL_CHANGED_FIELDS = 5
JOURNAL_COL_SUMMARY = 6
