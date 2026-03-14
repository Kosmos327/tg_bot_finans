"""
Expense service — high-level business logic for expenses.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import expenses as crud_expenses
from app.database.models import Expense
from app.database.schemas import ExpenseCreate
from app.services.journal_service import log_action

logger = logging.getLogger(__name__)


async def create_expense(
    db: AsyncSession,
    data: ExpenseCreate,
    user_id: Optional[str] = None,
    role_name: Optional[str] = None,
) -> Expense:
    expense = await crud_expenses.create_expense(db, data)
    await log_action(
        db,
        action="create_expense",
        user_id=user_id,
        role_name=role_name,
        entity="expense",
        entity_id=expense.id,
        details=f"expense_type={expense.expense_type} amount={expense.amount_with_vat}",
    )
    return expense
