#!/usr/bin/env python3
import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone

MANUAL_FIELDS = [
    "manual_status",
    "memo",
    "next_manual_action",
    "owner",
    "manual_checked_date",
    "manual_updated_at",
    "manual_updated_by",
]

FACT_FIELDS = [
    "country", "project_name", "sector", "scheme", "ga_date", "pq_required",
    "notice_date", "notice_media", "notice_url", "result_url", "oda_url",
    "status_auto", "status_detail", "source_type", "source_url", "raw_text",
]


def load_records(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def merge_and_diff(previous, current):
    prev_map = {r["project_id"]: r for r in previous}
    cur_map = {r["project_id"]: r for r in current}
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
            changed = [f for f in FACT_FIELDS if p.get(f) != c.get(f)]
            record["change_flag"] = "updated" if changed else "no_change"
            for field in changed:
                history.append({"changed_at": changed_at, "project_id": pid, "field_name": field, "old_value": p.get(field), "new_value": c.get(field), "source_url": c.get("source_url", ""), "change_summary": "自動差分検知", "run_id": "local"})
        elif c and not p:
            record = deepcopy(c)
            record["change_flag"] = "new"
        else:
            record = deepcopy(p)
            record["change_flag"] = "missing"
            record["status_detail"] = "掲載消滅／要確認"
        merged.append(record)
    return merged, history


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    previous = load_records(args.previous)
    current = load_records(args.current)
    merged, history = merge_and_diff(previous, current)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"projects": merged, "history": history}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
