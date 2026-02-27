# Known Risks and Backlog

## Known Risks

1. Security model is intentionally lightweight.
   - Annotator has no password.
   - Admin uses single shared password.
   - No CSRF protection.
   - Acceptable for internal trusted environment, not internet-exposed.

2. Single-file Flask app (`app.py`) will become hard to maintain as scope grows.
   - Consider splitting into blueprints/services.

3. SQLite concurrency limits.
   - Fine for small teams; consider Postgres for higher concurrent write load.

4. Export size and list rendering scale.
   - Some pages still render large tables directly.

5. Search-results section parsing is heuristic.
   - Different pipeline formats may need parser adjustments.

## Prioritized Backlog

1. Add explicit assignment management actions:
   - unassign single `(user, question)`
   - bulk unassign by filter
2. Add question edit/delete (or hard-delete) admin tools.
3. Add pipeline run metadata:
   - `batch_id` / `imported_at` in questions.
4. Add richer conflict handling in import:
   - detect duplicate IDs with conflicting text.
5. Add full automated test suite.
6. Add optional "resume last draft first" queue strategy toggle.
7. Add stronger audit logs for admin actions.
