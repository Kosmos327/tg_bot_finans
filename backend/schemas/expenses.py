"""Pydantic schemas for expense-related endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ExpenseCreateRequest(BaseModel):
    """Request body for POST /expenses/create → public.api_create_expense(...)."""

    deal_id: Optional[int] = None
    category_level_1_id: Optional[int] = None
    category_level_2_id: Optional[int] = None
    amount_without_vat: Decimal = Field(..., description="Сумма без НДС")
    vat_type_id: Optional[int] = None
    vat_rate: Optional[Decimal] = None
    comment: Optional[str] = None
    # Legacy / convenience fields kept for backwards compatibility
    expense_type: Optional[str] = None
    category_level_1: Optional[str] = None
    category_level_2: Optional[str] = None
