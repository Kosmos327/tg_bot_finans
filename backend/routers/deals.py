import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from backend.models.deal import DealCreate, DealUpdate
from backend.services import deals_service, settings_service
from backend.services.miniapp_auth_service import (
    get_user_by_telegram_id,
    get_role_code,
)
from backend.services.permissions import (
    NO_ACCESS_ROLE,
    can_see_all_deals,
    filter_update_payload,
)
from backend.services.sheets_service import SheetsError
from backend.services.telegram_auth import extract_user_from_init_data
from backend.services.journal_service import append_journal_entry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deal", tags=["deals"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_user_db(
    db: AsyncSession,
    telegram_id_header: Optional[str],
) -> tuple:
    """
    Resolve (user_id, role, full_name) from app_users table using X-Telegram-Id header.

    This is the primary resolution path when the Mini App sends its telegram_id
    after a successful /auth/miniapp-login.

    Returns:
        (user_id_str, role_code, full_name)
        Falls back to ("", NO_ACCESS_ROLE, "") on failure.
    """
    if not telegram_id_header:
        logger.debug("_resolve_user_db: X-Telegram-Id header missing")
        return "", NO_ACCESS_ROLE, ""

    try:
        telegram_id = int(telegram_id_header.strip())
    except (ValueError, TypeError):
        logger.warning("_resolve_user_db: invalid X-Telegram-Id value: %r", telegram_id_header)
        return "", NO_ACCESS_ROLE, ""

    logger.info("_resolve_user_db: resolving telegram_id=%s", telegram_id)

    user = await get_user_by_telegram_id(db, telegram_id)
    if user is None:
        logger.info(
            "_resolve_user_db: telegram_id=%s not found or inactive → deny",
            telegram_id,
        )
        return "", NO_ACCESS_ROLE, ""

    role_code = await get_role_code(db, user.role_id)
    if not role_code:
        logger.warning(
            "_resolve_user_db: telegram_id=%s app_user_id=%s has unknown role_id=%s → deny",
            telegram_id,
            user.id,
            user.role_id,
        )
        return "", NO_ACCESS_ROLE, ""

    logger.info(
        "_resolve_user_db: telegram_id=%s app_user_id=%s role=%r full_name=%r → allow",
        telegram_id,
        user.id,
        role_code,
        user.full_name,
    )
    return str(telegram_id), role_code, user.full_name


def _resolve_user_legacy(init_data: Optional[str]) -> tuple:
    """
    Fallback resolution from Telegram initData header (legacy path).

    Used only when X-Telegram-Id header is absent.
    Falls back to ("", NO_ACCESS_ROLE, "") on failure.
    """
    if not init_data:
        return "", NO_ACCESS_ROLE, ""
    user = extract_user_from_init_data(init_data)
    if not user:
        return "", NO_ACCESS_ROLE, ""
    user_id = str(user.get("id", ""))
    role = settings_service.get_user_role(user_id) if user_id else NO_ACCESS_ROLE
    full_name = settings_service.get_user_full_name(user_id) if user_id else ""
    return user_id, role, full_name


async def _resolve_user(
    db: AsyncSession,
    x_telegram_id: Optional[str],
    x_telegram_init_data: Optional[str],
) -> tuple:
    """
    Unified user resolution:
    1. Try X-Telegram-Id header → app_users table (primary, secure path).
    2. Fall back to X-Telegram-Init-Data header (legacy Sheets path).

    Always returns (user_id_str, role_code, full_name).
    """
    if x_telegram_id:
        return await _resolve_user_db(db, x_telegram_id)
    return _resolve_user_legacy(x_telegram_init_data)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/create", response_model=dict)
async def create_deal(
    deal: DealCreate,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Create a new deal (requires manager role or higher)."""
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        log_user_id = user_id or x_telegram_id or "no-id"
        logger.info(
            "POST /deal/create DENIED: user_id=%r resolved_role=%r — "
            "user not found in app_users or not active",
            log_user_id,
            role,
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Access denied: user not found or not active. "
                "Please log in via /auth/miniapp-login first."
            ),
        )

    logger.info(
        "POST /deal/create ALLOWED: user_id=%s role=%r full_name=%r",
        user_id,
        role,
        full_name,
    )

    try:
        deal_id = deals_service.create_deal(
            deal_data=deal.model_dump(),
            telegram_user_id=user_id,
            user_role=role,
            full_name=full_name,
        )
        return {"success": True, "deal_id": deal_id}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error creating deal: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error creating deal: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/all", response_model=list)
async def get_all_deals(
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> list:
    """Return all deals (accountant / director / head_of_sales only)."""
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data)

    if not can_see_all_deals(role):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return deals_service.get_all_deals()
    except SheetsError as exc:
        logger.error("Sheets error fetching all deals: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/user", response_model=list)
async def get_user_deals(
    manager: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> list:
    """
    Return deals for the current user.
    Managers see only their own deals; higher roles may pass ?manager= to filter.
    """
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        if role == "manager":
            return deals_service.get_deals_by_user(full_name) if full_name else []
        if manager:
            return deals_service.get_deals_by_user(manager)
        return deals_service.get_all_deals()
    except SheetsError as exc:
        logger.error("Sheets error fetching deals: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/filter", response_model=list)
async def get_deals_filtered(
    manager: Optional[str] = None,
    client: Optional[str] = None,
    status: Optional[str] = None,
    business_direction: Optional[str] = None,
    month: Optional[str] = None,
    paid: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> list:
    """Filter deals by various criteria."""
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    filters: dict = {}
    if manager is not None:
        filters["manager"] = manager
    if client is not None:
        filters["client"] = client
    if status is not None:
        filters["status"] = status
    if business_direction is not None:
        filters["business_direction"] = business_direction
    if month is not None:
        filters["month"] = month
    if paid is not None:
        filters["paid"] = paid

    if role == "manager" and full_name:
        filters["manager"] = full_name

    try:
        return deals_service.get_deals_filtered(filters)
    except SheetsError as exc:
        logger.error("Sheets error filtering deals: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{deal_id}", response_model=dict)
async def get_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Get a single deal by ID."""
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        deal = deals_service.get_deal_by_id(deal_id)
    except SheetsError as exc:
        logger.error("Sheets error fetching deal %s: %s", deal_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")

    if role == "manager" and deal.get("manager") != full_name:
        raise HTTPException(status_code=403, detail="Access denied")

    return deal


@router.put("/{deal_id}", response_model=dict)
async def update_deal(
    deal_id: str,
    update: DealUpdate,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Update an existing deal (role-based field permissions enforced)."""
    return await _do_update_deal(deal_id, update, db, x_telegram_id, x_telegram_init_data)


@router.patch("/update/{deal_id}", response_model=dict)
async def patch_deal(
    deal_id: str,
    update: DealUpdate,
    db: AsyncSession = Depends(get_db),
    x_telegram_id: Optional[str] = Header(default=None),
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> dict:
    """Partially update an existing deal — 2-step workflow."""
    return await _do_update_deal(deal_id, update, db, x_telegram_id, x_telegram_init_data)


async def _do_update_deal(
    deal_id: str,
    update: DealUpdate,
    db: AsyncSession,
    x_telegram_id: Optional[str],
    x_telegram_init_data: Optional[str],
) -> dict:
    user_id, role, full_name = await _resolve_user(db, x_telegram_id, x_telegram_init_data)

    if role == NO_ACCESS_ROLE:
        raise HTTPException(status_code=403, detail="Access denied")

    update_data = {k: v for k, v in update.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=422, detail="No fields to update")

    if role == "manager":
        try:
            deal = deals_service.get_deal_by_id(deal_id)
        except SheetsError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if deal is None:
            raise HTTPException(status_code=404, detail="Deal not found")
        if deal.get("manager") != full_name:
            append_journal_entry(
                telegram_user_id=user_id,
                full_name=full_name,
                user_role=role,
                action="forbidden_update_attempt",
                deal_id=deal_id,
                payload_summary="Manager attempted to update another manager's deal",
            )
            raise HTTPException(status_code=403, detail="Access denied")

    try:
        success = deals_service.update_deal(
            deal_id=deal_id,
            update_data=update_data,
            telegram_user_id=user_id,
            user_role=role,
            full_name=full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SheetsError as exc:
        logger.error("Sheets error updating deal %s: %s", deal_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error updating deal %s: %s", deal_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    if not success:
        raise HTTPException(status_code=404, detail="Deal not found")

    return {"success": True, "deal_id": deal_id}

