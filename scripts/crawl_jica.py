#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    from scripts.http_client import HTTPFetchError, fetch_text
    from scripts.parsers import parse_jica_grant_notice
    from scripts.parsers.jica_discovery import PARSER_NAME, PARSER_VERSION, extract_candidates, parse_detail
    from scripts.source_loader import load_enabled_sources
except ModuleNotFoundError:
    from http_client import HTTPFetchError, fetch_text
    from parsers import parse_jica_grant_notice
    from parsers.jica_discovery import PARSER_NAME, PARSER_VERSION, extract_candidates, parse_detail
    from source_loader import load_enabled_sources


def load_watchlist(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_crawl_scope(path="config/crawl_scope.yml"):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("scope", {})


def build_base_records(projects):
    now = datetime.now(timezone.utc).isoformat()
    return [{
        "project_id": p["project_id"], "country": p["country"], "project_name": p["project_name"],
        "sector": p.get("sector", ""), "scheme": p.get("scheme", "無償資金協力"), "status_auto": "要確認",
        "status_detail": "初期MVPのダミー収集結果", "source_type": "stub", "source_url": "https://www.jica.go.jp/oda/",
        "oda_url": "https://www.jica.go.jp/oda/", "raw_text": p.get("keywords", ""), "parser_name": "stub_orchestrator",
        "parser_version": "0.1", "fetched_at": now, "last_checked": now,
    } for p in projects]


def select_parser(source_type):
    return parse_jica_grant_notice if source_type == "jica_grant_notice" else None


def crawl_sources(projects, sources):
    records = build_base_records(projects)
    details = []
    for source in sources:
        parser_fn = select_parser(source["source_type"])
        if parser_fn is None:
            details.append(f"{source['source_type']}: 対応parser未実装のため要確認")
            continue
        try:
            html = fetch_text(source["url"])
        except HTTPFetchError:
            details.append(f"{source['source_type']}: HTTP取得失敗のため要確認")
            continue
        links = parser_fn(html, source["url"]).get("links", [])
        details.append(f"{source['source_type']}: 取得成功。候補リンク数 {len(links)}" if links else f"{source['source_type']}: 取得成功（該当案件未検出）のため要確認")
    joined = " | ".join(details) if details else "source処理結果なしのため要確認"
    for r in records:
        r["status_detail"] = joined
    return records


def validate_discovered_records(records):
    valid, errors, seen = [], [], set()
    for r in records:
        missing = []
        if not (r.get("project_id") or "").strip(): missing.append("project_id")
        if not (r.get("project_name") or "").strip(): missing.append("project_name")
        if not ((r.get("source_url") or "").strip() or (r.get("notice_url") or "").strip()): missing.append("source_url/notice_url")
        if not (r.get("parser_name") or "").strip(): missing.append("parser_name")
        if not (r.get("parser_version") or "").strip(): missing.append("parser_version")
        pid = (r.get("project_id") or "").strip()
        if pid and pid in seen: missing.append("duplicate_project_id")
        if pid: seen.add(pid)
        if missing:
            errors.append({"level": "error", "reason": ",".join(missing), "record": r})
        else:
            valid.append(r)
    return valid, errors


def discover_records(sources, scope):
    target_sources = set(scope.get("sources", ["jica_grant_notice"]))
    max_pages = int(scope.get("max_pages_per_source", 10))
    max_detail = int(scope.get("max_detail_pages", 20))
    records, count = [], 0
    now = datetime.now(timezone.utc).isoformat()

    for source in sources:
        if source["source_type"] not in target_sources:
            continue
        if source["source_type"] != "jica_grant_notice":
            continue
        if count >= max_pages:
            break
        try:
            html = fetch_text(source["url"])
        except HTTPFetchError:
            continue
        candidates = extract_candidates(html, source["url"], source["source_type"])
        for c in candidates[:max_detail]:
            try:
                detail_html = fetch_text(c["candidate_url"])
            except HTTPFetchError:
                detail_html = ""
            records.append(parse_detail(detail_html, c, now))
        count += 1

    valid, errors = validate_discovered_records(records)
    if not valid:
        print("warning: discover mode generated no valid records")
    return {"records": valid, "errors": errors, "meta": {"parser_name": PARSER_NAME, "parser_version": PARSER_VERSION}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["watchlist", "discover"], default=None)
    p.add_argument("--watchlist", required=False)
    p.add_argument("--output", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    mode = args.mode or ("watchlist" if args.watchlist else "discover")
    sources = load_enabled_sources("config/sources.yml")

    if mode == "watchlist":
        if not args.watchlist:
            raise SystemExit("watchlist mode requires --watchlist")
        projects = load_watchlist(args.watchlist)
        output_obj = crawl_sources(projects, sources)
    else:
        scope = load_crawl_scope("config/crawl_scope.yml")
        output_obj = discover_records(sources, scope)

    if args.dry_run:
        n = len(output_obj if isinstance(output_obj, list) else output_obj.get("records", []))
        print(f"dry-run: {n} records fetched")
        return

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_obj, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
