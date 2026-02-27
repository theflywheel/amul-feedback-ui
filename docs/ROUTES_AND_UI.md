# Routes and UI Behavior

## Public / Annotator

- `GET /`
  - Redirects to annotator login (or annotate if already logged in).
- `GET|POST /annotator/login`
  - Email dropdown login.
- `GET /annotator/logout`
  - Clears annotator session.
- `GET /annotate`
  - Shows next pending assigned question.
  - Loads existing feedback values if draft/submitted row exists.
  - Search results are displayed in collapsible sections.
- `POST /annotate/save`
  - `save_action=draft`: save partial feedback.
  - `save_action=submitted`: strict validation + submit + move to next.
- `GET|POST /questions`
  - View all active questions.
  - Submit suggested question.

## Admin

- `GET|POST /admin/login`
  - Checks env-configured admin credentials (`ADMIN_EMAIL`, `ADMIN_PASSWORD`).
- `GET /admin/logout`
  - Clears admin session.
- `GET|POST /admin/users`
  - Add single user.
  - Add bulk users from email text area.
- `GET|POST /admin/assignments`
  - Random assignment:
    - fixed count per user
    - all-unassigned round-robin
  - Manual assignment:
    - searchable simple question picker
  - Filters + pagination + metrics + per-user progress.
- `GET|POST /admin/data`
  - CSV import, including assignment pre-allocation.
  - Suggestions list.
- `GET /admin/export/questions.csv`
- `GET /admin/export/feedback.csv`

## Validation Rules in Annotator Submit

- Required ratings for submit:
  - question translation
  - answer accuracy
  - answer translation
- Search feedback:
  - open-ended text only (no required rating)
- If rating is 1 or 2:
  - corresponding comment required.

## UX Notes Already Embedded in UI

The templates include "Expected behavior" notes for:
- draft vs submit semantics
- repeated import/sync behavior
- user creation expectations
- admin password location
