"""
managers_service.py – Async CRUD operations for the 'managers' table via PostgreSQL.

Public API
----------
get_managers(db)                              → List[dict]
add_manager(db, manager_name, role)           → dict
update_manager(db, manager_id, name, role)    → dict | None
delete_manager(db, manager_id)               → bool
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Manager

logger = logging.getLogger(__name__)


def _manager_to_dict(manager: Manager, role: str = "manager") -> Dict:
    """Convert a Manager ORM object to the dict format expected by the Mini App."""
    return {
        "manager_id": str(manager.id),
        "manager_name": manager.full_name,
        "role": role,
        "created_at": (
            manager.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if manager.created_at
            else ""
        ),
    }


async def get_managers(db: AsyncSession) -> List[dict]:
    """Return all active managers from the managers table."""
    result = await db.execute(
        select(Manager).where(Manager.active.is_(True)).order_by(Manager.id)
    )
    managers = result.scalars().all()
    return [_manager_to_dict(m) for m in managers]


async def add_manager(
    db: AsyncSession, manager_name: str, role: str = "manager"
) -> dict:
    """Create a new manager row. Returns the created record."""
    manager_name = manager_name.strip()
    if not manager_name:
        raise ValueError("manager_name cannot be empty")

    manager = Manager(full_name=manager_name, active=True)
    db.add(manager)
    await db.flush()
    await db.refresh(manager)
    logger.info("Created manager id=%s name=%r role=%r", manager.id, manager_name, role)
    return _manager_to_dict(manager, role=role)


async def update_manager(
    db: AsyncSession,
    manager_id: str,
    manager_name: Optional[str] = None,
    role: Optional[str] = None,
) -> Optional[dict]:
    """Update manager fields. Returns updated record or None if not found."""
    if manager_name is not None:
        manager_name = manager_name.strip()
        if not manager_name:
            raise ValueError("manager_name cannot be empty")

    try:
        mid = int(manager_id)
    except (ValueError, TypeError):
        logger.warning("Invalid manager_id value: %r", manager_id)
        return None

    result = await db.execute(select(Manager).where(Manager.id == mid))
    manager = result.scalar_one_or_none()
    if manager is None:
        return None

    if manager_name is not None:
        manager.full_name = manager_name
    await db.flush()
    await db.refresh(manager)
    logger.info("Updated manager id=%s", mid)
    return _manager_to_dict(manager, role=role or "manager")


async def delete_manager(db: AsyncSession, manager_id: str) -> bool:
    """Soft-delete a manager. Returns True if deleted, False if not found."""
    try:
        mid = int(manager_id)
    except (ValueError, TypeError):
        logger.warning("Invalid manager_id value: %r", manager_id)
        return False

    result = await db.execute(select(Manager).where(Manager.id == mid))
    manager = result.scalar_one_or_none()
    if manager is None:
        return False

    manager.active = False
    await db.flush()
    logger.info("Soft-deleted manager id=%s", mid)
    return True

