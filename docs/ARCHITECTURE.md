# Architecture

## Stack

- Backend: Flask (single `app.py`)
- Database: SQLite (`app.db`)
- Frontend: Server-rendered Jinja templates + vanilla CSS/JS
- Data interchange: CSV import/export

## System Shape

- One-process web app.
- No external auth provider.
- Session auth for annotator/admin:
  - Annotator session key: `user_id`
  - Admin session key: `admin_user_id`

## Main Modules in `app.py`

- DB setup/migration:
  - `init_db()`
  - `migrate_db()`
- Utility helpers:
  - `parse_search_sections()`
  - `get_pending_question_for_user()`
  - `get_user_progress()`
  - `get_feedback()`
- Annotator routes:
  - login/logout, annotate, save, all questions + suggestions
- Admin routes:
  - login/logout
  - users
  - assignments
  - data import/export

## Design Intent

- Fast iteration for a frequently changing data pipeline.
- Admin can repeatedly import regenerated question sets.
- Annotators can save draft or submit finalized feedback.
- Assignment can come from:
  - CSV pre-allocation (`assigned_emails`)
  - random assignment UI
  - manual assignment UI
