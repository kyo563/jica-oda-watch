#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.http_client import HTTPFetchError, fetch_text
    from scripts.parsers import parse_jica_grant_notice
    from scripts.source_loader import load_enabled_sources
except ModuleNotFoundError:
    from http_client import HTTPFetchError, fetch_text
    from parsers import parse_jica_grant_notice
    from source_loader import load_enabled_sources


def load_watchlist(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_base_records(projects):
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
            "parser_name": "stub_orchestrator",
            "parser_version": "0.1",
            "fetched_at": now,
            "last_checked": now,
        })
    return records


def select_parser(source_type):
    if source_type == "jica_grant_notice":
        return parse_jica_grant_notice
    return None


def crawl_sources(projects, sources):
    records = build_base_records(projects)
    details = []

    for source in sources:
        source_type = source["source_type"]
        source_url = source["url"]
        parser_fn = select_parser(source_type)

        if parser_fn is None:
            details.append(f"{source_type}: 対応parser未実装のため要確認")
            continue

        try:
            html = fetch_text(source_url)
        except HTTPFetchError:
            details.append(f"{source_type}: HTTP取得失敗のため要確認")
            continue

        parsed = parser_fn(html, source_url)
        links = parsed.get("links", [])
        if links:
            details.append(f"{source_type}: 取得成功。候補リンク数 {len(links)}")
        else:
            details.append(f"{source_type}: 取得成功（該当案件未検出）のため要確認")

    joined = " | ".join(details) if details else "source処理結果なしのため要確認"
    for r in records:
        r["status_detail"] = joined

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    projects = load_watchlist(args.watchlist)
    sources = load_enabled_sources("config/sources.yml")
    records = crawl_sources(projects, sources)

    if args.dry_run:
        print(f"dry-run: {len(records)} records fetched")
        return

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
