#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def load_watchlist(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def crawl_stub(projects):
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for p in projects:
        records.append({
            "project_id": p["project_id"],
            "country": p["country"],
            "project_name": p["project_name"],
            "sector": p.get("sector", ""),
            "scheme": p.get("scheme", "無償資金協力"),
            "status_auto": "要確認",
            "status_detail": "初期MVPのダミー収集結果",
            "source_type": "stub",
            "source_url": "https://www.jica.go.jp/oda/",
            "oda_url": "https://www.jica.go.jp/oda/",
            "raw_text": p.get("keywords", ""),
            "fetched_at": now,
            "last_checked": now,
        })
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    projects = load_watchlist(args.watchlist)
    records = crawl_stub(projects)
    if args.dry_run:
        print(f"dry-run: {len(records)} records fetched")
        return
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
