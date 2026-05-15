#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build

WATCH_SHEET = "JICA_ODA_WATCH"
HISTORY_SHEET = "JICA_ODA_HISTORY"
RAW_SHEET = "JICA_ODA_RAW"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


def load_schema(schema_path="config/sheet_schema.yml"):
    with open(schema_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    sheets = data.get("sheets", {})
    watch = sheets.get(WATCH_SHEET, {})
    history = sheets.get(HISTORY_SHEET, {})
    raw = sheets.get(RAW_SHEET, {})
    auto_fields = watch.get("auto_fields", [])
    manual_fields = watch.get("manual_fields", [])
    history_fields = history.get("fields", [])
    raw_fields = raw.get("fields", [])
    if not auto_fields or not manual_fields:
        raise ValueError("sheet_schema.yml: WATCH定義が不正です")
    if not history_fields or not raw_fields:
        raise ValueError("sheet_schema.yml: HISTORY/RAW定義が不正です")
    return {
        "watch_headers": auto_fields + manual_fields,
        "auto_fields": auto_fields,
        "manual_fields": manual_fields,
        "history_fields": history_fields,
        "raw_fields": raw_fields,
    }


def extract_payload_parts(payload):
    if isinstance(payload, list):
        return payload, []
    return payload.get("projects", payload), payload.get("history", [])


def validate_headers(actual, expected, sheet_name):
    if actual != expected:
        raise RuntimeError(
            f"{sheet_name} ヘッダー不一致のため停止します。"
            f" expected={expected} actual={actual}"
        )


def validate_state_headers(state, schema):
    validate_headers(state[WATCH_SHEET]["headers"], schema["watch_headers"], WATCH_SHEET)
    validate_headers(state[HISTORY_SHEET]["headers"], schema["history_fields"], HISTORY_SHEET)
    validate_headers(state[RAW_SHEET]["headers"], schema["raw_fields"], RAW_SHEET)


def column_letter(index):
    if index < 1:
        raise ValueError("column index must be >= 1")
    out = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        out = chr(65 + remainder) + out
    return out


def quote_sheet_name(sheet_name):
    return "'" + sheet_name.replace("'", "''") + "'"


def pad_row(row, length):
    return list(row[:length]) + [""] * max(0, length - len(row))


def rows_to_dicts(values, headers, start_row_number=2):
    rows = []
    for offset, row in enumerate(values):
        padded = pad_row(row, len(headers))
        item = {headers[i]: padded[i] for i in range(len(headers))}
        item["_row_number"] = start_row_number + offset
        rows.append(item)
    return rows


def dict_rows_to_values(rows, fields):
    return [[row.get(field, "") for field in fields] for row in rows]


def build_sheets_service(service_account_json=None):
    raw_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw_json:
        raise SystemExit("エラー: GOOGLE_SERVICE_ACCOUNT_JSON が未設定です")
    try:
        info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise SystemExit("エラー: GOOGLE_SERVICE_ACCOUNT_JSON がJSONとして解釈できません") from exc

    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=[SHEETS_SCOPE],
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def get_spreadsheet_id(cli_spreadsheet_id=None):
    spreadsheet_id = cli_spreadsheet_id or os.getenv("SPREADSHEET_ID")
    if not spreadsheet_id:
        raise SystemExit("エラー: SPREADSHEET_ID が未設定です")
    return spreadsheet_id


def read_sheet_values(service, spreadsheet_id, sheet_name, width):
    last_col = column_letter(width)
    a1_range = f"{quote_sheet_name(sheet_name)}!A1:{last_col}"
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=a1_range,
    ).execute()
    return result.get("values", [])


def read_sheet_state(service, spreadsheet_id, schema):
    sheet_specs = {
        WATCH_SHEET: schema["watch_headers"],
        HISTORY_SHEET: schema["history_fields"],
        RAW_SHEET: schema["raw_fields"],
    }
    state = {}
    for sheet_name, expected_headers in sheet_specs.items():
        values = read_sheet_values(service, spreadsheet_id, sheet_name, len(expected_headers))
        if not values:
            raise RuntimeError(f"{sheet_name} のヘッダー行を取得できません")
        headers = pad_row(values[0], len(expected_headers))
        rows = rows_to_dicts(values[1:], headers)
        state[sheet_name] = {"headers": headers, "rows": rows}
    validate_state_headers(state, schema)
    return state


def build_watch_upserts(projects, existing_watch_rows, auto_fields, manual_fields):
    manual_by_project = {}
    for row in existing_watch_rows:
        pid = (row.get("project_id") or "").strip()
        if not pid:
            continue
        manual_by_project[pid] = {k: row.get(k, "") for k in manual_fields}

    upserts = []
    warnings = []
    for p in projects:
        pid = (p.get("project_id") or "").strip()
        if not pid:
            warnings.append("project_id missing: skipped 1 row")
            continue
        auto_values = {k: p.get(k, "") for k in auto_fields if k != "project_id"}
        manual_values = manual_by_project.get(pid, {k: "" for k in manual_fields})
        upserts.append(
            {
                "project_id": pid,
                "auto_values": auto_values,
                "manual_values_on_insert": manual_values,
            }
        )
    return upserts, warnings


def build_history_rows(history_items, history_fields):
    rows = []
    for item in history_items:
        rows.append({f: item.get(f, "") for f in history_fields})
    return rows


def build_raw_rows(projects, raw_fields, run_id):
    rows = []
    for p in projects:
        rows.append(
            {
                f: (
                    run_id
                    if f == "run_id"
                    else p.get(f, "")
                )
                for f in raw_fields
            }
        )
    return rows


def plan_updates(payload, state, schema):
    projects, history_items = extract_payload_parts(payload)
    validate_state_headers(state, schema)

    watch_upserts, warnings = build_watch_upserts(
        projects,
        state[WATCH_SHEET].get("rows", []),
        schema["auto_fields"],
        schema["manual_fields"],
    )

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    history_rows = build_history_rows(history_items, schema["history_fields"])
    raw_rows = build_raw_rows(projects, schema["raw_fields"], run_id)

    return {
        "run_id": run_id,
        "watch_upserts": watch_upserts,
        "history_appends": history_rows,
        "raw_appends": raw_rows,
        "warnings": warnings,
        "counts": {
            "watch_upserts": len(watch_upserts),
            "history_appends": len(history_rows),
            "raw_appends": len(raw_rows),
        },
    }


def build_existing_watch_index(state):
    out = {}
    for row in state[WATCH_SHEET].get("rows", []):
        pid = (row.get("project_id") or "").strip()
        row_number = row.get("_row_number")
        if pid and row_number:
            out[pid] = row_number
    return out


def build_watch_values_for_auto_fields(upsert, auto_fields):
    return [
        upsert["project_id"] if field == "project_id" else upsert["auto_values"].get(field, "")
        for field in auto_fields
    ]


def build_watch_values_for_insert(upsert, auto_fields, manual_fields):
    auto_values = build_watch_values_for_auto_fields(upsert, auto_fields)
    manual_values = [upsert["manual_values_on_insert"].get(field, "") for field in manual_fields]
    return auto_values + manual_values


def append_rows(service, spreadsheet_id, sheet_name, rows):
    if not rows:
        return {"updatedRows": 0}
    return service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{quote_sheet_name(sheet_name)}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()


def apply_updates(service, spreadsheet_id, plan, state, schema):
    validate_state_headers(state, schema)
    existing_index = build_existing_watch_index(state)
    auto_fields = schema["auto_fields"]
    manual_fields = schema["manual_fields"]
    auto_last_col = column_letter(len(auto_fields))

    update_data = []
    insert_values = []
    for upsert in plan["watch_upserts"]:
        pid = upsert["project_id"]
        if pid in existing_index:
            row_number = existing_index[pid]
            update_data.append(
                {
                    "range": f"{quote_sheet_name(WATCH_SHEET)}!A{row_number}:{auto_last_col}{row_number}",
                    "values": [build_watch_values_for_auto_fields(upsert, auto_fields)],
                }
            )
        else:
            insert_values.append(build_watch_values_for_insert(upsert, auto_fields, manual_fields))

    result = {
        "watch_updated_rows": 0,
        "watch_inserted_rows": 0,
        "history_appended_rows": 0,
        "raw_appended_rows": 0,
    }

    if update_data:
        resp = service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": update_data,
            },
        ).execute()
        result["watch_updated_rows"] = resp.get("totalUpdatedRows", 0)

    if insert_values:
        resp = append_rows(service, spreadsheet_id, WATCH_SHEET, insert_values)
        result["watch_inserted_rows"] = resp.get("updates", {}).get("updatedRows", 0)

    history_values = dict_rows_to_values(plan["history_appends"], schema["history_fields"])
    resp = append_rows(service, spreadsheet_id, HISTORY_SHEET, history_values)
    result["history_appended_rows"] = resp.get("updates", {}).get("updatedRows", 0)

    raw_values = dict_rows_to_values(plan["raw_appends"], schema["raw_fields"])
    resp = append_rows(service, spreadsheet_id, RAW_SHEET, raw_values)
    result["raw_appended_rows"] = resp.get("updates", {}).get("updatedRows", 0)

    return result


def dry_run_without_state(payload):
    projects, history_items = extract_payload_parts(payload)
    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    return {
        "counts": {
            "watch_upserts": len([p for p in projects if (p.get("project_id") or "").strip()]),
            "history_appends": len(history_items),
            "raw_appends": len(projects),
        },
        "warning": "dry-run without sheet state; remote manual field preservation not verified",
        "run_id": run_id,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--state-file")
    parser.add_argument("--spreadsheet-id")
    args = parser.parse_args()

    Path(args.input).parent.mkdir(parents=True, exist_ok=True)
    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    schema = load_schema()

    if args.dry_run and not args.state_file:
        print("dry-run: no write to Google Sheets")
        print(json.dumps(dry_run_without_state(payload), ensure_ascii=False, indent=2))
        return

    if args.state_file:
        with open(args.state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        plan = plan_updates(payload, state, schema)
        if args.dry_run:
            print("dry-run: no write to Google Sheets")
            print(json.dumps({"counts": plan["counts"], "warnings": plan["warnings"]}, ensure_ascii=False, indent=2))
            return
        raise SystemExit("エラー: --state-file はdry-run検証専用です。実書き込みでは使用できません")

    spreadsheet_id = get_spreadsheet_id(args.spreadsheet_id)
    service = build_sheets_service()
    state = read_sheet_state(service, spreadsheet_id, schema)
    plan = plan_updates(payload, state, schema)
    result = apply_updates(service, spreadsheet_id, plan, state, schema)
    print(json.dumps({"status": "ok", "run_id": plan["run_id"], "counts": plan["counts"], "warnings": plan["warnings"], "result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
