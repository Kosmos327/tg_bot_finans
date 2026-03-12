"""
Tests for src/settings_parser.py

Run with:  pytest tests/test_settings_parser.py -v
"""

import sys
import os

# Allow importing from src/ without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from settings_parser import (
    SettingsParser,
    _is_empty_row,
    _normalise_bool,
    _normalise_int,
    _normalise_text,
    _parse_roles_block,
    _parse_simple_block,
    _row_as_header,
)


# ---------------------------------------------------------------------------
# Helper / normalisation unit tests
# ---------------------------------------------------------------------------


class TestNormaliseText:
    def test_strips_leading_trailing_whitespace(self):
        assert _normalise_text("  hello  ") == "hello"

    def test_collapses_internal_whitespace(self):
        assert _normalise_text("hello   world") == "hello world"

    def test_handles_tabs_and_newlines(self):
        assert _normalise_text("hello\t\nworld") == "hello world"

    def test_non_string_input(self):
        assert _normalise_text(42) == "42"

    def test_none_input(self):
        assert _normalise_text(None) == ""

    def test_empty_string(self):
        assert _normalise_text("") == ""


class TestNormaliseBool:
    @pytest.mark.parametrize(
        "value",
        ["TRUE", "true", "True", "  TRUE  ", "1", "YES", "yes", "Yes", "ДА", "да", "Y", "y"],
    )
    def test_truthy_values(self, value):
        assert _normalise_bool(value) is True

    @pytest.mark.parametrize(
        "value",
        ["FALSE", "false", "0", "NO", "no", "НЕТ", "", "  ", "nope"],
    )
    def test_falsy_values(self, value):
        assert _normalise_bool(value) is False


class TestNormaliseInt:
    def test_valid_integer_string(self):
        assert _normalise_int("123456789") == 123456789

    def test_integer_with_whitespace(self):
        assert _normalise_int("  42  ") == 42

    def test_float_string_is_invalid(self):
        assert _normalise_int("3.14") is None

    def test_empty_string_returns_none(self):
        assert _normalise_int("") is None

    def test_whitespace_only_returns_none(self):
        assert _normalise_int("   ") is None

    def test_non_numeric_returns_none(self):
        assert _normalise_int("abc") is None

    def test_actual_int_input(self):
        assert _normalise_int(99) == 99


class TestIsEmptyRow:
    def test_all_empty_strings(self):
        assert _is_empty_row(["", "", ""]) is True

    def test_all_whitespace(self):
        assert _is_empty_row(["  ", "\t", "\n"]) is True

    def test_empty_list(self):
        assert _is_empty_row([]) is True

    def test_row_with_content(self):
        assert _is_empty_row(["", "value", ""]) is False

    def test_row_with_only_non_empty_first_cell(self):
        assert _is_empty_row(["value"]) is False


class TestRowAsHeader:
    def test_known_header(self):
        assert _row_as_header(["Статусы", "", ""]) == "статусы"

    def test_known_header_case_insensitive(self):
        assert _row_as_header(["СТАТУСЫ"]) == "статусы"

    def test_known_header_with_extra_whitespace(self):
        assert _row_as_header(["  Статусы  "]) == "статусы"

    def test_known_multiword_header(self):
        assert _row_as_header(["Направления бизнеса"]) == "направления бизнеса"

    def test_unknown_header_returns_none(self):
        assert _row_as_header(["Unknown header"]) is None

    def test_empty_row_returns_none(self):
        assert _row_as_header([]) is None

    def test_all_empty_cells_returns_none(self):
        assert _row_as_header(["", "  ", ""]) is None

    @pytest.mark.parametrize(
        "header",
        [
            "Статусы",
            "Направления бизнеса",
            "Клиенты",
            "Менеджеры",
            "НДС",
            "Источники",
            "Роли",
        ],
    )
    def test_all_known_headers(self, header):
        assert _row_as_header([header]) is not None


# ---------------------------------------------------------------------------
# Block parser unit tests
# ---------------------------------------------------------------------------


class TestParseSimpleBlock:
    def test_basic_values(self):
        rows = [["Статус A"], ["Статус B"], ["Статус C"]]
        assert _parse_simple_block(rows) == ["Статус A", "Статус B", "Статус C"]

    def test_skips_empty_rows(self):
        rows = [["A"], [""], ["B"], ["  "], ["C"]]
        assert _parse_simple_block(rows) == ["A", "B", "C"]

    def test_normalises_whitespace(self):
        rows = [["  hello   world  "]]
        assert _parse_simple_block(rows) == ["hello world"]

    def test_empty_block(self):
        assert _parse_simple_block([]) == []

    def test_only_empty_rows(self):
        assert _parse_simple_block([[""], ["  "]]) == []


class TestParseRolesBlock:
    def _make_rows(self, *entries):
        return [list(e) for e in entries]

    def test_parses_valid_row(self):
        rows = self._make_rows(["123456789", "Иван Иванов", "manager", "TRUE"])
        result = _parse_roles_block(rows)
        assert result == [
            {
                "telegram_user_id": 123456789,
                "full_name": "Иван Иванов",
                "role": "manager",
                "active": True,
            }
        ]

    def test_active_false(self):
        rows = self._make_rows(["111", "Test User", "admin", "FALSE"])
        result = _parse_roles_block(rows)
        assert result[0]["active"] is False

    def test_role_lowercased(self):
        rows = self._make_rows(["222", "User", "MANAGER", "TRUE"])
        result = _parse_roles_block(rows)
        assert result[0]["role"] == "manager"

    def test_skips_column_header_row(self):
        rows = self._make_rows(
            ["telegram_user_id", "full_name", "role", "active"],
            ["333", "Some Name", "user", "TRUE"],
        )
        result = _parse_roles_block(rows)
        assert len(result) == 1
        assert result[0]["telegram_user_id"] == 333

    def test_skips_empty_rows(self):
        rows = self._make_rows(
            ["111", "User 1", "admin", "TRUE"],
            ["", "", "", ""],
            ["222", "User 2", "manager", "FALSE"],
        )
        result = _parse_roles_block(rows)
        assert len(result) == 2

    def test_invalid_telegram_user_id_becomes_none(self):
        rows = self._make_rows(["not_a_number", "User", "role", "TRUE"])
        result = _parse_roles_block(rows)
        assert result[0]["telegram_user_id"] is None

    def test_short_row_padded_safely(self):
        rows = self._make_rows(["999"])
        result = _parse_roles_block(rows)
        assert result[0]["telegram_user_id"] == 999
        assert result[0]["full_name"] == ""
        assert result[0]["role"] == ""
        assert result[0]["active"] is False

    def test_normalises_whitespace_in_full_name(self):
        rows = self._make_rows(["555", "  Иван   Иванов  ", "admin", "TRUE"])
        result = _parse_roles_block(rows)
        assert result[0]["full_name"] == "Иван Иванов"

    def test_multiple_roles(self):
        rows = self._make_rows(
            ["1", "Alice", "admin", "TRUE"],
            ["2", "Bob", "manager", "FALSE"],
            ["3", "Carol", "user", "TRUE"],
        )
        result = _parse_roles_block(rows)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# SettingsParser integration tests
# ---------------------------------------------------------------------------


class TestSettingsParser:
    def setup_method(self):
        self.parser = SettingsParser()

    # --- Minimal sheet ---

    def test_empty_sheet_returns_empty_lists(self):
        payload = self.parser.parse([])
        assert payload == {
            "statuses": [],
            "business_directions": [],
            "clients": [],
            "managers": [],
            "vat_types": [],
            "sources": [],
            "roles": [],
        }

    # --- All blocks present ---

    def test_full_sheet_all_blocks(self):
        rows = [
            ["Статусы"],
            ["Новый"],
            ["В работе"],
            [""],
            ["Направления бизнеса"],
            ["Торговля"],
            ["Услуги"],
            [""],
            ["Клиенты"],
            ["ООО Ромашка"],
            [""],
            ["Менеджеры"],
            ["Иванов"],
            [""],
            ["НДС"],
            ["20%"],
            [""],
            ["Источники"],
            ["Сайт"],
            [""],
            ["Роли"],
            ["telegram_user_id", "full_name", "role", "active"],
            ["123", "Admin User", "admin", "TRUE"],
            ["456", "Regular User", "user", "FALSE"],
        ]
        payload = self.parser.parse(rows)

        assert payload["statuses"] == ["Новый", "В работе"]
        assert payload["business_directions"] == ["Торговля", "Услуги"]
        assert payload["clients"] == ["ООО Ромашка"]
        assert payload["managers"] == ["Иванов"]
        assert payload["vat_types"] == ["20%"]
        assert payload["sources"] == ["Сайт"]
        assert len(payload["roles"]) == 2
        assert payload["roles"][0] == {
            "telegram_user_id": 123,
            "full_name": "Admin User",
            "role": "admin",
            "active": True,
        }
        assert payload["roles"][1] == {
            "telegram_user_id": 456,
            "full_name": "Regular User",
            "role": "user",
            "active": False,
        }

    # --- Spacing rows ---

    def test_ignores_blank_rows_between_blocks(self):
        rows = [
            [""],
            ["  "],
            ["Статусы"],
            [""],
            ["Статус 1"],
            ["  "],
            ["Статус 2"],
        ]
        payload = self.parser.parse(rows)
        assert payload["statuses"] == ["Статус 1", "Статус 2"]

    # --- Partial sheet (only some blocks) ---

    def test_missing_blocks_default_to_empty_list(self):
        rows = [
            ["Статусы"],
            ["Готово"],
        ]
        payload = self.parser.parse(rows)
        assert payload["statuses"] == ["Готово"]
        assert payload["roles"] == []
        assert payload["clients"] == []

    # --- Case / whitespace normalisation in headers ---

    def test_header_case_insensitive(self):
        rows = [
            ["СТАТУСЫ"],
            ["Active"],
        ]
        payload = self.parser.parse(rows)
        assert payload["statuses"] == ["Active"]

    def test_header_extra_whitespace(self):
        rows = [
            ["  Клиенты  "],
            ["Client A"],
        ]
        payload = self.parser.parse(rows)
        assert payload["clients"] == ["Client A"]

    # --- Rows before first block header ---

    def test_rows_before_first_header_are_ignored(self):
        rows = [
            ["Какой-то заголовок документа"],
            [""],
            ["Статусы"],
            ["Активен"],
        ]
        payload = self.parser.parse(rows)
        assert payload["statuses"] == ["Активен"]

    # --- Values whitespace normalisation ---

    def test_value_whitespace_normalised(self):
        rows = [
            ["Статусы"],
            ["  Статус   с   пробелами  "],
        ]
        payload = self.parser.parse(rows)
        assert payload["statuses"] == ["Статус с пробелами"]

    # --- Roles block: active field variants ---

    def test_roles_active_true_variants(self):
        rows = [
            ["Роли"],
        ] + [
            [str(i), f"User {i}", "user", v]
            for i, v in enumerate(["true", "1", "YES", "yes", "ДА"], start=1)
        ]
        payload = self.parser.parse(rows)
        assert all(r["active"] is True for r in payload["roles"])

    def test_roles_active_false_variants(self):
        rows = [
            ["Роли"],
        ] + [
            [str(i), f"User {i}", "user", v]
            for i, v in enumerate(["false", "0", "NO", ""], start=1)
        ]
        payload = self.parser.parse(rows)
        assert all(r["active"] is False for r in payload["roles"])

    # --- Extensibility: unknown block headers are ignored ---

    def test_unknown_block_header_is_silently_ignored(self):
        rows = [
            ["Неизвестный блок"],
            ["Какое-то значение"],
            ["Статусы"],
            ["Верный статус"],
        ]
        payload = self.parser.parse(rows)
        assert payload["statuses"] == ["Верный статус"]
        # All standard keys still present and other blocks empty
        assert payload["clients"] == []
