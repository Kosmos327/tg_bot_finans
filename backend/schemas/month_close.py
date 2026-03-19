"""Pydantic schemas for month-close endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class MonthOperationRequest(BaseModel):
    """Base request for month operations (archive / cleanup / close).

    `comment` is preserved for backward compatibility; `notes` is the new
    canonical field for SQL functions and takes precedence when both are sent.
    """

    year: int
    month: int  # 1..12
    dry_run: bool = False
    comment: Optional[str] = None
    notes: Optional[str] = None


class ArchiveMonthRequest(MonthOperationRequest):
    """POST /month/archive"""


class CleanupMonthRequest(BaseModel):
    """POST /month/cleanup"""

    year: int
    month: int


class CloseMonthRequest(MonthOperationRequest):
    """POST /month/close"""
