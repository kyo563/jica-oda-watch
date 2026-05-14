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
    manual_fields = set(watch.get("manual_fields", []))
    if manual_fields != MANUAL_FIELDS:
        raise ValueError(
            "sheet_schema.yml: manual_fields がAGENTS.md定義と不一致です"
        )


def main():
    try:
        validate_watchlist("config/watchlist.example.csv")
        validate_sources("config/sources.yml")
        validate_sheet_schema("config/sheet_schema.yml")
    except Exception as e:
        print(f"NG: {e}")
        sys.exit(1)
    print("OK: config validation passed")


if __name__ == "__main__":
    main()
