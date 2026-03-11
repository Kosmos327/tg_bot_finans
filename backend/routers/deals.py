"""
Deals router — POST /deal/create, GET /deals/user
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.services import sheets_service
from backend.services.auth_service import verify_init_data

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deals"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DealCreateRequest(BaseModel):
    status: str = Field(..., min_length=1, description="Статус сделки")
    business_direction: str = Field(..., min_length=1, description="Направление бизнеса")
    client: str = Field(..., min_length=1, description="Клиент")
    manager: str = Field(..., min_length=1, description="Менеджер")
    amount_with_vat: float = Field(..., ge=0, description="Начислено с НДС")
    vat_type: str = Field(..., description="Наличие НДС")
    start_date: str = Field(..., description="Дата начала проекта (YYYY-MM-DD)")
    end_date: str = Field(..., description="Дата окончания проекта (YYYY-MM-DD)")
    document_link: str = Field("", description="Документ/ссылка")
    comment: str = Field("", description="Комментарий")
    source: str = Field("", description="Источник")


class DealCreateResponse(BaseModel):
    deal_id: str
    message: str = "Deal created successfully"


class UserDealsRequest(BaseModel):
    manager: str


# ---------------------------------------------------------------------------
# Dependency — validate Telegram initData
# ---------------------------------------------------------------------------

def _get_init_data(x_init_data: Annotated[str | None, Header()] = None) -> dict:
    """Validate X-Init-Data header sent by the Mini App."""
    if not x_init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Init-Data header",
        )
    try:
        return verify_init_data(x_init_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/deal/create",
    response_model=DealCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deal(
    payload: DealCreateRequest,
    init_data: Annotated[dict, Depends(_get_init_data)],
) -> DealCreateResponse:
    """Create a new deal and write it to Google Sheets."""
    user_info = init_data.get("user", {})
    telegram_user_id = user_info.get("id", "") if isinstance(user_info, dict) else ""

    deal_data = payload.model_dump()
    deal_data["telegram_user_id"] = telegram_user_id

    try:
        deal_id = sheets_service.create_deal(deal_data)
    except Exception as exc:
        logger.exception("Failed to create deal")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write deal to Google Sheets",
        ) from exc

    return DealCreateResponse(deal_id=deal_id)


@router.get("/deals/user", response_model=list[dict])
async def get_user_deals(
    manager: str,
    init_data: Annotated[dict, Depends(_get_init_data)],
) -> list[dict]:
    """Return all deals for a given manager."""
    try:
        return sheets_service.get_deals_by_manager(manager)
    except Exception as exc:
        logger.exception("Failed to fetch deals for manager=%s", manager)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read deals from Google Sheets",
        ) from exc
