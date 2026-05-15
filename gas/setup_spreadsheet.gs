/**
 * このスクリプトは初回セットアップ用です。
 * スプレッドシート上のApps Scriptに一時的に貼り付けて実行します。
 * 実行後、スプレッドシート側のApps Scriptから削除して構いません。
 * GitHub上のこのファイルは、再セットアップ・仕様確認・変更履歴確認のために残します。
 *
 * JICA ODA Watch 用 Google Sheets 初回セットアップ
 * - 既存シート削除なし
 * - 2行目以降のデータ削除なし
 * - 1行目ヘッダーのみ設定・補正
 *
 * NOTE: このヘッダー定義は config/sheet_schema.yml と同期して保守すること。
 */
function setupJicaOdaWatch() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();

  const SHEET_ORDER = [
    'JICA_ODA_WATCH',
    'JICA_ODA_MANUAL',
    'JICA_ODA_HISTORY',
    'JICA_ODA_RAW',
    'JICA_ODA_CONFIG',
  ];

  const WATCH_AUTO_FIELDS = [
    'project_id', 'country', 'project_name', 'sector', 'scheme', 'ga_date', 'pq_required',
    'notice_date', 'notice_media', 'notice_url', 'result_url', 'oda_url', 'status_auto',
    'status_detail', 'source_type', 'source_url', 'raw_text', 'evidence_text', 'parser_name',
    'parser_version', 'parse_confidence', 'fetched_at', 'last_checked', 'change_flag',
    'ai_summary', 'ai_change_summary', 'ai_next_action', 'ai_risk_note', 'ai_confidence',
  ];

  const WATCH_MANUAL_FIELDS = [
    'manual_status',
    'memo',
    'next_manual_action',
    'owner',
    'manual_checked_date',
    'manual_updated_at',
    'manual_updated_by',
  ];

  const MANUAL_SHEET_FIELDS = ['project_id'].concat(WATCH_MANUAL_FIELDS);

  const HISTORY_FIELDS = [
    'changed_at', 'project_id', 'field_name', 'old_value', 'new_value', 'source_url',
    'change_summary', 'run_id',
  ];

  const RAW_FIELDS = [
    'run_id',
    'fetched_at',
    'project_id',
    'source_type',
    'source_url',
    'parser_name',
    'parser_version',
    'http_status',
    'raw_text',
    'raw_html_excerpt',
    'evidence_text',
    'error_message',
  ];

  const CONFIG_FIELDS = ['key', 'value', 'description', 'updated_at'];

  const DEFINITIONS = {
    JICA_ODA_WATCH: {
      headers: WATCH_AUTO_FIELDS.concat(WATCH_MANUAL_FIELDS),
      kind: 'watch',
      manualCount: WATCH_MANUAL_FIELDS.length,
    },
    JICA_ODA_MANUAL: { headers: MANUAL_SHEET_FIELDS, kind: 'manual' },
    JICA_ODA_HISTORY: { headers: HISTORY_FIELDS, kind: 'history' },
    JICA_ODA_RAW: { headers: RAW_FIELDS, kind: 'raw' },
    JICA_ODA_CONFIG: { headers: CONFIG_FIELDS, kind: 'config' },
  };

  const VALIDATIONS = {
    change_flag: ['new', 'updated', 'missing', 'no_change', 'ai_low_confidence', 'error', 'manual_updated'],
    manual_status: ['', '未確認', '確認中', '対応不要', '要対応', '対応済み', '保留'],
    pq_required: ['', '要確認', 'あり', 'なし', '不明'],
  };

  const HEADER_COLORS = {
    watch_auto: '#e0eefa',
    watch_manual: '#fbf2d6',
    manual: '#fbf2d6',
    history: '#e3f5e3',
    raw: '#ededed',
    config: '#ede6fa',
  };

  SHEET_ORDER.forEach(function(sheetName) {
    const definition = DEFINITIONS[sheetName];
    const headers = definition.headers;
    const sheet = ensureSheet_(spreadsheet, sheetName);

    ensureHeaderRow_(sheet, headers);
    applyFormat_(sheet, headers, definition, HEADER_COLORS);
    applyNotes_(sheet, headers);
    applyValidation_(sheet, headers, VALIDATIONS);
  });
}

function ensureSheet_(spreadsheet, sheetName) {
  const existing = spreadsheet.getSheetByName(sheetName);
  if (existing) return existing;
  return spreadsheet.insertSheet(sheetName);
}

function ensureHeaderRow_(sheet, headers) {
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
}

function applyFormat_(sheet, headers, definition, colors) {
  const kind = definition.kind;
  const colCount = Math.max(headers.length, 1);

  sheet.setFrozenRows(1);

  const headerRange = sheet.getRange(1, 1, 1, colCount);
  headerRange.setFontWeight('bold');
  headerRange.setHorizontalAlignment('center');
  headerRange.setVerticalAlignment('top');
  headerRange.setWrap(true);

  const allRange = sheet.getRange(1, 1, sheet.getMaxRows(), colCount);
  allRange.setVerticalAlignment('top');
  allRange.setWrap(true);

  if (kind === 'watch') {
    const manualCount = definition.manualCount;
    const autoCount = colCount - manualCount;
    if (autoCount > 0 && manualCount > 0) {
      sheet.getRange(1, 1, 1, autoCount).setBackground(colors.watch_auto);
      sheet.getRange(1, autoCount + 1, 1, manualCount).setBackground(colors.watch_manual);
    }
  } else {
    sheet.getRange(1, 1, 1, colCount).setBackground(colors[kind]);
  }

  const existingFilter = sheet.getFilter();
  if (existingFilter) existingFilter.remove();
  sheet.getRange(1, 1, Math.max(sheet.getMaxRows(), 1), colCount).createFilter();

  for (let col = 1; col <= colCount; col += 1) {
    sheet.setColumnWidth(col, 180);
  }
}

function applyNotes_(sheet, headers) {
  const notes = {
    manual_status: '手入力ステータス。自動更新で上書きしない。',
    memo: '手入力メモ。自動更新で上書きしない。',
    next_manual_action: '次の手動対応。自動更新で上書きしない。',
    owner: '担当者。自動更新で上書きしない。',
    manual_checked_date: '手動確認日。自動更新で上書きしない。',
    manual_updated_at: '手動更新日時。自動更新で上書きしない。',
    manual_updated_by: '手動更新者。自動更新で上書きしない。',
  };

  Object.keys(notes).forEach(function(field) {
    const idx = headers.indexOf(field);
    if (idx >= 0) {
      sheet.getRange(1, idx + 1).setNote(notes[field]);
    }
  });
}

function applyValidation_(sheet, headers, validations) {
  const rowCount = sheet.getMaxRows();
  if (rowCount < 2) return;

  const targets = ['change_flag', 'manual_status', 'pq_required'];

  targets.forEach(function(field) {
    const idx = headers.indexOf(field);
    if (idx < 0 || !validations[field]) return;

    const rule = SpreadsheetApp.newDataValidation()
      .requireValueInList(validations[field], true)
      .setAllowInvalid(false)
      .build();

    sheet.getRange(2, idx + 1, rowCount - 1, 1).setDataValidation(rule);
  });
}
