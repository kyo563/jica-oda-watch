from typing import TypedDict


class ParsedRecord(TypedDict, total=False):
    # parserが返す最小record形式
    project_id: str
    country: str
    project_name: str
    status_auto: str
    status_detail: str
    source_type: str
    source_url: str
    oda_url: str
    raw_text: str
    parser_name: str
    parser_version: str
    fetched_at: str
    last_checked: str
