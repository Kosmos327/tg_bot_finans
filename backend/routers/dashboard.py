"""Dashboard router – role-aware aggregated data."""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.config import (
    ROLE_ACCOUNTANT,
    ROLE_HEAD_OF_SALES,
    ROLE_MANAGER,
    ROLE_OPERATIONS_DIRECTOR,
)
from backend.dependencies import get_current_user, require_active_user
from backend.models.schemas import MeResponse
from backend.services.deals import (
    build_accountant_dashboard,
    build_manager_dashboard,
    build_operations_dashboard,
    build_sales_dashboard,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=Dict[str, Any])
def dashboard(current_user: MeResponse = Depends(get_current_user)) -> Dict[str, Any]:
    """Return role-aware dashboard payload."""
    require_active_user(current_user)

    if current_user.role == ROLE_MANAGER:
        data = build_manager_dashboard(current_user)
    elif current_user.role == ROLE_ACCOUNTANT:
        data = build_accountant_dashboard()
    elif current_user.role == ROLE_OPERATIONS_DIRECTOR:
        data = build_operations_dashboard()
    elif current_user.role == ROLE_HEAD_OF_SALES:
        data = build_sales_dashboard()
    else:
        data = {}

    return {"role": current_user.role, "data": data}


# Convenience role-specific endpoints
@router.get("/manager", response_model=Dict[str, Any])
def dashboard_manager(current_user: MeResponse = Depends(get_current_user)):
    require_active_user(current_user)
    return {"role": ROLE_MANAGER, "data": build_manager_dashboard(current_user)}


@router.get("/accountant", response_model=Dict[str, Any])
def dashboard_accountant(current_user: MeResponse = Depends(get_current_user)):
    require_active_user(current_user)
    return {"role": ROLE_ACCOUNTANT, "data": build_accountant_dashboard()}


@router.get("/operations", response_model=Dict[str, Any])
def dashboard_operations(current_user: MeResponse = Depends(get_current_user)):
    require_active_user(current_user)
    return {"role": ROLE_OPERATIONS_DIRECTOR, "data": build_operations_dashboard()}


@router.get("/sales", response_model=Dict[str, Any])
def dashboard_sales(current_user: MeResponse = Depends(get_current_user)):
    require_active_user(current_user)
    return {"role": ROLE_HEAD_OF_SALES, "data": build_sales_dashboard()}
