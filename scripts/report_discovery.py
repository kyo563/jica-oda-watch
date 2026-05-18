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
        "project_id_missing": sum(1 for r in records if not (r.get("project_id") or "").strip()),
    }


def _duplicate_project_ids(records: list[dict]) -> list[str]:
    c = Counter((r.get("project_id") or "").strip() for r in records if (r.get("project_id") or "").strip())
    return sorted([k for k, v in c.items() if v > 1])


def _review_status(records: list[dict], errors: list[dict], dups: list[str], missing: dict, low_rate: float) -> str:
    n = len(records)
    error_count = len(errors)
    notice_missing_rate = (missing["notice_url_missing"] / n) if n else 0.0
    error_rate = (error_count / n) if n else (1.0 if error_count else 0.0)

    if dups or not records or low_rate == 1.0 or missing["project_id_missing"] > 0:
        return "BLOCK"
    if missing["evidence_text_missing"] >= max(1, int(n * 0.8)):
        return "BLOCK"
    if error_count >= max(1, n):
        return "BLOCK"
    if notice_missing_rate >= 0.8:
        return "BLOCK"

    if low_rate >= 0.5 or missing["notice_date_missing"] >= max(1, int(n * 0.5)):
        return "REVIEW"
    if error_rate >= 0.3:
        return "REVIEW"
    if notice_missing_rate >= 0.5:
        return "REVIEW"
    if missing["evidence_text_missing"] >= max(1, int(n * 0.5)):
        return "REVIEW"
    return "PASS_CANDIDATE"


def build_report(obj: dict) -> str:
    records = obj.get("records", [])
    errors = obj.get("errors", [])
    meta = obj.get("meta", {})

    confidence = Counter((r.get("parse_confidence") or "unknown") for r in records)
    source_types = Counter((r.get("source_type") or "unknown") for r in records)
    pq_dist = Counter((r.get("pq_required") or "unknown") for r in records)
    dups = _duplicate_project_ids(records)
    missing = _missing_counts(records)
    all_low = bool(records) and all((r.get("parse_confidence") or "") == "low" for r in records)
    low_count = confidence.get("low", 0)
    low_rate = (low_count / len(records)) if records else 0.0
    review_status = _review_status(records, errors, dups, missing, low_rate)
    error_rate = (len(errors) / len(records)) if records else (1.0 if errors else 0.0)
    reject_warnings = [e for e in errors if (e.get("reason") or "") == "candidate_rejected"]
    deduped_warnings = [e for e in errors if (e.get("reason") or "") == "candidate_deduped"]
    reject_reason_counts = Counter((e.get("reject_reason") or "unknown") for e in reject_warnings)
    pdf_metadata_only_count = sum(1 for r in records if (r.get("status_detail") or "") == "pdf_metadata_only")
    non_project_records = sum(1 for r in records if any(x in (r.get("notice_url") or "") for x in ["/forresearchers", "/about/announce/notice", "/about/announce/manual", "/about/disc/settle", "/about/chotatsu/program/"]))
    mojibake_detected = sum(1 for r in records if any(x in (r.get("project_name") or "") for x in ["ã", "ã", "ã", "Â", "ï¼"]))

    lines = [
        "# discovery_report",
        "",
        "## 集計",
        f"- review_status: {review_status}",
        f"- records件数: {len(records)}",
        f"- errors件数: {len(errors)}",
        f"- duplicate_project_id件数: {len(dups)}",
        f"- project_id_missing件数: {missing['project_id_missing']}",
        f"- error率(records比): {error_rate:.0%}",
        f"- notice_url欠落件数: {missing['notice_url_missing']}",
        f"- evidence_text欠落件数: {missing['evidence_text_missing']}",
        f"- notice_date欠落件数: {missing['notice_date_missing']}",
        f"- raw_text欠落/短文件数(<40): {missing['raw_text_missing_or_short']}",
        f"- project_name=要確認 件数: {missing['project_name_yokakunin']}",
        f"- parse_confidence全件low: {'はい' if all_low else 'いいえ'}",
        f"- parse_confidence low率: {low_rate:.0%}",
        f"- pdf_metadata_only件数: {pdf_metadata_only_count}",
        f"- mojibake_detected件数: {mojibake_detected}",
        f"- high-risk records総数: 0",
        "",
        "",
        "## candidate抽出診断",
        f"- sources_checked: {meta.get('sources_checked', 0)}",
        f"- list_fetch_success: {meta.get('list_fetch_success', 0)}",
        f"- anchors_seen: {meta.get('anchors_seen', 0)}",
        f"- candidates_found: {meta.get('candidates_found', 0)}",
        f"- candidate_deduped: {len(deduped_warnings)}",
        f"- candidate_rejected: {len(reject_warnings)}",
        f"- pdf_metadata_only件数: {pdf_metadata_only_count}",
        f"- non_project records件数: {non_project_records}",

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
    if missing["project_id_missing"] > 0:
        lines.append("- project_id欠落があります。Sheets投入は停止してください。")
    if len(errors) >= max(1, len(records)):
        lines.append("- errorsがrecords以上です。再クロール/修正後に再判定してください。")
    if error_rate >= 0.3:
        lines.append("- errors率が高いです。再クロールまたはパーサ確認を推奨します。")
    notice_missing_rate = (missing["notice_url_missing"] / len(records)) if records else 0.0
    if notice_missing_rate >= 0.5:
        lines.append("- notice_url欠落が多いです。detail抽出の確認が必要です。")
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
    lines = [x if x != "- high-risk records総数: 0" else f"- high-risk records総数: {len(high_risk_rows)}" for x in lines]
    if high_risk_rows:
        lines.extend(["", "## high-risk records", "- ※表示は先頭20件まで", "", "| project_id | project_name | reason | notice_url | parse_confidence |", "|---|---|---|---|---|"])
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

    if reject_reason_counts:
        lines.append("")
        lines.append("## candidate_rejected内訳")
        for reason, cnt in sorted(reject_reason_counts.items()):
            lines.append(f"- {reason}: {cnt}")

    if not errors:
        lines.append("- なし")
    else:
        reason_counts = Counter((e.get("reason") or "unknown") for e in errors)
        for reason, cnt in sorted(reason_counts.items()):
            lines.append(f"- {reason}: {cnt}")


    no_candidate_warnings = [e for e in errors if (e.get("reason") or "") == "no_candidates_found"]
    if no_candidate_warnings:
        lines.extend(["", "## no_candidates_found詳細"])
        for w in no_candidate_warnings:
            lines.append(f"- source_url: {w.get('source_url','')}")
            lines.append(f"  - anchors_seen: {w.get('anchors_seen', 0)}")
            lines.append(f"  - candidates_found: {w.get('candidates_found', 0)}")
            sample_links = w.get("sample_links", [])
            if sample_links:
                lines.append("  - sample_links:")
                for item in sample_links[:10]:
                    lines.append(f"    - [{item.get('title','')}]({item.get('url','')})")
            rejected = w.get("rejected_link_samples", [])
            if rejected:
                lines.append("  - rejected_link_samples:")
                for item in rejected[:20]:
                    lines.append(f"    - [{item.get('title','')}]({item.get('url','')})")

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
