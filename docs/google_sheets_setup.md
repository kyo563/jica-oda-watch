# Google Sheets初回セットアップ仕様

## 推奨スプレッドシート名

`JICA ODA Watch Master`

> Google Sheetsが正本であるため、`Master` を付けることを推奨します。  
> GitHub Pagesは閲覧・入力補助UIであり、正本ではありません。  
> 必要に応じて将来 `JICA ODA Watch Master - Production` / `JICA ODA Watch Master - Test` のように分離しても構いません。  
> 現段階では `JICA ODA Watch Master` を推奨します。

## このドキュメントの目的

このドキュメントは、JICA ODA WatchのGoogle Sheets正本について、初回セットアップ時に作成されるシート構成・ヘッダー・入力規則・書式設定を記録するものです。

## 初回セットアップApps Scriptについて

初回セットアップには `gas/setup_spreadsheet.gs` を使用します。

このスクリプトは、対象スプレッドシートのApps Scriptエディタに一時的に貼り付けて実行します。

実行後、スプレッドシート側のApps Scriptから削除して構いません。

GitHub上の `gas/setup_spreadsheet.gs` は、再セットアップ・仕様確認・変更履歴確認のために残します。

## 作成されるシート

- `JICA_ODA_WATCH`
- `JICA_ODA_MANUAL`
- `JICA_ODA_HISTORY`
- `JICA_ODA_RAW`
- `JICA_ODA_CONFIG`

## 各シートの役割

| シート名 | 役割 | 更新主体 | 備考 |
|---|---|---|---|
| JICA_ODA_WATCH | 案件ごとの最新状態を保持するメインシート | crawler / 手入力 | auto fields + manual fields |
| JICA_ODA_MANUAL | 手入力情報を分離管理する補助シート | 人間 / Apps Script | 将来の双方向入力用 |
| JICA_ODA_HISTORY | 差分履歴をappend-onlyで保存 | crawler | 削除・上書きしない |
| JICA_ODA_RAW | 取得原文・証跡・parser結果を保存 | crawler | AI要約だけに依存しない証跡 |
| JICA_ODA_CONFIG | 運用設定・補助設定を保存 | 人間 / 管理者 | 将来拡張用 |

## Apps Scriptが行うこと

- 5シートを作成する
- 既存シートがある場合は再利用する
- 既存シートを削除しない
- 2行目以降の既存データを削除しない
- 1行目ヘッダーを設定・補正する
- 1行目を固定する
- ヘッダーを太字にする
- ヘッダー背景色を設定する
- フィルターを設定する
- 列幅を調整する
- 折り返し表示を有効化する
- manual fieldsに説明noteを付ける
- `change_flag`, `manual_status`, `pq_required` に入力規則を設定する

## Apps Scriptが行わないこと

- crawler実行
- JICA公式サイト取得
- GitHub Pages更新
- 日次更新
- AI要約
- 既存データ行の削除
- manual fieldsの上書き
- 既存シートの削除

## 実行手順

1. 対象スプレッドシートを開く
2. スプレッドシート名を `JICA ODA Watch Master` に変更する
3. メニューから「拡張機能」→「Apps Script」を開く
4. `gas/setup_spreadsheet.gs` の内容を `Code.gs` に貼り付ける
5. 保存する
6. 関数 `setupJicaOdaWatch` を選択する
7. 実行する
8. 初回権限確認を許可する
9. 5シートが作成されたことを確認する
10. 問題なければ、スプレッドシート側のApps Scriptから貼り付けたコードを削除してよい

## 実行後の確認項目

- `JICA_ODA_WATCH` が存在する
- `JICA_ODA_MANUAL` が存在する
- `JICA_ODA_HISTORY` が存在する
- `JICA_ODA_RAW` が存在する
- `JICA_ODA_CONFIG` が存在する
- `JICA_ODA_WATCH` の `project_id` が重複していない
- manual fieldsが右側に並んでいる
- `manual_status`, `memo`, `next_manual_action`, `owner` が存在する
- `change_flag`, `manual_status`, `pq_required` にプルダウンがある
- 1行目が固定されている
- ヘッダーに色が付いている

## 再セットアップ時の注意

このスクリプトは既存シートを削除せず、2行目以降のデータも削除しません。

ただし、1行目ヘッダーはschemaに合わせて補正されます。

既に実データが入っている状態で再実行する場合は、事前にスプレッドシートをコピーしてバックアップを取ることを推奨します。

## 関連ファイル

- `gas/setup_spreadsheet.gs`
- `config/sheet_schema.yml`
- `README.md`
