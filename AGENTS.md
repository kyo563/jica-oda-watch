# AGENTS.md

## Project Name

JICA ODA Tender Watcher

## Purpose

This repository builds and maintains a monitoring system for JICA ODA projects, especially grant aid procurement and tender-related information.

The system must:

- Crawl public JICA and related official sources.
- Track target ODA projects.
- Detect changes in procurement status, tender notices, P/Q status, result postings, and related metadata.
- Preserve human-entered notes and manual statuses.
- Generate concise AI summaries without treating AI output as the source of truth.
- Update Google Sheets as the master data store.
- Generate a mobile-friendly GitHub Pages interface.
- Allow mobile note entry through a safe backend endpoint such as Google Apps Script Web App.

## Non-Negotiable Design Principles

### 1. Google Sheets is the source of truth

Google Sheets is the master data store.

GitHub Pages is a viewing and input interface only.
GitHub Pages must not be treated as the database.

### 2. Never destroy manual data

Do not use full-sheet clear operations on sheets that contain manual notes.

Manual fields must never be overwritten by crawler output.

The following fields are human-managed and must be preserved:

- manual_status
- memo
- next_manual_action
- owner
- manual_checked_date
- manual_updated_at
- manual_updated_by

### 3. Use stable project_id

Every target project must have a stable project_id.

Do not rely on row numbers.
Do not rely only on exact project names.
Project names may vary across sources.

Use project_id as the primary key for merging:

- crawler output
- previous snapshot
- manual notes
- history records
- GitHub Pages data

### 4. Separate automatic and manual data

Use separate logical sheets:

- MASTER or WATCH
- MANUAL
- HISTORY
- RAW
- CONFIG or WATCHLIST

Recommended sheets:

- JICA_ODA_WATCH
- JICA_ODA_MANUAL
- JICA_ODA_HISTORY
- JICA_ODA_RAW
- JICA_ODA_CONFIG

### 5. AI is for summarization only

AI may generate:

- plain Japanese summary
- change summary
- next action suggestion
- risk note

AI must not be used as the final source of truth for:

- P/Q status
- tender status
- contract result
- dates
- monetary amounts
- official URLs

Facts must come from extracted source data.

If source data is ambiguous, mark the field as 要確認.

### 6. Preserve raw source evidence

For every extracted record, keep:

- source_url
- source_type
- fetched_at
- raw_text or raw_html excerpt
- parser_name
- parser_version if available

Do not store only AI summaries.

### 7. No secrets in frontend

Never expose the following in GitHub Pages files:

- Google service account JSON
- Google API credentials
- OpenAI API key
- Gemini API key
- GitHub PAT
- Apps Script secret tokens
- Any private keys

Use GitHub Actions secrets or server-side Apps Script properties.

### 8. JICA source limitations

JICA public notice pages may not be complete.
Expired notices may disappear.
Do not interpret disappearance as contract award.

If a previously detected notice disappears, mark it as:

- missing
- 掲載消滅／要確認
- 受付終了可能性あり

Do not delete the project row.

### 9. Change detection must be deterministic

change_flag must be determined by machine comparison, not by AI wording.

Valid change_flag values:

- new
- updated
- missing
- no_change
- ai_low_confidence
- error
- manual_updated

### 10. Keep history

All meaningful changes must be appended to HISTORY.

Do not rely only on the latest WATCH sheet.

History records should include:

- changed_at
- project_id
- field_name
- old_value
- new_value
- source_url
- change_summary
- run_id

### 11. Mobile-first UI

GitHub Pages must be designed for mobile access first.

The UI should support:

- search
- filtering
- status badges
- colored update indicators
- project detail view
- source links
- AI summary
- manual memo display
- note entry form

### 12. Safe update strategy

Do not update data by row number unless the row is resolved by project_id.
Do not assume current order equals previous order.
Do not delete rows merely because a source did not return a project in one run.

### 13. Dry-run mode

Crawler and sheet update scripts should support dry-run mode.

Dry-run must:

- fetch data
- parse data
- compute diffs
- print or save planned changes
- avoid writing to Google Sheets
- avoid committing generated files

### 14. Logging

All workflows should log:

- run_id
- start time
- end time
- fetched source count
- parsed record count
- changed record count
- errors
- warnings

### 15. Japanese user-facing output

README, UI labels, sheet headers visible to humans, and AI summaries should be Japanese unless there is a strong reason to keep a field technical.

Internal variable names may be English.

## Spreadsheet (planned source of truth)

- https://docs.google.com/spreadsheets/d/1WQiDT4LdqkJ6z361uxVaZOipEBhfofv0PTpnGEO26yk/edit?gid=0#gid=0
