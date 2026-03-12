import logging
from typing import Optional

from backend.services import deals_service, journal_service

logger = logging.getLogger(__name__)


def create_deal(
    deal_data: dict,
    telegram_user_id: str = "",
    user_role: str = "",
    full_name: str = "",
) -> str:
    """Create a new deal and log the action. Returns deal_id."""
    return deals_service.create_deal(
        deal_data=deal_data,
        telegram_user_id=telegram_user_id,
        user_role=user_role,
        full_name=full_name,
    )


def get_user_deals(manager_name: Optional[str] = None) -> list:
    """Get deals, optionally filtered by manager name."""
    if manager_name:
        return deals_service.get_deals_by_user(manager_name)
    return deals_service.get_all_deals()


def get_deal_by_id(deal_id: str) -> Optional[dict]:
    """Get a single deal by ID."""
    return deals_service.get_deal_by_id(deal_id)


def update_deal(
    deal_id: str,
    update_data: dict,
    telegram_user_id: str = "",
    user_role: str = "",
    full_name: str = "",
) -> bool:
    """Update a deal and log the action."""
    return deals_service.update_deal(
        deal_id=deal_id,
        update_data=update_data,
        telegram_user_id=telegram_user_id,
        user_role=user_role,
        full_name=full_name,
    )
