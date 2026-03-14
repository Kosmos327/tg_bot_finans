"""Managers router — POST /managers, GET /managers, DELETE /managers/{id}."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import managers as crud
from app.database.database import get_db
from app.database.schemas import ManagerCreate, ManagerResponse
from app.services.journal_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/managers", tags=["managers"])


@router.post("", response_model=ManagerResponse, status_code=201)
async def create_manager(
    data: ManagerCreate,
    db: AsyncSession = Depends(get_db),
) -> ManagerResponse:
    manager = await crud.create_manager(db, data)
    await log_action(
        db,
        action="create_manager",
        entity="manager",
        entity_id=manager.id,
        details=f"full_name={manager.full_name}",
    )
    return ManagerResponse.model_validate(manager)


@router.get("", response_model=List[ManagerResponse])
async def list_managers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> List[ManagerResponse]:
    managers = await crud.get_managers(db, skip=skip, limit=limit)
    return [ManagerResponse.model_validate(m) for m in managers]


@router.delete("/{manager_id}", status_code=204)
async def delete_manager(
    manager_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await crud.delete_manager(db, manager_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Manager not found")
    await log_action(
        db,
        action="delete_manager",
        entity="manager",
        entity_id=manager_id,
    )
