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
# Deal schemas
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
# Journal
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
