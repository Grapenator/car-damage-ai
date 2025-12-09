import os
import datetime
from dotenv import load_dotenv

load_dotenv()

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
MASTER_SHEET_NAME = os.getenv("GOOGLE_SHEETS_TAB_NAME", "DamageReports")

# We only need Sheets scope; Drive sharing is handled manually via the UI.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_sheets_available = False
_service = None

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    if (
        SPREADSHEET_ID
        and os.path.exists(SERVICE_ACCOUNT_FILE)
        and os.path.getsize(SERVICE_ACCOUNT_FILE) > 0
    ):
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        _service = build("sheets", "v4", credentials=creds)
        _sheets_available = True
        print("[Sheets] Google Sheets client initialized (master + per-report tabs).")
    else:
        print(
            "[Sheets] Missing SPREADSHEET_ID or service account file; running in STUB mode."
        )
except Exception as e:
    print(f"[Sheets] Failed to initialize Sheets client ({e}); running in STUB mode.")
    _sheets_available = False


def _header_row():
    """
    Shared header for both the master log and per-report tabs.

    Columns:
      A: report_id
      B: date
      C: part_id
      D: part_name
      E: damage_description
      F: severity
      G: estimated_labor_hours
      H: estimated_material_cost
      I: estimated_paint_cost
      J: estimated_structural_cost
      K: estimated_total_part_cost
      L: part_number        (user later)
      M: part_url           (user later)
      N: part_cost          (user later)
      O: labor_rate         (user later)
      P: total_cost         (formula/user)
    """
    return [[
        "report_id",                  # A
        "date",                       # B
        "part_id",                    # C
        "part_name",                  # D
        "damage_description",         # E
        "severity",                   # F
        "estimated_labor_hours",      # G
        "estimated_material_cost",    # H
        "estimated_paint_cost",       # I
        "estimated_structural_cost",  # J
        "estimated_total_part_cost",  # K
        "part_number",                # L
        "part_url",                   # M
        "part_cost",                  # N
        "labor_rate",                 # O
        "total_cost",                 # P
    ]]


def _build_rows_for_master(report_id: str, parts: list) -> list:
    """
    Rows for the master log sheet.

    The master log stores all estimated values and leaves the user-editable
    cost fields blank.
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
            part.get("estimated_labor_hours", ""),       # G
            part.get("estimated_material_cost", ""),     # H
            part.get("estimated_paint_cost", ""),        # I
            part.get("estimated_structural_cost", ""),   # J
            part.get("estimated_total_part_cost", ""),   # K
            "",                                          # L: part_number (user later)
            "",                                          # M: part_url    (user later)
            "",                                          # N: part_cost   (user later)
            "",                                          # O: labor_rate  (user later)
            "",                                          # P: total_cost  (formula/user later)
        ]
        rows.append(row)
    return rows


def write_damage_report(report_id: str, damage_json: dict) -> str:
    """
    Design:
      1) Append all parts to the MASTER_SHEET_NAME tab (global log).
      2) Create a new tab inside the same spreadsheet just for this report:
         - Name: "Report_<short_id>"
         - Write header row to A1:P1
         - Write this report's rows to A2:P...
           - Columns H–K hold the AI's cost estimates.
           - Columns L–O are empty for the user to fill in.
           - Column P contains a formula:
               =IF(AND(Nn<>"",On<>""), Nn + (Gn * On), "")
         - Add one extra row at the bottom:
               "Total Estimated Repair Cost" with K = SUM(K2:K_last)
      3) Return a URL that jumps directly to the new tab.
    """

    parts = damage_json.get("parts", []) or []

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

    # 1) Append to master log tab (no formulas here)
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

        # 3) Write header row to the new tab
        header_body = {"values": _header_row()}
        _service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_title}!A1",
            valueInputOption="RAW",
            body=header_body,
        ).execute()

        # 4) Build rows for this report tab, with formulas in total_cost (column P)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_rows = []

        start_row = 2  # first data row
        for row_index, part in enumerate(parts, start=start_row):
            # Column P formula uses part_cost (N) and labor_rate (O) plus labor hours (G)
            total_cost_formula = (
                f'=IF(AND(N{row_index}<>"",O{row_index}<>""), '
                f'N{row_index} + (G{row_index} * O{row_index}), "")'
            )

            row = [
                report_id,                              # A: report_id
                date_str,                               # B: date
                part.get("part_id", ""),                # C
                part.get("part_name", ""),              # D
                part.get("damage_description", ""),     # E
                part.get("severity", ""),               # F
                part.get("estimated_labor_hours", ""),  # G
                part.get("estimated_material_cost", ""),     # H
                part.get("estimated_paint_cost", ""),        # I
                part.get("estimated_structural_cost", ""),   # J
                part.get("estimated_total_part_cost", ""),   # K
                "",                                     # L: part_number (user later)
                "",                                     # M: part_url    (user later)
                "",                                     # N: part_cost   (user later)
                "",                                     # O: labor_rate  (user later)
                total_cost_formula,                     # P: total_cost (auto formula)
            ]
            report_rows.append(row)

        # 5) Summary row: Total Estimated Repair Cost (sum of K)
        if parts:
            last_part_row = start_row + len(parts) - 1
            summary_row_index = last_part_row + 1
            sum_formula = f"=SUM(K{start_row}:K{last_part_row})"

            summary_row = [
                report_id,                     # A
                date_str,                      # B
                "TOTAL",                       # C
                "Total Estimated Repair Cost", # D
                "", "", "", "", "", "",        # E–K
                sum_formula,                   # K: formula
                "", "", "", "",                # L–P (leave blank)
            ]

            # ^ count carefully: we need 16 cells total
            # A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P
            # We've given A,B,C,D, five empty (E–I), then two empty (J?), need to ensure right length.
            # Let's just expand manually:
            summary_row = [
                report_id,                     # A
                date_str,                      # B
                "TOTAL",                       # C
                "Total Estimated Repair Cost", # D
                "",                            # E
                "",                            # F
                "",                            # G
                "",                            # H
                "",                            # I
                "",                            # J
                sum_formula,                   # K
                "",                            # L
                "",                            # M
                "",                            # N
                "",                            # O
                "",                            # P
            ]

            report_rows.append(summary_row)

        report_body = {"values": report_rows}
        _service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_title}!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=report_body,
        ).execute()

        # Direct link to this tab via gid
        return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={new_sheet_id}"

    except Exception as e:
        # If we fail to create a per-report tab, we still have the master log.
        print(f"[Sheets] Warning: failed to create per-report tab: {e}")
        return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"