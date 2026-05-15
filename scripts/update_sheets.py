#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
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


def fetch_sheet_state(endpoint, secret):
    resp = requests.post(
        endpoint,
        json={"action": "get_state"},
        headers={"X-Shared-Secret": secret},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def validate_headers(actual, expected, sheet_name):
    if actual != expected:
        raise RuntimeError(
            f"{sheet_name} ヘッダー不一致のため停止します。"
            f" expected={expected} actual={actual}"
        )


def build_watch_upserts(projects, existing_watch_rows, auto_fields, manual_fields):
    manual_by_project = {}
    for row in existing_watch_rows:
        pid = (row.get("project_id") or "").strip()
        if not pid:
            continue
        manual_by_project[pid] = {k: row.get(k, "") for k in manual_fields}

    upserts = []
    for p in projects:
        pid = (p.get("project_id") or "").strip()
        if not pid:
            continue
        row = {k: p.get(k, "") for k in auto_fields}
        preserved = manual_by_project.get(pid, {})
        for mf in manual_fields:
            row[mf] = preserved.get(mf, "")
        upserts.append(row)
    return upserts


def build_raw_rows(projects, raw_fields, run_id):
    out = []
    for p in projects:
        row = {f: "" for f in raw_fields}
        row.update(
            {
                "run_id": run_id,
                "fetched_at": p.get("fetched_at", ""),
                "project_id": p.get("project_id", ""),
                "source_type": p.get("source_type", ""),
                "source_url": p.get("source_url", ""),
                "parser_name": p.get("parser_name", ""),
                "parser_version": p.get("parser_version", ""),
                "raw_text": p.get("raw_text", ""),
                "evidence_text": p.get("evidence_text", ""),
            }
        )
        out.append(row)
    return out


def plan_updates(payload, state, schema):
    projects = payload.get("projects", payload)
    history_rows = payload.get("history", [])
    watch_headers = schema["watch_headers"]

    validate_headers(state[WATCH_SHEET]["headers"], watch_headers, WATCH_SHEET)

    watch_upserts = build_watch_upserts(
        projects,
        state[WATCH_SHEET].get("rows", []),
        schema["auto_fields"],
        schema["manual_fields"],
    )

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    raw_rows = build_raw_rows(projects, schema["raw_fields"], run_id)

    return {
        "run_id": run_id,
        "watch_upserts": watch_upserts,
        "history_appends": history_rows,
        "raw_appends": raw_rows,
        "counts": {
            "watch_upserts": len(watch_upserts),
            "history_appends": len(history_rows),
            "raw_appends": len(raw_rows),
        },
    }


def write_back(endpoint, secret, plan):
    payload = {
        "action": "apply_updates",
        "run_id": plan["run_id"],
        "watch_upserts": plan["watch_upserts"],
        "history_appends": plan["history_appends"],
        "raw_appends": plan["raw_appends"],
    }
    resp = requests.post(
        endpoint,
        json=payload,
        headers={"X-Shared-Secret": secret},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    Path(args.input).parent.mkdir(parents=True, exist_ok=True)
    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    endpoint = os.getenv("APPS_SCRIPT_ENDPOINT")
    secret = os.getenv("APPS_SCRIPT_SHARED_SECRET", "")
    if not endpoint:
        raise SystemExit("エラー: APPS_SCRIPT_ENDPOINT が未設定です")

    schema = load_schema()
    state = fetch_sheet_state(endpoint, secret)
    plan = plan_updates(payload, state, schema)

    if args.dry_run:
        print("dry-run: no write to Google Sheets")
        print(json.dumps(plan["counts"], ensure_ascii=False, indent=2))
        return

    result = write_back(endpoint, secret, plan)
    print(json.dumps({"status": "ok", "result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
