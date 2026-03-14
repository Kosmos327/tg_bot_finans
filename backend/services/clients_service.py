"""
clients_service.py – Async CRUD operations for the 'clients' table via PostgreSQL.

Public API
----------
get_clients(db)                          → List[dict]
add_client(db, client_name)              → dict
update_client(db, client_id, name)       → dict | None
delete_client(db, client_id)             → bool
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Client

logger = logging.getLogger(__name__)


def _client_to_dict(client: Client) -> Dict:
    """Convert a Client ORM object to the dict format expected by the Mini App."""
    return {
        "client_id": str(client.id),
        "client_name": client.client_name,
        "created_at": (
            client.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if client.created_at
            else ""
        ),
    }


async def get_clients(db: AsyncSession) -> List[dict]:
    """Return all clients from the clients table."""
    result = await db.execute(
        select(Client).order_by(Client.id)
    )
    clients = result.scalars().all()
    return [_client_to_dict(c) for c in clients]


async def add_client(db: AsyncSession, client_name: str) -> dict:
    """Create a new client row. Returns the created record."""
    client_name = client_name.strip()
    if not client_name:
        raise ValueError("client_name cannot be empty")

    client = Client(client_name=client_name)
    db.add(client)
    await db.flush()
    await db.refresh(client)
    logger.info("Created client id=%s name=%r", client.id, client_name)
    return _client_to_dict(client)


async def update_client(
    db: AsyncSession, client_id: str, client_name: str
) -> Optional[dict]:
    """Update the client name. Returns updated record or None if not found."""
    client_name = client_name.strip()
    if not client_name:
        raise ValueError("client_name cannot be empty")

    try:
        cid = int(client_id)
    except (ValueError, TypeError):
        logger.warning("Invalid client_id value: %r", client_id)
        return None

    result = await db.execute(select(Client).where(Client.id == cid))
    client = result.scalar_one_or_none()
    if client is None:
        return None

    client.client_name = client_name
    await db.flush()
    await db.refresh(client)
    logger.info("Updated client id=%s new_name=%r", cid, client_name)
    return _client_to_dict(client)


async def delete_client(db: AsyncSession, client_id: str) -> bool:
    """Delete a client. Returns True if deleted, False if not found."""
    try:
        cid = int(client_id)
    except (ValueError, TypeError):
        logger.warning("Invalid client_id value: %r", client_id)
        return False

    result = await db.execute(select(Client).where(Client.id == cid))
    client = result.scalar_one_or_none()
    if client is None:
        return False

    await db.delete(client)
    await db.flush()
    logger.info("Deleted client id=%s", cid)
    return True

