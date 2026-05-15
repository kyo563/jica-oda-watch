# Discovery Validation Log

## 実行概要

- 実行日: 2026-05-15
- 対象Issue: #26
- 実行者: Codex
- 実行環境: `/workspace/jica-oda-watch` (local CLI, UTC)
- discover mode: 実施（小規模スコープ）
- Sheets接続: 未実施
- workflow変更: 未実施

## 一時crawl_scope設定

```yaml
scope:
  schemes:
    - grant_aid
  sources:
    - jica_grant_notice
  max_pages_per_source: 1
  request_interval_seconds: 2
  max_detail_pages: 10
```

## 実行コマンド

```bash
python scripts/validate_config.py
python scripts/crawl_jica.py --mode discover --output data/raw/discovered.json
python scripts/report_discovery.py --input data/raw/discovered.json --output data/raw/discovery_report.md
```

## 実行結果サマリー

* records件数: 0
* errors件数: 1
* review_status: BLOCK
* project_id重複: 0
* project_id_missing: 0
* notice_url欠落: 0
* notice_date欠落: 0
* evidence_text欠落: 0
* raw_text短文: 0
* high-risk records件数: 0

## parse_confidence分布

| parse_confidence | 件数 |
| ---------------- | -: |
| medium           | 0 |
| low              | 0 |
| その他              | 0 |

## pq_required分布

| pq_required | 件数 |
| ----------- | -: |
| あり          | 0 |
| なし          | 0 |
| 要確認         | 0 |
| 空欄/その他      | 0 |

## 手動照合結果

公式ページ直接確認不可（records=0 のため照合対象なし。取得結果は `list_fetch_failed` のみ）。

| No | project_id | project_name | notice_url | project_name妥当性 | notice_date妥当性 | evidence_text妥当性 | pq_required妥当性 | raw_text品質 | 判定              | メモ |
| -: | ---------- | ------------ | ---------- | --------------- | -------------- | ---------------- | -------------- | ---------- | --------------- | -- |
|  1 | N/A | N/A | https://www.jica.go.jp/activities/schemes/grant_aid/chotatsu/index.html | 要確認 | 要確認 | 要確認 | 要確認 | 要確認 | BLOCK | list_fetch_failed により records 未生成 |

## 発見した問題

* `jica_grant_notice` の一覧ページ取得が失敗し、discover結果が0件になった。
* `review_status=BLOCK` で、今回の出力は候補化判断に使える品質に達していない。

## parser/report/crawler別の課題

### parser

* recordsが0件のため、抽出品質（date/PQ/confidence）の検証ができない。

### report

* report自体はエラーを適切に集計し `BLOCK` を返している。

### crawler

* 一覧URL `https://www.jica.go.jp/activities/schemes/grant_aid/chotatsu/index.html` の fetch失敗原因切り分け（User-Agent, timeout, TLS, robots相当の挙動差）が必要。

## 次アクション判断

以下のいずれかを選ぶ。

| 判断                                 | 該当     |
| ---------------------------------- | ------ |
| parser改善Issueへ進む                   | no |
| crawler/detail fetch改善Issueへ進む     | yes |
| notice_date抽出改善Issueへ進む            | no |
| PQ判定改善Issueへ進む                     | no |
| discover結果のSheets投入候補化dry-run設計へ進む | no |

## 結論

* #26の初回小規模検証では crawler の list fetch 段階で失敗し、recordsが0件だった。まずは crawler 側の fetch安定化を先に実施し、再検証後に parser/date/PQ品質レビューへ進むべき。

## 再検証: Issue #28 fetch diagnostics

- 実行日: 2026-05-15
- 修正内容: HTTPFetchErrorに診断情報（status_code / exception_type / response_excerpt等）を追加し、discoverのlist/detail fetch失敗をerrorsへ詳細出力するよう改善。
- 一時crawl_scope:
  - schemes: [grant_aid]
  - sources: [jica_grant_notice]
  - max_pages_per_source: 1
  - request_interval_seconds: 2
  - max_detail_pages: 10
- records件数: 0
- errors件数: 1
- review_status: BLOCK
- list_fetch_failed 解消: no
- detail_fetch_failed 件数: 0
- status_code: N/A
- exception_type: ProxyError
- error_message: HTTP接続失敗（ProxyError: Tunnel connection failed: 403 Forbidden）
- response_excerpt有無: 無
- 次アクション: 接続経路/Proxy環境を考慮した取得戦略と、source到達性確認手順の追加を検討する。
