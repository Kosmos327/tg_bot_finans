"""Pydantic schemas for billing-related endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class BillingUpsertRequest(BaseModel):
    """Request body for POST /billing/upsert → public.api_upsert_billing_entry(...)."""

    client_id: int
    warehouse_id: int
    month: str = Field(..., description="YYYY-MM")
    period: Optional[str] = None  # p1 / p2 (legacy)
    shipments_with_vat: Optional[Decimal] = None
    shipments_without_vat: Optional[Decimal] = None
    units_count: Optional[int] = None
    storage_with_vat: Optional[Decimal] = None
    storage_without_vat: Optional[Decimal] = None
    pallets_count: Optional[int] = None
    returns_pickup_with_vat: Optional[Decimal] = None
    returns_pickup_without_vat: Optional[Decimal] = None
    returns_trips_count: Optional[int] = None
    additional_services_with_vat: Optional[Decimal] = None
    additional_services_without_vat: Optional[Decimal] = None
    penalties: Optional[Decimal] = None
    vat_type_id: Optional[int] = None
    comment: Optional[str] = None


class BillingPayRequest(BaseModel):
    """Request body for POST /billing/pay → public.api_pay_billing_entry(...)."""

    billing_entry_id: int
    payment_amount: Decimal
    payment_date: Optional[date] = None


class BillingPaymentMarkRequest(BaseModel):
    """Request body for POST /billing/v2/payment/mark → public.api_pay_deal(...)."""

    deal_id: str = Field(..., description="Deal ID (numeric string or deal code)")
    payment_amount: Decimal
    payment_date: Optional[date] = None
