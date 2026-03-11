"""
Entry point for the Telegram financial bot.

Usage
-----
Set the following environment variables (or add them to a ``.env`` file):

    BOT_TOKEN=<telegram bot token>
    SPREADSHEET_ID=<google spreadsheet id>
    GOOGLE_CREDENTIALS_FILE=credentials.json   # default
    DEALS_SHEET=Сделки                         # default
    JOURNAL_SHEET=Журнал действий              # default
    DEAL_ID_PREFIX=DEAL-                       # default
    REQUIRED_DEAL_FIELDS=Название,Клиент,Сумма # default

Then run::

    python bot.py
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from routers.deal_router import router as deal_router
from services.sheets_service import build_client, open_spreadsheet

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def main() -> None:
    client = build_client(config.GOOGLE_CREDENTIALS_FILE)
    spreadsheet = open_spreadsheet(client, config.SPREADSHEET_ID)

    deals_ws = spreadsheet.worksheet(config.DEALS_SHEET)
    journal_ws = spreadsheet.worksheet(config.JOURNAL_SHEET)

    bot = Bot(token=config.BOT_TOKEN)
    bot.data["deals_ws"] = deals_ws
    bot.data["journal_ws"] = journal_ws
    bot.data["required_fields"] = config.REQUIRED_DEAL_FIELDS
    bot.data["id_prefix"] = config.DEAL_ID_PREFIX

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(deal_router)

    log.info("Bot starting …")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
