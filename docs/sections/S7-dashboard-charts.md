# Section
Dashboard & Charts

## Summary
Build an interactive monthly dashboard that surfaces key financial KPIs and visualizations for end users. The dashboard will default to the current month and allow month selection. Backend will expose a single analytics endpoint that returns totals, per-category aggregates, and budget comparisons. Aggregation will be performed in SQL for performance; results will be cached per-month and invalidated on writes. The UI will show KPIs, a budget overview, and two charts (expense-by-category pie/donut and budget-vs-spent bar for top N categories). Deliverables include a responsive dashboard page that loads in <2s for the defined dataset, unit/integration tests for analytics, and basic visual regression checks.

Success criteria: correctness of aggregates vs. source data, responsiveness (<2s), and visual parity across supported viewports.

## Design
Overview
- Single-page dashboard that requests pre-aggregated monthly analytics from backend.
- Month selector component (defaults to current month). All displayed numbers and charts update when month changes.
- Backend endpoint returns all data needed by the page in one request to avoid multiple round-trips.

Data model (inputs)
- Transactions table: id, user_id, amount (positive incomes, negative expenses or type flag), category_id, occurred_at (timestamp), created_at, updated_at.
- Categories table: id, user_id, name, budget_amount (nullable).
- Budgets: if budgets are separate, map to category_id and month/year.
- Assumption: user-level isolation via user_id; multi-tenant customers require tenant scoping in queries.

API contract
- Endpoint: GET /api/analytics/monthly?month=YYYY-MM
- Response JSON:
  - month: "YYYY-MM"
  - totals: { total_income: number, total_expenses: number, net: number, transaction_count: int }
  - categories: [{ category_id, name, budget_amount, spent_amount, spent_count, over_budget: boolean }]
  - budget_overview: { total_budgeted, total_spent, categories_over_budget_count, categories_over_budget: [category_id,...] }
  - charts:
    - expense_by_category: [{ category_id, name, amount, percent }]
    - budget_vs_spent_top: [{ category_id, name, budget_amount, spent_amount }]
  - generated_at: ISO timestamp

Query & aggregation strategy
- Use a single SQL aggregation query (or small set of queries combined in transaction) to compute totals and per-category aggregates grouped by category_id for the requested month.
- Use indexed columns: occurred_at (with functional index on date or month), category_id, user_id.
- Avoid N+1 or per-category queries.

Caching & invalidation
- Cache computed month result per user (or per tenant) with key pattern analytics:{user_id}:{YYYY-MM}.
- TTL: configurable (e.g., 1 hour) but require immediate invalidation on writes that affect the month (transaction create/update/delete, category budget change).
- Invalidation strategy: on write events that modify relevant tables, delete the cache key(s) for the month(s) impacted (determine month from occurred_at or budget effective month). Optionally publish invalidation messages to a cache/queue system for multi-instance setups.

Frontend architecture
- Chart library: pick one (e.g., Chart.js, Recharts). Keep chart code encapsulated for easy swap.
- Accessible components: use aria labels for charts, provide numeric table/list fallback.
- Responsive: single-column mobile, two-column desktop.

Instrumentation & monitoring
- Track API latency, cache hit/miss rates, and error rates via application monitoring.
- Add logs for cache invalidation events and aggregate generation.

Security & permissions
- Authenticate request; ensure user/tenant isolation at query layer to prevent cross-user data leaks.

## Implementation Steps
1. Schema & Index Review (1-2 days)
   - Verify required columns exist on transactions, categories, budgets.
   - Add indexes if missing:
     - transactions: INDEX (user_id, occurred_at), INDEX (user_id, category_id, occurred_at)
     - budgets: INDEX (user_id, category_id, effective_month)
   - Add functional/index on date_trunc or stored month field to speed month queries, e.g. transactions_month (YYYY-MM) if necessary.

2. Backend: Aggregation Query & Endpoint (2-4 days)
   - Implement and test SQL aggregation:
     - totals: SUM(CASE WHEN type='income' THEN amount ELSE 0 END), SUM(CASE WHEN type='expense' THEN amount ELSE 0 END)
     - per-category: GROUP BY category_id -> SUM(spent), COUNT(*)
     - join budgets/categories to include budget_amount
   - Example SQL sketch:
     - SELECT
         c.id AS category_id, c.name,
         COALESCE(b.budget_amount, 0) AS budget_amount,
         SUM(t.amount) FILTER (WHERE t.amount < 0) * -1 AS spent_amount,
         COUNT(t.id) FILTER (WHERE t.amount < 0) AS spent_count
       FROM categories c
       LEFT JOIN budgets b ON b.category_id = c.id AND b.effective_month = :month
       LEFT JOIN transactions t ON t.category_id = c.id AND t.user_id = :user_id
         AND t.occurred_at >= :month_start AND t.occurred_at < :next_month_start
       GROUP BY c.id, c.name, b.budget_amount;
   - Implement endpoint GET /api/analytics/monthly that:
     - Validates month format (YYYY-MM).
     - Computes month_start and next_month_start in UTC or user timezone (see Risks).
     - Checks cache; if cache miss, runs aggregation, stores result, returns JSON.

3. Caching & Invalidation (1-2 days)
   - Choose cache store (Redis recommended).
   - Implement cache key strategy and TTL.
   - Add cache invalidation hooks:
     - On transaction create/update/delete: compute affected month(s) and delete analytics:{user_id}:{YYYY-MM}.
     - On budget/category update: delete the affected month(s) for that category (if budgets are month-scoped) or delete current month if budgets are global.
   - For multi-instance systems, ensure invalidation is global (Redis OK).

4. Frontend: UI & Charts (3-5 days)
   - Month selector component wired to query the endpoint and show loading skeletons.
   - KPI widgets for total income, total expenses, net — include formatting and accessibility.
   - Budget overview panel with totals and list/count of categories over budget; allow clicking a category to open detail (optional).
   - Pie/donut chart for expense by category (shows percentage & amount tooltips).
   - Bar chart for budget vs spent per category (display top N categories by spent_amount; allow "show more").
   - Provide fallback numeric list/table for screen readers / noscript.

5. Tests & Visual QA (2-3 days)
   - Backend: unit tests for aggregation logic; test cases including:
     - Months with no transactions.
     - Transactions spanning months.
     - Transactions with incomes and expenses.
     - Budget comparisons and over-budget flags.
   - Integration tests for endpoint with test DB fixtures.
   - Performance tests (see Performance).
   - Visual regression tests for key viewports (desktop & mobile) using a tool like Percy or Playwright snapshots.

6. Performance & Load Testing (1-2 days)
   - Run queries against defined dataset and verify <2s end-to-end (backend query + serialization + network).
   - If slow, optimize: add indexes, materialized views (optional), or pre-aggregate nightly.

7. Rollout & Monitoring (1 day)
   - Feature-flag the new dashboard.
   - Deploy to canary users, monitor latency, cache hit ratio, errors.
   - Collect user feedback and adjust.

8. Documentation & Handoff (0.5-1 day)
   - Document API schema, cache keys & invalidation, and any DB changes.
   - Add runbook for cache invalidation issues and performance regressions.

Total estimated dev time: ~10–16 developer-days (depends on existing infra & complexity).

## Risks
- Stale cache presenting incorrect numbers
  - Mitigation: immediate invalidation on writes; short TTL; surface "last updated" timestamp on UI.
- Month boundary/timezone mismatches
  - Mitigation: agree on canonical timezone (UTC or user-preferred timezone). Convert occurred_at to month using that timezone consistently both in writes and reads.
- Large datasets cause slow aggregations
  - Mitigation: ensure proper indexes, consider materialized monthly aggregates if query cost is high, or move heavy work to scheduled pre-aggregation jobs.
- Incorrect budget mapping
  - Mitigation: define clear rules for how budgets are scoped (per-category per-month vs rolling). Test edge cases.
- N+1 queries or multiple queries per user
  - Mitigation: implement single aggregation query (or small bounded set) and profile SQL.
- Multi-tenant cache isolation mistakes
  - Mitigation: include user_id/tenant_id in cache keys and enforce scoping at query layer.
- Visual regressions across browsers/screen sizes
  - Mitigation: run visual regression tests for common viewports; ensure charts degrade gracefully.

## Dependencies
- Backend:
  - Database with transactions, categories, and budgets (Postgres recommended).
  - DB permissions to add indexes or columns if needed.
  - Redis (or in-memory cache) for caching; clear cross-instance invalidation if multi-node.
  - Backend framework support for adding API route and typical middleware (auth, rate-limiting).
- Frontend:
  - Charting library (Chart.js, Recharts, or equivalent) and client build pipeline.
  - Existing auth/session to get user_id or token.
- Testing & CI:
  - Unit/integration test runner and test DB.
  - Visual regression tooling (Percy, Playwright screenshots, or similar).
- Ops:
  - Monitoring/metrics stack (Prometheus, Datadog, etc.) to capture latency and errors.
- Human:
  - Product owner for design sign-off on widget behaviors and budget rules.
  - QA for visual regression and cross-browser testing.

## Acceptance Criteria
Functional
- A user can open the dashboard and see KPIs, budget overview, and charts for the current month by default.
- Month selector updates all data for the selected month within the dashboard.
- The API GET /api/analytics/monthly?month=YYYY-MM returns the documented JSON schema and consistent numbers compared to raw transaction data.
- Categories have correct over_budget flag and are listed in budget_overview.categories_over_budget when applicable.

Performance
- End-to-end load time for the dashboard page (API + render) is <2 seconds on the defined dataset (define dataset size in project doc; e.g., 100k transactions across categories for single user or representative tenant).
- Backend analytics query returns in <500ms for cache miss on defined dataset (target; allow fallback to 1s depending on infra).
- Cache hit path returns in <200ms.

Correctness & Tests
- Backend unit tests for aggregation logic covering edge cases pass.
- Integration tests for the API endpoint pass in CI.
- Visual regression tests exist for desktop and mobile and do not regress (baseline images recorded).

Reliability & Monitoring
- Cache invalidation works: after creating/updating/deleting a transaction that affects month M, a subsequent GET for month M returns updated data (tests / manual verification).
- Monitoring dashboards track API latency and cache hit/miss rates; alerts configured for error rate or latency regressions.

Accessibility & UX
- Charts include accessible labels or a table alternative.
- Page is responsive: usable on mobile and desktop breakpoints.

Deliverables
- Dashboard page meeting <2s for defined dataset.
- Visual regression checks (basic) and analytics unit tests.
