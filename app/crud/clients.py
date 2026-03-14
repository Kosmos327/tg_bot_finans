"""CRUD operations for clients."""

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Client
from app.database.schemas import ClientCreate


async def create_client(db: AsyncSession, data: ClientCreate) -> Client:
    client = Client(**data.model_dump())
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


async def get_clients(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> Sequence[Client]:
    result = await db.execute(select(Client).offset(skip).limit(limit))
    return result.scalars().all()


async def get_client(db: AsyncSession, client_id: int) -> Optional[Client]:
    result = await db.execute(select(Client).where(Client.id == client_id))
    return result.scalar_one_or_none()


async def delete_client(db: AsyncSession, client_id: int) -> bool:
    client = await get_client(db, client_id)
    if client is None:
        return False
    await db.delete(client)
    return True
