import logging

from fastapi import APIRouter, HTTPException

from backend.models.settings import SettingsResponse
from backend.services import sheets_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Load reference data from Google Sheets 'Настройки' sheet."""
    try:
        data = sheets_service.load_settings()
        return SettingsResponse(**data)
    except Exception as exc:
        logger.error("Error loading settings: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
