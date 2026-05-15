#!/usr/bin/env python3
import argparse
import json
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


def validate_state_headers(state, schema):
    validate_headers(state[WATCH_SHEET]["headers"], schema["watch_headers"], WATCH_SHEET)
    validate_headers(state[HISTORY_SHEET]["headers"], schema["history_fields"], HISTORY_SHEET)
    validate_headers(state[RAW_SHEET]["headers"], schema["raw_fields"], RAW_SHEET)


def build_existing_watch_index(existing_watch_rows, manual_fields):
    manual_by_project = {}
    for row in existing_watch_rows:
        pid = (row.get("project_id") or "").strip()
        if not pid:
            continue
        if pid in manual_by_project:
            raise RuntimeError(f"JICA_ODA_WATCH に重複した project_id があります: {pid}")
        manual_by_project[pid] = {k: row.get(k, "") for k in manual_fields}
    return manual_by_project


def build_watch_upserts(projects, existing_watch_rows, auto_fields, manual_fields):
    manual_by_project = build_existing_watch_index(existing_watch_rows, manual_fields)
    seen_project_ids = set()

    upserts = []
    warnings = []
    for p in projects:
        pid = (p.get("project_id") or "").strip()
        if not pid:
            warnings.append("project_id missing: skipped 1 row")
            continue
        if pid in seen_project_ids:
            raise RuntimeError(f"入力projectsに重複した project_id があります: {pid}")
        seen_project_ids.add(pid)
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
    projects = payload.get("projects", payload)
    history_items = payload.get("history", [])
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--state-file")
    args = parser.parse_args()

    Path(args.input).parent.mkdir(parents=True, exist_ok=True)
    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    schema = load_schema()

    if args.dry_run and not args.state_file:
        projects = payload.get("projects", payload)
        history_items = payload.get("history", [])
        run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
        summary = {
            "counts": {
                "watch_upserts": len([p for p in projects if (p.get("project_id") or "").strip()]),
                "history_appends": len(history_items),
                "raw_appends": len(projects),
            },
            "warning": "dry-run without sheet state; remote manual field preservation not verified",
            "run_id": run_id,
        }
        print("dry-run: no write to Google Sheets")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if not args.state_file:
        raise SystemExit("エラー: 現在は --state-file が必要です（実書き込み未対応）")

    with open(args.state_file, "r", encoding="utf-8") as f:
        state = json.load(f)

    plan = plan_updates(payload, state, schema)
    if args.dry_run:
        print("dry-run: no write to Google Sheets")
        print(json.dumps({"counts": plan["counts"], "warnings": plan["warnings"]}, ensure_ascii=False, indent=2))
        return

    raise SystemExit("エラー: 実書き込みは未実装です。Google Sheets API直接方式を次フェーズで実装します。")


if __name__ == "__main__":
    main()
