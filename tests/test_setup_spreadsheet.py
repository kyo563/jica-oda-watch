from scripts.setup_spreadsheet import build_sheet_definitions, load_schema


def test_build_sheet_definitions_includes_required_sheets():
    schema = load_schema("config/sheet_schema.yml")
    defs = build_sheet_definitions(schema)
    assert set(defs.keys()) == {
        "JICA_ODA_WATCH",
        "JICA_ODA_MANUAL",
        "JICA_ODA_HISTORY",
        "JICA_ODA_RAW",
        "JICA_ODA_CONFIG",
    }


def test_watch_header_order_auto_then_manual():
    schema = load_schema("config/sheet_schema.yml")
    defs = build_sheet_definitions(schema)
    watch = defs["JICA_ODA_WATCH"].headers
    auto = schema["sheets"]["JICA_ODA_WATCH"]["auto_fields"]
    manual = schema["sheets"]["JICA_ODA_WATCH"]["manual_fields"]

    assert watch == auto + manual
    assert watch[-len(manual):] == manual


def test_history_headers_follow_schema():
    schema = load_schema("config/sheet_schema.yml")
    defs = build_sheet_definitions(schema)
    assert defs["JICA_ODA_HISTORY"].headers == schema["sheets"]["JICA_ODA_HISTORY"]["fields"]


def test_manual_raw_config_definitions_have_expected_headers():
    schema = load_schema("config/sheet_schema.yml")
    defs = build_sheet_definitions(schema)
    assert "manual_status" in defs["JICA_ODA_MANUAL"].headers
    assert "raw_html_excerpt" in defs["JICA_ODA_RAW"].headers
    assert defs["JICA_ODA_CONFIG"].headers == ["key", "value", "description", "updated_at"]
