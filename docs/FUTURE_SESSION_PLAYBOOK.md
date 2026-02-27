# Future Session Playbook

Use this when continuing work in a new session.

## Before Coding

1. Read:
   - `docs/README.md`
   - `docs/KNOWN_RISKS_AND_BACKLOG.md`
2. Run:
```bash
python3 -m py_compile app.py
```
3. Start app and smoke-check:
   - `/annotator/login`
   - `/admin/login`

## If Pipeline Format Changes

1. Update column handling in `/admin/data` import logic.
2. Update `scripts/init_from_sheets.py` and `scripts/sync_eval_sheet.py` if sheet structure changed.
3. Update `docs/CSV_IMPORT_EXPORT.md`.
4. Add UI note in `templates/admin_data.html` explaining new expected behavior.

## If Feedback Schema Changes

1. Add migration block in `migrate_db()`.
2. Update form fields in `templates/annotate.html`.
3. Update export query in `export_feedback`.
4. Update docs:
   - `docs/DATA_MODEL.md`
   - `docs/ROUTES_AND_UI.md`

## Required Docs Update Policy

Any behavior change must update docs in same session:

- route changes -> `ROUTES_AND_UI.md`
- DB changes -> `DATA_MODEL.md`
- import/export changes -> `CSV_IMPORT_EXPORT.md`
- operational steps -> `OPERATIONS_RUNBOOK.md`
- testing additions -> `TESTING.md`
- known tradeoffs -> `KNOWN_RISKS_AND_BACKLOG.md`

If docs are not updated, the task is incomplete.
