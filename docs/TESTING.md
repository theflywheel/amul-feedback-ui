# Testing Guide

## Current Validation Performed

- Syntax:
```bash
python3 -m py_compile app.py
```
- Smoke via Flask test client:
  - annotator login page
  - admin login page
  - draft save path
  - submit validation path
  - submit success redirect
  - admin assignment page filters
  - CSV import with assignee pre-allocation

## Recommended Manual QA Before Each Release

1. Annotator flow
   - login with known email
   - save draft
   - verify question still pending
   - submit with all ratings
   - verify next question loads
2. Admin flow
   - bulk add users
   - random assign
   - manual assign
   - verify filters and pagination
3. CSV flow
   - upload upsert file
   - upload sync file
   - verify active/inactive behavior
   - verify assignee import behavior with and without replace checkbox
4. Export flow
   - questions export opens
   - feedback export includes `submission_status`

## Suggested Future Automated Tests

- Unit tests around `upsert_question` behavior with:
  - id update
  - key-based update
  - insertion
- Tests for sync deactivation.
- Tests for assignment replacement behavior.
- Route tests for malformed numeric input (no 500s).
