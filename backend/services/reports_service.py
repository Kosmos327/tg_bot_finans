"""
reports_service.py – Generate CSV and XLSX reports from PostgreSQL data.

Public API – async PostgreSQL generators (suffix _pg, preferred):
generate_warehouse_report_pg(db, warehouse, fmt)      → bytes
generate_clients_report_pg(db, fmt)                   → bytes
generate_warehouse_revenue_report_pg(db, fmt)         → bytes
generate_paid_deals_report_pg(db, fmt)                → bytes
generate_unpaid_deals_report_pg(db, fmt)              → bytes
generate_paid_billing_report_pg(db, fmt)              → bytes
generate_unpaid_billing_report_pg(db, fmt)            → bytes
generate_billing_by_month_report_pg(db, month, fmt)   → bytes
generate_billing_by_client_report_pg(db, client, fmt) → bytes
generate_debt_by_client_report_pg(db, fmt)            → bytes
generate_debt_by_warehouse_report_pg(db, fmt)         → bytes
generate_overdue_payments_report_pg(db, fmt)          → bytes
generate_partially_paid_billing_report_pg(db, fmt)    → bytes
generate_expenses_report_pg(db, fmt)                  → bytes
generate_profit_report_pg(db, fmt)                    → bytes

Legacy synchronous generators below are kept for backward compatibility only.
They rely on Google Sheets services that raise NotImplementedError and should
not be called in production. Use the _pg variants instead.
"""

import csv
import io
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal float helper
# ---------------------------------------------------------------------------

def _to_float(value: Any) -> float:
    """Convert a value to float, returning 0.0 on failure."""
    if value is None:
        return 0.0
    try:
        return float(str(value).strip().replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


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
    Return a profit summary report.

    Combines data from the 'deals' sheet (revenue, VAT, margins, gross profit)
    and falls back to the 'analytics_monthly' sheet when available.
    Includes: vat_totals, revenue_without_vat, gross_profit, warehouse_revenue.
    """
    from backend.services.sheets_service import (
        SHEET_ANALYTICS_MONTHLY,
        SHEET_DEALS,
        SheetNotFoundError,
        SheetsError,
        get_worksheet,
        get_header_map,
    )

    # Try to build profit summary from the deals sheet
    deals_data: List[dict] = []
    try:
        from backend.services.deals_service import get_all_deals
        raw_deals = get_all_deals()

        for deal in raw_deals:
            charged = _to_float(deal.get("charged_with_vat"))
            vat_amount = _to_float(deal.get("vat_amount"))
            amount_no_vat = _to_float(deal.get("amount_without_vat"))
            marginal = _to_float(deal.get("marginal_income"))
            gross = _to_float(deal.get("gross_profit"))
            bonus = _to_float(deal.get("manager_bonus_amount"))
            direction = str(deal.get("business_direction", ""))

            deals_data.append({
                "deal_id": deal.get("deal_id", ""),
                "client": deal.get("client", ""),
                "manager": deal.get("manager", ""),
                "status": deal.get("status", ""),
                "business_direction": direction,
                "project_start_date": deal.get("project_start_date", ""),
                "charged_with_vat": charged,
                "vat_amount": vat_amount,
                "revenue_without_vat": amount_no_vat,
                "marginal_income": marginal,
                "gross_profit": gross,
                "manager_bonus_amount": bonus,
            })
    except Exception as exc:
        logger.warning("Could not read deals for profit report: %s", exc)

    # If we got deals data, return it
    if deals_data:
        return _serialise(deals_data, fmt)

    # Fallback: analytics_monthly sheet
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


# ---------------------------------------------------------------------------
# Payment status constants (used by multiple report generators)
# ---------------------------------------------------------------------------
_PAID_STATUSES = frozenset({"оплачено", "paid", "оплачен"})


def generate_warehouse_revenue_report(fmt: str = "csv") -> bytes:
    """
    Return aggregated revenue (with VAT, without VAT, VAT amount) per warehouse
    from the billing sheets.
    """
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    combined: List[dict] = []
    for wh_key in BILLING_SHEETS:
        entries = get_billing_entries(wh_key)
        for e in entries:
            # Support both old and new format
            client = e.get("client") or e.get("client_name", "")
            total_with = _to_float(
                e.get("total_with_vat") or e.get("p1_total_with_penalties")
            )
            total_vat = _to_float(e.get("total_vat"))
            total_no = _to_float(
                e.get("total_without_vat") or e.get("p1_total_without_penalties")
            )
            combined.append({
                "warehouse": wh_key,
                "client": client,
                "total_with_vat": total_with,
                "total_vat": total_vat,
                "total_without_vat": total_no,
                "payment_status": e.get("payment_status", ""),
            })
    return _serialise(combined, fmt)


def generate_paid_deals_report(fmt: str = "csv") -> bytes:
    """Return deals that have been fully paid (payment_status == 'оплачено' or paid_amount >= revenue)."""
    from backend.services.deals_service import get_all_deals
    try:
        deals = get_all_deals()
    except Exception as exc:
        logger.warning("Could not read deals for paid report: %s", exc)
        return _serialise([], fmt)

    paid = []
    for d in deals:
        status = str(d.get("payment_status", "")).strip().lower()
        paid_amount = _to_float(d.get("paid_amount") or d.get("paid") or 0)
        revenue = _to_float(d.get("revenue_with_vat") or d.get("charged_with_vat") or 0)
        if status in _PAID_STATUSES or (revenue > 0 and paid_amount >= revenue):
            paid.append(d)

    return _serialise(paid, fmt)


def generate_unpaid_deals_report(fmt: str = "csv") -> bytes:
    """Return deals that have not been fully paid."""
    from backend.services.deals_service import get_all_deals
    try:
        deals = get_all_deals()
    except Exception as exc:
        logger.warning("Could not read deals for unpaid report: %s", exc)
        return _serialise([], fmt)

    unpaid = []
    for d in deals:
        status = str(d.get("payment_status", "")).strip().lower()
        paid_amount = _to_float(d.get("paid_amount") or d.get("paid") or 0)
        revenue = _to_float(d.get("revenue_with_vat") or d.get("charged_with_vat") or 0)
        if status not in _PAID_STATUSES and not (revenue > 0 and paid_amount >= revenue):
            unpaid.append(d)

    return _serialise(unpaid, fmt)


def generate_paid_billing_report(fmt: str = "csv") -> bytes:
    """Return billing entries with payment_status == 'оплачено'."""
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    paid: List[dict] = []
    for wh_key in BILLING_SHEETS:
        for e in get_billing_entries(wh_key):
            status = str(e.get("payment_status", "")).strip().lower()
            if status in _PAID_STATUSES:
                paid.append({"warehouse": wh_key, **e})

    return _serialise(paid, fmt)


def generate_unpaid_billing_report(fmt: str = "csv") -> bytes:
    """Return billing entries that are not marked as paid."""
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    unpaid: List[dict] = []
    for wh_key in BILLING_SHEETS:
        for e in get_billing_entries(wh_key):
            status = str(e.get("payment_status", "")).strip().lower()
            if status not in _PAID_STATUSES:
                unpaid.append({"warehouse": wh_key, **e})

    return _serialise(unpaid, fmt)


def generate_billing_by_month_report(month: str, fmt: str = "csv") -> bytes:
    """
    Return billing entries for a specific month (YYYY-MM format).

    Matches entries whose 'period' field starts with the given month string.
    For old-format sheets (no period column), all entries are returned.
    """
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    result: List[dict] = []
    for wh_key in BILLING_SHEETS:
        for e in get_billing_entries(wh_key):
            period = str(e.get("period", "")).strip()
            # New format: filter by period prefix
            if period:
                if period == month or period.startswith(f"{month}-"):
                    result.append({"warehouse": wh_key, **e})
            else:
                # Old format: no period column — include all entries
                result.append({"warehouse": wh_key, **e})

    return _serialise(result, fmt)


def generate_billing_by_client_report(client: str, fmt: str = "csv") -> bytes:
    """Return billing entries for a specific client across all warehouses."""
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    result: List[dict] = []
    client_lower = client.strip().lower()
    for wh_key in BILLING_SHEETS:
        for e in get_billing_entries(wh_key):
            c = (e.get("client") or e.get("client_name", "")).strip().lower()
            if c == client_lower:
                result.append({"warehouse": wh_key, **e})

    return _serialise(result, fmt)


# ---------------------------------------------------------------------------
# Debt / receivables report generators
# ---------------------------------------------------------------------------

def _debt_entry(
    wh_key: str, e: dict
) -> dict:
    """Return a flat debt record from a billing entry."""
    client = (e.get("client") or e.get("client_name") or "").strip()
    total_with_vat = _to_float(
        e.get("total_with_vat") or e.get("p1_total_with_penalties")
    )
    payment_amount = _to_float(e.get("payment_amount") or e.get("paid_amount") or 0)
    pay_status_raw = str(e.get("payment_status", "")).strip().lower()
    paid_statuses = frozenset({"оплачено", "paid", "оплачен"})
    if pay_status_raw in paid_statuses:
        payment_amount = total_with_vat
    debt = max(total_with_vat - payment_amount, 0.0)
    return {
        "warehouse": wh_key.upper(),
        "client": client,
        "period": e.get("period", ""),
        "total_with_vat": total_with_vat,
        "payment_amount": payment_amount,
        "debt": debt,
        "payment_status": e.get("payment_status", ""),
    }


def generate_debt_by_client_report(fmt: str = "csv") -> bytes:
    """Return a debt summary grouped by client across all warehouses."""
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    client_debt: dict = {}
    for wh_key in BILLING_SHEETS:
        for e in get_billing_entries(wh_key):
            rec = _debt_entry(wh_key, e)
            c = rec["client"] or "Неизвестно"
            if c not in client_debt:
                client_debt[c] = {"client": c, "total_with_vat": 0.0, "payment_amount": 0.0, "debt": 0.0}
            client_debt[c]["total_with_vat"] += rec["total_with_vat"]
            client_debt[c]["payment_amount"] += rec["payment_amount"]
            client_debt[c]["debt"] += rec["debt"]

    rows = sorted(client_debt.values(), key=lambda x: -x["debt"])
    return _serialise(rows, fmt)


def generate_debt_by_warehouse_report(fmt: str = "csv") -> bytes:
    """Return a debt summary grouped by warehouse."""
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    wh_debt: dict = {}
    for wh_key in BILLING_SHEETS:
        if wh_key.upper() not in wh_debt:
            wh_debt[wh_key.upper()] = {"warehouse": wh_key.upper(), "total_with_vat": 0.0, "payment_amount": 0.0, "debt": 0.0}
        for e in get_billing_entries(wh_key):
            rec = _debt_entry(wh_key, e)
            wh_debt[wh_key.upper()]["total_with_vat"] += rec["total_with_vat"]
            wh_debt[wh_key.upper()]["payment_amount"] += rec["payment_amount"]
            wh_debt[wh_key.upper()]["debt"] += rec["debt"]

    return _serialise(list(wh_debt.values()), fmt)


def generate_overdue_payments_report(fmt: str = "csv") -> bytes:
    """Return billing entries that are overdue (unpaid/partial and past end_date)."""
    from datetime import date as _date
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    today = _date.today()
    result: List[dict] = []
    for wh_key in BILLING_SHEETS:
        for e in get_billing_entries(wh_key):
            rec = _debt_entry(wh_key, e)
            if rec["debt"] <= 0:
                continue
            end_date_str = str(e.get("end_date") or e.get("project_end_date") or "")
            if end_date_str:
                try:
                    end = _date.fromisoformat(end_date_str[:10])
                    if end < today:
                        result.append({**rec, "end_date": end_date_str})
                except (ValueError, TypeError):
                    pass

    return _serialise(result, fmt)


def generate_partially_paid_billing_report(fmt: str = "csv") -> bytes:
    """Return billing entries where payment_amount > 0 but debt > 0."""
    from backend.services.sheets_service import BILLING_SHEETS
    from backend.services.billing_service import get_billing_entries

    result: List[dict] = []
    for wh_key in BILLING_SHEETS:
        for e in get_billing_entries(wh_key):
            rec = _debt_entry(wh_key, e)
            if rec["payment_amount"] > 0 and rec["debt"] > 0:
                result.append(rec)

    return _serialise(result, fmt)


# ===========================================================================
# PostgreSQL-based async report generators (suffix: _pg)
# These replace the Google Sheets-based generators above and are used by the
# reports router when a db session is available.
# ===========================================================================

_BILLING_QUERY = """
    SELECT
        be.id,
        be.month,
        be.period,
        be.payment_status,
        COALESCE(be.payment_amount, 0) AS payment_amount,
        be.payment_date,
        COALESCE(be.shipments_with_vat, 0)        AS shipments_with_vat,
        COALESCE(be.storage_with_vat, 0)           AS storage_with_vat,
        COALESCE(be.returns_pickup_with_vat, 0)    AS returns_pickup_with_vat,
        COALESCE(be.additional_services_with_vat, 0) AS additional_services_with_vat,
        COALESCE(be.penalties, 0)                  AS penalties,
        COALESCE(be.total_without_vat, 0)          AS total_without_vat,
        COALESCE(be.total_vat, 0)                  AS total_vat,
        COALESCE(be.total_with_vat, 0)             AS total_with_vat,
        be.units_count,
        be.pallets_count,
        be.returns_trips_count,
        COALESCE(c.client_name, '') AS client,
        COALESCE(w.code, '')        AS warehouse_code,
        COALESCE(w.name, '')        AS warehouse_name
    FROM billing_entries be
    LEFT JOIN clients    c ON be.client_id    = c.id
    LEFT JOIN warehouses w ON be.warehouse_id = w.id
"""

_DEALS_QUERY = """
    SELECT
        d.id,
        d.deal_name,
        d.status,
        d.business_direction,
        COALESCE(d.amount_with_vat, 0)     AS charged_with_vat,
        COALESCE(d.amount_without_vat, 0)  AS amount_without_vat,
        COALESCE(d.vat_amount, 0)          AS vat_amount,
        d.vat_rate,
        COALESCE(d.paid_amount, 0)         AS paid_amount,
        COALESCE(d.remaining_amount, 0)    AS remaining_amount,
        COALESCE(d.variable_expense_1, 0)  AS variable_expense_1,
        COALESCE(d.variable_expense_2, 0)  AS variable_expense_2,
        COALESCE(d.production_expense, 0)  AS production_expense,
        d.marginal_income,
        d.gross_profit,
        d.source,
        d.date_start                       AS project_start_date,
        d.act_date,
        d.created_at,
        COALESCE(c.client_name, '')        AS client,
        COALESCE(m.manager_name, '')       AS manager
    FROM deals d
    LEFT JOIN clients  c ON d.client_id  = c.id
    LEFT JOIN managers m ON d.manager_id = m.id
"""


async def _query_billing(db, where_clause: str = "", params: dict = None) -> List[dict]:
    """Execute billing query with optional WHERE clause and return list of dicts."""
    from sqlalchemy import text
    sql = _BILLING_QUERY
    if where_clause:
        sql += f" WHERE {where_clause}"
    result = await db.execute(text(sql), params or {})
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


async def _query_deals(db, where_clause: str = "", params: dict = None) -> List[dict]:
    """Execute deals query with optional WHERE clause and return list of dicts."""
    from sqlalchemy import text
    sql = _DEALS_QUERY
    if where_clause:
        sql += f" WHERE {where_clause}"
    result = await db.execute(text(sql), params or {})
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


async def _query_expenses(db, where_clause: str = "", params: dict = None) -> List[dict]:
    """Execute expenses query and return list of dicts."""
    from sqlalchemy import text
    sql = """
        SELECT
            e.id, e.deal_id, e.category_level_1, e.category_level_2,
            e.expense_type, e.amount_with_vat, e.vat_amount, e.amount_without_vat,
            e.comment, e.created_at,
            COALESCE(d.deal_name, '') AS deal_name
        FROM expenses e
        LEFT JOIN deals d ON e.deal_id = d.id
    """
    if where_clause:
        sql += f" WHERE {where_clause}"
    result = await db.execute(text(sql), params or {})
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


def _billing_debt_entry_pg(row: dict) -> dict:
    """Build a debt record from a billing row dict (PostgreSQL version)."""
    total_with_vat = _to_float(row.get("total_with_vat"))
    payment_amount = _to_float(row.get("payment_amount"))
    pay_status_raw = str(row.get("payment_status", "")).strip().lower()
    if pay_status_raw in _PAID_STATUSES:
        payment_amount = total_with_vat
    debt = max(total_with_vat - payment_amount, 0.0)
    wh = (row.get("warehouse_code") or row.get("warehouse_name") or "").upper()
    return {
        "warehouse": wh,
        "client": row.get("client", ""),
        "month": row.get("month", ""),
        "period": row.get("period", ""),
        "total_with_vat": total_with_vat,
        "payment_amount": payment_amount,
        "debt": debt,
        "payment_status": row.get("payment_status", ""),
    }


async def generate_warehouse_report_pg(db, warehouse: str, fmt: str = "csv") -> bytes:
    """Return billing report for a specific warehouse (msk/nsk/ekb)."""
    try:
        data = await _query_billing(
            db,
            "LOWER(w.code) = :code",
            {"code": warehouse.lower()},
        )
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        data = []
    return _serialise(data, fmt)


async def generate_clients_report_pg(db, fmt: str = "csv") -> bytes:
    """Return billing report for all clients across all warehouses."""
    try:
        data = await _query_billing(db)
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        data = []
    return _serialise(data, fmt)


async def generate_warehouse_revenue_report_pg(db, fmt: str = "csv") -> bytes:
    """Return aggregated revenue (with VAT, without VAT, VAT amount) per warehouse."""
    try:
        rows = await _query_billing(db)
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    combined = [
        {
            "warehouse": r.get("warehouse_code", "").upper(),
            "client": r.get("client", ""),
            "total_with_vat": _to_float(r.get("total_with_vat")),
            "total_vat": _to_float(r.get("total_vat")),
            "total_without_vat": _to_float(r.get("total_without_vat")),
            "payment_status": r.get("payment_status", ""),
        }
        for r in rows
    ]
    return _serialise(combined, fmt)


async def generate_paid_deals_report_pg(db, fmt: str = "csv") -> bytes:
    """Return deals that have been fully paid."""
    try:
        deals = await _query_deals(db)
    except Exception as exc:
        logger.warning("PostgreSQL deals query failed: %s", exc)
        deals = []
    paid = []
    for d in deals:
        status = str(d.get("status", "")).strip().lower()
        paid_amount = _to_float(d.get("paid_amount"))
        revenue = _to_float(d.get("charged_with_vat"))
        if status in _PAID_STATUSES or (revenue > 0 and paid_amount >= revenue):
            paid.append(d)
    return _serialise(paid, fmt)


async def generate_unpaid_deals_report_pg(db, fmt: str = "csv") -> bytes:
    """Return deals that have not been fully paid."""
    try:
        deals = await _query_deals(db)
    except Exception as exc:
        logger.warning("PostgreSQL deals query failed: %s", exc)
        deals = []
    unpaid = []
    for d in deals:
        status = str(d.get("status", "")).strip().lower()
        paid_amount = _to_float(d.get("paid_amount"))
        revenue = _to_float(d.get("charged_with_vat"))
        if status not in _PAID_STATUSES and not (revenue > 0 and paid_amount >= revenue):
            unpaid.append(d)
    return _serialise(unpaid, fmt)


async def generate_paid_billing_report_pg(db, fmt: str = "csv") -> bytes:
    """Return billing entries with payment_status == 'оплачено'."""
    try:
        rows = await _query_billing(db)
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    paid = [r for r in rows if str(r.get("payment_status", "")).strip().lower() in _PAID_STATUSES]
    return _serialise(paid, fmt)


async def generate_unpaid_billing_report_pg(db, fmt: str = "csv") -> bytes:
    """Return billing entries that are not marked as paid."""
    try:
        rows = await _query_billing(db)
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    unpaid = [r for r in rows if str(r.get("payment_status", "")).strip().lower() not in _PAID_STATUSES]
    return _serialise(unpaid, fmt)


async def generate_billing_by_month_report_pg(db, month: str, fmt: str = "csv") -> bytes:
    """Return billing entries for a specific month (YYYY-MM format)."""
    try:
        rows = await _query_billing(db, "be.month = :month", {"month": month})
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    return _serialise(rows, fmt)


async def generate_billing_by_client_report_pg(db, client: str, fmt: str = "csv") -> bytes:
    """Return billing entries for a specific client across all warehouses."""
    try:
        rows = await _query_billing(
            db,
            "LOWER(c.client_name) = LOWER(:client)",
            {"client": client.strip()},
        )
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    return _serialise(rows, fmt)


async def generate_debt_by_client_report_pg(db, fmt: str = "csv") -> bytes:
    """Return a debt summary grouped by client across all warehouses."""
    try:
        rows = await _query_billing(db)
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    client_debt: dict = {}
    for row in rows:
        rec = _billing_debt_entry_pg(row)
        c = rec["client"] or "Неизвестно"
        if c not in client_debt:
            client_debt[c] = {"client": c, "total_with_vat": 0.0, "payment_amount": 0.0, "debt": 0.0}
        client_debt[c]["total_with_vat"] += rec["total_with_vat"]
        client_debt[c]["payment_amount"] += rec["payment_amount"]
        client_debt[c]["debt"] += rec["debt"]
    result = sorted(client_debt.values(), key=lambda x: -x["debt"])
    return _serialise(result, fmt)


async def generate_debt_by_warehouse_report_pg(db, fmt: str = "csv") -> bytes:
    """Return a debt summary grouped by warehouse."""
    try:
        rows = await _query_billing(db)
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    wh_debt: dict = {}
    for row in rows:
        rec = _billing_debt_entry_pg(row)
        wh = rec["warehouse"] or "UNKNOWN"
        if wh not in wh_debt:
            wh_debt[wh] = {"warehouse": wh, "total_with_vat": 0.0, "payment_amount": 0.0, "debt": 0.0}
        wh_debt[wh]["total_with_vat"] += rec["total_with_vat"]
        wh_debt[wh]["payment_amount"] += rec["payment_amount"]
        wh_debt[wh]["debt"] += rec["debt"]
    return _serialise(list(wh_debt.values()), fmt)


async def generate_overdue_payments_report_pg(db, fmt: str = "csv") -> bytes:
    """Return billing entries that are overdue (unpaid/partial and past payment_date)."""
    from datetime import date as _date
    today = _date.today()
    try:
        rows = await _query_billing(db)
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    result = []
    for row in rows:
        rec = _billing_debt_entry_pg(row)
        if rec["debt"] <= 0:
            continue
        payment_date = row.get("payment_date")
        if payment_date:
            try:
                end = payment_date.date() if hasattr(payment_date, "date") else _date.fromisoformat(str(payment_date)[:10])
                if end < today:
                    result.append({**rec, "payment_date": str(payment_date)[:10]})
            except (ValueError, TypeError, AttributeError):
                pass
    return _serialise(result, fmt)


async def generate_partially_paid_billing_report_pg(db, fmt: str = "csv") -> bytes:
    """Return billing entries where payment_amount > 0 but debt > 0."""
    try:
        rows = await _query_billing(db)
    except Exception as exc:
        logger.warning("PostgreSQL billing query failed: %s", exc)
        rows = []
    result = [
        _billing_debt_entry_pg(row)
        for row in rows
        if _to_float(row.get("payment_amount")) > 0 and _billing_debt_entry_pg(row)["debt"] > 0
    ]
    return _serialise(result, fmt)


async def generate_expenses_report_pg(db, fmt: str = "csv") -> bytes:
    """Return all expenses from PostgreSQL."""
    try:
        data = await _query_expenses(db)
    except Exception as exc:
        logger.warning("PostgreSQL expenses query failed: %s", exc)
        data = []
    return _serialise(data, fmt)


async def generate_profit_report_pg(db, fmt: str = "csv") -> bytes:
    """Return profit summary from deals in PostgreSQL."""
    try:
        deals = await _query_deals(db)
    except Exception as exc:
        logger.warning("PostgreSQL deals query failed: %s", exc)
        deals = []
    data = []
    for d in deals:
        charged = _to_float(d.get("charged_with_vat"))
        vat_amount = _to_float(d.get("vat_amount"))
        amount_no_vat = _to_float(d.get("amount_without_vat"))
        marginal = _to_float(d.get("marginal_income"))
        gross = _to_float(d.get("gross_profit"))
        data.append({
            "deal_id": d.get("id", ""),
            "deal_name": d.get("deal_name", ""),
            "client": d.get("client", ""),
            "manager": d.get("manager", ""),
            "status": d.get("status", ""),
            "business_direction": d.get("business_direction", ""),
            "project_start_date": str(d.get("project_start_date") or ""),
            "charged_with_vat": charged,
            "vat_amount": vat_amount,
            "revenue_without_vat": amount_no_vat,
            "marginal_income": marginal,
            "gross_profit": gross,
        })
    return _serialise(data, fmt)

