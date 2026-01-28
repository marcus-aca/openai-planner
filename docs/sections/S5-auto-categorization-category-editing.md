# Section
Auto-Categorization & Category Editing

## Summary
Add automatic transaction categorization and interactive category editing so users can quickly organize imported transactions and correct misclassifications. Deliver an MVP that:

- Automatically assigns categories during import using CSV-provided categories (when available) and a simple keyword-based heuristic.
- Allows inline editing of a transaction's category and single-step persistence.
- Provides a category management UI for CRUD operations with safeguards.
- Optionally (MVP+): a lightweight rule engine for user-defined keyword rules and a bulk-recategorize action.

This feature should be safe (prevent accidental data loss), discoverable, and test-covered.

## Design

Data model
- category
  - id (PK)
  - name (unique, not null)
  - description (optional)
  - color (optional)
  - created_by
  - created_at, updated_at
  - is_default (boolean) — for "Uncategorized" or system default
- transaction (existing)
  - category_id (FK nullable -> category.id)
  - category_source (enum: manual, csv, heuristic, rule) — for provenance
  - category_rule_id (FK nullable -> rule.id) — reference when rule applied
  - category_updated_at, category_updated_by
- rule (optional)
  - id (PK)
  - pattern (string)
  - match_type (enum: contains, equals, starts_with, regex)
  - category_id (FK)
  - priority (integer; lower = higher priority)
  - active (boolean)
  - created_by, created_at, updated_at

Auto-categorization flow (MVP baseline)
1. Import handler receives CSV.
2. If CSV contains a "category" column and the value is non-empty:
   - Try to map the value to an existing category by case-insensitive name match.
   - If no match and auto-create-categories setting is ON: create category; else mark transaction as Uncategorized (or present mapping UI).
   - Set category_source = csv.
3. Else (no CSV category):
   - Apply keyword/contains matching against transaction description (case-insensitive).
   - If match found, set category_source = heuristic and record rule/category if applicable.
   - If no match, set category_id = id of "Uncategorized" category and category_source = manual/default.

Rule engine (optional)
- Rules evaluated in priority order (lower numeric priority first).
- Matching supports contains (default), equals, starts_with, and regex.
- On import and on explicit "Re-categorize" action, rules are applied; a matching rule sets transaction.category_id and category_rule_id.
- Rules UI should provide a preview (run sample on a subset or show number of matches) before saving.

UI Components / UX
- Transactions table (MVP): inline category dropdown per row:
  - Typeahead to search categories; selecting updates transaction immediately (PATCH) with visual success state.
  - Show small metadata: category_source (tooltip) and last updated timestamp.
  - Undo/notification toast after change (5–10s).
- Bulk edit (MVP+): multi-select transactions -> action bar -> choose category -> apply -> background job for large sets -> show progress and results.
- Categories management page:
  - List categories, counts (number of transactions), actions: rename, delete, reassign.
  - Create modal with name + optional color/description.
  - Delete safeguards: if category in use, require reassigning to another category or automatic reassign to "Uncategorized" after explicit confirmation.
- Rules page (optional):
  - List rules, create/edit/delete, toggle active, reorder priority.
  - Create rule modal: pattern + match type + category + preview button that runs a dry-run on sample transactions (or returns match count).
- Import UI:
  - Mapping step shows any CSV category values that don't match existing categories and lets user map them to existing or create new.
  - Option to "Apply automatic rules" toggle.
  - Summary of categories created/mapped after import.

API design (examples)
- Categories:
  - GET /api/categories
  - POST /api/categories
  - PUT /api/categories/:id
  - DELETE /api/categories/:id (returns 409 with usage info unless reassign param given)
- Transactions:
  - GET /api/transactions?filters...
  - PATCH /api/transactions/:id { category_id }
  - POST /api/transactions/bulk-categorize { transaction_ids[], category_id }
  - POST /api/transactions/re-categorize { rule_ids? or all }
- Rules (optional):
  - GET /api/rules
  - POST /api/rules
  - PUT /api/rules/:id
  - POST /api/rules/preview { rule definition }

Performance and scale considerations
- For large imports, run categorization in a background job with progress tracking.
- Index category_id on transactions.
- For keyword/rule matching across many rows, consider batching or leveraging full-text indexes if complex matching is added later.

Security & permissions
- Only users with category-management permission can create/rename/delete categories and modify rules.
- Category edits on transactions require transaction-edit permission.
- Audit who changed categories and when.

## Implementation Steps

Phase 1 — Preparation (1 week)
1. Define DB migrations:
   - Add category table.
   - Add category_id, category_source, category_updated_at, category_updated_by, category_rule_id to transactions.
   - Add rule table if included.
   - Seed "Uncategorized" category (is_default = true).
2. Define API contracts and front-end component skeletons.
3. Add basic unit-test scaffolding for rule engine and categorization logic.

Phase 2 — MVP auto-categorization baseline + inline editing (2–3 weeks)
1. Backend:
   - Implement category CRUD endpoints with input validation and deletion safeguards.
   - Implement transaction PATCH endpoint to update category_id and category_source = manual. Record audit fields.
   - Extend CSV import handler:
     - Detect category column.
     - If present: map existing categories (case-insensitive). If auto-create flag enabled, create missing categories; otherwise mark unmapped as Uncategorized and return mapping info.
     - If no category column: run a simple keyword dictionary (in-memory config or DB table) matching description -> category.
     - Persist category_source accordingly.
   - Add migration tests.
2. Frontend:
   - Transactions table: add inline category dropdown with typeahead (calls GET /api/categories).
   - Implement PATCH on-selection, optimistic UI update, success & error handling, and undo via toast.
   - Categories management page: list/create/rename flows.
3. Tests:
   - Unit tests for CSV mapping and keyword matching logic.
   - Integration tests for inline edit API call and DB update.

Phase 3 — Import mapping UI + safeguards + UX polish (1–2 weeks)
1. Implement import UI mapping step to let user map unknown CSV categories to existing or create new categories before finalizing import.
2. Add confirmation flows for deleting categories in use:
   - Modal that shows count of transactions for the category.
   - Option to reassign to another category or to "Uncategorized".
3. Add versioning/last-edit metadata display in transactions table.

Phase 4 — Optional rules and bulk operations (2–3 weeks)
1. Backend:
   - Implement rule CRUD and evaluation engine.
   - Add POST /api/transactions/re-categorize to re-apply rules to existing transactions; implement as background job for large sets.
2. Frontend:
   - Rules management page with create/edit/preview.
   - Bulk-select UI for transactions and bulk-categorize action; show progress and results.
3. Tests:
   - Unit tests for rule matching (contains, equals, starts_with, regex).
   - Integration tests for re-categorize job and bulk-categorize endpoint.
   - E2E tests for rule creation -> preview -> import -> match.

Phase 5 — QA, performance tuning, and rollout (1 week)
1. Load-test import path with large CSV to ensure background processing and reasonable memory/CPU usage.
2. UX testing to ensure mappings and edits are intuitive.
3. Release feature as opt-in for a subset of users before wider rollout.

Detailed implementation notes (actionable)
- CSV mapping algorithm:
  - Normalize category text: trim, toLower(), collapse whitespace.
  - Try direct name match -> if match, use id.
  - Otherwise, if auto_create_categories flag true, create new category (record created_by = importer user).
  - Else mark as unmapped and present in mapping UI.
- Keyword matching:
  - Maintain a small in-memory default mapping for MVP-lite (e.g., "UBER" -> Transport) plus a DB-backend keyword table for future extensibility.
  - Matching should be case-insensitive substring on description; ignore punctuation.
- Concurrency:
  - When creating categories on import, wrap creation in transaction and use unique constraint on category.name to avoid duplicates. On duplicate error, fetch existing and continue.
- Bulk apply:
  - For up to X (e.g., 500) transactions do synchronous updates, beyond that queue background job and return job id.
- Logging:
  - Log mapping decisions for audit and to help improve heuristics (e.g., record when heuristics matched).

Tests to include
- Unit: categorizer module, rule matcher, CSV mapping.
- API: categories CRUD, transaction update, bulk-categorize.
- Integration: import end-to-end (upload -> mapping -> persisted categories).
- E2E: inline change persists, bulk change works, categories delete modal handles reassign.

## Risks
- Mis-categorization causing user frustration:
  - Mitigation: make edits easy and visible; provide undo and re-categorize options; clear provenance of category assignment.
- Duplicate categories created during concurrent imports:
  - Mitigation: enforce unique constraint, handle conflicts by re-fetching existing row and retry.
- Performance degradation on large imports or re-categorize runs:
  - Mitigation: run heavy jobs as background tasks, paginate/batch rule evaluation, and present progress UI.
- User confusion over where categories come from (csv vs heuristic vs manual):
  - Mitigation: surface category_source metadata and provide mapping UI during import.
- Data loss or accidental deletes:
  - Mitigation: require explicit confirmation for deleting categories in use and offer reassign option; audit logs.
- Regex rules causing expensive evaluations or DoS:
  - Mitigation: limit rule complexity (max length) and reject pathological regexes server-side; run rule application in controlled batches.

## Dependencies
- Authentication & authorization system to enforce permissions for category/rule management.
- CSV import/parsing service or library.
- Background job runner (for large imports and re-categorize jobs).
- Database (supports migrations, unique constraints, transactions).
- Frontend framework and existing transactions table components (assumed React/JS stack).
- Logging/analytics to capture mapping results and errors.
- Optional: text-search or indexing features if rules become complex.

## Acceptance Criteria
Functional
- CSV import:
  - If CSV contains a category column, imported transactions receive category_id if category name maps to an existing category (case-insensitive). If auto-create flag enabled, missing names are created as categories. If not enabled, unmapped values are shown in a mapping UI and transactions default to "Uncategorized" until mapping is completed. Evidence: API logs and DB rows show category_source = csv for mapped items.
- Heuristic matching:
  - When CSV category absent, a simple keyword-contains heuristic runs and assigns categories (e.g., "UBER" in description -> Transport). Evidence: unit tests and sample imports validate mapping.
- Inline edit:
  - Each transaction row has an inline category dropdown. Selecting a category updates the transaction in DB, shows success toast, and records category_source = manual and audit info (who/when).
- Category management:
  - Users with permission can create, rename, and delete categories.
  - Deleting a category in use requires reassigning transactions or explicit confirmation to reassign to "Uncategorized". The system prevents silent deletion that would orphan transactions. Evidence: delete operation returns appropriate confirmation and DB state after operation.
- Rule engine (if included):
  - Users can create simple rules (contains/equals/starts_with/regex), preview matches, enable/disable rules, and re-apply rules to existing transactions. Evidence: rule evaluation unit tests, preview results match persisted changes after re-categorize job runs.
- Bulk operations (if included):
  - Selecting multiple transactions and applying a category updates all selected, returns results, and handles large sets via background job with progress tracking.
- Tests:
  - Unit tests cover categorization logic and rule matching.
  - Integration tests cover import->mapping->persistence.
  - E2E tests cover inline and bulk edits.
Non-functional
- No regressions in transaction import performance under typical loads. For very large imports, classification runs as background tasks and UI shows progress.
- Category CRUD and transaction update APIs require appropriate permissions.
- UI provides clear provenance (csv vs heuristic vs manual) for category assignments.

Deliverables (explicit)
- Transactions table with inline category editing (MVP).
- Categories management page with create/rename/delete + safeguards.
- CSV import mapping flow that respects CSV category column and falls back to heuristic.
- Rule engine and rules UI (optional deliverable depending on scope).
- Unit and integration tests for the categorization components and import flows.
