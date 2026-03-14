"""CRUD operations for managers."""

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Manager
from app.database.schemas import ManagerCreate


async def create_manager(db: AsyncSession, data: ManagerCreate) -> Manager:
    manager = Manager(**data.model_dump())
    db.add(manager)
    await db.flush()
    await db.refresh(manager)
    return manager


async def get_managers(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> Sequence[Manager]:
    result = await db.execute(select(Manager).offset(skip).limit(limit))
    return result.scalars().all()


async def get_manager(db: AsyncSession, manager_id: int) -> Optional[Manager]:
    result = await db.execute(select(Manager).where(Manager.id == manager_id))
    return result.scalar_one_or_none()


async def delete_manager(db: AsyncSession, manager_id: int) -> bool:
    manager = await get_manager(db, manager_id)
    if manager is None:
        return False
    await db.delete(manager)
    return True
