from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards import main_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start command — greet user and show Mini App button."""
    await message.answer(
        text=(
            "👋 Добро пожаловать в систему учёта сделок!\n\n"
            "Нажмите кнопку ниже, чтобы открыть приложение."
        ),
        reply_markup=main_keyboard(),
    )
