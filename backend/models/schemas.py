"""Pydantic schemas for the tg_bot_finans backend."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# User / Auth
# ---------------------------------------------------------------------------

class UserInfo(BaseModel):
    telegram_id: int
    full_name: str
    role: str
    active: bool


class MeResponse(BaseModel):
    telegram_id: int
    full_name: str
    role: str
    role_label_ru: str
    active: bool
    editable_fields: List[str]


# ---------------------------------------------------------------------------
# Deal schemas (new structure: deals sheet)
# ---------------------------------------------------------------------------

class DealNewBase(BaseModel):
    """Deal fields matching the new 'deals' sheet structure."""
    client: Optional[str] = None
    manager: Optional[str] = None
    city: Optional[str] = None
    service: Optional[str] = None
    status: Optional[str] = None
    revenue_with_vat: Optional[float] = None
    vat_amount: Optional[float] = None
    revenue_without_vat: Optional[float] = None
    paid_amount: Optional[float] = None
    remaining_amount: Optional[float] = None


class DealNewCreate(DealNewBase):
    pass


class DealNewUpdate(BaseModel):
    client: Optional[str] = None
    manager: Optional[str] = None
    city: Optional[str] = None
    service: Optional[str] = None
    status: Optional[str] = None
    revenue_with_vat: Optional[float] = None
    vat_amount: Optional[float] = None
    revenue_without_vat: Optional[float] = None
    paid_amount: Optional[float] = None
    remaining_amount: Optional[float] = None


class PaymentMarkRequest(BaseModel):
    """Request body for marking a payment on a deal."""
    deal_id: str
    payment_amount: float
    user: str = ""


# ---------------------------------------------------------------------------
# Billing schemas (billing_msk / billing_nsk / billing_ekb sheets)
# ---------------------------------------------------------------------------

class BillingPeriod(BaseModel):
    """One billing period block (p1 or p2) – old format."""
    shipments_amount: Optional[float] = None
    units: Optional[float] = None
    storage_amount: Optional[float] = None
    pallets: Optional[float] = None
    returns_amount: Optional[float] = None
    returns_trips: Optional[float] = None
    extra_services: Optional[float] = None
    penalties: Optional[float] = None
    # Calculated automatically by the backend:
    total_without_penalties: Optional[float] = None
    total_with_penalties: Optional[float] = None


class BillingEntryCreate(BaseModel):
    """Full billing entry for one client in one warehouse – old format (p1/p2 periods)."""
    client_name: str
    p1: Optional[BillingPeriod] = None
    p2: Optional[BillingPeriod] = None


class BillingEntryResponse(BillingEntryCreate):
    row_index: Optional[int] = None


class BillingEntryCreateV2(BaseModel):
    """
    Billing entry in new VAT-aware format (one row per client/period).

    VAT-derived fields (shipments_vat, shipments_without_vat, etc.) and totals
    (total_without_vat, total_vat, total_with_vat) are calculated automatically
    by the backend.

    input_mode controls VAT handling:
      "с НДС"   – entered values are WITH VAT; auto-calc VAT and without_vat (default)
      "без НДС" – entered values are WITHOUT VAT; vat=0, total_with_vat=total_without_vat
      "old"     – use old p1/p2 format via BillingEntryCreate instead
    """
    client: str
    month: Optional[str] = None
    period: Optional[str] = None
    input_mode: Optional[str] = None  # "с НДС" | "без НДС"

    shipments_with_vat: Optional[float] = None
    units_count: Optional[int] = None
    storage_with_vat: Optional[float] = None
    pallets_count: Optional[int] = None
    returns_pickup_with_vat: Optional[float] = None
    returns_trips_count: Optional[int] = None
    additional_services_with_vat: Optional[float] = None
    penalties: Optional[float] = None
    payment_status: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Expense schemas (expenses sheet)
# ---------------------------------------------------------------------------

EXPENSE_TYPES = frozenset({"variable", "production", "logistics", "returns", "extra"})


class ExpenseCreate(BaseModel):
    # New 2-level category fields (take priority over old category/expense_type)
    category_level_1: Optional[str] = None
    category_level_2: Optional[str] = None
    comment: Optional[str] = None

    # New field names (take priority over legacy)
    category: Optional[str] = None
    amount_with_vat: Optional[float] = None
    vat_rate: Optional[float] = None
    created_by: Optional[str] = None

    # Legacy field names (kept for backward compatibility)
    deal_id: Optional[str] = None
    expense_type: Optional[str] = None
    amount: Optional[float] = None
    vat: Optional[float] = None
    amount_without_vat: Optional[float] = None

    @field_validator("category", "expense_type", mode="before")
    @classmethod
    def validate_expense_type(cls, v: Any) -> Any:
        if v is None:
            return v
        v_str = str(v).strip().lower()
        if v_str not in EXPENSE_TYPES:
            raise ValueError(
                f"category/expense_type must be one of: {', '.join(sorted(EXPENSE_TYPES))}"
            )
        return v_str


class ExpenseBulkCreate(BaseModel):
    """Bulk expense creation – submit multiple expense rows in one request."""
    rows: List["ExpenseCreate"]


class ExpenseResponse(BaseModel):
    expense_id: Optional[str] = None
    date: Optional[str] = None
    category: Optional[str] = None
    amount_with_vat: Optional[float] = None
    vat_rate: Optional[float] = None
    vat_amount: Optional[float] = None
    amount_without_vat: Optional[float] = None
    created_by: Optional[str] = None
    # backward compat
    deal_id: Optional[str] = None
    expense_type: Optional[str] = None
    amount: Optional[float] = None
    vat: Optional[float] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Deal schemas (legacy structure kept for backward-compat)
# ---------------------------------------------------------------------------

class DealBase(BaseModel):
    status: Optional[str] = None
    direction: Optional[str] = None
    client: Optional[str] = None
    manager: Optional[str] = None
    amount_with_vat: Optional[str] = None
    has_vat: Optional[str] = None
    paid: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    act_date: Optional[str] = None
    var_exp1: Optional[str] = None
    var_exp2: Optional[str] = None
    bonus_pct: Optional[str] = None
    bonus_paid: Optional[str] = None
    prod_exp: Optional[str] = None
    source: Optional[str] = None
    document: Optional[str] = None
    comment: Optional[str] = None
    creator_tg_id: Optional[str] = None


class DealCreate(DealBase):
    pass


class DealUpdate(DealBase):
    pass


class Deal(DealBase):
    id: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------

class ManagerDashboard(BaseModel):
    total_my_deals: int
    in_progress: int
    completed: int
    total_amount: float
    deals: List[Deal]


class AccountantDashboard(BaseModel):
    awaiting_payment: int
    partially_paid: int
    fully_paid: int
    total_receivable: float
    total_paid: float
    deals: List[Deal]


class OperationsDashboard(BaseModel):
    total_deals: int
    active_deals: int
    total_amount: float
    total_paid: float
    receivable: float
    total_expenses: float
    gross_profit: float
    deals: List[Deal]
    by_manager: List[Dict[str, Any]]


class SalesDashboard(BaseModel):
    deals_in_progress: int
    new_deals: int
    completed_deals: int
    total_amount: float
    avg_deal_amount: float
    by_manager: List[Dict[str, Any]]
    deals: List[Deal]


class DashboardResponse(BaseModel):
    role: str
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Financial summary
# ---------------------------------------------------------------------------

class FinancialSummary(BaseModel):
    """Aggregated financial metrics."""
    revenue: float
    expenses: float
    gross_profit: float
    margin_percent: float


# ---------------------------------------------------------------------------
# Journal (new structure: timestamp, user, action, entity, entity_id, details)
# ---------------------------------------------------------------------------

class JournalEntryNew(BaseModel):
    timestamp: str
    user: str
    action: str
    entity: str
    entity_id: str
    details: str


class JournalEntryNewCreate(BaseModel):
    user: str
    role: str = ""
    action: str
    entity: str
    entity_id: str = ""
    details: str = ""


# ---------------------------------------------------------------------------
# Journal (legacy structure, kept for backward-compat)
# ---------------------------------------------------------------------------

class JournalEntry(BaseModel):
    timestamp: str
    telegram_id: str
    role: str
    action: str
    deal_id: str
    changed_fields: str
    summary: str


class JournalResponse(BaseModel):
    entries: List[JournalEntry]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsUser(BaseModel):
    telegram_id: str
    full_name: str
    role: str
    active: str


class SettingsResponse(BaseModel):
    users: List[SettingsUser]

