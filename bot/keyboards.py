from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)

from config.config import settings


def main_keyboard() -> ReplyKeyboardMarkup:
    """Return reply keyboard with a button that opens the Mini App."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📊 Открыть систему учёта",
                    web_app=WebAppInfo(url=settings.mini_app_url),
                )
            ]
        ],
        resize_keyboard=True,
    )
