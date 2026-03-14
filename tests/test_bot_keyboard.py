"""Tests for the bot keyboard Mini App button."""

from __future__ import annotations

import sys
import os

import pytest

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


WEBAPP_URL = "https://example.com/miniapp"


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """Patch settings.webapp_url before importing keyboards."""
    monkeypatch.setenv("WEBAPP_URL", WEBAPP_URL)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost:5432/test")

    # Reload settings and keyboards with the patched env
    import importlib
    import config.config as cfg_module
    cfg_module.settings = cfg_module.Settings()

    import bot.keyboards as kb_module
    importlib.reload(kb_module)

    yield kb_module


class TestMainKeyboard:
    """Tests for get_main_keyboard()."""

    def test_contains_open_app_button(self, patch_settings):
        kb = patch_settings
        keyboard = kb.get_main_keyboard()
        all_buttons = [btn for row in keyboard.keyboard for btn in row]
        texts = [btn.text for btn in all_buttons]
        assert "Открыть приложение" in texts, (
            "Main keyboard must contain a button with text 'Открыть приложение'"
        )

    def test_open_app_button_uses_webapp_info(self, patch_settings):
        kb = patch_settings
        keyboard = kb.get_main_keyboard()
        all_buttons = [btn for row in keyboard.keyboard for btn in row]
        app_button = next(
            (btn for btn in all_buttons if btn.text == "Открыть приложение"), None
        )
        assert app_button is not None, "Button 'Открыть приложение' not found"
        assert app_button.web_app is not None, (
            "Button 'Открыть приложение' must have web_app (WebAppInfo)"
        )
        assert app_button.web_app.url == WEBAPP_URL, (
            f"web_app.url must equal WEBAPP_URL ({WEBAPP_URL})"
        )

    def test_existing_buttons_preserved(self, patch_settings):
        kb = patch_settings
        keyboard = kb.get_main_keyboard()
        all_buttons = [btn for row in keyboard.keyboard for btn in row]
        texts = [btn.text for btn in all_buttons]
        assert "📋 Мои сделки" in texts, "Existing '📋 Мои сделки' button must be preserved"
        assert "ℹ️ Помощь" in texts, "Existing 'ℹ️ Помощь' button must be preserved"


class TestInlineWebappKeyboard:
    """Tests for get_inline_webapp_keyboard()."""

    def test_contains_open_app_button(self, patch_settings):
        kb = patch_settings
        keyboard = kb.get_inline_webapp_keyboard()
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        texts = [btn.text for btn in all_buttons]
        assert "Открыть приложение" in texts, (
            "Inline keyboard must contain a button with text 'Открыть приложение'"
        )

    def test_open_app_button_uses_webapp_info(self, patch_settings):
        kb = patch_settings
        keyboard = kb.get_inline_webapp_keyboard()
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        app_button = next(
            (btn for btn in all_buttons if btn.text == "Открыть приложение"), None
        )
        assert app_button is not None, "Button 'Открыть приложение' not found"
        assert app_button.web_app is not None, (
            "Button 'Открыть приложение' must have web_app (WebAppInfo)"
        )
        assert app_button.web_app.url == WEBAPP_URL, (
            f"web_app.url must equal WEBAPP_URL ({WEBAPP_URL})"
        )
