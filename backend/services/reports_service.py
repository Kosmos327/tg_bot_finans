"""
reports_service.py – Generate CSV and XLSX reports from Google Sheets data.

Public API
----------
generate_warehouse_report(warehouse, fmt) → bytes
generate_clients_report(fmt)             → bytes
generate_expenses_report(fmt)            → bytes
generate_profit_report(fmt)              → bytes
"""

import csv
import io
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level serialisation helpers
# ---------------------------------------------------------------------------

def _to_csv(headers: List[str], rows: List[List[Any]]) -> bytes:
    """Serialise *rows* to UTF-8 CSV with BOM (for Excel compatibility)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def _to_xlsx(headers: List[str], rows: List[List[Any]]) -> bytes:
    """Serialise *rows* to XLSX format."""
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl is required for XLSX export. Install it with: pip install openpyxl"
        ) from exc

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append(headers)
    for row in rows:
        ws.append([str(v) if v is not None else "" for v in row])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _serialise(data: List[dict], fmt: str) -> bytes:
    """
    Convert a list of dicts to *fmt* bytes.
    *fmt* must be 'csv' or 'xlsx'.
    """
    if not data:
        headers: List[str] = []
        rows: List[List[Any]] = []
    else:
        headers = list(data[0].keys())
        rows = [[row.get(h, "") for h in headers] for row in data]

    fmt = fmt.lower()
    if fmt == "xlsx":
        return _to_xlsx(headers, rows)
    # Default: CSV
    return _to_csv(headers, rows)


# ---------------------------------------------------------------------------
# Report generators
# ---------------------------------------------------------------------------

def generate_warehouse_report(warehouse: str, fmt: str = "csv") -> bytes:
    """Return a billing report for *warehouse* (msk/nsk/ekb)."""
    from backend.services.billing_service import get_billing_entries
    data = get_billing_entries(warehouse)
    return _serialise(data, fmt)


def generate_clients_report(fmt: str = "csv") -> bytes:
    """Return a report of all clients across all warehouses."""
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    combined: List[dict] = []
    for wh_key in BILLING_SHEETS:
        entries = get_billing_entries(wh_key)
        for e in entries:
            combined.append({"warehouse": wh_key, **e})
    return _serialise(combined, fmt)


def generate_expenses_report(fmt: str = "csv") -> bytes:
    """Return all expenses."""
    from backend.services.expenses_service import get_expenses
    data = get_expenses()
    return _serialise(data, fmt)


def generate_profit_report(fmt: str = "csv") -> bytes:
    """
    Return a simple profit summary (revenue, expenses, gross_profit, margin_percent)
    aggregated from the 'analytics_monthly' sheet.  Falls back to an empty report
    when the sheet is unavailable.
    """
    from backend.services.sheets_service import (
        SHEET_ANALYTICS_MONTHLY,
        SheetNotFoundError,
        SheetsError,
        get_worksheet,
        get_header_map,
    )

    try:
        ws = get_worksheet(SHEET_ANALYTICS_MONTHLY)
        header_map = get_header_map(ws)
        all_rows = ws.get_all_values()
    except (SheetNotFoundError, SheetsError) as exc:
        logger.warning("analytics_monthly sheet unavailable: %s", exc)
        return _serialise([], fmt)

    data: List[dict] = []
    for i, row in enumerate(all_rows):
        if i == 0:
            continue  # skip header
        if not any(c.strip() for c in row):
            continue
        entry: dict = {}
        for col_name, idx in header_map.items():
            entry[col_name] = row[idx] if idx < len(row) else ""
        data.append(entry)

    return _serialise(data, fmt)
