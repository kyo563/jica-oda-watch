#!/usr/bin/env python3
from pathlib import Path

import yaml

REQUIRED_SOURCE_FIELDS = {"source_type", "url", "enabled"}


def load_enabled_sources(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    sources = data.get("sources")
    if not isinstance(sources, list):
        raise ValueError("sources.yml: sourcesリストが必要です")

    enabled_sources = []
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"sources.yml: sources[{i}] がオブジェクトではありません")
        missing = REQUIRED_SOURCE_FIELDS - set(source.keys())
        if missing:
            raise ValueError(f"sources.yml: sources[{i}] の必須項目不足: {sorted(missing)}")
        if source["enabled"] is True:
            enabled_sources.append(source)

    return enabled_sources
