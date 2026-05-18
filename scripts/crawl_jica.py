#!/usr/bin/env python3
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    from scripts.http_client import HTTPFetchError, fetch_text
    from scripts.parsers import parse_jica_grant_notice
    from scripts.parsers.jica_discovery import (
        PARSER_NAME,
        PARSER_VERSION,
        build_pdf_metadata_only_record,
        extract_candidates_with_diagnostics,
        parse_detail,
        _is_pdf_candidate,
        _should_reject_candidate,
        dedupe_and_prioritize_candidates,
    )
    from scripts.source_loader import load_enabled_sources
except ModuleNotFoundError:
    from http_client import HTTPFetchError, fetch_text
    from parsers import parse_jica_grant_notice
    from parsers.jica_discovery import (
        PARSER_NAME,
        PARSER_VERSION,
        build_pdf_metadata_only_record,
        extract_candidates_with_diagnostics,
        parse_detail,
        _is_pdf_candidate,
        _should_reject_candidate,
        dedupe_and_prioritize_candidates,
    )
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


def discover_records(sources, scope, fetcher=fetch_text, sleeper=time.sleep):
    target_sources = set(scope.get("sources", ["jica_grant_notice"]))
    max_pages = int(scope.get("max_pages_per_source", 10))
    max_detail = int(scope.get("max_detail_pages", 20))
    records, errors, count = [], [], 0
    now = datetime.now(timezone.utc).isoformat()
    request_interval = int(scope.get("request_interval_seconds", 1))
    sources_checked = 0
    list_fetch_success = 0
    anchors_seen_total = 0
    candidates_found_total = 0

    for source in sources:
        if source["source_type"] not in target_sources:
            continue
        if source["source_type"] != "jica_grant_notice":
            continue
        if count >= max_pages:
            break
        sources_checked += 1
        try:
            html = fetcher(source["url"])
        except HTTPFetchError as err:
            details = err.to_dict() if hasattr(err, "to_dict") else {}
            errors.append({
                "level": "error",
                "reason": "list_fetch_failed",
                "source_url": source.get("url", ""),
                "error_message": str(err),
                "status_code": details.get("status_code"),
                "exception_type": details.get("exception_type", ""),
                "response_excerpt": details.get("response_excerpt", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
            continue
        sleeper(request_interval)
        list_fetch_success += 1
        candidates, diagnostics = extract_candidates_with_diagnostics(html, source["url"], source["source_type"])
        anchors_seen_total += diagnostics.get("anchors_seen", 0)
        candidates_found_total += diagnostics.get("candidates_found", 0)
        if not candidates:
            errors.append({
                "level": "warning",
                "reason": "no_candidates_found",
                "source_url": source.get("url", ""),
                "anchors_seen": diagnostics.get("anchors_seen", 0),
                "candidates_found": diagnostics.get("candidates_found", 0),
                "sample_links": diagnostics.get("sample_links", []),
                "rejected_link_samples": diagnostics.get("rejected_link_samples", []),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
        prioritized, deduped_count = dedupe_and_prioritize_candidates(candidates, max_detail)
        for _ in range(deduped_count):
            errors.append({
                "level": "warning",
                "reason": "candidate_deduped",
                "source_url": source.get("url", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })

        for c in prioritized:
            rejected, reject_reason = _should_reject_candidate(c)
            if rejected:
                errors.append({
                    "level": "warning",
                    "reason": "candidate_rejected",
                    "reject_reason": reject_reason,
                    "candidate_url": c.get("candidate_url", ""),
                    "candidate_title": c.get("candidate_title", ""),
                    "source_url": c.get("source_url", source.get("url", "")),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
                continue

            if _is_pdf_candidate(c):
                records.append(build_pdf_metadata_only_record(c, now))
                continue

            try:
                detail_html = fetcher(c["candidate_url"])
            except HTTPFetchError as err:
                details = err.to_dict() if hasattr(err, "to_dict") else {}
                errors.append({
                    "level": "error",
                    "reason": "detail_fetch_failed",
                    "candidate_url": c.get("candidate_url", ""),
                    "candidate_title": c.get("candidate_title", ""),
                    "source_url": c.get("source_url", source.get("url", "")),
                    "error_message": str(err),
                    "status_code": details.get("status_code"),
                    "exception_type": details.get("exception_type", ""),
                    "response_excerpt": details.get("response_excerpt", ""),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
                continue
            records.append(parse_detail(detail_html, c, now))
            sleeper(request_interval)
        count += 1

    valid, validation_errors = validate_discovered_records(records)
    errors.extend(validation_errors)
    if not valid:
        print("warning: discover mode generated no valid records")
    return {
        "records": valid,
        "errors": errors,
        "meta": {
            "parser_name": PARSER_NAME,
            "parser_version": PARSER_VERSION,
            "sources_checked": sources_checked,
            "list_fetch_success": list_fetch_success,
            "anchors_seen": anchors_seen_total,
            "candidates_found": candidates_found_total,
            "candidate_deduped": sum(1 for e in errors if e.get("reason")=="candidate_deduped"),
            "candidate_rejected": sum(1 for e in errors if e.get("reason")=="candidate_rejected"),
        },
    }


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
