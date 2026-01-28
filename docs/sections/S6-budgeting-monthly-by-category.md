# Section
Budgeting (Monthly by Category)

## Summary
Provide per-category budgets for a selected month (default: current month). Users can create, read, update and delete budgets for each expense category. The UI shows budgeted amount, spent amount, remaining amount and a progress bar. The MVP excludes income categories from budgeting. Budgets are per-user and stored at month granularity (YYYY-MM). Amounts are non-negative and stored in the user's primary currency (no cross-currency conversion in MVP).

## Design

Data model
- Budget
  - id (UUID)
  - userId (UUID) — owner
  - categoryId (UUID) — references category
  - month (string, format "YYYY-MM") — unique month key
  - amountCents (int, >= 0) — budget amount in cents (stored as integer)
  - currency (ISO-4217) — user's currency at creation (MVP: single-currency per user)
  - createdAt, updatedAt (timestamps)
  - unique constraint: (userId, categoryId, month)

Business rules
- Default month is the current month in the user's locale/timezone; explicit month param must be YYYY-MM.
- Budgets are non-negative. Zero is allowed (explicitly budgeted as 0).
- If no budget exists for a category-month, treat budgetAmount = 0 for display and calculations.
- Income categories are excluded from budgeting in MVP (no CRUD for income categories).
- Spent calculation includes only final/posted expense transactions (see "Transaction filtering" below).
- Progress = spent / budgetAmount; when budgetAmount = 0 show progress = 0 and indicate "No budget set" or "Budget = 0" as appropriate.
- Display clamped progress: min 0, no upper bound on visual but color change after 100%.

Transaction filtering and calculation details
- Expense definition: transactions with amount < 0 (negative) count as expense.
- Include: posted transactions, transactions assigned to a category (including split transactions where one split has categoryId = X).
- Exclude: transactions marked as transfers between user accounts, pending or scheduled/future transactions, transactions with isDeleted = true.
- Splits: use the split line amount and categoryId for summation.
- Rounding: sum amounts in cents (integer math) then convert to currency display format.
- Time boundaries: month boundaries are based on user's local date (start at 00:00:00 local of first day to 23:59:59.999 local of last day). Back-end should accept month=YYYY-MM and compute UTC ranges using user's timezone.

API design
- GET /api/budgets?month=YYYY-MM
  - returns budgets for user for that month plus computed spent/remaining/progress per category (optionally include categories with no budget but with spending)
- POST /api/budgets
  - body: { categoryId, month (YYYY-MM), amountCents, currency? }
  - creates budget; enforce unique constraint
- PUT /api/budgets/:id
  - update amountCents
- DELETE /api/budgets/:id
- POST /api/budgets/bulk-upsert
  - body: { month, budgets: [{categoryId, amountCents}] } — convenience for saving many budgets at once from UI
- Response model includes: id, categoryId, month, amountCents, currency, spentCents, remainingCents, progress (float 0..inf), updatedAt
- Errors: 400 for invalid month/amount, 403 for unauthorized, 409 for unique constraint violations in single-create flow (bulk-upsert should use upsert semantics)

Frontend behavior & UX
- Budget table by category with:
  - Category name and icon
  - Budget amount (inline editable input, numeric; shows currency)
  - Spent (read-only)
  - Remaining (read-only; computed = budget - spent; can be negative)
  - Progress bar with percent and color coding (green <= 100%, red > 100%)
  - Sorting by category name or over/under budget
- Editing model:
  - Inline edit with local validation (non-negative numbers, cents precision)
  - Save on blur + explicit Save All button for bulk edits (debounced autosave optional)
  - Optimistic UI update with server-side validation result; show error toast/inline error on conflict
- Default and empty states:
  - When no budget exists, show blank/0 and an affordance to "Add budget"
  - Show passed month navigation (Prev/Next month) and a month picker
- Accessibility:
  - Inputs labeled, progress bars with screen-reader text
  - Ensure keyboard navigation for editing and saving

Calculations and display
- Use integer cents for all arithmetic; format for display.
- spent = sum(abs(amountCents)) where amountCents < 0 and categoryId = X and transactionDate ∈ month and transaction is posted and not transfer
- progress = (budgetAmountCents > 0) ? (spent / budgetAmountCents) : 0
- remaining = budgetAmountCents - spent
- UI displays progress as a percent (progress*100), clamp display colors but show actual numeric percent even if >100%

Security and permissions
- User can access and modify only their budgets.
- Admin role may have access to view others (if product supports).
- Validate categoryId belongs to user's category set.

Storage & performance
- Add an index on (userId, month), and on (userId, categoryId, month) for quick lookups.
- Consider a periodic materialized monthly totals table for heavy accounts (out-of-scope in MVP; flag as optimization).
- Cache GET /api/budgets?month= for short TTL if needed.

## Implementation Steps

1. Schema Migration
   - Create budgets table with columns and constraints as specified.
   - Add DB indices: (userId, month), (userId, categoryId, month).
   - Add foreign key to categories (nullable enforcement depends on product model).
   - Write rollback migration.

2. Backend: Core Endpoints & Logic
   - Implement services to:
     - compute month start/end timestamps in user's timezone
     - fetch transactions filtered by date/category/status and sum in cents
     - upsert and CRUD budgets with validation
   - Implement endpoints:
     - GET /api/budgets?month=
     - POST /api/budgets
     - PUT /api/budgets/:id
     - DELETE /api/budgets/:id
     - POST /api/budgets/bulk-upsert
   - Add request validation: month format, amount integer >= 0, category exists and is expense category.
   - Ensure authorization middleware applied.

3. Backend: Tests
   - Unit tests: budget service, calculations, timezone month boundary logic.
   - Integration tests: endpoints with mocked transactions and categories.
   - Edge case tests: split transactions, transfers excluded, no budget set, zero budget, over-budget, leap-year/month boundary.

4. Frontend: Components & Flows
   - Build BudgetTable component with rows per category and inline editable amounts.
   - Build MonthPicker and Prev/Next navigation.
   - Implement client-side validation and save flows:
     - Single-cell save on blur
     - Bulk save via bulk-upsert
     - Optimistic UI and error handling
   - Build progress bar component with accessible labels.

5. Frontend: Tests
   - Unit tests for component rendering and calculation logic.
   - Integration/E2E tests to cover a representative scenario:
     - create budgets, navigate months, verify spent/remaining for transactions, test over-budget visualization.

6. QA & Data Validation
   - Manual QA checklist: verify month boundaries in several timezones, confirm transfers excluded, confirm split handling, confirm rounding behavior.
   - Run migration in staging; backfill existing budgets if required by product.

7. Monitoring, Telemetry, and Metrics
   - Add logging for budget creation/update/deletion events.
   - Add tracking of errors and key performance metrics (API latency, bulk-upsert size).
   - Add a metric for number of budgets per user (for capacity planning).

8. Deployment and Rollout
   - Deploy DB migration, backend, frontend in coordinated release.
   - Soft launch to a subset of users if applicable.
   - Monitor error rates and performance and rollback if critical issues.

Checklist for each step:
- Code review
- Security & permissions review
- Automated tests passing
- Documentation updated (API docs + UI help text)

## Risks
- Incorrect transaction filtering: misclassifying transfers or pending transactions could inflate spent numbers. Mitigation: strict filters and test cases.
- Timezone/month boundary bugs: month start/end must use user's timezone; test across international timezones and DST transitions.
- Split transactions complexity: improper handling could double-count or omit parts. Mitigation: use split line amounts keyed to categoryId.
- Currency mismatch: budgets stored in a currency; users with multi-currency transactions may see confusing numbers. MVP avoids cross-currency conversion—document limitation.
- Performance: naive aggregation over large transaction sets may be slow. Mitigation: index on transaction date/category and consider materialized monthly totals for heavy accounts.
- Concurrent edits: two clients editing the same budget may cause conflicts. Mitigation: optimistic locking (updatedAt) and user-facing error messages.
- UX confusion when no budget is set: users may expect recurring budgets; document that budgets are month-scoped, and consider future recurring budgets feature.
- Data migration/backfill issues: existing budgets (if any product history) must be consistent; create migration plan.

## Dependencies
- Transactions service / DB table (must expose transaction amount, date, categoryId, split lines, status, isTransfer, isDeleted)
- Categories service / table (to validate category types: expense vs income)
- Auth & user service (userId, timezone, currency)
- Database with support for migrations and indices
- Frontend framework components (input, modal, progress bar) and form library (if used)
- Monitoring/logging systems for rollout
- Optional: background job system if later implementing aggregated monthly totals

## Acceptance Criteria
- Functional
  - User can select a month (default is current month in their timezone).
  - User can create/update/delete a budget per category for the selected month.
  - The budget amount must be non-negative and stored in cents.
  - UI shows for each category: budget amount, spent amount, remaining amount, and a progress bar.
  - Spent is computed as: sum(abs(amountCents)) where amountCents < 0 and categoryId = X and date in month and transaction is posted and not a transfer (including split lines).
  - Remaining = budgetAmountCents - spentCents (can be negative).
  - Progress = (budgetAmountCents > 0) ? (spentCents / budgetAmountCents) : 0; displayed percent and color coding reflect over-budget when >100%.
  - Income categories are not available for budgeting in MVP.

- Edge cases
  - Split transactions: only the split lines assigned to the category are counted.
  - Transfers are excluded from spent totals.
  - Transactions on the month boundary are correctly included/excluded using user's timezone.
  - Zero-budget behavior: when budgetAmount = 0 show appropriate messaging and 0 progress (or "No budget set" if no record).
  - Multiple saves: bulk-upsert works and doesn't create duplicate records for same (userId, categoryId, month).
  - Concurrent edit conflict surface to the user with clear message.

- Non-functional
  - GET /api/budgets?month= for a typical user (<= 200 categories) responds under 300ms in production conditions (subject to infra SLA).
  - System logs budget create/update/delete events and exposes errors to monitoring.
  - All new unit/integration tests added and passing in CI.
  - Frontend accessible: keyboard navigable inputs and screen-reader labels for progress bars.

- Tests
  - Unit tests covering calculation logic (including timezone month boundaries, splits, transfers).
  - Integration tests for endpoints and roundtrip UI flows.
  - E2E tests covering create/update/delete and month navigation.

## Functional Requirements
- Select month (default current month).
- For each category, set a budget amount.
- Display spent vs budget and remaining.

## Calculations
- For expense categories:
  - `spent = sum(abs(amount)) where amount < 0 and categoryId = X and date in month`
  - `progress = spent / budgetAmount`
- For income categories: optionally exclude from budgets in MVP.

Additional calculation rules
- Use cents/integer arithmetic and convert to display format to avoid floating-point rounding.
- Exclude transfers and pending/future/scheduled transactions; include splits by split line category and amount.
- If budgetAmount = 0 show progress = 0 (and zero or "No budget" UI state), but still compute remaining = -spent.

## UI
- Budget table by category:
  - Category name
  - Budget amount (editable)
  - Spent
  - Remaining
  - Progress bar

Additional UI behaviors
- Inline editing with validation, optimistic updates, and server reconciliation.
- Bulk save option and per-row save behavior.
- Month navigation and picker.
- Color-coded progress and accessible labels.

## Deliverables
- Budgets CRUD endpoints and UI.
- Validation (non-negative budgets).
- Tests for month calculations.

Deliverables (expanded)
- DB migration scripts for budgets table and indexes.
- Backend service and API endpoints with validation and authorization.
- Frontend components (BudgetTable, MonthPicker, ProgressBar) with editable cells and bulk-upsert flow.
- Automated unit tests, integration tests, and E2E tests covering critical calculations and UI flows.
- API documentation and a short user help text describing month-scoped budgets and currency limitations.
- Monitoring/metrics setup and rollout plan notes.
