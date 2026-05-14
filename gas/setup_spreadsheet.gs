function setupJicaOdaWatch() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const headerColor = '#d9ead3';
  const wrapStrategy = SpreadsheetApp.WrapStrategy.WRAP;

  const sheetDefs = [
    {
      name: 'JICA_ODA_WATCH',
      headers: [
        'project_id','country','project_name','sector','scheme','ga_date','pq_required','notice_date','notice_media','notice_url','result_url','oda_url','status_auto','status_detail','change_flag','ai_summary_ja','ai_change_summary','ai_next_action','ai_risk_note','source_type','source_url','raw_text','evidence_text','parser_name','parser_version','parse_confidence','fetched_at','last_checked','manual_status','memo','next_manual_action','owner','manual_checked_date','manual_updated_at','manual_updated_by'
      ],
      manualFields: ['manual_status','memo','next_manual_action','owner','manual_checked_date','manual_updated_at','manual_updated_by']
    },
    {
      name: 'JICA_ODA_MANUAL',
      headers: ['project_id','manual_status','memo','next_manual_action','owner','manual_checked_date','manual_updated_at','manual_updated_by']
    },
    {
      name: 'JICA_ODA_HISTORY',
      headers: ['changed_at','project_id','field_name','old_value','new_value','source_url','change_summary','run_id']
    },
    {
      name: 'JICA_ODA_RAW',
      headers: ['project_id','source_url','source_type','fetched_at','raw_text','raw_html_excerpt','parser_name','parser_version','parse_confidence','run_id']
    },
    {
      name: 'JICA_ODA_CONFIG',
      headers: ['key','value','description','updated_at','updated_by']
    }
  ];

  sheetDefs.forEach((def) => {
    const sheet = ensureSheet(ss, def.name);
    upsertHeader(sheet, def.headers);
    applyCommonFormat(sheet, def.headers.length, headerColor, wrapStrategy);
    applyRules(sheet, def.headers);
    if (def.manualFields) {
      applyManualNotes(sheet, def.headers, def.manualFields);
    }
  });
}

function ensureSheet(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function upsertHeader(sheet, headers) {
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
}

function applyCommonFormat(sheet, width, headerColor, wrapStrategy) {
  const header = sheet.getRange(1, 1, 1, width);
  header.setFontWeight('bold').setBackground(headerColor);
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, width);

  const maxRows = sheet.getMaxRows();
  const dataRows = Math.max(maxRows - 1, 1);
  sheet.getRange(2, 1, dataRows, width).setWrapStrategy(wrapStrategy);

  if (sheet.getFilter()) {
    sheet.getFilter().remove();
  }
  const maxCols = sheet.getMaxColumns();
  sheet.getRange(1, 1, Math.max(maxRows, 2), Math.max(width, maxCols)).createFilter();
}

function applyRules(sheet, headers) {
  setListRule(sheet, headers, 'change_flag', ['new', 'updated', 'missing', 'no_change', 'ai_low_confidence', 'error', 'manual_updated']);
  setListRule(sheet, headers, 'manual_status', ['', '未確認', '確認中', '対応不要', '要対応', '対応済み', '保留']);
  setListRule(sheet, headers, 'pq_required', ['', '要確認', 'あり', 'なし', '不明']);
}

function setListRule(sheet, headers, fieldName, values) {
  const col = headers.indexOf(fieldName) + 1;
  if (col <= 0) return;
  const rule = SpreadsheetApp.newDataValidation().requireValueInList(values, true).setAllowInvalid(true).build();
  const maxRows = sheet.getMaxRows();
  const dataRows = Math.max(maxRows - 1, 1);
  sheet.getRange(2, col, dataRows, 1).setDataValidation(rule);
}

function applyManualNotes(sheet, headers, manualFields) {
  const note = 'manual fields: 自動処理で上書きしない（人手管理列）';
  manualFields.forEach((field) => {
    const col = headers.indexOf(field) + 1;
    if (col > 0) {
      sheet.getRange(1, col).setNote(note);
    }
  });
}
