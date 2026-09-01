import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from app.config import GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_FILE

logger = logging.getLogger("sheets")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_sheet = None
HEADERS = ["Phone", "Name", "Interest", "Budget", "Notes", "Last Updated"]


def _get_sheet():
    global _sheet
    if _sheet is not None:
        return _sheet
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    _sheet = sh.sheet1
    # Ensure header row exists
    first_row = _sheet.row_values(1)
    if first_row != HEADERS:
        _sheet.update("A1", [HEADERS])
    return _sheet


def upsert_row(phone: str, name: str = None, interest: str = None,
               budget: str = None, notes: str = None):
    """
    Finds a row by phone number and updates it, or appends a new row.
    Only overwrites a field if a new non-empty value is provided.
    """
    try:
        sheet = _get_sheet()
        cell = None
        try:
            cell = sheet.find(phone)
        except gspread.exceptions.CellNotFound:
            cell = None

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        if cell:
            row_idx = cell.row
            existing = sheet.row_values(row_idx)
            existing += [""] * (6 - len(existing))
            new_row = [
                phone,
                name or existing[1],
                interest or existing[2],
                budget or existing[3],
                notes or existing[4],
                now,
            ]
            sheet.update(f"A{row_idx}:F{row_idx}", [new_row])
        else:
            sheet.append_row([phone, name or "", interest or "", budget or "", notes or "", now])

    except Exception:
        logger.exception("Failed to update Google Sheet for %s", phone)
