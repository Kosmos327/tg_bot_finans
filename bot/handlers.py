from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from bot.keyboards import get_main_keyboard, get_inline_webapp_keyboard

router = Router()

WELCOME_TEXT = (
    "👋 <b>Добро пожаловать в Финансовую систему!</b>\n\n"
    "Это приложение для учёта сделок и финансовых операций.\n\n"
    "📌 <b>Что умеет система:</b>\n"
    "• Создавать и вести учёт сделок\n"
    "• Отслеживать финансовые показатели\n"
    "• Работать с Google Sheets в реальном времени\n\n"
    "Нажмите <b>Открыть приложение</b>, чтобы начать работу."
)

HELP_TEXT = (
    "ℹ️ <b>Справка по системе</b>\n\n"
    "<b>Открыть приложение</b> — запуск полного интерфейса системы\n"
    "<b>📋 Мои сделки</b> — просмотр ваших сделок\n\n"
    "<b>Возможности Mini App:</b>\n"
    "• 🆕 Создание новых сделок\n"
    "• 📂 Просмотр и фильтрация сделок\n"
    "• ⚙️ Настройки и справочники\n\n"
    "По вопросам обращайтесь к администратору системы."
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        text=WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def handle_help(message: Message) -> None:
    await message.answer(
        text=HELP_TEXT,
        parse_mode="HTML",
        reply_markup=get_inline_webapp_keyboard(),
    )


@router.message(F.text == "📋 Мои сделки")
async def handle_my_deals(message: Message) -> None:
    await message.answer(
        text=(
            "📋 <b>Ваши сделки</b>\n\n"
            "Для просмотра и управления сделками откройте Mini App:"
        ),
        parse_mode="HTML",
        reply_markup=get_inline_webapp_keyboard(),
    )


@router.callback_query(F.data == "my_deals")
async def handle_my_deals_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        text=(
            "📋 <b>Ваши сделки</b>\n\n"
            "Для просмотра и управления сделками откройте Mini App:"
        ),
        parse_mode="HTML",
        reply_markup=get_inline_webapp_keyboard(),
    )


@router.callback_query(F.data == "help")
async def handle_help_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        text=HELP_TEXT,
        parse_mode="HTML",
    )
