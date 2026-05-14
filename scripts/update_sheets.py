#!/usr/bin/env python3
import argparse
import json


def plan_updates(payload):
    projects = payload.get("projects", payload)
    return {
        "watch_upserts": len(projects),
        "history_appends": len(payload.get("history", [])),
        "raw_appends": len(projects),
        "manual_fields_preserved": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)
    plan = plan_updates(payload)

    if args.dry_run:
        print("dry-run: no write to Google Sheets")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    raise NotImplementedError("TODO: Google Sheets API統合")


if __name__ == "__main__":
    main()
