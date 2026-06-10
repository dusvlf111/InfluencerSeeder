import pytest
from unittest.mock import MagicMock, patch, call

import core.sheets as sheets


@pytest.fixture
def mock_client():
    client = MagicMock()
    spreadsheet = MagicMock()
    client.open_by_key.return_value = spreadsheet
    return client, spreadsheet


class TestSyncResults:
    def test_adds_header_when_sheet_empty(self, mock_client):
        client, spreadsheet = mock_client
        ws = MagicMock()
        ws.get_all_values.return_value = []
        spreadsheet.worksheet.return_value = ws

        with patch("core.sheets._get_client", return_value=client):
            sheets.sync_results("sheet_id", [
                {"account": "@alice", "profile_url": "", "followers": "1만",
                 "caption_snippet": "", "post_url": ""},
            ], "cred.json")

        ws.append_row.assert_called_once_with(sheets._RESULTS_HEADERS)

    def test_skips_duplicate_account(self, mock_client):
        client, spreadsheet = mock_client
        ws = MagicMock()
        ws.get_all_values.return_value = [
            ["account", "profile_url", "followers", "caption_snippet", "post_url"],
            ["@alice", "", "1만", "", ""],
        ]
        spreadsheet.worksheet.return_value = ws

        with patch("core.sheets._get_client", return_value=client):
            sheets.sync_results("sheet_id", [
                {"account": "@alice", "profile_url": "", "followers": "1만",
                 "caption_snippet": "", "post_url": ""},
            ], "cred.json")

        ws.append_rows.assert_not_called()

    def test_appends_new_accounts(self, mock_client):
        client, spreadsheet = mock_client
        ws = MagicMock()
        ws.get_all_values.return_value = [
            ["account", "profile_url", "followers", "caption_snippet", "post_url"],
        ]
        spreadsheet.worksheet.return_value = ws

        with patch("core.sheets._get_client", return_value=client):
            sheets.sync_results("sheet_id", [
                {"account": "@bob", "profile_url": "https://instagram.com/bob/",
                 "followers": "2만", "caption_snippet": "test", "post_url": "https://..."},
            ], "cred.json")

        ws.append_rows.assert_called_once()


class TestLoadExcludedFromSheets:
    def test_returns_empty_when_sheet_missing(self, mock_client):
        import gspread
        client, spreadsheet = mock_client
        spreadsheet.worksheet.side_effect = gspread.WorksheetNotFound

        with patch("core.sheets._get_client", return_value=client):
            result = sheets.load_excluded_from_sheets("sheet_id", "cred.json")

        assert result == []

    def test_parses_accounts_correctly(self, mock_client):
        client, spreadsheet = mock_client
        ws = MagicMock()
        ws.get_all_values.return_value = [
            ["account"],
            ["@alice"],
            ["@bob"],
            [""],
        ]
        spreadsheet.worksheet.return_value = ws

        with patch("core.sheets._get_client", return_value=client):
            result = sheets.load_excluded_from_sheets("sheet_id", "cred.json")

        assert "alice" in result
        assert "bob" in result
        assert "" not in result


class TestSyncExcluded:
    def test_clears_and_rewrites(self, mock_client):
        client, spreadsheet = mock_client
        ws = MagicMock()
        spreadsheet.worksheet.return_value = ws

        with patch("core.sheets._get_client", return_value=client):
            sheets.sync_excluded("sheet_id", ["alice", "bob"], "cred.json")

        ws.clear.assert_called_once()
        ws.append_row.assert_called_once_with(["account"])
        ws.append_rows.assert_called_once()
