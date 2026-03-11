from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config.config import settings


def get_main_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(
            text="🚀 Открыть Mini App",
            web_app=WebAppInfo(url=settings.webapp_url),
        )
    )
    builder.row(
        KeyboardButton(text="📋 Мои сделки"),
        KeyboardButton(text="ℹ️ Помощь"),
    )
    return builder.as_markup(resize_keyboard=True)


def get_inline_webapp_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🚀 Открыть Mini App",
            web_app=WebAppInfo(url=settings.webapp_url),
        )
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои сделки", callback_data="my_deals"),
        InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
    )
    return builder.as_markup()
