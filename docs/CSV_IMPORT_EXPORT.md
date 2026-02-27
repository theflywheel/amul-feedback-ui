# CSV Import / Export Guide

## Required Question Columns

- `Category`
- `Q (Gu)`
- `Q (En)`
- `Search Results`
- `A(En)`
- `A (Gu)`

`Q (Gu)` is required for import row validity.

## Optional Columns

- Question identity hints:
  - `id`, `ID`, `question_id`, `Question ID`
- Assignee emails:
  - `assigned_emails`
  - `Assigned Emails`
  - `Members`
  - `members`
  - `Assignees`
  - `assignees`
  - `Assigned To`
  - `assigned_to`

Assignee lists can be separated by comma, semicolon, or pipe.

## Import Modes (`/admin/data`)

- `upsert` (recommended)
  - Update existing rows by `id` if provided and found.
  - Else match by `(Category, Q (Gu), Q (En))`.
  - Insert new rows when no match.
  - Marks matched/inserted rows active.

- `insert`
  - Insert only, ignore duplicates via unique index.

- `sync`
  - Same as upsert + deactivates (`active=0`) DB questions not present in incoming file.
  - Does not hard-delete rows.

## Assignment Behavior During Import

- If assignee column exists in a row:
  - Missing users are auto-created from email.
  - Assignments are inserted for listed users.
- Optional checkbox: `Replace assignments from CSV assignee columns`
  - If enabled, assignments for that question are cleared before applying CSV assignees.
  - Use this to avoid assignment drift in frequent pipeline runs.

## Exports

- Questions export:
  - current DB state, including inactive rows.
- Feedback export:
  - includes `submission_status` (`draft` or `submitted`) and all feedback fields.
