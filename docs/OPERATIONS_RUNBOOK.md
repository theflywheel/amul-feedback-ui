# Operations Runbook

## First Launch

1. `pip install -r requirements.txt`
2. `python3 app.py`
3. Login as admin:
   - email: value from `ADMIN_EMAIL`
   - password: value from `ADMIN_PASSWORD`

## Common Admin Tasks

## Add users from sheets export

1. Go to `Admin > Users`.
2. Use `Bulk Add Users`.
3. Paste emails (comma/semicolon/newline separated).

## Import new pipeline output

1. Go to `Admin > Data`.
2. Upload CSV.
3. Choose import mode:
   - normal refresh: `upsert`
   - keep only current batch active: `sync`
4. If CSV includes assignees and should override old assignees:
   - check `Replace assignments from CSV assignee columns`.

## Full init from spreadsheets

Use this when you copy/paste new spreadsheets and want DB refreshed.

```bash
python3 scripts/init_from_sheets.py --sync-active
```

What it does:
- Upserts questions from `data/Sheets/500_goldenset_final_sheet.csv`.
- Optionally deactivates questions missing from golden sheet (`--sync-active`).
- Rebuilds users + assignments from `data/Sheets/Amul Eval Sheet.csv` (`Members` column).
- Admin login remains independent from annotator users and is controlled by env vars.

If you only want user/assignment sync without question upsert:
```bash
python3 scripts/sync_eval_sheet.py --apply
```

## Randomly assign remaining

1. Go to `Admin > Assignments`.
2. Select users.
3. Choose mode:
   - fixed count per user
   - all unassigned round-robin
4. Click `Run Random Assignment`.

## Manual correction for specific question

1. Go to `Admin > Assignments`.
2. Use search input in manual assignment section.
3. Select user and question and click `Assign`.

## Interpreting progress

- Completed = submitted feedback only.
- Drafts = saved but not finalized.
- Pending = assigned - completed.

## Backup / Restore

- Backup DB:
```bash
cp app.db app.db.backup.$(date +%Y%m%d_%H%M%S)
```
- Restore DB:
```bash
cp app.db.backup.YYYYMMDD_HHMMSS app.db
```

## Environment Variables

- `SECRET_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

## Docker Compose

```bash
docker compose up --build
```

Service details:
- Host port: `57631`
- Container port: `5001`
- Optional init on boot controlled by `INIT_FROM_SHEETS` (default `1` in compose file)

See full remote rollout steps:
- `docs/DEPLOYMENT_GUIDE.md`
