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
    """Create a new deal and log the action.

    Args:
        deal_data: Field values for the new deal.
        telegram_user_id: Telegram user ID for the audit log.
        user_role: Role of the user creating the deal.
        full_name: Full name of the user creating the deal.

    Returns:
        The newly generated deal ID string.
    """
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
    """Update a deal and log the action.

    Args:
        deal_id: ID of the deal to update.
        update_data: Fields to update (role-level permissions enforced).
        telegram_user_id: Telegram user ID for the audit log.
        user_role: Role of the user performing the update.
        full_name: Full name of the user performing the update.

    Returns:
        True if the deal was found and updated, False if not found.
    """
    return deals_service.update_deal(
        deal_id=deal_id,
        update_data=update_data,
        telegram_user_id=telegram_user_id,
        user_role=user_role,
        full_name=full_name,
    )
