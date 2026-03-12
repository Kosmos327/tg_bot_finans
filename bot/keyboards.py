from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from config.config import settings


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=settings.webapp_url))],
            [KeyboardButton(text="📋 Мои сделки"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def get_inline_webapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=settings.webapp_url))],
            [
                InlineKeyboardButton(text="📋 Мои сделки", callback_data="my_deals"),
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
            ],
        ]
    )
