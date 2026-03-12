"""
Telegram bot entry point for tg_bot_finans.
"""

import logging
import os

from telegram.ext import Application

from backend.config import BOT_TOKEN
from bot.handlers import register_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    application = Application.builder().token(BOT_TOKEN).build()
    register_handlers(application)

    logger.info("Bot started. Polling...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
