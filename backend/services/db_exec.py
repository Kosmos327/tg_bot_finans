"""
db_exec.py – Thin service layer for calling PostgreSQL SQL functions and views.

All backend write operations go through public.api_* and *_month SQL functions.
All read operations go through public.v_api_* and public.v_* SQL views.

Usage:
    from backend.services.db_exec import call_sql_function, read_sql_view

Design rules:
  - Use SQLAlchemy text() with bind params — never concatenate SQL strings.
  - Always return plain dicts / lists of dicts (JSON-serialisable).
  - Surface SQL exceptions as plain Python exceptions with a helpful message.
"""

import logging
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> dict:
    """Convert a SQLAlchemy Row (or Mapping) to a plain dict."""
    try:
        return dict(row._mapping)
    except AttributeError:
        return dict(row)


def _serialise(value: Any) -> Any:
    """Convert non-JSON-safe types (Decimal, date, datetime) to primitives."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _clean_row(row: dict) -> dict:
    return {k: _serialise(v) for k, v in row.items()}


def _extract_sql_error_message(exc: Exception) -> str:
    """Pull the PostgreSQL error detail from a DBAPIError / SQLAlchemyError."""
    if isinstance(exc, DBAPIError) and exc.orig:
        # asyncpg surfaces the DETAIL in the string representation of orig
        msg = str(exc.orig)
        # try to extract the DETAIL / MESSAGE part
        for prefix in ("DETAIL:  ", "DETAIL: ", "MESSAGE:  ", "ERROR:  "):
            if prefix in msg:
                return msg.split(prefix, 1)[1].splitlines()[0].strip()
        return msg.splitlines()[0].strip()
    return str(exc)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

async def call_sql_function(
    db: AsyncSession,
    func_call: str,
    params: Optional[dict] = None,
) -> list[dict]:
    """
    Execute a SQL function call and return all result rows as dicts.

    ``func_call`` must be a SELECT expression such as:
        "SELECT * FROM public.api_create_deal(:p_status_id, :p_manager_id, ...)"

    All user-supplied values must be passed via ``params`` (bind parameters).
    Never interpolate user data directly into ``func_call``.

    Raises:
        ValueError: for application-level errors raised by SQL functions
                    (e.g. invalid input, business rule violations).
        RuntimeError: for unexpected database errors.
    """
    params = params or {}
    logger.debug("call_sql_function: %s | params=%s", func_call, list(params.keys()))
    try:
        result = await db.execute(text(func_call), params)
        rows = result.fetchall()
        return [_clean_row(_row_to_dict(r)) for r in rows]
    except DBAPIError as exc:
        msg = _extract_sql_error_message(exc)
        logger.warning("SQL function error: %s | query=%s", msg, func_call)
        raise ValueError(msg) from exc
    except SQLAlchemyError as exc:
        logger.error("SQLAlchemy error in call_sql_function: %s", exc)
        raise RuntimeError(f"Database error: {exc}") from exc


async def call_sql_function_one(
    db: AsyncSession,
    func_call: str,
    params: Optional[dict] = None,
) -> Optional[dict]:
    """Like call_sql_function but returns only the first row, or None."""
    rows = await call_sql_function(db, func_call, params)
    return rows[0] if rows else None


async def read_sql_view(
    db: AsyncSession,
    view_name: str,
    where_clause: str = "",
    params: Optional[dict] = None,
    order_by: str = "",
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Read rows from a SQL view with optional WHERE / ORDER BY / LIMIT.

    ``where_clause`` may contain named bind parameters (e.g. "manager_id = :manager_id").
    All parameter values must be passed via ``params``.

    Example:
        rows = await read_sql_view(
            db,
            "public.v_api_deals",
            where_clause="manager_id = :mid",
            params={"mid": 5},
            order_by="act_date DESC",
            limit=100,
        )
    """
    params = params or {}
    sql = f"SELECT * FROM {view_name}"
    if where_clause:
        sql += f" WHERE {where_clause}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit is not None:
        sql += f" LIMIT {limit}"

    logger.debug("read_sql_view: %s | params=%s", sql, list(params.keys()))
    try:
        result = await db.execute(text(sql), params)
        rows = result.fetchall()
        return [_clean_row(_row_to_dict(r)) for r in rows]
    except SQLAlchemyError as exc:
        logger.error("SQLAlchemy error in read_sql_view(%s): %s", view_name, exc)
        raise RuntimeError(f"Database error reading {view_name}: {exc}") from exc
