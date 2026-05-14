#!/usr/bin/env python3
"""Google Sheets初回セットアップ。

安全要件:
- 既存シート削除なし
- 既存データ(2行目以降)削除なし
- ヘッダー(1行目)のみ補正
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import yaml

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except ImportError:  # dry-run単体利用を許容
    Credentials = None
    build = None

LOGGER = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_ORDER = [
    "JICA_ODA_WATCH",
    "JICA_ODA_MANUAL",
    "JICA_ODA_HISTORY",
    "JICA_ODA_RAW",
    "JICA_ODA_CONFIG",
]

MANUAL_FIELDS = [
    "project_id",
    "manual_status",
    "memo",
    "next_manual_action",
    "owner",
    "manual_checked_date",
    "manual_updated_at",
    "manual_updated_by",
]

RAW_FIELDS = [
    "run_id",
    "fetched_at",
    "project_id",
    "source_type",
    "source_url",
    "parser_name",
    "parser_version",
    "http_status",
    "raw_text",
    "raw_html_excerpt",
    "evidence_text",
    "error_message",
]

CONFIG_FIELDS = ["key", "value", "description", "updated_at"]

VALIDATIONS = {
    "change_flag": ["new", "updated", "missing", "no_change", "ai_low_confidence", "error", "manual_updated"],
    "manual_status": ["", "未確認", "確認中", "対応不要", "要対応", "対応済み", "保留"],
    "pq_required": ["", "要確認", "あり", "なし", "不明"],
}

HEADER_COLORS = {
    "watch_auto": {"red": 0.88, "green": 0.94, "blue": 0.98},
    "watch_manual": {"red": 0.98, "green": 0.95, "blue": 0.84},
    "manual": {"red": 0.98, "green": 0.95, "blue": 0.84},
    "history": {"red": 0.89, "green": 0.96, "blue": 0.89},
    "raw": {"red": 0.93, "green": 0.93, "blue": 0.93},
    "config": {"red": 0.93, "green": 0.90, "blue": 0.98},
}


@dataclass
class SheetDefinition:
    name: str
    headers: list[str]
    kind: str


def load_schema(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_sheet_definitions(schema: dict[str, Any]) -> dict[str, SheetDefinition]:
    sheets = schema["sheets"]
    watch_auto = sheets["JICA_ODA_WATCH"]["auto_fields"]
    watch_manual = sheets["JICA_ODA_WATCH"]["manual_fields"]
    history_fields = sheets["JICA_ODA_HISTORY"]["fields"]

    return {
        "JICA_ODA_WATCH": SheetDefinition("JICA_ODA_WATCH", watch_auto + watch_manual, "watch"),
        "JICA_ODA_MANUAL": SheetDefinition("JICA_ODA_MANUAL", MANUAL_FIELDS, "manual"),
        "JICA_ODA_HISTORY": SheetDefinition("JICA_ODA_HISTORY", history_fields, "history"),
        "JICA_ODA_RAW": SheetDefinition("JICA_ODA_RAW", RAW_FIELDS, "raw"),
        "JICA_ODA_CONFIG": SheetDefinition("JICA_ODA_CONFIG", CONFIG_FIELDS, "config"),
    }


def get_credentials_from_env():
    payload = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not payload:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON が未設定です")
    if Credentials is None:
        raise RuntimeError("google-auth が未インストールです")
    info = json.loads(payload)
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def get_sheets_service(credentials):
    if build is None:
        raise RuntimeError("google-api-python-client が未インストールです")
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def get_existing_sheets(service, spreadsheet_id: str) -> dict[str, int]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta.get("sheets", [])}


def ensure_sheet_exists(service, spreadsheet_id: str, sheet_name: str) -> None:
    request = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request).execute()


def ensure_headers(service, spreadsheet_id: str, sheet_name: str, headers: list[str]) -> None:
    rng = f"{sheet_name}!1:1"
    current = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
    current_values = current.get("values", [[]])
    current_headers = current_values[0] if current_values else []
    if current_headers and current_headers != headers:
        LOGGER.warning("ヘッダー差異を検出: %s。1行目をschema順に補正します", sheet_name)
    body = {"values": [headers]}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body=body,
    ).execute()


def _col_index(headers: list[str], col: str) -> int | None:
    try:
        return headers.index(col)
    except ValueError:
        return None


def apply_basic_formatting(service, spreadsheet_id: str, sheet_id: int, headers: list[str], sheet_kind: str) -> None:
    col_count = max(len(headers), 1)
    requests: list[dict[str, Any]] = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "TOP",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id},
                "cell": {"userEnteredFormat": {"verticalAlignment": "TOP", "wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat(verticalAlignment,wrapStrategy)",
            }
        },
        {
            "setBasicFilter": {
                "filter": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "startColumnIndex": 0, "endColumnIndex": col_count}}
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": col_count},
                "properties": {"pixelSize": 180},
                "fields": "pixelSize",
            }
        },
    ]

    if sheet_kind == "watch":
        auto_len = col_count - 7
        requests.extend([
            {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": auto_len}, "cell": {"userEnteredFormat": {"backgroundColor": HEADER_COLORS["watch_auto"]}}, "fields": "userEnteredFormat.backgroundColor"}},
            {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": auto_len, "endColumnIndex": col_count}, "cell": {"userEnteredFormat": {"backgroundColor": HEADER_COLORS["watch_manual"]}}, "fields": "userEnteredFormat.backgroundColor"}},
        ])
        notes = {
            "manual_status": "手入力ステータス。自動更新で上書きしない。",
            "memo": "手入力メモ。自動更新で上書きしない。",
            "next_manual_action": "次の手動対応。自動更新で上書きしない。",
        }
        for field, text in notes.items():
            idx = _col_index(headers, field)
            if idx is not None:
                requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": idx, "endColumnIndex": idx + 1}, "cell": {"note": text}, "fields": "note"}})
    else:
        key = sheet_kind
        requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": col_count}, "cell": {"userEnteredFormat": {"backgroundColor": HEADER_COLORS[key]}}, "fields": "userEnteredFormat.backgroundColor"}})

    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _validation_request(sheet_id: int, col_idx: int, values: list[str]) -> dict[str, Any]:
    return {
        "setDataValidation": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": col_idx, "endColumnIndex": col_idx + 1},
            "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in values]},
                "strict": True,
                "showCustomUi": True,
            },
        }
    }


def apply_data_validations(service, spreadsheet_id: str, sheet_id: int, sheet_name: str, headers: list[str]) -> None:
    requests: list[dict[str, Any]] = []
    if sheet_name == "JICA_ODA_WATCH":
        for col, values in (("change_flag", VALIDATIONS["change_flag"]), ("manual_status", VALIDATIONS["manual_status"]), ("pq_required", VALIDATIONS["pq_required"])):
            idx = _col_index(headers, col)
            if idx is not None:
                requests.append(_validation_request(sheet_id, idx, values))
    if sheet_name == "JICA_ODA_MANUAL":
        idx = _col_index(headers, "manual_status")
        if idx is not None:
            requests.append(_validation_request(sheet_id, idx, VALIDATIONS["manual_status"]))
    if requests:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def apply_protection_if_possible(service, spreadsheet_id: str, sheet_id: int, headers: list[str]) -> None:
    auto_len = len(headers) - 7
    if auto_len <= 0:
        return
    req = {
        "requests": [
            {
                "addProtectedRange": {
                    "protectedRange": {
                        "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": auto_len},
                        "description": "auto fields 保護候補",
                        "warningOnly": True,
                    }
                }
            }
        ]
    }
    try:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=req).execute()
    except Exception as exc:  # 権限依存のため継続
        LOGGER.warning("保護設定をスキップ: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--schema", default="config/sheet_schema.yml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    schema = load_schema(args.schema)
    definitions = build_sheet_definitions(schema)

    if args.dry_run:
        LOGGER.info("DRY-RUN: Google Sheets書き込みは行いません")
        for name in SHEET_ORDER:
            d = definitions[name]
            LOGGER.info("予定シート: %s", name)
            LOGGER.info("ヘッダー: %s", ", ".join(d.headers))
        LOGGER.info("書式予定: 1行目固定/太字/背景色/フィルター/列幅/折り返し")
        LOGGER.info("入力規則予定: change_flag/manual_status/pq_required")
        return

    credentials = get_credentials_from_env()
    service = get_sheets_service(credentials)

    existing = get_existing_sheets(service, args.spreadsheet_id)
    for name in SHEET_ORDER:
        if name not in existing:
            LOGGER.info("シート作成: %s", name)
            ensure_sheet_exists(service, args.spreadsheet_id, name)
    existing = get_existing_sheets(service, args.spreadsheet_id)

    for name in SHEET_ORDER:
        definition = definitions[name]
        sheet_id = existing[name]
        ensure_headers(service, args.spreadsheet_id, name, definition.headers)
        apply_basic_formatting(service, args.spreadsheet_id, sheet_id, definition.headers, definition.kind)
        apply_data_validations(service, args.spreadsheet_id, sheet_id, name, definition.headers)
        if name == "JICA_ODA_WATCH":
            apply_protection_if_possible(service, args.spreadsheet_id, sheet_id, definition.headers)


if __name__ == "__main__":
    main()
