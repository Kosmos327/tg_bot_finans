"""
Expenses router — POST /expenses, GET /expenses.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import expenses as crud
from app.database.database import get_db
from app.database.schemas import ExpenseCreate, ExpenseResponse
from app.services.expense_service import create_expense as svc_create

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", response_model=ExpenseResponse, status_code=201)
async def create_expense(
    data: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    expense = await svc_create(db, data)
    return ExpenseResponse.model_validate(expense)


@router.get("", response_model=List[ExpenseResponse])
async def list_expenses(
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
) -> List[ExpenseResponse]:
    expenses = await crud.get_expenses(db, skip=skip, limit=limit)
    return [ExpenseResponse.model_validate(e) for e in expenses]
