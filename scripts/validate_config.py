#!/usr/bin/env python3
import csv
import sys
import yaml

REQUIRED_WATCHLIST_COLUMNS = {"project_id", "country", "project_name", "keywords"}


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


def main():
    try:
        validate_watchlist("config/watchlist.example.csv")
        validate_sources("config/sources.yml")
    except Exception as e:
        print(f"NG: {e}")
        sys.exit(1)
    print("OK: config validation passed")


if __name__ == "__main__":
    main()
