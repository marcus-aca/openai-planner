# Section
Product Requirements & UX Flows

## Summary
Build an MVP personal finance desktop/web app (single-user, local-only storage) that lets a user import bank transaction CSVs, view and edit transactions, manage categories and monthly budgets, and view a monthly dashboard. Scope is limited to core flows needed for useful budgeting and reconciliation within a 4-week delivery window.

MVP goals:
- Reliable CSV import with column mapping and preview.
- Transaction list with filtering, search, and per-transaction category override.
- Basic auto-categorization (rule/keyword-based) with manual override.
- Category management and monthly budgets per category.
- Dashboard showing month-level income/expense/net, budget progress, top categories, and simple charts.
- Single-user local storage (SQLite or embedded DB file).

Baseline performance target: dashboard monthly summary loads in under 2s on a baseline dataset (see Acceptance Criteria).

## Design
Minimum dataset (schema) and UX design decisions to minimize scope while keeping the product useful.

Data model (minimal):
- transactions
  - id (string/UUID or provided transaction id)
  - date (ISO date, stored in local timezone)
  - amount (decimal, positive for income, negative for expense or use separate type field)
  - description (string)
  - payee (optional string)
  - imported_currency (optional, string)
  - category_id (nullable FK)
  - source_file (optional)
  - created_at, updated_at
  - meta JSON (optional for original CSV row)
- categories
  - id
  - name
  - color (optional)
  - default (boolean) — optional for uncategorized fallback
- category_rules (MVP-lite; optional)
  - id
  - category_id
  - pattern_type (keyword / regex)
  - pattern (string)
  - priority (int)
- budgets
  - id
  - category_id
  - month (YYYY-MM)  // calendar month in local timezone
  - amount (decimal)
  - created_at, updated_at

Design principles:
- Keep UI simple: 4 main screens (Import, Transactions, Categories/Budgets, Dashboard).
- Calendar month defined as the user's local calendar month (00:00 local time on first day to 23:59:59 local time on last day).
- CSV import flow: auto-detect delimiter + header row, show preview (first 100 rows), allow mapping to required fields (date, amount, description), suggest date format parsing, allow saving mapping presets.
- Auto-categorization: rule/keyword-based only for MVP. Apply highest-priority matching rule; if none match, leave uncategorized. Allow bulk re-categorize via rule creation.
- Transactions list: pagination or infinite scroll, filters (month selector, category, search), inline edit for category and description.
- Budgets: monthly budget per category; show used and remaining; allow setting budgets for future months.
- Dashboard: month selector, total income, total expense, net, budget progress bars per category (top N categories), top categories list, simple charts (donut or bar for category distribution, small sparkline for trend). Charts rendered client-side.
- Persistence: local-only SQLite (file) or embedded browser DB (e.g., sql.js) depending on target packaging. Include explicit DB file backup/export option.

CSV spec (MVP):
- Required columns to import without mapping: date, amount, description. If CSV includes a category column it will be respected but still subject to user override.
- Supported date formats: ISO (YYYY-MM-DD), DD/MM/YYYY, MM/DD/YYYY, YYYY/MM/DD, along with detection heuristics and explicit mapping.
- Amount column must be numeric, optional thousands separators, negative or parentheses for expenses allowed.
- Encoding: UTF-8 expected. Provide a warning/convert flow for other encodings.

UX wireframes (deliverables): low-fidelity for Import, Dashboard, Transactions, Budgets/Categories.

## Implementation Steps
Plan split into 4 calendar weeks (deliverable at end of week 4). Each step includes owner roles: PM/design (PRD, wireframes), FE (UI), BE (DB + parsing), QA (tests).

Week 0 (Planning, Day 0–2)
- Finalize PRD (1–2 pages) and low-fidelity wireframes for four screens.
- Confirm tech stack (desktop vs web PWA) and list of libraries (CSV parser, date library, charting, SQLite driver).
- Create repo, CI skeleton, coding standards, and baseline test dataset (see Acceptance Criteria).

Week 1 (Core storage + CSV import)
- Implement local DB schema and migrations (SQLite file). Add indexes: transactions(date), transactions(category_id), budgets(category_id, month).
- Implement CSV import backend:
  - Detect delimiter and header presence.
  - Parse first 100 rows for preview; attempt auto-mapping to date, amount, description.
  - Date parsing heuristics with fallback to user selection.
  - Validate amounts and show error rows.
  - Offer “import” confirmation and write to DB within transaction (atomic import).
  - Store original CSV row in meta for traceability.
- UI: Import screen with file upload, preview table, mapping controls, and progress feedback.
- Tests: unit tests for parsing and mapping; manual test with sample CSVs (add to repo).

Week 2 (Transactions list, editing, and basic auto-categorization)
- Implement transactions list UI:
  - Month selector, search, filters (category), pagination / virtualized list for performance.
  - Inline edit of category and description; save to DB.
- Implement category entity + simple management UI (add/edit/delete).
- Implement auto-categorization engine:
  - Keyword matching in description (case-insensitive, word boundaries).
  - Priority ordering and ability to apply to imported transactions in bulk.
- Implement “undo” or simple edit history per transaction (or at minimum, keep original meta for revert).
- Tests: interaction flows, bulk categorization, mapping persistence.

Week 3 (Budgets + Dashboard + Performance tuning)
- Implement budgets UI (per-month per-category); allow quick set for month.
- Implement aggregation queries for dashboard:
  - Precompute monthly aggregates on import or use indexed queries.
  - Cache last-selected month aggregates in memory for responsiveness.
- Build dashboard UI with charts (top categories, budget progress bars).
- Performance tuning:
  - Ensure indices exist, aggregate queries optimized.
  - Add lazy loading and memoization for large transaction sets.
  - Measure dashboard render time against baseline dataset and optimize until <2s.
- Tests: performance test script (measured with timing API), functional tests for budget calculations.

Week 4 (Polish, QA, docs, deliverables)
- Polish UI, error handling, messaging, and accessibility basics.
- Add sample CSVs and CSV column specification docs to repo.
- Prepare deliverables: PRD, wireframes, sample CSV, CSV spec.
- QA pass: full manual QA on defined scenarios, fix high priority bugs.
- Final acceptance testing & sign-off.

Implementation details, tooling recommendations
- CSV parser: PapaParse (web), or a robust backend CSV library if server-side/desktop (e.g., Python csv, fast-csv for Node).
- Date parsing: date-fns or Luxon.
- Charts: Chart.js or lightweight charting lib to keep bundle small.
- DB: SQLite with a small ORM or query layer (knex, better-sqlite3, or sql.js for pure web).
- Packaging: Electron for desktop or PWA build if web-only. Choose based on target distribution.
- Testing: unit tests for parsers and aggregation logic, integration tests for import+DB. Add a small performance test harness.

## Risks
1. CSV variability and malformed data
   - Mitigation: robust parsing, delimiter/date heuristics, preview + explicit mapping, row-level validation and skip/reporting, sample CSVs and instructions.
2. Ambiguous date formats (DD/MM vs MM/DD)
   - Mitigation: auto-detect with heuristics but require explicit confirmation when ambiguous; allow user to set format in mapping.
3. Performance on large imports or datasets
   - Mitigation: stream CSV parsing, bulk DB inserts inside transactions, create required indexes, cache monthly aggregates, virtualize lists. Set baseline dataset and tune.
4. Incorrect auto-categorization leading to user distrust
   - Mitigation: keep auto-categorization rule-based for predictable results, expose rule editor and priority, allow easy per-transaction override and bulk reapply.
5. Data loss or corruption (local storage)
   - Mitigation: write imports atomically, store original CSV content/meta, add export/backup of DB or export-to-CSV, and inform users about local storage nature.
6. Scope creep beyond 4 weeks
   - Mitigation: enforce MVP scope (no ML categorization, no multi-user sync). Any additional features moved to backlog.

## Dependencies
- Platform decisions:
  - Packaging: Electron (desktop) or browser PWA (web) — decide before implementation.
- Libraries/tools:
  - CSV parser (PapaParse or equivalent)
  - Date parser (date-fns or Luxon)
  - SQLite driver (better-sqlite3 / sql.js / native SQLite bindings depending on platform)
  - Charting (Chart.js or similar)
  - UI framework (React / Vue / Svelte) — pick one and standardize components.
- Test data:
  - Baseline dataset: sample CSV(s) with 5,000 transactions spanning 12 months and ~50 categories for performance tests.
- Dev environment:
  - CI runner with at least 4 cores and 8GB RAM for performance automation (optional).
- Stakeholders:
  - PM/Designer for PRD and wireframes sign-off.
  - QA for acceptance testing.
- Legal / privacy:
  - Ensure local-only storage is documented and no network calls send transaction data off-device in MVP.

## Acceptance Criteria
Functional acceptance criteria (must be verifiable):
- Import
  - User can upload a CSV file, preview first 100 rows, map CSV columns to required fields (date, amount, description), and import transactions.
  - The import process validates rows and reports/skips invalid rows; import is atomic per file (partial rollbacks on failure).
  - Sample CSV provided with documented columns reproduces expected results.
- Transactions
  - Imported transactions appear in the Transactions list and can be filtered by month and searched by description.
  - User can edit category and description of any transaction; edits persist locally.
  - Transactions can be auto-categorized using rule-based keyword rules; users can override per-transaction.
- Categories & Budgets
  - User can create/edit/delete categories.
  - User can set a monthly budget amount for any category for a given month.
  - Dashboard shows budget progress per category and flags categories over budget.
- Dashboard & Performance
  - Dashboard shows totals for income, expense, and net for the selected month.
  - Dashboard shows top categories and budget progress bars, and renders charts for category distribution and trends.
  - Performance: On the baseline dataset (5,000 transactions spanning 12 months, ~50 categories, measured on a standard dev machine—4-core CPU, 8GB RAM), the dashboard monthly summary (aggregation + UI render) completes in under 2 seconds from the moment the month is selected.
    - Measurement method: use a timing API in the app to record aggregation start and render-complete events; run three trials and median must be <2s.
- Reliability & Data safety
  - Imports are stored persistently in local DB; user can export transactions to CSV for backup.
  - There is no network transfer of transaction data in MVP (local-only).
- Deliverables
  - PRD (1–2 pages) defining scope and known limitations.
  - Low-fidelity wireframes for Import, Dashboard, Transactions, Budgets/Categories.
  - CSV column specification and at least one sample CSV for testing in the repo.
  - Automated unit tests for core parsing and aggregation logic; manual QA checklist completed.

## Objectives
- Lock MVP scope and user journeys for a 4-week delivery.
- Define the minimum dataset required for transactions, categories, and budgets.

## Key Decisions
- Single-user, local-only storage (e.g., SQLite file or embedded DB).
- Supported CSV format(s) and required columns:
  - Required: date, amount, description.
  - Optional: transaction id, payee, currency, category.
  - Supported date formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, YYYY/MM/DD (auto-detect with confirmation on ambiguity).
  - Encoding: UTF-8 preferred.
- Definition of "month": calendar month in the user's local timezone (UTC offset applied at parse-time for date classification).

## UX Flows (MVP)
1. Import CSV: Upload -> preview (first 100 rows) -> auto-map columns -> user confirms or manually maps -> validate rows -> import (transactionally) -> show result summary with errors/skips.
2. Transactions List: Default shows current month -> user can change month selector -> filter by category/search text -> click transaction to edit category/description -> save persists locally.
3. Categories: View list -> add/edit/delete category -> optional: add keyword/rule (MVP-lite) -> apply rule to existing transactions in bulk.
4. Budgets: Select month -> set monthly budget amounts per category -> save -> view progress on dashboard.
5. Dashboard: Month selector -> compute income/expense/net -> show budget progress bars for categories with budgets, top categories, and simple charts. Click a category in chart -> filter transactions list.

## Acceptance Criteria
- Upload a CSV and see transactions populated for a selected month.
- Transactions are auto-categorized with ability to override per transaction.
- Users can set budgets per category and see progress vs budget.
- Dashboard renders monthly summary under **2s** on a baseline dataset (5,000 transactions across 12 months, ~50 categories) measured on a 4-core, 8GB RAM dev machine.
