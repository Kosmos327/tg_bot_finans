"""CRUD operations for expenses."""

from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Expense
from app.database.schemas import ExpenseCreate


def _calc_expense_vat(expense: Expense) -> None:
    """Auto-calculate VAT breakdown for expense."""
    if expense.amount_with_vat and expense.vat_rate:
        rate = Decimal(str(expense.vat_rate))
        amount = Decimal(str(expense.amount_with_vat))
        expense.amount_without_vat = round(amount / (1 + rate), 2)
        expense.vat_amount = round(amount - expense.amount_without_vat, 2)


async def create_expense(db: AsyncSession, data: ExpenseCreate) -> Expense:
    expense = Expense(**data.model_dump(exclude_none=True))
    _calc_expense_vat(expense)
    db.add(expense)
    await db.flush()
    await db.refresh(expense)
    return expense


async def get_expenses(
    db: AsyncSession, skip: int = 0, limit: int = 200
) -> Sequence[Expense]:
    result = await db.execute(select(Expense).offset(skip).limit(limit))
    return result.scalars().all()


async def get_expense(db: AsyncSession, expense_id: int) -> Optional[Expense]:
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    return result.scalar_one_or_none()
