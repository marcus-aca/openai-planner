# Section
4-Week MVP Delivery Plan (Timeline)

## Summary
Goal: Deliver a usable MVP for personal financial tracking that supports CSV transaction import, basic auto-categorization, per-category budgets, and a monthly dashboard that renders summary data under 2 seconds on the benchmark dataset.

Scope (MVP):
- Auth (basic email/password or single-tenant dev mode).
- CSV import with preview, validation, deduplication, and persistence.
- Transactions list with month/category filters and category editing.
- Baseline auto-categorization using a configurable mapping (rule-based).
- Budgets per category with progress computation.
- Dashboard with monthly totals and category breakdowns.
- Basic tests, performance tuning, and documentation.

Success metrics:
- CSV import -> transactions appear and are categorized (or marked Uncategorized).
- Budgets display progress per category.
- Dashboard monthly summary endpoint + UI render < 2s on benchmark dataset.
- No critical bugs blocking usage; automated import dedup prevents >95% duplicate inserts.

## Design
Architecture overview
- Frontend: Single-page app (React or Vue) served by CDN. Components: Import flow, Transactions list, Budgets CRUD, Dashboard.
- Backend: REST API (Node/Express or Django/DRF) with JSON endpoints. Background worker optional for large imports (e.g., Celery or Bull).
- Database: Postgres (recommended) with migrations.
- File storage: S3-compatible (for raw CSVs) or local storage for initial MVP.
- Optional: Redis for caching aggregated results and rate-limiting.
- Monitoring: Application logs + simple request timing metrics.

Core data model (tables / key fields)
- users: id, email, password_hash, created_at
- categories: id, name, parent_id (nullable), is_active, seed_flag
- budgets: id, user_id, category_id, month (YYYY-MM), amount_cents, created_at, updated_at
- transactions: id, user_id, date (date), amount_cents (integer), payee (text), raw_category (text), category_id (nullable), imported_from_id (nullable), external_id (nullable), hash (text), created_at
- imports: id, user_id, filename, row_count, created_at, status (pending/processed/failed)
- category_mappings: id, user_id (nullable), raw_value_normalized, category_id, priority

CSV format expectations
- Required columns: date (YYYY-MM-DD), amount (decimal, positive or negative), payee (string). Optional: raw_category, external_id.
- Upload size limit: set reasonable default (e.g., 5 MB) for synchronous processing; larger uploads routed to background processing.
- Validation: date parseability, amount numeric, payee non-empty, row-level error reporting in preview.

Deduplication algorithm
- Compute deterministic hash per row: SHA256(normalized_date + '|' + normalize_amount_cents + '|' + normalize_payee + '|' + coalesce(external_id, '')).
- Uniqueness constraint: optionally unique index on (user_id, hash) to prevent duplicates on persist.
- For robustness, when hash collision or missing fields, fallback to a similarity check (date + amount + payee substrings).

Auto-categorization baseline
- Rule-based mapping: normalize raw_category and payee strings (lowercase, strip punctuation), exact mapping via category_mappings, then fuzzy substring matching if no exact. If no match -> Uncategorized (null category_id).
- Provide admins/UX to seed global mappings and allow user overrides.

API surface (examples)
- POST /api/imports/upload -> accept CSV, store raw file, return import id and preview URL or preview rows inline.
- POST /api/imports/{id}/confirm -> validate and persist (or enqueue).
- GET /api/transactions?month=YYYY-MM&category=ID&page=X
- PATCH /api/transactions/{id} -> edit category/payee
- POST /api/budgets -> create; GET /api/budgets?month=YYYY-MM
- GET /api/aggregation/monthly?month=YYYY-MM -> totals + breakdown (used by dashboard)
- GET /api/health and /api/perf-benchmark (internal) to run the benchmark dataset

UX flows
- Import flow: Upload -> parse -> preview with row-level validation and dedup flags -> user confirms -> backend persists and returns summary.
- Transactions: list + inline category edit + bulk change for selected rows.
- Budgets: CRUD with month selection and category selector.
- Dashboard: month selector, totals, budget-vs-spent bars, category breakdown chart.

Security & compliance
- Minimal viable auth; ensure password hashing, CSRF protection for browsers, and rate limiting on uploads.
- Sanitize CSV contents; don't execute any content from CSVs.

Performance targets
- Aggregation query and dashboard endpoint < 2s on benchmark dataset (define benchmark: e.g., 100k transactions).
- Acceptable synchronous import processing for up to 5k rows; larger imports processed asynchronously.

Observability
- Request timing metrics, DB slow query logging, import failure alerts, and a simple runbook for performance troubleshooting.

## Implementation Steps
(Tasks broken down by week, with owners and acceptance checks. Owners are roles: PM, FE (frontend dev), BE (backend dev), DB (DB/migrations), QA.)

## Week 1: Foundations
- Finalize PRD + wireframes.
  - PM: confirm scope, UX wireframes, and edge-case decisions (CSV columns, auth behavior).
  - Acceptance: Sign-off from PM + one stakeholder; annotated wireframes delivered.
- Set up repo, frontend scaffolding, backend/API scaffolding.
  - BE/FE: create mono-repo or two repos, CI pipeline (build, lint, tests), basic README and contribution guide.
  - Acceptance: Pipeline green on a sample commit; dev run scripts documented.
- Implement DB schema + migrations + seed categories.
  - DB: implement migrations for tables listed in Design. Seed a starter set of categories (e.g., Groceries, Rent, Utilities, Uncategorized).
  - Acceptance: migrations run locally; categories seeded visible via GET /api/categories.
- Basic transactions list page (empty state).
  - FE: implement transactions list UI with empty state copy + skeleton.
  - BE: API GET /api/transactions returns [].
  - Acceptance: UI shows empty state, API responds, simple end-to-end smoke test passes.

Deliverables end of Week 1:
- Running dev environment, basic CI, DB schema, seeding, empty transactions UI.

## Week 2: CSV Import + Transactions
- CSV upload + parse + validation + preview.
  - FE: upload form, progress, preview table with per-row validation messages and duplicate flags (if duplicates detected against existing persisted hashes).
  - BE: POST /api/imports/upload returns parsed preview (first N rows with validation state) or stores and returns id for background processing.
  - Acceptance: Upload small CSV (<=500 rows) shows preview with validation errors; preview matches server-side parsing.
- Persist transactions + dedup.
  - BE/DB: POST /api/imports/{id}/confirm persists validated rows, computes and stores hash, enforces uniqueness (unique index or explicit check), records import record.
  - Handle concurrency: upsert or transactional insert with ON CONFLICT DO NOTHING.
  - Acceptance: Re-uploading same CSV does not create duplicate transactions; dedup test with intentional duplicate rows shows only one persisted row per duplicate hash.
- Transactions list with filters by month and category editing.
  - FE: list populated after import, month selector, category filter, inline category edit UI.
  - BE: implement filter params on GET /api/transactions; implement PATCH /api/transactions/{id} for category update.
  - Acceptance: After import, transactions appear; filtering shows correct subset; patch updates category and UI reflects change.
- Baseline auto-categorization (raw category mapping or Uncategorized).
  - BE: implement category_mappings table and matching logic used during persist. Default to Uncategorized (category_id = null) when no mapping found.
  - Acceptance: Transactions with raw_category matching seeded mapping are assigned correct category_id; otherwise remain Uncategorized.

Deliverables end of Week 2:
- Import flow end-to-end for small CSVs, deduplication in place, transactions visible and editable, baseline auto-categorization applied.

## Week 3: Budgets + Analytics
- Budgets CRUD UI.
  - FE: pages for creating/editing/deleting budgets, per-month selector and category selector.
  - BE: endpoints POST/GET/PATCH/DELETE /api/budgets; validation (one budget per user+month+category).
  - Acceptance: Create budget -> GET shows it; UI shows validation errors for duplicates.
- Monthly aggregation endpoint (totals + category breakdown).
  - BE: implement optimized SQL aggregation endpoint GET /api/aggregation/monthly?month=YYYY-MM that returns total_spent, total_income (if positive/negative split), and per-category totals and counts.
  - Consider materialized views or pre-aggregations for performance if needed.
  - Acceptance: Endpoint returns expected totals for sample dataset; unit tests validate SQL correctness.
- Budget vs spent computations.
  - BE: compute progress = min(100, (spent / budget) * 100) and return per-budget data in GET /api/budgets?month=YYYY-MM with spent amount.
  - FE: UI shows progress bar and numeric values.
  - Acceptance: Budget progress values match manual calculation in test cases.
- Start performance profiling with sample dataset.
  - DB/BE: load benchmark dataset (e.g., 100k transactions) into a staging DB and run the aggregation endpoint, capture query plan and timings.
  - Acceptance: baseline measurements recorded; top 3 slow queries identified and documented.

Deliverables end of Week 3:
- Budgets working, aggregation endpoint implemented and profiled with initial tuning candidates listed.

## Week 4: Dashboard + Hardening
- Build dashboard UI and charts.
  - FE: implement dashboard page with month selector, total spent/income, budget vs spent chart, and category breakdown chart (bar/pie).
  - BE: ensure endpoint data shapes match frontend needs; add pagination or limits where applicable.
  - Acceptance: Dashboard renders with data for several months; charts are interactive (hover / tooltips).
- Optimize queries/caching to meet <2s summary target.
  - DB/BE: apply indexes, rewrite queries, add Redis caching for aggregation results keyed by month and invalidated on relevant imports or category edits.
  - Acceptance: Aggregation endpoint + frontend render time < 2s on benchmark dataset in staging; repeatability verified.
- Add tests, fix bugs, polish UX.
  - QA/FE/BE: unit tests for backend services, integration tests for import flow, basic e2e test for import->dashboard. Fix reported bugs and improve error messages/UX edge cases (e.g., bad CSV rows).
  - Acceptance: CI test coverage threshold met for critical flows (e.g., import, dedup, budgets, aggregation). No high-severity open defects.
- Documentation and acceptance runbook.
  - PM/BE: write README for running locally, import runbook (how to run performance benchmark, how to re-run migrations, how to recover from failed import).
  - Acceptance: Documentation reviewed and minimal runbook added to repo.

Deliverables end of Week 4:
- Dashboard in production-like environment, performance goals met, tests and docs available, a demo runthrough completed.

## Risks
- Parsing variability: CSVs come in many shapes (different date formats, thousands separators). Mitigation: define strict CSV spec, implement robust date parsing with fallback and row-level errors, surface clear error messages in preview.
- Dedup false negatives/positives: hash-based dedup may miss duplicates with minor differences in payee formatting. Mitigation: allow configurable dedup tolerance, provide manual bulk dedup tools, log ambiguous cases for review.
- Performance on large datasets: aggregation queries may exceed target. Mitigation: benchmark early, add indexes, use materialized views or incremental aggregation, cache results, and move heavy imports to background.
- Scope creep: adding ML classification or complex UX may delay MVP. Mitigation: freeze scope for 4-week MVP; log enhancements for next phase.
- Operational gaps: missing infra (S3, Redis) may block features. Mitigation: use local fallbacks for MVP and plan infra provisioning early.
- Data loss/corruption during imports: Mitigation: transactional inserts, store raw CSVs, keep import records and ability to rollback (mark imported rows deleted rather than drop).

## Dependencies
- Infrastructure: Postgres instance, optional Redis, object storage (S3) for raw CSVs, CI runner access.
- Libraries/Services: CSV parsing library (papaparse or csv-parse), ORM (Prisma/TypeORM/SQLAlchemy), charting library (Chart.js or Recharts), background queue (Bull/Celery) if async processing used.
- Sample data: Representative benchmark dataset (e.g., 100k rows) for performance testing.
- Stakeholders: PM and product owner availability for PRD sign-off and UX decisions during Week 1.
- Security/Compliance: access to secrets management (DB credentials), TLS certs for production staging.
- Team availability: at least 1 FE, 1 BE, 1 DB/DevOps, 1 QA with overlapping availability.

## Acceptance Criteria
(High-confidence, measurable criteria the MVP must meet)
- Functional
  - A user can upload a CSV (following the spec), preview parsed rows with per-row validation, confirm import, and see persisted transactions in the transactions list.
  - Deduplication prevents duplicate persisted transactions for the same content (re-uploading the same CSV does not create duplicates).
  - Transactions show category_id assigned either by mapping rules or left Uncategorized; users can edit a transaction's category and changes persist.
  - Users can create budgets per category per month; the UI shows budget amount and current spent with progress percentage.
  - Dashboard displays monthly totals and per-category breakdowns; charts reflect aggregated data for the selected month.
- Performance
  - Aggregation endpoint + dashboard frontend render completes in under 2 seconds on the benchmark dataset (defined as X transactions — e.g., 100k — in staging). Measurement reproducible and documented.
- Reliability & Quality
  - Critical import paths covered by automated tests (unit and integration). E2E tests exist for import -> view transactions -> set budget -> view dashboard and pass in CI for main branch.
  - No P0/P1 bugs remain open blocking the demo. All high-severity bugs fixed or have documented mitigations.
- Operational
  - Runbook included: how to run import, reprocess failed import, run performance benchmark, and rollback migration.
  - CI configured to run linting, unit tests, and basic integration tests on PRs.
- Security
  - Basic auth implemented with secure password hashing; no plaintext secrets in the repo; dependencies reviewed for critical vulnerabilities.

## Week 1: Foundations
- Finalize PRD + wireframes.
- Set up repo, frontend scaffolding, backend/API scaffolding.
- Implement DB schema + migrations + seed categories.
- Basic transactions list page (empty state).

## Week 2: CSV Import + Transactions
- CSV upload + parse + validation + preview.
- Persist transactions + dedup.
- Transactions list with filters by month and category editing.
- Baseline auto-categorization (raw category mapping or Uncategorized).

## Week 3: Budgets + Analytics
- Budgets CRUD UI.
- Monthly aggregation endpoint (totals + category breakdown).
- Budget vs spent computations.
- Start performance profiling with sample dataset.

## Week 4: Dashboard + Hardening
- Build dashboard UI and charts.
- Optimize queries/caching to meet <2s summary target.
- Add tests, fix bugs, polish UX.
- Documentation and acceptance runbook.

## Exit Criteria (MVP)
- Import CSV -> categorized transactions visible.
- Budgets set per category -> progress shown.
- Dashboard monthly summary renders under 2 seconds on benchmark dataset.
