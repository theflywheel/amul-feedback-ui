# Golden Set Feedback UI - Dev Docs

This folder is the source of truth for future sessions.  
You can delete `Task.md` and use these docs instead.

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```
2. Run app:
```bash
python3 app.py
```
3. Open `http://127.0.0.1:5001`

## One-Command Sheet Sync

To initialize questions from the golden sheet, then sync users+assignments from eval sheet:
```bash
python3 scripts/init_from_sheets.py --sync-active
```

## Docker (Compose)

```bash
docker compose up --build
```

App URL:
- `http://localhost:57631`

## Defaults

- Database: `app.db` (auto-created)
- Source CSV bootstrap: `data/Sheets/500_goldenset_final_sheet.csv`
- Admin email comes from `ADMIN_EMAIL`.
- Admin password comes from `ADMIN_PASSWORD`.
- No default annotator users are seeded.

## Doc Map

- [Architecture](./ARCHITECTURE.md)
- [Data Model](./DATA_MODEL.md)
- [Routes and UI Behavior](./ROUTES_AND_UI.md)
- [CSV Import/Export Guide](./CSV_IMPORT_EXPORT.md)
- [Operations Runbook](./OPERATIONS_RUNBOOK.md)
- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Testing Guide](./TESTING.md)
- [Known Risks and Backlog](./KNOWN_RISKS_AND_BACKLOG.md)
- [Future Session Playbook](./FUTURE_SESSION_PLAYBOOK.md)
