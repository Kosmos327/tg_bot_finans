import logging
from typing import Optional

from backend.services import sheets_service

logger = logging.getLogger(__name__)


def create_deal(deal_data: dict, telegram_user_id: str = "") -> str:
    """Create a new deal and log the action. Returns deal_id."""
    deal_id = sheets_service.create_deal(deal_data)
    sheets_service.append_journal_entry(
        telegram_user_id=telegram_user_id,
        action="create_deal",
        deal_id=deal_id,
        payload_summary=(
            f"client={deal_data.get('client', '')}, "
            f"status={deal_data.get('status', '')}, "
            f"charged_with_vat={deal_data.get('charged_with_vat', '')}"
        ),
    )
    return deal_id


def get_user_deals(manager_name: Optional[str] = None) -> list:
    """Get deals, optionally filtered by manager name."""
    return sheets_service.get_user_deals(manager_name=manager_name)


def get_deal_by_id(deal_id: str) -> Optional[dict]:
    """Get a single deal by ID."""
    return sheets_service.get_deal_by_id(deal_id)


def update_deal(deal_id: str, update_data: dict, telegram_user_id: str = "") -> bool:
    """Update a deal and log the action."""
    success = sheets_service.update_deal(deal_id, update_data)
    if success:
        sheets_service.append_journal_entry(
            telegram_user_id=telegram_user_id,
            action="update_deal",
            deal_id=deal_id,
            payload_summary=str(list(update_data.keys())),
        )
    return success
