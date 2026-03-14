"""
Reports router — aggregated data endpoints.

GET /reports/deals    – revenue by month and status
GET /reports/billing  – billing totals by warehouse
GET /reports/expenses – expenses by category
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.models import BillingEntry, Deal, Expense

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/deals", response_model=List[Dict[str, Any]])
async def report_deals(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Revenue by month grouped by status."""
    result = await db.execute(
        select(
            func.to_char(Deal.created_at, "YYYY-MM").label("month"),
            Deal.status,
            func.count(Deal.id).label("count"),
            func.coalesce(func.sum(Deal.amount_with_vat), 0).label("revenue"),
            func.coalesce(func.sum(Deal.paid_amount), 0).label("paid"),
        )
        .group_by("month", Deal.status)
        .order_by("month")
    )
    return [
        {
            "month": row.month,
            "status": row.status,
            "count": row.count,
            "revenue": float(row.revenue),
            "paid": float(row.paid),
        }
        for row in result
    ]


@router.get("/billing", response_model=List[Dict[str, Any]])
async def report_billing(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Billing totals by warehouse and month."""
    result = await db.execute(
        select(
            BillingEntry.warehouse_id,
            BillingEntry.month,
            func.count(BillingEntry.id).label("entries"),
            func.coalesce(func.sum(BillingEntry.total_with_vat), 0).label(
                "total_with_vat"
            ),
            func.coalesce(func.sum(BillingEntry.total_without_vat), 0).label(
                "total_without_vat"
            ),
        )
        .group_by(BillingEntry.warehouse_id, BillingEntry.month)
        .order_by(BillingEntry.month)
    )
    return [
        {
            "warehouse_id": row.warehouse_id,
            "month": row.month,
            "entries": row.entries,
            "total_with_vat": float(row.total_with_vat),
            "total_without_vat": float(row.total_without_vat),
        }
        for row in result
    ]


@router.get("/expenses", response_model=List[Dict[str, Any]])
async def report_expenses(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Expenses by category."""
    result = await db.execute(
        select(
            Expense.expense_type,
            Expense.category_level_1,
            func.count(Expense.id).label("count"),
            func.coalesce(func.sum(Expense.amount_with_vat), 0).label(
                "total_with_vat"
            ),
            func.coalesce(func.sum(Expense.amount_without_vat), 0).label(
                "total_without_vat"
            ),
        )
        .group_by(Expense.expense_type, Expense.category_level_1)
        .order_by(Expense.expense_type)
    )
    return [
        {
            "expense_type": row.expense_type,
            "category_level_1": row.category_level_1,
            "count": row.count,
            "total_with_vat": float(row.total_with_vat),
            "total_without_vat": float(row.total_without_vat),
        }
        for row in result
    ]
