#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

WATCH_SHEET = "JICA_ODA_WATCH"
HISTORY_SHEET = "JICA_ODA_HISTORY"
RAW_SHEET = "JICA_ODA_RAW"


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
    return {
        "watch_headers": auto_fields + manual_fields,
        "auto_fields": auto_fields,
        "manual_fields": manual_fields,
        "history_fields": history_fields,
        "raw_fields": raw_fields,
    }


def validate_headers(actual, expected, sheet_name):
    if actual != expected:
        raise RuntimeError(
            f"{sheet_name} ヘッダー不一致のため停止します。"
            f" expected={expected} actual={actual}"
        )


def build_existing_watch_index(existing_watch_rows, manual_fields):
    index = {}
    for i, row in enumerate(existing_watch_rows, start=2):
        pid = (row.get("project_id") or "").strip()
        if not pid:
            continue
        if pid in index:
            raise RuntimeError(f"JICA_ODA_WATCH に重複した project_id があります: {pid}")
        index[pid] = {
            "row_number": i,
            "manual_values": {k: row.get(k, "") for k in manual_fields},
        }
    return index


def build_watch_upserts(projects, existing_watch_rows, auto_fields, manual_fields):
    existing_by_project = build_existing_watch_index(existing_watch_rows, manual_fields)
    seen = set()
    upserts = []
    warnings = []

    for p in projects:
        pid = (p.get("project_id") or "").strip()
        if not pid:
            warnings.append("project_id missing: skipped 1 row")
            continue
        if pid in seen:
            raise RuntimeError(f"入力projectsに重複した project_id があります: {pid}")
        seen.add(pid)

        auto_values = {k: p.get(k, "") for k in auto_fields}
        found = existing_by_project.get(pid)
        if found:
            upserts.append(
                {
                    "project_id": pid,
                    "mode": "update",
                    "row_number": found["row_number"],
                    "auto_values": {k: auto_values.get(k, "") for k in auto_fields if k != "project_id"},
                    "manual_values_on_insert": found["manual_values"],
                }
            )
            continue

        upserts.append(
            {
                "project_id": pid,
                "mode": "append",
                "row_number": None,
                "auto_values": auto_values,
                "manual_values_on_insert": {k: "" for k in manual_fields},
            }
        )

    return upserts, warnings


def build_history_rows(history_items, history_fields):
    return [{f: item.get(f, "") for f in history_fields} for item in history_items]


def build_raw_rows(projects, raw_fields, run_id):
    rows = []
    for p in projects:
        rows.append({f: run_id if f == "run_id" else p.get(f, "") for f in raw_fields})
    return rows


def plan_updates(payload, state, schema):
    projects = payload.get("projects", payload)
    history_items = payload.get("history", [])

    validate_headers(state[WATCH_SHEET]["headers"], schema["watch_headers"], WATCH_SHEET)
    validate_headers(state[HISTORY_SHEET]["headers"], schema["history_fields"], HISTORY_SHEET)
    validate_headers(state[RAW_SHEET]["headers"], schema["raw_fields"], RAW_SHEET)

    watch_upserts, warnings = build_watch_upserts(
        projects,
        state[WATCH_SHEET].get("rows", []),
        schema["auto_fields"],
        schema["manual_fields"],
    )

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    return {
        "run_id": run_id,
        "watch_upserts": watch_upserts,
        "history_appends": build_history_rows(history_items, schema["history_fields"]),
        "raw_appends": build_raw_rows(projects, schema["raw_fields"], run_id),
        "warnings": warnings,
        "counts": {
            "watch_upserts": len(watch_upserts),
            "history_appends": len(history_items),
            "raw_appends": len(projects),
        },
    }


def _to_sheet_row(row_dict, headers):
    return [row_dict.get(h, "") for h in headers]


def fetch_sheet_state(service, spreadsheet_id, schema):
    ranges = [f"{WATCH_SHEET}!A:ZZ", f"{HISTORY_SHEET}!A:ZZ", f"{RAW_SHEET}!A:ZZ"]
    result = service.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id, ranges=ranges
    ).execute()

    value_ranges = {vr["range"].split("!")[0]: vr.get("values", []) for vr in result.get("valueRanges", [])}

    def parse_rows(values, headers):
        if not values:
            return []
        data = []
        for raw in values[1:]:
            raw = raw + [""] * (len(headers) - len(raw))
            data.append({h: raw[i] for i, h in enumerate(headers)})
        return data

    watch_values = value_ranges.get(WATCH_SHEET, [])
    history_values = value_ranges.get(HISTORY_SHEET, [])
    raw_values = value_ranges.get(RAW_SHEET, [])

    state = {
        WATCH_SHEET: {
            "headers": watch_values[0] if watch_values else [],
            "rows": parse_rows(watch_values, schema["watch_headers"]),
        },
        HISTORY_SHEET: {
            "headers": history_values[0] if history_values else [],
            "rows": parse_rows(history_values, schema["history_fields"]),
        },
        RAW_SHEET: {
            "headers": raw_values[0] if raw_values else [],
            "rows": parse_rows(raw_values, schema["raw_fields"]),
        },
    }
    return state


def apply_plan(service, spreadsheet_id, plan, schema):
    updates = []
    for u in plan["watch_upserts"]:
        if u["mode"] == "update":
            values = [_to_sheet_row(u["auto_values"], [f for f in schema["auto_fields"] if f != "project_id"])]
            updates.append({
                "range": f"{WATCH_SHEET}!B{u['row_number']}",
                "values": values,
            })

    if updates:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()

    append_watch = []
    for u in plan["watch_upserts"]:
        if u["mode"] == "append":
            row = {**u["auto_values"], **u["manual_values_on_insert"]}
            append_watch.append(_to_sheet_row(row, schema["watch_headers"]))
    if append_watch:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{WATCH_SHEET}!A:A",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": append_watch},
        ).execute()

    if plan["history_appends"]:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{HISTORY_SHEET}!A:A",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [_to_sheet_row(r, schema["history_fields"]) for r in plan["history_appends"]]},
        ).execute()

    if plan["raw_appends"]:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{RAW_SHEET}!A:A",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [_to_sheet_row(r, schema["raw_fields"]) for r in plan["raw_appends"]]},
        ).execute()


def build_sheets_service(service_account_json):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_info = json.loads(service_account_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--state-file")
    parser.add_argument("--spreadsheet-id")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    schema = load_schema()

    if args.state_file and not args.dry_run:
        raise SystemExit("エラー: --state-file はdry-run専用です")

    if args.dry_run and not args.state_file:
        projects = payload.get("projects", payload)
        history_items = payload.get("history", [])
        seen = set()
        for p in projects:
            pid = (p.get("project_id") or "").strip()
            if not pid:
                continue
            if pid in seen:
                raise SystemExit(f"入力projectsに重複した project_id があります: {pid}")
            seen.add(pid)
        run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
        print("dry-run: no write to Google Sheets")
        print(json.dumps({"counts": {"watch_upserts": len([p for p in projects if (p.get('project_id') or '').strip()]), "history_appends": len(history_items), "raw_appends": len(projects)}, "warning": "dry-run without sheet state; remote manual field preservation not verified", "run_id": run_id}, ensure_ascii=False, indent=2))
        return

    if args.state_file:
        with open(args.state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    else:
        spreadsheet_id = args.spreadsheet_id or os.getenv("SPREADSHEET_ID")
        if not spreadsheet_id:
            raise SystemExit("エラー: SPREADSHEET_ID または --spreadsheet-id が必要です")
        service_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not service_json:
            raise SystemExit("エラー: GOOGLE_SERVICE_ACCOUNT_JSON が必要です")
        service = build_sheets_service(service_json)
        state = fetch_sheet_state(service, spreadsheet_id, schema)

    plan = plan_updates(payload, state, schema)
    if args.dry_run:
        print("dry-run: no write to Google Sheets")
        print(json.dumps({"counts": plan["counts"], "warnings": plan["warnings"]}, ensure_ascii=False, indent=2))
        return

    spreadsheet_id = args.spreadsheet_id or os.getenv("SPREADSHEET_ID")
    if not spreadsheet_id:
        raise SystemExit("エラー: SPREADSHEET_ID または --spreadsheet-id が必要です")
    service_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_json:
        raise SystemExit("エラー: GOOGLE_SERVICE_ACCOUNT_JSON が必要です")
    service = build_sheets_service(service_json)
    apply_plan(service, spreadsheet_id, plan, schema)
    print(json.dumps({"result": "ok", "run_id": plan["run_id"], "counts": plan["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
