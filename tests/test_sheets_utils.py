"""
Tests for pure helper functions in the Google Sheets service layer.
These tests do NOT require a live Google Sheets connection.
"""

import pytest

# ---------------------------------------------------------------------------
# deals_service helpers
# ---------------------------------------------------------------------------
from backend.services.deals_service import (
    generate_next_deal_id,
    parse_deal_id_number,
    format_deal_id,
    normalise_date,
    _col_index_to_letter,
    _matches_filters,
)

# ---------------------------------------------------------------------------
# sheets_service helpers
# ---------------------------------------------------------------------------
from backend.services.sheets_service import (
    row_to_dict,
    dict_to_row,
    normalise_header,
    safe_float,
    safe_optional_float,
)

# ---------------------------------------------------------------------------
# settings_service helpers
# ---------------------------------------------------------------------------
from backend.services.settings_service import parse_settings_sheet

# ---------------------------------------------------------------------------
# permissions helpers
# ---------------------------------------------------------------------------
from backend.services.permissions import (
    filter_update_payload,
    get_editable_fields,
    can_see_all_deals,
    ALLOWED_ROLES,
    NO_ACCESS_ROLE,
)


# ===========================================================================
# Deal ID generation
# ===========================================================================


class TestGenerateNextDealId:
    def test_empty_list(self):
        assert generate_next_deal_id([]) == "DEAL-000001"

    def test_single_id(self):
        assert generate_next_deal_id(["DEAL-000001"]) == "DEAL-000002"

    def test_multiple_ids(self):
        ids = ["DEAL-000001", "DEAL-000003", "DEAL-000002"]
        assert generate_next_deal_id(ids) == "DEAL-000004"

    def test_ignores_malformed_ids(self):
        ids = ["DEAL-000001", "INVALID", "", "DEAL-ABC", "DEAL-000005"]
        assert generate_next_deal_id(ids) == "DEAL-000006"

    def test_format_padding(self):
        assert generate_next_deal_id(["DEAL-000099"]) == "DEAL-000100"

    def test_large_sequence(self):
        assert generate_next_deal_id(["DEAL-999999"]) == "DEAL-1000000"


class TestParseDealIdNumber:
    def test_valid(self):
        assert parse_deal_id_number("DEAL-000042") == 42

    def test_invalid_prefix(self):
        assert parse_deal_id_number("DEAL000042") is None

    def test_non_numeric_suffix(self):
        assert parse_deal_id_number("DEAL-ABC") is None

    def test_empty(self):
        assert parse_deal_id_number("") is None

    def test_none(self):
        assert parse_deal_id_number(None) is None  # type: ignore[arg-type]


class TestFormatDealId:
    def test_padding(self):
        assert format_deal_id(1) == "DEAL-000001"
        assert format_deal_id(999999) == "DEAL-999999"
        assert format_deal_id(1000000) == "DEAL-1000000"


# ===========================================================================
# Date normalisation
# ===========================================================================


class TestNormaliseDate:
    def test_iso_passthrough(self):
        assert normalise_date("2024-03-15") == "2024-03-15"

    def test_dot_format(self):
        assert normalise_date("15.03.2024") == "2024-03-15"

    def test_slash_format(self):
        assert normalise_date("15/03/2024") == "2024-03-15"

    def test_us_format(self):
        assert normalise_date("03/15/2024") == "2024-03-15"

    def test_unknown_format_passthrough(self):
        # Unknown formats are returned as-is
        result = normalise_date("March 2024")
        assert result == "March 2024"

    def test_empty(self):
        assert normalise_date("") == ""

    def test_whitespace(self):
        assert normalise_date("  2024-01-01  ") == "2024-01-01"


# ===========================================================================
# Column index to letter
# ===========================================================================


class TestColIndexToLetter:
    def test_a(self):
        assert _col_index_to_letter(0) == "A"

    def test_z(self):
        assert _col_index_to_letter(25) == "Z"

    def test_aa(self):
        assert _col_index_to_letter(26) == "AA"

    def test_s(self):
        assert _col_index_to_letter(18) == "S"


# ===========================================================================
# sheets_service header-mapping helpers
# ===========================================================================


class TestRowToDict:
    def test_basic(self):
        hmap = {"A": 0, "B": 1, "C": 2}
        row = ["x", "y", "z"]
        result = row_to_dict(hmap, row)
        assert result == {"A": "x", "B": "y", "C": "z"}

    def test_short_row(self):
        hmap = {"A": 0, "B": 1, "C": 2}
        row = ["x"]
        result = row_to_dict(hmap, row)
        assert result["A"] == "x"
        assert result["B"] == ""
        assert result["C"] == ""

    def test_empty_hmap(self):
        assert row_to_dict({}, ["a", "b"]) == {}


class TestDictToRow:
    def test_basic(self):
        hmap = {"A": 0, "B": 1, "C": 2}
        payload = {"A": "x", "B": "y", "C": "z"}
        result = dict_to_row(hmap, payload, ["A", "B", "C"])
        assert result == ["x", "y", "z"]

    def test_none_becomes_empty_string(self):
        hmap = {"A": 0, "B": 1}
        payload = {"A": "x", "B": None}
        result = dict_to_row(hmap, payload, ["A", "B"])
        assert result[1] == ""

    def test_partial_payload(self):
        hmap = {"A": 0, "B": 1, "C": 2}
        payload = {"A": "hello"}
        result = dict_to_row(hmap, payload, ["A", "B", "C"])
        assert result[0] == "hello"
        assert result[1] == ""
        assert result[2] == ""

    def test_empty_ordered_headers(self):
        assert dict_to_row({"A": 0}, {"A": "x"}, []) == []


class TestNormaliseHeader:
    def test_strips_and_lowercases(self):
        assert normalise_header("  ID Сделки  ") == "id сделки"


class TestSafeFloat:
    def test_plain(self):
        assert safe_float("1234.56") == 1234.56

    def test_comma_decimal(self):
        assert safe_float("1234,56") == 1234.56

    def test_space_thousands(self):
        assert safe_float("1 234.56") == 1234.56

    def test_invalid(self):
        assert safe_float("N/A") == 0.0

    def test_empty(self):
        assert safe_float("") == 0.0

    def test_none(self):
        assert safe_float(None) == 0.0  # type: ignore[arg-type]


class TestSafeOptionalFloat:
    def test_valid(self):
        assert safe_optional_float("42.5") == 42.5

    def test_empty_returns_none(self):
        assert safe_optional_float("") is None

    def test_whitespace_returns_none(self):
        assert safe_optional_float("  ") is None


# ===========================================================================
# settings_service parser
# ===========================================================================


_SAMPLE_SETTINGS = [
    ["[Статусы сделок]"],
    ["Новая"],
    ["В работе"],
    [""],
    ["[Направления бизнеса]"],
    ["Фулфилмент"],
    ["Логистика"],
    [""],
    ["[Клиенты]"],
    ["ООО Альфа"],
    [""],
    ["[Менеджеры]"],
    ["Иван"],
    ["Мария"],
    [""],
    ["[Наличие НДС]"],
    ["с НДС"],
    ["без НДС"],
    [""],
    ["[Источники]"],
    ["Входящий"],
    ["Рекомендация"],
    [""],
    ["[Роли пользователей]"],
    ["telegram_user_id | full_name | role | active"],
    ["123456789 | Иван Петров | manager | TRUE"],
    ["987654321 | Анна Смирнова | accountant | FALSE"],
]


class TestParseSettingsSheet:
    def setup_method(self):
        self.result = parse_settings_sheet(_SAMPLE_SETTINGS)

    def test_statuses(self):
        assert self.result["statuses"] == ["Новая", "В работе"]

    def test_business_directions(self):
        assert self.result["business_directions"] == ["Фулфилмент", "Логистика"]

    def test_clients(self):
        assert self.result["clients"] == ["ООО Альфа"]

    def test_managers(self):
        assert self.result["managers"] == ["Иван", "Мария"]

    def test_vat_types(self):
        assert self.result["vat_types"] == ["с НДС", "без НДС"]

    def test_sources(self):
        assert self.result["sources"] == ["Входящий", "Рекомендация"]

    def test_roles_mapping_count(self):
        assert len(self.result["roles_mapping"]) == 2

    def test_roles_mapping_first_entry(self):
        entry = self.result["roles_mapping"][0]
        assert entry["telegram_user_id"] == "123456789"
        assert entry["full_name"] == "Иван Петров"
        assert entry["role"] == "manager"
        assert entry["active"] == "TRUE"

    def test_roles_mapping_second_entry(self):
        entry = self.result["roles_mapping"][1]
        assert entry["telegram_user_id"] == "987654321"
        assert entry["active"] == "FALSE"

    def test_empty_sheet(self):
        result = parse_settings_sheet([])
        for key in ("statuses", "business_directions", "clients", "managers", "vat_types",
                    "sources", "roles_mapping"):
            assert result[key] == []

    def test_unknown_section_ignored(self):
        data = [["[Неизвестная секция]"], ["value1"], [""], *_SAMPLE_SETTINGS]
        result = parse_settings_sheet(data)
        # Known sections still parsed correctly
        assert result["statuses"] == ["Новая", "В работе"]


# ===========================================================================
# permissions helpers
# ===========================================================================


class TestPermissions:
    def test_manager_editable_fields(self):
        fields = get_editable_fields("manager")
        assert "status" in fields
        assert "paid" not in fields

    def test_accountant_editable_fields(self):
        fields = get_editable_fields("accountant")
        assert "paid" in fields
        assert "status" not in fields

    def test_director_editable_all(self):
        fields = get_editable_fields("operations_director")
        assert "status" in fields
        assert "paid" in fields

    def test_no_access_empty(self):
        assert get_editable_fields(NO_ACCESS_ROLE) == set()

    def test_filter_update_payload_manager(self):
        payload = {"status": "Новая", "paid": 1000.0}
        filtered = filter_update_payload("manager", payload)
        assert "status" in filtered
        assert "paid" not in filtered

    def test_filter_update_payload_accountant(self):
        payload = {"status": "Новая", "paid": 1000.0}
        filtered = filter_update_payload("accountant", payload)
        assert "paid" in filtered
        assert "status" not in filtered

    def test_can_see_all_deals(self):
        assert not can_see_all_deals("manager")
        assert can_see_all_deals("accountant")
        assert can_see_all_deals("operations_director")
        assert can_see_all_deals("head_of_sales")
        assert not can_see_all_deals(NO_ACCESS_ROLE)

    def test_allowed_roles_set(self):
        assert "manager" in ALLOWED_ROLES
        assert "no_access" not in ALLOWED_ROLES


# ===========================================================================
# _matches_filters
# ===========================================================================


class TestMatchesFilters:
    def _deal(self, **kwargs):
        base = {
            "deal_id": "DEAL-000001",
            "status": "Новая",
            "manager": "Иван",
            "client": "ООО Альфа",
            "business_direction": "Логистика",
            "project_start_date": "2024-03-15",
            "paid": 1000.0,
        }
        base.update(kwargs)
        return base

    def test_no_filters(self):
        assert _matches_filters(self._deal(), {}) is True

    def test_manager_match(self):
        assert _matches_filters(self._deal(), {"manager": "Иван"}) is True

    def test_manager_no_match(self):
        assert _matches_filters(self._deal(), {"manager": "Мария"}) is False

    def test_month_match(self):
        assert _matches_filters(self._deal(), {"month": "2024-03"}) is True

    def test_month_no_match(self):
        assert _matches_filters(self._deal(), {"month": "2024-04"}) is False

    def test_paid_true(self):
        assert _matches_filters(self._deal(paid=500.0), {"paid": True}) is True

    def test_paid_false_on_unpaid(self):
        assert _matches_filters(self._deal(paid=0.0), {"paid": False}) is True

    def test_paid_false_on_paid(self):
        assert _matches_filters(self._deal(paid=500.0), {"paid": False}) is False

    def test_multiple_filters_all_match(self):
        filters = {"manager": "Иван", "status": "Новая"}
        assert _matches_filters(self._deal(), filters) is True

    def test_multiple_filters_one_fails(self):
        filters = {"manager": "Иван", "status": "Завершена"}
        assert _matches_filters(self._deal(), filters) is False

    def test_none_filter_value_ignored(self):
        # None values in filters should be ignored
        assert _matches_filters(self._deal(), {"manager": None}) is True
