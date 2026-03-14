import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

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
from backend.services.sheets_service import SheetsError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settings"])


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
async def create_client(body: ClientCreate) -> Dict[str, Any]:
    """Add a new client."""
    try:
        from backend.services.clients_service import add_client
        return add_client(body.client_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error creating client: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/settings/clients/{client_id}", response_model=Dict[str, Any])
async def update_client(client_id: str, body: ClientUpdate) -> Dict[str, Any]:
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
    return result


@router.delete("/settings/clients/{client_id}", response_model=Dict[str, Any])
async def delete_client(client_id: str) -> Dict[str, Any]:
    """Delete a client by ID."""
    try:
        from backend.services.clients_service import delete_client as svc_delete
        deleted = svc_delete(client_id)
    except SheetsError as exc:
        logger.error("Sheets error deleting client %s: %s", client_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
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
async def create_manager(body: ManagerCreate) -> Dict[str, Any]:
    """Add a new manager."""
    try:
        from backend.services.managers_service import add_manager
        return add_manager(body.manager_name, body.role or "manager")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error creating manager: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/settings/managers/{manager_id}", response_model=Dict[str, Any])
async def update_manager(manager_id: str, body: ManagerUpdate) -> Dict[str, Any]:
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
    return result


@router.delete("/settings/managers/{manager_id}", response_model=Dict[str, Any])
async def delete_manager(manager_id: str) -> Dict[str, Any]:
    """Delete a manager by ID."""
    try:
        from backend.services.managers_service import delete_manager as svc_delete
        deleted = svc_delete(manager_id)
    except SheetsError as exc:
        logger.error("Sheets error deleting manager %s: %s", manager_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Manager not found")
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
