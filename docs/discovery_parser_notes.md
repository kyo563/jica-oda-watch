# Discovery Parser Notes (first-pass)

## 初期対象source
- `jica_grant_notice`

## 取得対象URL
- discover listページから抽出した detail URL（`candidate_url`）
- 例: `https://www.jica.go.jp/.../index.html`

## 抽出想定（first-pass）
- `project_name`
  - 優先: `<h1>`, `<h2>`, `<title>`
  - fallback: `candidate_title`
- `notice_date`
  - 本文テキスト内の日付文字列（例: `2026年5月1日`）
- `raw_text`
  - detail本文テキストを正規化して短く保持（上限あり）
- `evidence_text`
  - 「公告」「公示」「入札」「事前資格審査」など周辺の短い抜粋
- `notice_url`
  - canonicalized `candidate_url`

## 取れない項目（推測しない）
- `country`（明示記載がない場合）
- `sector`（明示記載がない場合）
- `ga_date`（GA日付と断定できない場合）
- `pq_required`（肯定/否定が明確でない場合は `要確認`）

## 低信頼（parse_confidence=low）条件
- heading/title が取れない
- または本文テキスト不足
- または candidate metadata 依存が強い

## 補足
- discover mode は検証段階。
- Sheets投入前に `discovery_report.md` を人間確認する。
- `parse_confidence` が low ばかりの場合、投入しない。
- schedule の discover 切替はまだ行わない。
