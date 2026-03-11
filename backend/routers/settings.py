"""
Settings router — GET /settings
"""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.services import sheets_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    statuses: list[str] = []
    business_directions: list[str] = []
    clients: list[str] = []
    managers: list[str] = []
    vat_types: list[str] = []


# Map from Russian column headers in the sheet to response field names.
# Adjust the header names to match what's actually in the "Настройки" sheet.
_COLUMN_MAP: dict[str, str] = {
    "Статусы": "statuses",
    "Направления бизнеса": "business_directions",
    "Клиенты": "clients",
    "Менеджеры": "managers",
    "Типы НДС": "vat_types",
}


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Load reference/dictionary values from the 'Настройки' sheet."""
    try:
        raw = sheets_service.get_settings()
    except Exception as exc:
        logger.exception("Failed to load settings from Google Sheets")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load settings from Google Sheets",
        ) from exc

    result: dict[str, list[str]] = {v: [] for v in _COLUMN_MAP.values()}
    for sheet_col, field_name in _COLUMN_MAP.items():
        result[field_name] = raw.get(sheet_col, [])

    return SettingsResponse(**result)
