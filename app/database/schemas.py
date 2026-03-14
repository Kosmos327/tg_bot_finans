"""
Pydantic schemas for request/response models.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Manager schemas
# ---------------------------------------------------------------------------


class ManagerCreate(BaseModel):
    full_name: str
    telegram_id: Optional[int] = None
    active: bool = True


class ManagerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    telegram_id: Optional[int] = None
    active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Client schemas
# ---------------------------------------------------------------------------


class ClientCreate(BaseModel):
    name: str
    contact: Optional[str] = None
    active: bool = True


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact: Optional[str] = None
    active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Deal schemas
# ---------------------------------------------------------------------------


class DealCreate(BaseModel):
    manager_id: Optional[int] = None
    client_id: Optional[int] = None
    status: Optional[str] = None
    business_direction: Optional[str] = None
    deal_name: Optional[str] = None
    description: Optional[str] = None
    amount_with_vat: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    source: Optional[str] = None
    comment: Optional[str] = None
    act_date: Optional[datetime] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None


class DealUpdate(BaseModel):
    manager_id: Optional[int] = None
    client_id: Optional[int] = None
    status: Optional[str] = None
    business_direction: Optional[str] = None
    deal_name: Optional[str] = None
    description: Optional[str] = None
    amount_with_vat: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    variable_expense_1: Optional[Decimal] = None
    variable_expense_2: Optional[Decimal] = None
    production_expense: Optional[Decimal] = None
    manager_bonus_pct: Optional[Decimal] = None
    source: Optional[str] = None
    document_url: Optional[str] = None
    comment: Optional[str] = None
    act_date: Optional[datetime] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None


class DealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    manager_id: Optional[int] = None
    client_id: Optional[int] = None
    status: Optional[str] = None
    business_direction: Optional[str] = None
    deal_name: Optional[str] = None
    description: Optional[str] = None
    amount_with_vat: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    amount_without_vat: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    variable_expense_1: Optional[Decimal] = None
    variable_expense_2: Optional[Decimal] = None
    production_expense: Optional[Decimal] = None
    manager_bonus_pct: Optional[Decimal] = None
    manager_bonus_amount: Optional[Decimal] = None
    marginal_income: Optional[Decimal] = None
    gross_profit: Optional[Decimal] = None
    source: Optional[str] = None
    document_url: Optional[str] = None
    comment: Optional[str] = None
    act_date: Optional[datetime] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Billing schemas
# ---------------------------------------------------------------------------


class BillingCreate(BaseModel):
    client_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    month: Optional[str] = None  # YYYY-MM
    period: Optional[str] = None  # p1 / p2
    shipments_with_vat: Optional[Decimal] = None
    units_count: Optional[int] = None
    storage_with_vat: Optional[Decimal] = None
    pallets_count: Optional[int] = None
    returns_pickup_with_vat: Optional[Decimal] = None
    returns_trips_count: Optional[int] = None
    additional_services_with_vat: Optional[Decimal] = None
    penalties: Optional[Decimal] = None
    payment_status: Optional[str] = None
    payment_amount: Optional[Decimal] = None
    payment_date: Optional[datetime] = None


class BillingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    month: Optional[str] = None
    period: Optional[str] = None
    shipments_with_vat: Optional[Decimal] = None
    shipments_vat: Optional[Decimal] = None
    shipments_without_vat: Optional[Decimal] = None
    units_count: Optional[int] = None
    storage_with_vat: Optional[Decimal] = None
    storage_vat: Optional[Decimal] = None
    storage_without_vat: Optional[Decimal] = None
    pallets_count: Optional[int] = None
    returns_pickup_with_vat: Optional[Decimal] = None
    returns_pickup_vat: Optional[Decimal] = None
    returns_pickup_without_vat: Optional[Decimal] = None
    returns_trips_count: Optional[int] = None
    additional_services_with_vat: Optional[Decimal] = None
    additional_services_vat: Optional[Decimal] = None
    additional_services_without_vat: Optional[Decimal] = None
    penalties: Optional[Decimal] = None
    total_without_vat: Optional[Decimal] = None
    total_vat: Optional[Decimal] = None
    total_with_vat: Optional[Decimal] = None
    payment_status: Optional[str] = None
    payment_amount: Optional[Decimal] = None
    payment_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Expense schemas
# ---------------------------------------------------------------------------


class ExpenseCreate(BaseModel):
    deal_id: Optional[int] = None
    category_level_1: Optional[str] = None
    category_level_2: Optional[str] = None
    expense_type: Optional[str] = None
    amount_with_vat: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    comment: Optional[str] = None
    created_by: Optional[str] = None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deal_id: Optional[int] = None
    category_level_1: Optional[str] = None
    category_level_2: Optional[str] = None
    expense_type: Optional[str] = None
    amount_with_vat: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    amount_without_vat: Optional[Decimal] = None
    comment: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Journal schemas
# ---------------------------------------------------------------------------


class JournalEntryCreate(BaseModel):
    user_id: Optional[str] = None
    role_name: Optional[str] = None
    action: str
    entity: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[str] = None


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[str] = None
    role_name: Optional[str] = None
    action: str
    entity: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime
