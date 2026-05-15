# JICA ODA案件ウォッチャー

JICAのODA案件（特に無償資金協力）を定期監視し、**Google Sheetsを正本**として管理、GitHub Pagesでモバイル閲覧できるMVPです。

## 目的
- 公式情報を取得し、案件ごとの状態変化を追跡
- 手入力メモを保護しながら自動更新
- 差分履歴を保持
- Pagesで一覧表示

## アーキテクチャ（MVP）
- 収集: `scripts/crawl_jica.py`
- 差分: `scripts/diff_records.py`
- Sheets更新: `scripts/update_sheets.py`
- 表示: `site/`
- 定期実行: `.github/workflows/jica_watch.yml`

## セットアップ
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 必須環境変数
- Google Sheetsへ実書き込みする場合は、`GOOGLE_SERVICE_ACCOUNT_JSON` と `SPREADSHEET_ID` が必要です。

任意:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

## ローカル実行手順（MVP）
`--dry-run` は「外部更新（例: Google Sheets書き込み）を止める」ために使います。
このMVPでは `crawl_jica.py --dry-run` は出力ファイルを作らないため、差分処理の前段では使いません。

```bash
python scripts/validate_config.py
python scripts/crawl_jica.py --watchlist config/watchlist.example.csv --output data/raw/latest.json
python scripts/diff_records.py --previous data/snapshots/previous.json --current data/raw/latest.json --output site/data/projects.json
python scripts/update_sheets.py --input site/data/projects.json --dry-run
```

## snapshot（暫定MVP設計）
- `data/snapshots/previous.json` が存在しない場合、差分処理は「前回データなし」として扱い、全件 `new` になります。
- この `previous.json` は**暫定MVP用**です。正本はGoogle Sheetsです。
- TODO: 将来は `previous.json` ではなく、Google Sheets の WATCH / MANUAL / HISTORY から既存データを読み込む構成に移行します。

## GitHub Actions / Pages反映（現状）
- `schedule` 実行は dry-run のみです（Google Sheetsへ実書き込みしません）。
- `workflow_dispatch` で `write_sheets=true` の場合のみ Google Sheetsへ実書き込みします。
- 実書き込み前に `pytest -q` を実行します。
- Secrets（`GOOGLE_SERVICE_ACCOUNT_JSON`, `SPREADSHEET_ID`）は実書き込みstepにのみ渡します。

## 制約
- 公示消滅は契約確定とみなさない（`missing` + 要確認）
- AI要約は任意で、事実判定には使わない
- 手入力列は自動更新で上書きしない

## TODO（次フェーズ）
- 公式ページ本格パーサ実装
- Google Sheets API実装
- Pages詳細画面とメモ投稿

## Google Sheets仕様

詳細な初回セットアップ手順とシート仕様は `docs/google_sheets_setup.md` を参照してください。


### 基本方針
- Google Sheetsを正本とする。
- GitHub Pagesは閲覧・入力補助UIであり、正本ではない。
- `project_id` を主キーとし、行番号に依存しない。
- manual fieldsは自動処理で上書きしない。
- `missing` は「掲載消滅／要確認」であり、案件終了確定ではない。
- AI要約は補助情報であり、事実判定の根拠に使わない。

### シート構成
| シート名 | 役割 | 更新主体 | 備考 |
|---|---|---|---|
| JICA_ODA_WATCH | 案件ごとの最新状態を保持するメインシート | crawler / 手入力 | auto fields + manual fields |
| JICA_ODA_MANUAL | 手入力情報を分離管理する補助シート | 人間 | 将来の双方向入力用 |
| JICA_ODA_HISTORY | 差分履歴をappend-onlyで保存 | crawler | 削除・上書きしない |
| JICA_ODA_RAW | 取得原文・証跡・parser結果を保存 | crawler | AI要約だけに依存しない証跡 |
| JICA_ODA_CONFIG | 運用設定・補助設定を保存 | 人間 / 管理者 | 将来拡張用 |

### JICA_ODA_WATCH
- メインシート。`auto fields`（自動更新列）と`manual fields`（手入力列）で構成。
- manual fieldsは自動更新で上書きしない。

### JICA_ODA_MANUAL
- 手入力専用情報を分離管理する補助シート。
- 将来のPages/Apps Script入力連携を想定。

### JICA_ODA_HISTORY
- 変更履歴をappend-onlyで管理。
- 既存履歴の削除・上書きはしない。

### JICA_ODA_RAW
- 取得時の原文・抜粋・parser情報・エラーを保持する証跡シート。
- AI要約だけを保存してRAWを捨てる運用は禁止。

### JICA_ODA_CONFIG
- 運用設定の受け皿シート（初期は器のみ）。

### 自動更新列と手入力列
- auto fields: crawler / parser / diff / AI補助処理が更新。
- manual fields: 人間の判断を保持する列。自動処理で上書き禁止。

### 差分検知対象
`config/sheet_schema.yml` の `diff_fields` を差分検知対象とする。
除外方針:
- `fetched_at`
- `last_checked`
- `change_flag`
- `ai_*` 系
- manual fields

現在の `diff_fields`:
`country, project_name, sector, scheme, ga_date, pq_required, notice_date, notice_media, notice_url, result_url, oda_url, status_auto, status_detail, source_type, source_url, raw_text, evidence_text, parser_name, parser_version, parse_confidence`

### 入力規則
初回セットアップで可能な範囲で以下を設定:
| 対象列 | 許可値 |
|---|---|
| change_flag | new / updated / missing / no_change / ai_low_confidence / error / manual_updated |
| manual_status | 空欄 / 未確認 / 確認中 / 対応不要 / 要対応 / 対応済み / 保留 |
| pq_required | 空欄 / 要確認 / あり / なし / 不明 |

### 書式・保護方針
- 1行目固定
- ヘッダー太字
- フィルター設定
- 列幅調整
- 折り返し表示
- auto/manual色分け
- manual fieldsに説明note

保護方針:
- auto fieldsは保護候補
- manual fieldsは編集不能にしない
- 権限制約で保護設定に失敗しても警告ログで継続

## Google Sheets運用上の注意
- 既存シートは削除しない。
- 2行目以降の既存データは削除しない。
- 初回セットアップApps Scriptでは、1行目ヘッダーをschemaに合わせて設定・補正する。
- Google Sheets APIによる実書き込み時は、ヘッダーがschemaと一致しない場合、補正せず停止する。
- manual fieldsは自動更新で上書きしない。
- WATCH=最新状態、HISTORY=履歴、RAW=証跡を分離運用する。
- 掲載が消えた案件は削除せず `missing` / `掲載消滅／要確認` として扱う。
- AI要約は補助情報であり、公式情報の代替ではない。


### Apps Scriptで初回セットアップする方法

初回セットアップは `gas/setup_spreadsheet.gs` を使用します。

詳細手順は `docs/google_sheets_setup.md` を参照してください。

推奨スプレッドシート名: `JICA ODA Watch Master`

概要:

1. Googleスプレッドシートを開く
2. スプレッドシート名を `JICA ODA Watch Master` に変更する
3. 拡張機能 → Apps Script
4. `gas/setup_spreadsheet.gs` の内容を `Code.gs` に貼り付ける
5. `setupJicaOdaWatch` を実行する
6. 5シート作成後、スプレッドシート側のApps Scriptコードは削除してよい
