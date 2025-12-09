import os
import json
import datetime
from dotenv import load_dotenv

load_dotenv()

# Prefer JSON in env var (for deployment), but still support a file (for local dev)
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json")

SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
MASTER_SHEET_NAME = os.getenv("GOOGLE_SHEETS_TAB_NAME", "DamageReports")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_sheets_available = False
_service = None

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = None

    if SPREADSHEET_ID:
        if SERVICE_ACCOUNT_JSON:
            # Deployment-friendly: JSON stored directly in env var
            sa_info = json.loads(SERVICE_ACCOUNT_JSON)
            creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
            print("[Sheets] Using GOOGLE_SERVICE_ACCOUNT_JSON from env.")
        elif os.path.exists(SERVICE_ACCOUNT_FILE) and os.path.getsize(SERVICE_ACCOUNT_FILE) > 0:
            # Local dev fallback: JSON on disk
            creds = Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
            print(f"[Sheets] Using service account file: {SERVICE_ACCOUNT_FILE}")
        else:
            print(
                "[Sheets] No service account JSON or file found; running in STUB mode."
            )

    if SPREADSHEET_ID and creds is not None:
        _service = build("sheets", "v4", credentials=creds)
        _sheets_available = True
        print("[Sheets] Google Sheets client initialized (master + per-report tabs).")
    else:
        if not SPREADSHEET_ID:
            print(
                "[Sheets] Missing SPREADSHEET_ID; running in STUB mode."
            )

except Exception as e:
    print(f"[Sheets] Failed to initialize Sheets client ({e}); running in STUB mode.")
    _sheets_available = False


def _header_row():
    """
    Simpler schema – no row-level calculations, no extra cost fields.

    A: report_id
    B: date
    C: part_id
    D: part_name
    E: damage_description
    F: severity
    G: estimated_material_cost
    H: estimated_paint_cost
    I: estimated_structural_cost
    J: estimated_total_part_cost
    K: part_number      (user optional)
    L: part_url         (user optional)
    """
    return [[
        "report_id",                 # A
        "date",                      # B
        "part_id",                   # C
        "part_name",                 # D
        "damage_description",        # E
        "severity",                  # F
        "estimated_material_cost",   # G
        "estimated_paint_cost",      # H
        "estimated_structural_cost", # I
        "estimated_total_part_cost", # J
        "part_number",               # K (user later)
        "part_url",                  # L (user later)
    ]]


def _build_rows_for_master(report_id: str, parts: list) -> list:
    """
    Rows for the master log sheet.
    No formulas here – just raw numbers from the model/backend.
    """
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for part in parts:
        row = [
            report_id,                                   # A
            date_str,                                    # B
            part.get("part_id", ""),                     # C
            part.get("part_name", ""),                   # D
            part.get("damage_description", ""),          # E
            part.get("severity", ""),                    # F
            part.get("estimated_material_cost", ""),     # G
            part.get("estimated_paint_cost", ""),        # H
            part.get("estimated_structural_cost", ""),   # I
            part.get("estimated_total_part_cost", ""),   # J
            "",                                          # K: part_number (user)
            "",                                          # L: part_url    (user)
        ]
        rows.append(row)
    return rows


def write_damage_report(report_id: str, damage_json: dict) -> str:
    """
    Design:
      1) Append all parts to the MASTER_SHEET_NAME tab (global log).
      2) Create a new tab inside the same spreadsheet just for this report:
         - Name: "Report_<short_id>"
         - Write header row to A1:L1
         - Write this report's rows to A2:...
         - Append a final "TOTAL" row with SUM over estimated_total_part_cost.
      3) Return a URL that jumps directly to the new tab.
    """

    parts = damage_json.get("parts", [])

    # STUB MODE: no real Sheets configured
    if not _sheets_available:
        print(
            f"[Sheets] STUB: would log report {report_id} with {len(parts)} parts."
        )
        if SPREADSHEET_ID:
            return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
        return "https://docs.google.com/spreadsheets"

    # If no parts, still just return the main sheet URL (nothing to write)
    if not parts:
        return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"

    # 1) Append to master log tab
    master_rows = _build_rows_for_master(report_id, parts)
    master_body = {"values": master_rows}

    _service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{MASTER_SHEET_NAME}!A2",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=master_body,
    ).execute()

    # 2) Create a new tab for this specific report
    short_id = report_id.split("-")[0]  # first chunk of UUID
    sheet_title = f"Report_{short_id}"

    try:
        add_sheet_request = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": sheet_title,
                        }
                    }
                }
            ]
        }

        batch_resp = _service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body=add_sheet_request,
        ).execute()

        new_sheet_id = batch_resp["replies"][0]["addSheet"]["properties"]["sheetId"]

        # 3) Header row
        header_body = {"values": _header_row()}
        _service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_title}!A1",
            valueInputOption="RAW",
            body=header_body,
        ).execute()

        # 4) Data rows for this report tab
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_rows = []
        for part in parts:
            row = [
                report_id,                                 # A
                date_str,                                  # B
                part.get("part_id", ""),                   # C
                part.get("part_name", ""),                 # D
                part.get("damage_description", ""),        # E
                part.get("severity", ""),                  # F
                part.get("estimated_material_cost", ""),   # G
                part.get("estimated_paint_cost", ""),      # H
                part.get("estimated_structural_cost", ""), # I
                part.get("estimated_total_part_cost", ""), # J
                "",                                        # K: part_number
                "",                                        # L: part_url
            ]
            report_rows.append(row)

        report_body = {"values": report_rows}
        _service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_title}!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=report_body,
        ).execute()

        # 5) Add TOTAL row with SUM over J
        last_part_row = len(parts) + 1  # header is row 1
        total_row_index = last_part_row + 1

        total_formula = f"=SUM(J2:J{last_part_row})"
        total_row = [
            report_id,                       # A
            date_str,                        # B
            "TOTAL",                         # C
            "Total Estimated Repair Cost",   # D
            "", "", "", "",                  # E–H
            "",                              # I
            total_formula,                   # J
            "", "",                          # K–L
        ]

        _service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_title}!A{total_row_index}",
            valueInputOption="USER_ENTERED",
            body={"values": [total_row]},
        ).execute()

        # Link directly to this tab
        return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={new_sheet_id}"

    except Exception as e:
        print(f"[Sheets] Warning: failed to create per-report tab: {e}")
        return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"