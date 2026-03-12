"""
Centralized role-based permission configuration.

Role hierarchy:
  manager            – access only to own deals; edits business-side fields
  accountant         – access to all deals; edits accounting/payment fields
  operations_director– access to all deals + analytics; edits all fields
  head_of_sales      – access to all deals + sales analytics; edits all fields

Special values:
  no_access  – user not found or inactive; read-only / denied
"""

from typing import Dict, FrozenSet, Set

# ---------------------------------------------------------------------------
# Allowed roles
# ---------------------------------------------------------------------------

ALLOWED_ROLES: FrozenSet[str] = frozenset(
    {"manager", "accountant", "operations_director", "head_of_sales"}
)

NO_ACCESS_ROLE = "no_access"

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
        "variable_expense_1",
        "variable_expense_2",
        "manager_bonus_percent",
        "manager_bonus_paid",
        "general_production_expense",
    }
)

_ALL_FIELDS: FrozenSet[str] = _BUSINESS_FIELDS | _ACCOUNTING_FIELDS

ROLE_EDITABLE_FIELDS: Dict[str, FrozenSet[str]] = {
    "manager": _BUSINESS_FIELDS,
    "accountant": _ACCOUNTING_FIELDS,
    "operations_director": _ALL_FIELDS,
    "head_of_sales": _ALL_FIELDS,
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
    "operations_director": "all",
    "head_of_sales": "all",
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
