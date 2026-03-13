"""
Centralized role-based permission configuration.

Role hierarchy:
  manager            – access only to own deals; edits billing/payments/expenses
  accountant         – access to all deals; edits accounting/payment fields (legacy)
  accounting         – view profit, add expenses, download reports
  operations_director– access to all deals + analytics; edits all fields; download reports
  head_of_sales      – access to all deals + sales analytics; edits all fields (legacy)
  admin              – full access; view journal, all reports, all expenses

Special values:
  no_access  – user not found or inactive; read-only / denied
"""

from typing import Dict, FrozenSet, Set

# ---------------------------------------------------------------------------
# Allowed roles
# ---------------------------------------------------------------------------

ALLOWED_ROLES: FrozenSet[str] = frozenset(
    {
        "manager",
        "accountant",
        "accounting",
        "operations_director",
        "head_of_sales",
        "admin",
    }
)

NO_ACCESS_ROLE = "no_access"

# ---------------------------------------------------------------------------
# Role labels (Russian UI labels)
# ---------------------------------------------------------------------------

ROLE_LABELS_RU: Dict[str, str] = {
    "manager": "Менеджер",
    "accountant": "Бухгалтер",
    "accounting": "Бухгалтерия",
    "operations_director": "Операционный директор",
    "head_of_sales": "Руководитель отдела продаж",
    "admin": "Администратор",
    NO_ACCESS_ROLE: "Нет доступа",
}

# ---------------------------------------------------------------------------
# Password-based role auth (Mini App login)
# ---------------------------------------------------------------------------

ROLE_PASSWORDS: Dict[str, str] = {
    "manager": "1",
    "operations_director": "2",
    "accounting": "3",
    "admin": "12345",
}

# ---------------------------------------------------------------------------
# Feature-level access flags per role
# ---------------------------------------------------------------------------

# Roles that can edit billing sheets, enter invoice amounts, penalties, mark payments
BILLING_EDIT_ROLES: FrozenSet[str] = frozenset({"manager", "admin"})

# Roles that can add expenses
EXPENSE_ADD_ROLES: FrozenSet[str] = frozenset(
    {"manager", "accounting", "operations_director", "admin"}
)

# Roles that can view all finances
FINANCE_VIEW_ROLES: FrozenSet[str] = frozenset(
    {"operations_director", "accounting", "admin"}
)

# Roles that can download reports
REPORT_DOWNLOAD_ROLES: FrozenSet[str] = frozenset(
    {"operations_director", "accounting", "admin"}
)

# Roles that can view the audit journal
JOURNAL_VIEW_ROLES: FrozenSet[str] = frozenset(
    {"operations_director", "accounting", "admin"}
)

# Admin-only features
ADMIN_ROLES: FrozenSet[str] = frozenset({"admin"})

# ---------------------------------------------------------------------------
# Fields editable per role
# ---------------------------------------------------------------------------

# Business-side fields (who is the client, what direction, dates, docs, etc.)
_BUSINESS_FIELDS: FrozenSet[str] = frozenset(
    {
        "status",
        "business_direction",
        "client",
        "manager",
        "charged_with_vat",
        "vat_type",
        "vat_rate",
        "project_start_date",
        "project_end_date",
        "source",
        "document_link",
        "comment",
    }
)

# Accounting/payment fields (paid amounts, expenses, bonuses)
_ACCOUNTING_FIELDS: FrozenSet[str] = frozenset(
    {
        "paid",
        "act_date",
        # Legacy expense fields
        "variable_expense_1",
        "variable_expense_2",
        "manager_bonus_percent",
        "manager_bonus_paid",
        "general_production_expense",
        # New VAT breakdown fields
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
        # Calculated profitability (editable by accounting/director for overrides)
        "manager_bonus_amount",
        "marginal_income",
        "gross_profit",
    }
)

_ALL_FIELDS: FrozenSet[str] = _BUSINESS_FIELDS | _ACCOUNTING_FIELDS

ROLE_EDITABLE_FIELDS: Dict[str, FrozenSet[str]] = {
    "manager": _BUSINESS_FIELDS,
    "accountant": _ACCOUNTING_FIELDS,
    "operations_director": _ALL_FIELDS,
    "head_of_sales": _ALL_FIELDS,
    "accounting": _ACCOUNTING_FIELDS,
    "admin": _ALL_FIELDS,
    NO_ACCESS_ROLE: frozenset(),
}

# ---------------------------------------------------------------------------
# Visible data scope per role
# ---------------------------------------------------------------------------

ROLE_VISIBLE_DATA: Dict[str, str] = {
    # "own"  – only deals where deal['manager'] matches the user's name/id
    # "all"  – all deals in the sheet
    "manager": "own",
    "accountant": "all",
    "accounting": "all",
    "operations_director": "all",
    "head_of_sales": "all",
    "admin": "all",
    NO_ACCESS_ROLE: "none",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_editable_fields(role: str) -> Set[str]:
    """Return the set of field names a user with *role* may edit."""
    return set(ROLE_EDITABLE_FIELDS.get(role, frozenset()))


def filter_update_payload(role: str, payload: dict) -> dict:
    """
    Remove keys from *payload* that the given *role* is not allowed to edit.
    Returns a new dict containing only permitted fields.
    """
    allowed = ROLE_EDITABLE_FIELDS.get(role, frozenset())
    return {k: v for k, v in payload.items() if k in allowed}


def can_see_all_deals(role: str) -> bool:
    """Return True if the role can read all deals (not just own)."""
    return ROLE_VISIBLE_DATA.get(role, "none") == "all"


def check_role(role: str, allowed_roles: FrozenSet[str]) -> bool:
    """Return True if *role* is in *allowed_roles*."""
    return role in allowed_roles


def verify_role_password(role: str, password: str) -> bool:
    """Return True if the given *password* matches the role's configured password."""
    expected = ROLE_PASSWORDS.get(role)
    if expected is None:
        return False
    return password == expected
