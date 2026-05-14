from scripts.source_loader import load_enabled_sources


def test_load_enabled_sources_only(tmp_path):
    p = tmp_path / "sources.yml"
    p.write_text(
        """
sources:
  - source_type: a
    url: https://a
    enabled: true
  - source_type: b
    url: https://b
    enabled: false
""".strip(),
        encoding="utf-8",
    )

    sources = load_enabled_sources(p)
    assert len(sources) == 1
    assert sources[0]["source_type"] == "a"
