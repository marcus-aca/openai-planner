# Section
Architecture & Tech Stack

## Summary
This document defines the architecture, technology choices, data model and an actionable implementation plan for a local-first personal finance application (transactions, categories, budgets, analytics). Goals:
- Local-only persistence with optional export/import.
- Fast summary/analytics for up to ~10k transactions (target: summary endpoint <2s).
- Simple, maintainable codebase with clear module boundaries and test coverage.
- Portable desktop/web packaging options (e.g., Tauri/Electron or single-process Next.js/Vite app).

Primary recommendation:
- Frontend: React + TypeScript + Vite
- Backend: single-process API routes (Next.js or bundled Node/Express) or integrated server with the UI
- Database: SQLite using an ORM (Prisma or Drizzle)
- Charts: Recharts (recommended) or Chart.js

Trade-offs are noted below; alternatives are provided where appropriate.

## Design

High-level architecture
- UI -> REST/JSON (or internal IPC) API -> SQLite DB
- Clear module separation:
  - transactions: import (CSV/OFX), list, edit, delete, reconcile
  - categories: CRUD, classification rules (pattern matching, heuristics)
  - budgets: CRUD, per-category or grouped budgets
  - analytics: monthly aggregations, trends, forecasts

Data model (core tables and key fields)
- transactions
  - id: UUID
  - date: DATE (indexed)
  - amount_cents: INTEGER (store in smallest currency unit)
  - currency: TEXT
  - payee: TEXT
  - memo: TEXT
  - category_id: UUID (nullable, FK -> categories)
  - imported_from: TEXT (e.g., "csv", "bank_x")
  - imported_id: TEXT (optional identifier from source)
  - created_at / updated_at: TIMESTAMP
  - indexes: (date), (category_id), (imported_from, imported_id)
- categories
  - id: UUID
  - name: TEXT (unique)
  - type: ENUM('expense','income','transfer')
  - rules: JSON (pattern list, regexes, priority)
  - created_at / updated_at
- budgets
  - id: UUID
  - name: TEXT
  - category_id: UUID (nullable for group budgets)
  - period: ENUM('monthly','weekly','custom') + start_date/end_date
  - amount_cents: INTEGER
  - currency: TEXT
- monthly_aggregates (materialized summary)
  - id: UUID
  - year: INTEGER
  - month: INTEGER
  - category_id: UUID (nullable for totals)
  - total_cents: INTEGER
  - tx_count: INTEGER
  - last_updated: TIMESTAMP
  - unique index: (year, month, category_id)

API surface (example endpoints)
- GET /api/transactions?start=YYYY-MM-DD&end=YYYY-MM-DD&category=...&limit=...&offset=...
- POST /api/transactions/import (multipart/form-data, supports CSV/OFX)
- POST /api/transactions (create/update)
- DELETE /api/transactions/:id
- GET /api/categories, POST/PUT/DELETE /api/categories/:id
- GET /api/budgets, POST/PUT/DELETE /api/budgets/:id
- GET /api/analytics/monthly?year=YYYY&month=MM&groupBy=category|total
- GET /api/analytics/trends?months=12

State and UI considerations
- Client caching: React Query (recommended) for data fetching and background refetches.
- Local UI state: Zustand or React Context for small state (dialogs, selections).
- Charts: Recharts recommended for React + TypeScript ergonomics; Chart.js as lighter alternative.
- Routing: React Router or framework-provided router (Next.js).

Concurrency & reliability
- SQLite is single-writer, multi-reader. Use a short-lived connection per transaction (or a pooled driver that serializes writes).
- Wrap DB writes in transactions. Use WAL mode for better concurrency.
- Provide import job queue (in-memory queue persisted to DB) to avoid long-running single inserts and to show progress.

Indexing and query optimization
- Index by date and category. Cover common queries (date range + category).
- For summaries, either:
  - Maintain materialized monthly_aggregates updated on import / category change (preferred for fast reads).
  - Or execute optimized SQL with windowing and group-by for on-demand computation if write throughput is low.

Import and deduplication
- Allow mapping rules and heuristics for imported transactions (based on payee, amount, date fuzziness).
- Support imported_id + imported_from to detect duplicates on re-import.
- Provide a UI for resolving duplicates and bulk categorization.

Packaging options
- Desktop: Tauri (Rust + webview) preferred for smaller binary and lower attack surface; Electron as fallback.
- Web: Single-process app (Next.js) that runs a server with local SQLite (for self-hosting) — note browser-only apps cannot use SQLite locally without extra components.
- Mobile: out-of-scope for initial implementation.

Security & backups
- Data stored locally; encourage automatic backups/export and manual export to CSV/JSON.
- Encrypt DB file only if required; keep this optional and provide passphrase management.

Folder layout (suggested)
- /src
  - /client (React UI)
  - /server (API routes, job queue)
  - /db (migrations, schema)
  - /shared (types, validators)
  - /scripts (import utilities, seed)
- Tests, CI, packaging configs at repo root.

## Implementation Steps

1. Project setup (1–2 days)
   - Initialize mono-repo or single repo.
   - Create package.json, TypeScript config, ESLint, Prettier.
   - Scaffold Vite + React + TypeScript app OR Next.js app with API routes.
   - Add testing framework (Vitest + Testing Library) and CI skeleton.

2. Database & ORM (1–2 days)
   - Add SQLite driver and Prisma or Drizzle.
   - Define schema for transactions, categories, budgets, monthly_aggregates.
   - Create initial migration and a seed script with sample data (~1k tx).
   - Configure WAL mode and connection options.

3. Server API & DB access layer (2–3 days)
   - Implement repository layer (CRUD functions) with typed inputs/outputs.
   - Implement endpoints listed in Design.
   - Implement batch import endpoint with streaming/batched inserts and deduplication logic.
   - Add input validation (zod or yup).

4. Aggregation strategy (2 days)
   - Implement monthly_aggregates maintenance:
     - On import: compute monthly deltas for affected months and upsert aggregates.
     - On category change / delete: recompute affected aggregates (by month).
   - Alternatively, implement optimized on-demand queries (bench both).

5. Frontend basic UI (3–5 days)
   - Build pages: Transactions list (with filters & pagination), Transaction detail/edit, Import UI, Category manager, Budgets, Analytics dashboard.
   - Integrate React Query for data fetching, optimistic updates for edits/deletes.
   - Implement CSV/OFX import UI with progress and dedupe preview.

6. Charts & analytics UI (2–3 days)
   - Integrate chosen charting library (Recharts recommended).
   - Implement monthly summary view, category breakdown (donut), trend lines, budgets vs actual.

7. Testing & performance (2–3 days)
   - Add unit tests for repo functions and business logic (import dedupe, aggregations).
   - Add integration tests for API endpoints using in-memory/test DB.
   - Load test with benchmark dataset (10k–100k transactions). Measure summary endpoint <2s; optimize queries or use materialized aggregates.

8. Packaging & distribution (2–4 days)
   - Choose packaging (Tauri recommended). Create build pipelines and scripts.
   - Create installers for target platforms (Windows, macOS, Linux) or documentation for self-hosted server.
   - Add automatic backup/export command and UI.

9. Documentation & deliverables (1–2 days)
   - Produce architecture diagram, module boundaries, data flow, and performance measurement report.
   - Document dev setup, migrations, backup, and restore.

10. Polish & bugfixes (ongoing)
   - Implement edge-case handling (e.g., large imports, malformed files), UX improvements, accessibility checks.

Estimated total: 2–4 sprints (4–8 weeks) depending on team size and parallelization.

Concrete developer commands (examples)
- Init: npm init -y
- Install main deps:
  - npm install react react-dom typescript vite @prisma/client sqlite3
  - npm install -D prisma ts-node vitest eslint prettier
- Generate and run migrations (Prisma example):
  - npx prisma init
  - edit schema.prisma
  - npx prisma migrate dev --name init
- Run dev:
  - npm run dev (Vite)
  - or next dev (Next.js)
- Run tests:
  - npm test

## Risks

1. SQLite concurrency limits
   - Risk: long-running writes/large imports block reads or other writes.
   - Mitigation: use WAL mode; batch imports; keep transactions short; serialize writes via in-process queue.

2. Large imports and memory usage
   - Risk: importing very large files may spike memory/cpu.
   - Mitigation: stream parsing, batch DB inserts, show progress, set a reasonable max batch size (e.g., 500–1000 rows).

3. Data corruption or accidental deletes
   - Risk: user data loss via bugs or bad imports.
   - Mitigation: automatic backups before destructive operations, transaction journaling, export/restore flow, and an "undo" for bulk operations where feasible.

4. Performance of on-demand aggregation
   - Risk: long query times on larger datasets.
   - Mitigation: use materialized monthly_aggregates and precompute; index queries; benchmark and optimize SQL.

5. Complexity of category rules (false positives)
   - Risk: auto-categorization misclassifies transactions.
   - Mitigation: make rules adjustable, provide UI for bulk reassignment and rule testing, keep suggestions opt-in.

6. Packaging and cross-platform issues
   - Risk: desktop packaging (Tauri/Electron) introduces platform-specific bugs.
   - Mitigation: CI builds for target OSes, early testing on each platform, prefer Tauri for smaller surface area.

7. Third-party library constraints
   - Risk: charting or ORMs may have missing features or TypeScript friction.
   - Mitigation: choose well-supported libraries; keep alternatives in mind (Chart.js, direct SQL or lighter query builders).

## Dependencies

Core
- React (17+/18+)
- TypeScript (>=4.5)
- Vite (for fast dev) or Next.js (if server-side/API routes desired)
- SQLite (3.35+ recommended for features) and a Node driver (better-sqlite3 or sqlite3)
- ORM: Prisma (recommended) or Drizzle (alternative)
- HTTP server: Node/Express (if separate) or framework-provided API routes
- React Query (data fetching/cache)
- Zustand or React Context (local UI state)
- Charting: Recharts (recommended) or Chart.js
- Date library: dayjs or date-fns
- CSV/OFX parsers: csv-parse, ofx-parser or bank-specific parsers
- Packaging: Tauri (preferred) or Electron
- Testing: Vitest, Testing Library, Playwright (E2E)

Tooling
- ESLint, Prettier, Husky (pre-commit), CI (GitHub Actions)
- Prisma/Drizzle CLI
- Build tooling for installers (Tauri builder or Electron builder)

Platform constraints
- Desktop packaging requires native toolchains (Rust/cargo for Tauri).
- If self-hosting server, ensure Node environment available.

## Acceptance Criteria

Functional
- Transactions can be created, edited, deleted, imported (CSV/OFX) and listed with date-range filtering.
- Categories can be created, updated, deleted and referenced by transactions. Rules can be created to auto-suggest categories.
- Budgets can be created and viewed against actuals.
- Analytics dashboard shows monthly totals, category breakdown, and trend lines.

Performance
- With a benchmark dataset of 10,000 transactions:
  - Monthly summary endpoint returns in under 2 seconds (measured cold).
  - UI list paging loads page (~50 transactions) in <300ms on typical dev machine.
- Imports of 10k transactions complete within acceptable time (target <30s) using batch inserts; progress is reported.

Reliability & Data Integrity
- All DB writes are wrapped in transactions; no partial import states left after failure.
- Deduplication logic prevents obvious re-import duplicates (based on imported_from + imported_id or heuristic).
- Automatic backup created prior to major destructive operations (import with overwrite, mass delete).

Quality & Tests
- Unit tests covering import/deduplication, aggregation maintenance, and category-rule application with >=70% coverage on core domain logic.
- Integration tests for API endpoints (transactions, categories, analytics).
- E2E test covering import -> auto-categorize -> view analytics flow.

UX & Packaging
- Desktop package builds succeed on target OSes (at least one: macOS or Linux) with installable artifact.
- Export (CSV/JSON) and manual backup/restore documented and functional.

Documentation & Deliverables
- Architecture diagram and module boundary doc delivered.
- Performance measurement report with dataset, test method, and results.
- Setup docs for development and build steps.

## Proposed Stack (example)
- **Frontend**: React + TypeScript + Vite (fast dev) or Next.js (if server-side routing/API routes are desired)
- **Charts**: Recharts (recommended for React + TS) or Chart.js (alternative)
- **Backend**: Lightweight local server (Node/Express) *or* single-process app with API routes (e.g., Next.js)
- **Database**: SQLite (via Prisma or Drizzle) for local-only persistence

Notes:
- Recommended default: Vite + React + Prisma + sqlite3 + Recharts; package with Tauri.
- If you prefer minimal dependencies and lower runtime, Drizzle + better-sqlite3 can be considered.

## Architecture
- UI -> REST/JSON API -> DB
- Clear separation:
  - `transactions` module (import, list, edit)
  - `categories` module (CRUD, rules)
  - `budgets` module (CRUD)
  - `analytics` module (monthly aggregations)

Implementation specifics:
- API routes map to server module functions which call the DB repository layer.
- Repository layer contains all SQL/ORM logic; business rules (e.g., auto-categorization) live in a service layer above repository.
- Aggregates maintained in monthly_aggregates table; background job or synchronous update on import updates aggregates to keep read paths fast.
- UI communicates via typed DTOs; shared type definitions reside in /src/shared for consistency.

## Performance Plan
- Use indexed queries by date/month for list and summary queries.
- Precompute monthly aggregates on import and when transaction/category changes (materialized summary table) — primary approach for consistent sub-2s summary responses.
- Fallback: compute on-demand with optimized SQL (use GROUP BY, appropriate indexes, and LIMIT/OFFSET for paging).
- Benchmark dataset: 10,000 transactions (representative mix across 2–3 years).
- Measurement approach:
  - Cold run measurement (first request after restart) and warm run (after DB page cache warmed).
  - Use node-based benchmark scripts to call analytics endpoints and measure latency distribution (p50, p90, p99).
  - If materialized aggregates are used, measure update time on import and query time on reading.

Targets:
- Summary endpoint:
  - Cold: <2.0s
  - Warm: <200ms
- Page load (50 rows): <300ms
- Import (10k): <30s with batching; progress UI updates every batch.

## Deliverables
- Architecture diagram (1 page, PNG/PDF — shows UI, API, DB, modules, and data flows).
- Data flow + module boundaries document (Markdown, includes table of endpoints and schema).
- Performance target definition and measurement approach (CSV/markdown with scripts used and benchmark results).
- Repo with code, migrations, tests, and packaging scripts.
- Developer setup and build instructions (README).
