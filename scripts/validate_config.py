#!/usr/bin/env python3
import csv
import sys
import yaml

REQUIRED_WATCHLIST_COLUMNS = {"project_id", "country", "project_name", "keywords"}
MANUAL_FIELDS = {
    "manual_status",
    "memo",
    "next_manual_action",
    "owner",
    "manual_checked_date",
    "manual_updated_at",
    "manual_updated_by",
}
REQUIRED_SOURCE_FIELDS = {"source_type", "url", "enabled"}


def validate_watchlist(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_WATCHLIST_COLUMNS - headers
        if missing:
            raise ValueError(f"watchlist列不足: {sorted(missing)}")
        ids = set()
        for row in reader:
            pid = row["project_id"].strip()
            if not pid:
                raise ValueError("空のproject_idがあります")
            if pid in ids:
                raise ValueError(f"project_id重複: {pid}")
            ids.add(pid)


def validate_sources(path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "sources" not in data or not isinstance(data["sources"], list):
        raise ValueError("sources.yml: sourcesリストが必要です")
    for i, source in enumerate(data["sources"]):
        if not isinstance(source, dict):
            raise ValueError(f"sources.yml: sources[{i}] がオブジェクトではありません")
        missing = REQUIRED_SOURCE_FIELDS - set(source.keys())
        if missing:
            raise ValueError(f"sources.yml: sources[{i}] の必須項目不足: {sorted(missing)}")


def validate_sheet_schema(path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    sheets = data.get("sheets", {})
    watch = sheets.get("JICA_ODA_WATCH", {})

    auto_fields = set(watch.get("auto_fields", []))
    manual_fields = set(watch.get("manual_fields", []))
    diff_fields = watch.get("diff_fields")

    if manual_fields != MANUAL_FIELDS:
        raise ValueError("sheet_schema.yml: manual_fields が期待値と不一致です")

    if not isinstance(diff_fields, list) or not diff_fields:
        raise ValueError("sheet_schema.yml: diff_fields が必要です")

    diff_fields_set = set(diff_fields)
    if not diff_fields_set.issubset(auto_fields):
        invalid = sorted(diff_fields_set - auto_fields)
        raise ValueError(f"sheet_schema.yml: diff_fields は auto_fields の部分集合である必要があります: {invalid}")

    overlap = sorted(manual_fields & diff_fields_set)
    if overlap:
        raise ValueError(f"sheet_schema.yml: manual_fields と diff_fields が重複しています: {overlap}")




def validate_crawl_scope(path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    scope = data.get("scope", {})
    if not isinstance(scope, dict):
        raise ValueError("crawl_scope.yml: scopeが必要です")
    for key in ["schemes", "sources"]:
        if not isinstance(scope.get(key), list) or not scope.get(key):
            raise ValueError(f"crawl_scope.yml: scope.{key} は空でない配列が必要です")
    for key in ["max_pages_per_source", "max_detail_pages", "request_interval_seconds"]:
        val = scope.get(key)
        if not isinstance(val, int) or val < 1:
            raise ValueError(f"crawl_scope.yml: scope.{key} は1以上の整数が必要です")


def main():
    try:
        validate_watchlist("config/watchlist.example.csv")
        validate_sources("config/sources.yml")
        validate_sheet_schema("config/sheet_schema.yml")
        validate_crawl_scope("config/crawl_scope.yml")
    except Exception as e:
        print(f"NG: {e}")
        sys.exit(1)
    print("OK: config validation passed")


if __name__ == "__main__":
    main()
