import logging

from backend.services import sheets_service

logger = logging.getLogger(__name__)


def append_entry(
    telegram_user_id: str,
    action: str,
    deal_id: str = "",
    payload_summary: str = "",
) -> None:
    """Convenience wrapper around sheets_service.append_journal_entry."""
    sheets_service.append_journal_entry(
        telegram_user_id=telegram_user_id,
        action=action,
        deal_id=deal_id,
        payload_summary=payload_summary,
    )
