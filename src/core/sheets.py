import gspread
from google.oauth2.service_account import Credentials

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_RESULTS_HEADERS = ["account", "profile_url", "followers", "caption_snippet", "post_url"]
_RESULTS_SHEET = "수집결과"
_EXCLUDED_SHEET = "제외계정"
_SETTINGS_SHEET = "설정"


def _get_client(credential_path: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(credential_path, scopes=_SCOPES)
    return gspread.authorize(creds)


def _ensure_sheet(spreadsheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=1000, cols=20)


def test_connection(spreadsheet_id: str, credential_path: str) -> str:
    """연결 테스트. 성공 시 스프레드시트 제목 반환, 실패 시 예외 발생."""
    client = _get_client(credential_path)
    sheet = client.open_by_key(spreadsheet_id)
    return sheet.title


def sync_results(spreadsheet_id: str, results: list[dict], credential_path: str):
    """수집결과 시트에 결과 추가 (account 기준 중복 제거)."""
    client = _get_client(credential_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    ws = _ensure_sheet(spreadsheet, _RESULTS_SHEET)

    existing_rows = ws.get_all_values()
    if not existing_rows:
        ws.append_row(_RESULTS_HEADERS)
        existing_accounts: set[str] = set()
    else:
        # 헤더 행이 있으면 account 컬럼(첫 번째) 수집
        existing_accounts = {r[0].lstrip("@").lower() for r in existing_rows[1:] if r}

    new_rows = []
    for r in results:
        key = r.get("account", "").lstrip("@").lower()
        if key and key not in existing_accounts:
            new_rows.append([r.get(h, "") for h in _RESULTS_HEADERS])
            existing_accounts.add(key)

    if new_rows:
        ws.append_rows(new_rows, value_input_option="RAW")


def sync_excluded(spreadsheet_id: str, accounts: list[str], credential_path: str):
    """제외계정 시트를 현재 목록으로 덮어씁니다."""
    client = _get_client(credential_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    ws = _ensure_sheet(spreadsheet, _EXCLUDED_SHEET)
    ws.clear()
    ws.append_row(["account"])
    if accounts:
        ws.append_rows([["@" + a.lstrip("@")] for a in sorted(accounts)], value_input_option="RAW")


def load_excluded_from_sheets(spreadsheet_id: str, credential_path: str) -> list[str]:
    """제외계정 시트에서 계정 목록을 읽어옵니다."""
    client = _get_client(credential_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        ws = spreadsheet.worksheet(_EXCLUDED_SHEET)
    except gspread.WorksheetNotFound:
        return []
    rows = ws.get_all_values()
    result = []
    for row in rows[1:]:  # 헤더 제외
        if row and row[0].strip():
            result.append(row[0].strip().lstrip("@").lower())
    return result
