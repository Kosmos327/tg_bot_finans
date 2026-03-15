"""Pydantic schemas for deal-related endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DealCreateRequest(BaseModel):
    """Request body for POST /deals/create → public.api_create_deal(...)."""

    status_id: int = Field(..., description="ID статуса сделки")
    business_direction_id: int = Field(..., description="ID направления бизнеса")
    client_id: int = Field(..., description="ID клиента")
    manager_id: int = Field(..., description="ID менеджера")
    charged_with_vat: Decimal = Field(..., description="Начислено с НДС")
    charged_without_vat: Optional[Decimal] = None
    vat_type_id: Optional[int] = None
    vat_rate: Optional[Decimal] = None
    paid: Optional[Decimal] = Decimal("0")
    project_start_date: Optional[date] = None
    project_end_date: Optional[date] = None
    act_date: Optional[date] = None
    variable_expense_1_without_vat: Optional[Decimal] = None
    variable_expense_2_without_vat: Optional[Decimal] = None
    production_expense_without_vat: Optional[Decimal] = None
    manager_bonus_percent: Optional[Decimal] = None
    source_id: Optional[int] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None


class DealPayRequest(BaseModel):
    """Request body for POST /deals/pay → public.api_pay_deal(...)."""

    deal_id: int
    payment_amount: Decimal
    payment_date: Optional[date] = None
