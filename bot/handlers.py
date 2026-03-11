"""
Telegram bot handlers for tg_bot_finans.
"""

import logging

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from backend.config import MINI_APP_URL, ROLE_LABELS_RU
from backend.services.sheets import get_user_info
from bot.keyboards import main_keyboard, no_access_keyboard, quick_access_keyboard

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Welcome messages per role
# ---------------------------------------------------------------------------

WELCOME_MESSAGES = {
    "manager": (
        "👋 Добро пожаловать, {name}!\n\n"
        "🏷 Ваша роль: *Менеджер*\n\n"
        "Вы можете создавать и отслеживать свои сделки.\n"
        "Нажмите кнопку ниже, чтобы открыть систему."
    ),
    "accountant": (
        "👋 Добро пожаловать, {name}!\n\n"
        "🏷 Ваша роль: *Бухгалтер*\n\n"
        "Вы управляете оплатами, расходами и закрытием сделок.\n"
        "Нажмите кнопку ниже, чтобы открыть систему."
    ),
    "operations_director": (
        "👋 Добро пожаловать, {name}!\n\n"
        "🏷 Ваша роль: *Операционный директор*\n\n"
        "Вам доступна полная аналитика и управление компанией.\n"
        "Нажмите кнопку ниже, чтобы открыть систему."
    ),
    "head_of_sales": (
        "👋 Добро пожаловать, {name}!\n\n"
        "🏷 Ваша роль: *Руководитель отдела продаж*\n\n"
        "Вам доступен контроль команды, воронка и аналитика.\n"
        "Нажмите кнопку ниже, чтобы открыть систему."
    ),
}

NO_ACCESS_MESSAGE = (
    "👋 Здравствуйте, {name}!\n\n"
    "⛔️ К сожалению, у вас нет доступа к системе.\n\n"
    "Обратитесь к администратору для получения прав."
)

HELP_TEXT = (
    "ℹ️ *Помощь*\n\n"
    "Это внутренняя система управления сделками.\n\n"
    "Для получения доступа обратитесь к вашему руководителю "
    "или администратору системы.\n\n"
    "Роли в системе:\n"
    "• *Менеджер* — создание и ведение собственных сделок\n"
    "• *Бухгалтер* — учёт оплат и расходов\n"
    "• *Операционный директор* — полный доступ и аналитика\n"
    "• *Руководитель отдела продаж* — контроль команды и воронка"
)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tg_id = user.id
    first_name = user.first_name or "пользователь"

    user_info = get_user_info(tg_id)

    if (
        user_info
        and user_info.active.lower() in ("1", "true", "yes", "да")
        and user_info.role
    ):
        role = user_info.role.strip()
        full_name = user_info.full_name or first_name
        template = WELCOME_MESSAGES.get(role, "👋 Добро пожаловать, {name}!")
        text = template.format(name=full_name)
        keyboard = main_keyboard(role, MINI_APP_URL)
    else:
        text = NO_ACCESS_MESSAGE.format(name=first_name)
        keyboard = no_access_keyboard()

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Callback query handlers
# ---------------------------------------------------------------------------

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    user_info = get_user_info(tg_id)
    role = (
        user_info.role.strip()
        if user_info and user_info.active.lower() in ("1", "true", "yes", "да")
        else None
    )

    data = query.data

    if data == "help":
        await query.edit_message_text(HELP_TEXT, parse_mode="Markdown")

    elif data == "quick_access":
        if role:
            role_label = ROLE_LABELS_RU.get(role, role)
            await query.edit_message_text(
                f"⚡️ Быстрый доступ — *{role_label}*\n\nВыберите раздел:",
                parse_mode="Markdown",
                reply_markup=quick_access_keyboard(role, MINI_APP_URL),
            )
        else:
            await query.edit_message_text("⛔️ Нет доступа.", parse_mode="Markdown")

    elif data == "back_to_main":
        first_name = query.from_user.first_name or "пользователь"
        if role:
            full_name = (user_info.full_name if user_info else None) or first_name
            template = WELCOME_MESSAGES.get(role, "👋 Добро пожаловать, {name}!")
            text = template.format(name=full_name)
            keyboard = main_keyboard(role, MINI_APP_URL)
        else:
            text = NO_ACCESS_MESSAGE.format(name=first_name)
            keyboard = no_access_keyboard()
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Handler registration helper
# ---------------------------------------------------------------------------

def register_handlers(application) -> None:
    """Register all bot handlers onto an Application instance."""
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))
