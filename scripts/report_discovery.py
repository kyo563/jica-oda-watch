#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"records": data, "errors": [], "meta": {}}
    return {"records": data.get("records", []), "errors": data.get("errors", []), "meta": data.get("meta", {})}


def _missing_counts(records: list[dict]) -> dict:
    return {
        "notice_url_missing": sum(1 for r in records if not (r.get("notice_url") or "").strip()),
        "notice_date_missing": sum(1 for r in records if not (r.get("notice_date") or "").strip()),
        "evidence_text_missing": sum(1 for r in records if not (r.get("evidence_text") or "").strip()),
        "raw_text_missing_or_short": sum(1 for r in records if len((r.get("raw_text") or "").strip()) < 40),
        "project_name_yokakunin": sum(1 for r in records if (r.get("project_name") or "").strip() == "要確認"),
    }


def _duplicate_project_ids(records: list[dict]) -> list[str]:
    c = Counter((r.get("project_id") or "").strip() for r in records if (r.get("project_id") or "").strip())
    return sorted([k for k, v in c.items() if v > 1])


def _review_status(records: list[dict], dups: list[str], missing: dict, low_rate: float) -> str:
    if dups or not records or low_rate == 1.0 or missing["evidence_text_missing"] >= max(1, int(len(records) * 0.8)):
        return "BLOCK"
    if low_rate >= 0.5 or missing["notice_date_missing"] >= max(1, int(len(records) * 0.5)):
        return "REVIEW"
    return "PASS_CANDIDATE"


def build_report(obj: dict) -> str:
    records = obj.get("records", [])
    errors = obj.get("errors", [])

    confidence = Counter((r.get("parse_confidence") or "unknown") for r in records)
    source_types = Counter((r.get("source_type") or "unknown") for r in records)
    pq_dist = Counter((r.get("pq_required") or "unknown") for r in records)
    dups = _duplicate_project_ids(records)
    missing = _missing_counts(records)
    all_low = bool(records) and all((r.get("parse_confidence") or "") == "low" for r in records)
    low_count = confidence.get("low", 0)
    low_rate = (low_count / len(records)) if records else 0.0
    review_status = _review_status(records, dups, missing, low_rate)

    lines = [
        "# discovery_report",
        "",
        "## 集計",
        f"- review_status: {review_status}",
        f"- records件数: {len(records)}",
        f"- errors件数: {len(errors)}",
        f"- project_id重複件数: {len(dups)}",
        f"- notice_url欠落件数: {missing['notice_url_missing']}",
        f"- evidence_text欠落件数: {missing['evidence_text_missing']}",
        f"- notice_date欠落件数: {missing['notice_date_missing']}",
        f"- raw_text欠落/短文件数(<40): {missing['raw_text_missing_or_short']}",
        f"- project_name=要確認 件数: {missing['project_name_yokakunin']}",
        f"- parse_confidence全件low: {'はい' if all_low else 'いいえ'}",
        f"- parse_confidence low率: {low_rate:.0%}",
        "",
        "## parse_confidence別件数",
    ]
    for k, v in sorted(confidence.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("## pq_required別件数")
    for k in ["あり", "なし", "要確認", "unknown"]:
        lines.append(f"- {k}: {pq_dist.get(k, 0)}")

    lines.append("")
    lines.append("## source_type別件数")
    for k, v in sorted(source_types.items()):
        lines.append(f"- {k}: {v}")

    lines.extend(["", "## 警告", "- 初期段階のため警告中心。自動停止はしません。"])
    if dups:
        lines.append(f"- 重複project_id: {', '.join(dups[:10])}")
    if all_low:
        lines.append("- parse_confidenceが全件lowです。Sheets投入は見合わせてください。")
    if low_rate >= 0.5:
        lines.append("- parse_confidenceのlow率が高いです。手動レビューを強化してください。")
    if pq_dist.get("要確認", 0) >= max(1, int(len(records) * 0.5)):
        lines.append("- pq_required=要確認 が多いです。PQ判定は保留してください。")
    if missing["notice_date_missing"] >= max(1, int(len(records) * 0.5)):
        lines.append("- notice_date欠落が多いです。日付抽出ロジックまたは元ページを確認してください。")

    if dups:
        lines.extend(["", "## 重複project_id詳細", "", "| project_id | project_name | notice_url |", "|---|---|---|"])
        for pid in dups:
            for r in [x for x in records if (x.get("project_id") or "").strip() == pid][:5]:
                lines.append(
                    "| {pid} | {name} | {url} |".format(
                        pid=(r.get("project_id") or "").replace("|", "/"),
                        name=(r.get("project_name") or "").replace("|", "/"),
                        url=(r.get("notice_url") or "").replace("|", "/"),
                    )
                )

    high_risk_rows = []
    for r in records:
        reasons = []
        if (r.get("parse_confidence") or "") == "low":
            reasons.append("low_confidence")
        if not (r.get("evidence_text") or "").strip():
            reasons.append("missing_evidence")
        if not (r.get("notice_date") or "").strip():
            reasons.append("missing_notice_date")
        if reasons:
            high_risk_rows.append((r, ", ".join(reasons)))
    if high_risk_rows:
        lines.extend(["", "## high-risk records", "", "| project_id | project_name | reason | notice_url | parse_confidence |", "|---|---|---|---|---|"])
        for r, reason in high_risk_rows[:20]:
            lines.append(
                "| {pid} | {name} | {reason} | {url} | {conf} |".format(
                    pid=(r.get("project_id") or "").replace("|", "/"),
                    name=(r.get("project_name") or "").replace("|", "/"),
                    reason=reason.replace("|", "/"),
                    url=(r.get("notice_url") or "").replace("|", "/"),
                    conf=(r.get("parse_confidence") or "").replace("|", "/"),
                )
            )

    lines.extend(["", "## 先頭10件", "", "| project_id | project_name | notice_date | notice_url | parse_confidence |", "|---|---|---|---|---|"])
    for r in records[:10]:
        lines.append(
            "| {pid} | {name} | {date} | {url} | {conf} |".format(
                pid=(r.get("project_id") or "").replace("|", "/"),
                name=(r.get("project_name") or "").replace("|", "/"),
                date=(r.get("notice_date") or "").replace("|", "/"),
                url=(r.get("notice_url") or "").replace("|", "/"),
                conf=(r.get("parse_confidence") or "").replace("|", "/"),
            )
        )

    lines.extend(["", "## errors要約"])
    if not errors:
        lines.append("- なし")
    else:
        reason_counts = Counter((e.get("reason") or "unknown") for e in errors)
        for reason, cnt in sorted(reason_counts.items()):
            lines.append(f"- {reason}: {cnt}")

    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    obj = _load(args.input)
    report = build_report(obj)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    main()
