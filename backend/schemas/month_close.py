"""Pydantic schemas for month-close endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class MonthOperationRequest(BaseModel):
    """Base request for month operations (archive / cleanup / close)."""

    year: int
    month: int  # 1..12
    dry_run: bool = False


class ArchiveMonthRequest(MonthOperationRequest):
    """POST /month/archive"""
    notes: Optional[str] = None


class CleanupMonthRequest(BaseModel):
    """POST /month/cleanup"""

    year: int
    month: int


class CloseMonthRequest(BaseModel):
    """POST /month/close"""

    year: int
    month: int
    # Preferred field name for SQL function p_notes
    notes: Optional[str] = None
    # Backward-compatible alias kept for existing Mini App payloads
    comment: Optional[str] = None
    dry_run: bool = False
