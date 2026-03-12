"""
Telegram bot keyboards for tg_bot_finans.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from backend.config import MINI_APP_URL, ROLE_LABELS_RU


def main_keyboard(role: str, mini_app_url: str = MINI_APP_URL) -> InlineKeyboardMarkup:
    """Main keyboard shown after /start for a user with a known role."""
    role_label = ROLE_LABELS_RU.get(role, role)
    buttons = [
        [
            InlineKeyboardButton(
                text="🚀 Открыть систему",
                web_app={"url": mini_app_url},
            )
        ],
        [
            InlineKeyboardButton(text="📋 Быстрый доступ", callback_data="quick_access"),
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def no_access_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown when user has no role configured."""
    buttons = [
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(buttons)


def quick_access_keyboard(role: str, mini_app_url: str = MINI_APP_URL) -> InlineKeyboardMarkup:
    """Role-specific quick-access shortcuts."""
    buttons_by_role = {
        "manager": [
            [InlineKeyboardButton("➕ Новая сделка", web_app={"url": f"{mini_app_url}#new_deal"})],
            [InlineKeyboardButton("📂 Мои сделки", web_app={"url": f"{mini_app_url}#my_deals"})],
        ],
        "accountant": [
            [InlineKeyboardButton("💳 Оплаты", web_app={"url": f"{mini_app_url}#payments"})],
            [InlineKeyboardButton("📂 Все сделки", web_app={"url": f"{mini_app_url}#all_deals"})],
        ],
        "operations_director": [
            [InlineKeyboardButton("📊 Дашборд", web_app={"url": f"{mini_app_url}#dashboard"})],
            [InlineKeyboardButton("📂 Все сделки", web_app={"url": f"{mini_app_url}#all_deals"})],
        ],
        "head_of_sales": [
            [InlineKeyboardButton("👥 Команда", web_app={"url": f"{mini_app_url}#team"})],
            [InlineKeyboardButton("📈 Воронка", web_app={"url": f"{mini_app_url}#funnel"})],
        ],
    }
    role_buttons = buttons_by_role.get(role, [])
    role_buttons.append(
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    )
    return InlineKeyboardMarkup(role_buttons)
