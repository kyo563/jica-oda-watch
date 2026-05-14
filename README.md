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
- Sheets更新設計: `scripts/update_sheets.py`（骨格）
- 表示: `site/`
- 定期実行: `.github/workflows/jica_watch.yml`

## セットアップ
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 必須環境変数
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `SPREADSHEET_ID`（GitHub Actions secretで設定）

任意:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `APPS_SCRIPT_ENDPOINT`
- `APPS_SCRIPT_SHARED_SECRET`

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
- 現在は **dry-run / Pages JSON生成確認段階** です。
- MVPでは `site/data/projects.json` を生成し、必要に応じてコミットしてPagesへ反映する方針です。
- 自動コミットは次フェーズで安全性確認後に実装します。

## 制約
- 公示消滅は契約確定とみなさない（`missing` + 要確認）
- AI要約は任意で、事実判定には使わない
- 手入力列は自動更新で上書きしない

## TODO（次フェーズ）
- 公式ページ本格パーサ実装
- Google Sheets API実装
- Apps Script連携
- Pages詳細画面とメモ投稿
