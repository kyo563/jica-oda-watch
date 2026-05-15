#!/usr/bin/env python3
import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

MANUAL_FIELDS = [
    "manual_status",
    "memo",
    "next_manual_action",
    "owner",
    "manual_checked_date",
    "manual_updated_at",
    "manual_updated_by",
]

RECORD_FIELD_NAME = "__record__"


def load_records(path, *, required=False):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        if required:
            raise FileNotFoundError(f"currentファイルが見つかりません: {path}")
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return data["records"]
    raise ValueError(f"records形式が不正です: {path}")


def load_diff_fields(schema_path="config/sheet_schema.yml"):
    with open(schema_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    sheets = data.get("sheets", {})
    watch = sheets.get("JICA_ODA_WATCH", {})
    diff_fields = watch.get("diff_fields")
    if not isinstance(diff_fields, list) or not diff_fields:
        raise ValueError("sheet_schema.yml: sheets.JICA_ODA_WATCH.diff_fields が不正です")
    return diff_fields


def validate_project_ids(records, label):
    seen = set()
    duplicates = set()
    for i, row in enumerate(records):
        pid = row.get("project_id")
        if not isinstance(pid, str) or not pid.strip():
            raise ValueError(f"{label}: project_id欠落があります (index={i})")
        pid = pid.strip()
        if pid in seen:
            duplicates.add(pid)
        seen.add(pid)
    if duplicates:
        dup_list = ", ".join(sorted(duplicates))
        raise ValueError(f"{label}: project_id重複があります: {dup_list}")


def merge_and_diff(previous, current, diff_fields):
    validate_project_ids(previous, "previous")
    validate_project_ids(current, "current")

    prev_map = {r["project_id"].strip(): r for r in previous}
    cur_map = {r["project_id"].strip(): r for r in current}
    all_ids = sorted(set(prev_map) | set(cur_map))
    merged, history = [], []
    changed_at = datetime.now(timezone.utc).isoformat()

    for pid in all_ids:
        p = prev_map.get(pid)
        c = cur_map.get(pid)
        if p and c:
            record = deepcopy(c)
            for field in MANUAL_FIELDS:
                if field in p:
                    record[field] = p[field]
            changed = [f for f in diff_fields if p.get(f) != c.get(f)]
            record["change_flag"] = "updated" if changed else "no_change"
            for field in changed:
                history.append({
                    "changed_at": changed_at,
                    "project_id": pid,
                    "field_name": field,
                    "old_value": p.get(field),
                    "new_value": c.get(field),
                    "source_url": c.get("source_url", ""),
                    "change_summary": "自動差分検知",
                    "run_id": "local",
                })
        elif c and not p:
            record = deepcopy(c)
            record["change_flag"] = "new"
            history.append({
                "changed_at": changed_at,
                "project_id": pid,
                "field_name": RECORD_FIELD_NAME,
                "old_value": "",
                "new_value": "new",
                "source_url": c.get("source_url", ""),
                "change_summary": "新規案件を検出",
                "run_id": "local",
            })
        else:
            record = deepcopy(p)
            record["change_flag"] = "missing"
            record["status_detail"] = "掲載消滅／要確認"
            history.append({
                "changed_at": changed_at,
                "project_id": pid,
                "field_name": RECORD_FIELD_NAME,
                "old_value": "exists",
                "new_value": "missing",
                "source_url": p.get("source_url", ""),
                "change_summary": "前回存在した案件が今回取得結果に存在しません",
                "run_id": "local",
            })
        merged.append(record)
    return merged, history


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    previous = load_records(args.previous)
    try:
        current = load_records(args.current, required=True)
    except FileNotFoundError as e:
        raise SystemExit(f"エラー: {e}")
    diff_fields = load_diff_fields()
    merged, history = merge_and_diff(previous, current, diff_fields)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"projects": merged, "history": history}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
