"""
sheets.py - Deprecated. Google Sheets support has been removed.

This module is a stub kept for backward compatibility.
For PostgreSQL-based data access, use app.database and app.crud modules.
"""

from backend.services.sheets_service import SheetsError, SheetNotFoundError, BadCredentialsError


def get_spreadsheet():
    raise NotImplementedError(
        "Google Sheets support has been removed. Use PostgreSQL via app.database."
    )


def get_worksheet(name: str):
    raise NotImplementedError(
        "Google Sheets support has been removed. Use PostgreSQL via app.database."
    )
