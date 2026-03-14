import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException

from backend.models.settings import (
    SettingsResponse,
    ClientCreate,
    ClientUpdate,
    ManagerCreate,
    ManagerUpdate,
    DirectionItem,
    StatusItem,
)
from backend.services import settings_service
from backend.services.journal_service import append_new_journal_entry
from backend.services.sheets_service import SheetsError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settings"])


def _actor(init_data: Optional[str], role_header: Optional[str]) -> tuple:
    """
    Resolve the acting user from optional auth headers.

    Returns a (user_id: str, role: str) tuple.
    Falls back to ('system', 'admin') when no valid auth is provided,
    so that settings mutations are always logged even without Telegram auth.
    """
    if init_data:
        try:
            from backend.services.telegram_auth import extract_user_from_init_data
            user = extract_user_from_init_data(init_data)
            if user:
                user_id = str(user.get("id", ""))
                from backend.services.permissions import ALLOWED_ROLES, NO_ACCESS_ROLE
                role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
                return user_id, role
        except Exception:
            pass

    if role_header and role_header.strip():
        from backend.services.permissions import ALLOWED_ROLES
        role = role_header.strip().lower()
        if role in ALLOWED_ROLES:
            return "", role

    return "system", "admin"


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Load reference data from the 'Настройки' sheet."""
    try:
        data = settings_service.load_all_settings()
        return SettingsResponse(**data)
    except Exception as exc:
        logger.error("Error loading settings: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Clients CRUD
# ---------------------------------------------------------------------------

@router.get("/settings/clients", response_model=List[Dict[str, Any]])
async def list_clients() -> List[Dict[str, Any]]:
    """Return all clients."""
    try:
        from backend.services.clients_service import get_clients
        return get_clients()
    except Exception as exc:
        logger.error("Error listing clients: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/settings/clients", response_model=Dict[str, Any])
async def create_client(
    body: ClientCreate,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Add a new client."""
    try:
        from backend.services.clients_service import add_client
        result = add_client(body.client_name)
        user_id, role = _actor(x_telegram_init_data, x_user_role)
        append_new_journal_entry(
            user=user_id,
            role=role,
            action="create_client",
            entity="client",
            entity_id=str(result.get("client_id", body.client_name)),
            details=f"name={body.client_name}",
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error creating client: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/settings/clients/{client_id}", response_model=Dict[str, Any])
async def update_client(
    client_id: str,
    body: ClientUpdate,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Update a client's name."""
    try:
        from backend.services.clients_service import update_client as svc_update
        result = svc_update(client_id, body.client_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error updating client %s: %s", client_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Client not found")

    user_id, role = _actor(x_telegram_init_data, x_user_role)
    append_new_journal_entry(
        user=user_id,
        role=role,
        action="update_client",
        entity="client",
        entity_id=client_id,
        details=f"new_name={body.client_name}",
    )
    return result


@router.delete("/settings/clients/{client_id}", response_model=Dict[str, Any])
async def delete_client(
    client_id: str,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Delete a client by ID."""
    try:
        from backend.services.clients_service import delete_client as svc_delete
        deleted = svc_delete(client_id)
    except SheetsError as exc:
        logger.error("Sheets error deleting client %s: %s", client_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")

    user_id, role = _actor(x_telegram_init_data, x_user_role)
    append_new_journal_entry(
        user=user_id,
        role=role,
        action="delete_client",
        entity="client",
        entity_id=client_id,
        details="deleted",
    )
    return {"success": True, "client_id": client_id}


# ---------------------------------------------------------------------------
# Managers CRUD
# ---------------------------------------------------------------------------

@router.get("/settings/managers", response_model=List[Dict[str, Any]])
async def list_managers() -> List[Dict[str, Any]]:
    """Return all managers."""
    try:
        from backend.services.managers_service import get_managers
        return get_managers()
    except Exception as exc:
        logger.error("Error listing managers: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/settings/managers", response_model=Dict[str, Any])
async def create_manager(
    body: ManagerCreate,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Add a new manager."""
    try:
        from backend.services.managers_service import add_manager
        result = add_manager(body.manager_name, body.role or "manager")
        user_id, role = _actor(x_telegram_init_data, x_user_role)
        append_new_journal_entry(
            user=user_id,
            role=role,
            action="create_manager",
            entity="manager",
            entity_id=str(result.get("manager_id", body.manager_name)),
            details=f"name={body.manager_name} role={body.role or 'manager'}",
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error creating manager: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/settings/managers/{manager_id}", response_model=Dict[str, Any])
async def update_manager(
    manager_id: str,
    body: ManagerUpdate,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Update a manager's name and/or role."""
    try:
        from backend.services.managers_service import update_manager as svc_update
        result = svc_update(manager_id, body.manager_name, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error updating manager %s: %s", manager_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Manager not found")

    user_id, role = _actor(x_telegram_init_data, x_user_role)
    append_new_journal_entry(
        user=user_id,
        role=role,
        action="update_manager",
        entity="manager",
        entity_id=manager_id,
        details=f"new_name={body.manager_name} new_role={body.role}",
    )
    return result


@router.delete("/settings/managers/{manager_id}", response_model=Dict[str, Any])
async def delete_manager(
    manager_id: str,
    x_telegram_init_data: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Delete a manager by ID."""
    try:
        from backend.services.managers_service import delete_manager as svc_delete
        deleted = svc_delete(manager_id)
    except SheetsError as exc:
        logger.error("Sheets error deleting manager %s: %s", manager_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Manager not found")

    user_id, role = _actor(x_telegram_init_data, x_user_role)
    append_new_journal_entry(
        user=user_id,
        role=role,
        action="delete_manager",
        entity="manager",
        entity_id=manager_id,
        details="deleted",
    )
    return {"success": True, "manager_id": manager_id}


# ---------------------------------------------------------------------------
# Directions CRUD
# ---------------------------------------------------------------------------

@router.get("/settings/directions", response_model=List[str])
async def list_directions() -> List[str]:
    """Return all business directions."""
    try:
        return settings_service.load_business_directions()
    except Exception as exc:
        logger.error("Error listing directions: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/settings/directions", response_model=List[str])
async def add_direction(body: DirectionItem) -> List[str]:
    """Add a new direction."""
    try:
        return settings_service.add_direction(body.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error adding direction: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/settings/directions/{direction}", response_model=List[str])
async def remove_direction(direction: str) -> List[str]:
    """Remove a direction."""
    try:
        return settings_service.delete_direction(direction)
    except SheetsError as exc:
        logger.error("Sheets error deleting direction: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Statuses CRUD
# ---------------------------------------------------------------------------

@router.get("/settings/statuses", response_model=List[str])
async def list_statuses() -> List[str]:
    """Return all deal statuses."""
    try:
        return settings_service.load_statuses()
    except Exception as exc:
        logger.error("Error listing statuses: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/settings/statuses", response_model=List[str])
async def add_status(body: StatusItem) -> List[str]:
    """Add a new status."""
    try:
        return settings_service.add_status(body.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error adding status: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/settings/statuses/{status}", response_model=List[str])
async def remove_status(status: str) -> List[str]:
    """Remove a status."""
    try:
        return settings_service.delete_status(status)
    except SheetsError as exc:
        logger.error("Sheets error deleting status: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
