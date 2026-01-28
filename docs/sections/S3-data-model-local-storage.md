# Section
Data Model & Local Storage

## Summary
Define a durable, indexed local data model and storage plan for transactions, categories, budgets, and optional category-matching rules. The plan supports reliable CSV import, fast queries for monthly and per-category aggregates, schema migrations and seeding of defaults, and a small rule engine for automatic categorization. Storage choices support web (IndexedDB via Dexie.js) and native/mobile (SQLite) with a single abstracted data access layer so application logic is storage-agnostic.

## Design

- Storage options
  - Web: IndexedDB using Dexie.js (or equivalent) for transactions at scale and indexed queries.
  - Native/Mobile: SQLite (e.g., via react-native-sqlite-storage or Expo SQLite). Schema mapped 1:1 with SQL.
  - Abstraction: implement a Repository / DAO layer exposing the same methods (CRUD, queries, migrations, import pipeline) so the UI and business logic are independent of underlying engine.

- Entities (see below for full fields and constraints)
  - Transaction: atomic financial record; amounts are numeric stored in cents (integer) to avoid floating-point errors.
  - Category: named grouping, unique by normalized name.
  - Budget: per-month budget per category; enforce unique (month, categoryId).
  - CategoryRule (optional MVP-lite): simple text or regex rules used during import to assign categoryId to transactions automatically.

- IDs and formats
  - Use UUIDv4 for entity ids.
  - Dates stored as ISO 8601 strings (YYYY-MM-DD for dates; full ISO for timestamps) or as integer timestamps (ms since epoch) depending on storage engine; choose one consistently and convert on read/write.
  - Month in Budget: store as "YYYY-MM" string (index-friendly) and optionally store monthStart as ISO date for calendar calculations.

- Amounts and currency
  - Store amounts as integer number of minor currency units (e.g., cents). Example: $12.34 -> 1234. Do not store floats.
  - Include a single-app currency assumption for MVP. If multicurrency required later, add currency code field.

- Referential integrity
  - Where the storage engine supports FKs, enforce them. Otherwise, enforce referential integrity in the DAO layer (reject deletion of categories referenced by budgets/transactions, or cascade/mark as null per policy).

- Indexes & query patterns
  - Indexes to support:
    - transactions(date)
    - transactions(categoryId, date)
    - transactions(source, date) (optional, for import dedup)
    - budgets(month, categoryId) unique
  - Anticipated queries:
    - Monthly totals (sum of amount by month)
    - Monthly per-category aggregates
    - Transactions for a month or category
    - Budgets lookup per month + category

- CSV import & duplication
  - Normalize CSV fields (date normalization, trim, unify merchant casing).
  - Use a deterministic import deduplication strategy: compute a stable fingerprint (hash) of source+date+amount+merchant+description and store it on transaction as sourceFingerprint to detect duplicates from repeated imports.
  - Preserve rawCategory when present in CSV.

- CategoryRule behavior
  - Rules evaluated in priority order (lower number = higher priority).
  - matchType:
    - contains: case-insensitive substring match on merchant + description fields.
    - regex: applied to merchant + description; regex should be flagged as anchored/unanchored per pattern.
  - First matching rule sets categoryId; if none matches, leave categoryId null for manual categorization.

- Migrations & seed
  - Versioned migrations. Example versions:
    - v1: create tables and indexes, seed default categories.
    - v2: add CategoryRule table and sourceFingerprint on transactions.
    - v3: add budgets month index or change amount storage to integer cents.
  - Provide a migration runner that can run sequentially and supports roll-forward only for MVP.

## Implementation Steps
1. Choose storage adapter and abstraction
   - Decide target platforms (web only vs web+mobile).
   - For web: add Dexie.js; for mobile: choose SQLite adapter.
   - Implement a StorageAdapter interface with methods: migrate(), seedDefaults(), beginTransaction(), commit(), rollback(), getRepository(entity), export(), import().

2. Define schema and types
   - Finalize column names, types and constraints for each entity (see Entities section).
   - Decide representation for dates and amounts (recommend: ISO date strings for dates, integer cents for amount, ISO timestamps for createdAt/updatedAt).

3. Implement migrations
   - Implement migration runner that stores current schema version in a metadata table.
   - Write initial migration (v1) that creates tables, indexes and inserts default categories.
   - Add subsequent migrations as needed. Tests must run migrations on fresh DB and after simulated upgrades.

4. Implement repositories / DAOs
   - Methods for TransactionRepo: create, bulkCreate (with import dedupe), update, delete, findById, queryByDateRange, queryByMonth, queryByCategoryAndMonth, aggregateSumByMonth, aggregateSumByCategoryForMonth.
   - CategoryRepo: create, findAll, findByName (case-insensitive normalized), update, delete (with integrity checks).
   - BudgetRepo: createOrUpdate, getForMonth, delete.
   - CategoryRuleRepo: create, listOrdered, delete; pre-compile regex where practical.

5. Implement CSV import pipeline
   - Parse and normalize rows.
   - Validate each row (date parseable, amount numeric).
   - Create a sourceFingerprint per row: e.g., sha256(source + date + normalizedAmount + normalizedMerchant + normalizedDescription). Store sourceFingerprint and source='csv'.
   - Check for existing transaction with same sourceFingerprint; skip duplicates.
   - Apply CategoryRules (in order) to set categoryId.
   - Bulk write transactions via TransactionRepo.bulkCreate in a single transaction where supported.

6. Implement rule engine
   - Simple engine that accepts a transaction-like object and returns categoryId and matchedRuleId.
   - Ensure rules are evaluated deterministically and efficiently; short-circuit on first hit.
   - Store match metadata on transaction if useful (matchedRuleId, matchedAt) — optional.

7. Indexes & performance
   - Ensure proper indexes are created during migration.
   - For large import batches, use bulk-insert APIs, disable indexes momentarily if supported, or use transactions for faster commits.
   - Add simple pagination for transaction listing, and streaming aggregate compute if dataset is large.

8. Seed default categories
   - Seed a minimal set (Groceries, Rent, Utilities, Dining, Transport, Income, Uncategorized).
   - Use normalized names (lowercase trim) to detect duplicates.

9. Tests & validation
   - Unit tests for repositories and migration runner.
   - Integration tests for CSV import, deduplication, rule matching, and aggregate queries.
   - Manual QA: import known CSV, confirm totals match expected.

10. Export/backup & restore
    - Implement export to JSON/CSV including schema version and metadata.
    - Implement import restore that validates schema version and migrates if needed.

11. Documentation & examples
    - Document the schema, repository interface, migration steps and example queries (see Deliverables).

## Risks
- Performance degradation with large volume of transactions:
  - Mitigation: bulk inserts, appropriate indexes, pagination, and possibly WebWorker for import on web.
- Floating-point precision errors if amounts stored as floats:
  - Mitigation: store amounts as integer minor units (cents).
- CSV import duplicate detection false negatives/positives:
  - Mitigation: use a deterministic fingerprint of normalized fields; allow user to review duplicates during import.
- Date/timezone normalization issues:
  - Mitigation: normalize dates to local date portion on import (store dates without time for transaction date) and keep timestamps in UTC for createdAt/updatedAt.
- Referential integrity not enforced by storage engine:
  - Mitigation: DAO-level checks and constraints; prevent deletion if referenced or implement cascade policy explicitly.
- Regex misuse in CategoryRule causing performance or runtime errors:
  - Mitigation: validate and compile regex on creation; limit complexity; run in try/catch and fail-safe to no match.
- Schema migration failures leaving DB unusable:
  - Mitigation: test migrations thoroughly, store backups, migrate in transactions where supported, and provide clear rollback or recovery instructions.
- Privacy / security for local data:
  - Mitigation: recommend device-level encryption; for web, advise against storing highly sensitive PII or provide optional encryption layer.

## Dependencies
- Storage libraries:
  - Web: Dexie.js (IndexedDB wrapper) or equivalent.
  - Mobile/native: SQLite adapter (e.g., react-native-sqlite-storage, Expo SQLite).
- Utility libraries:
  - uuid for id generation
  - sha256 or other hash (for sourceFingerprint)
  - date-fns or Luxon for date normalization and month math
  - optional: a lightweight query builder (if using raw SQL on SQLite)
- Testing:
  - Jest or similar for unit/integration tests; test DB fixtures.
- Build/migration tooling:
  - Migration runner built into the app or an npm/script that runs on startup.

## Acceptance Criteria
- Schema & migrations
  - Migration runner creates tables and indexes on a fresh DB.
  - Upgrading a DB via migration runner applies all migrations in order without error (tested in CI).
- Referential integrity & constraints
  - Category.name uniqueness enforced (case-insensitive normalized).
  - Budget uniqueness enforced on (month, categoryId).
- CSV import
  - Import pipeline normalizes rows, computes sourceFingerprint, deduplicates by fingerprint, applies CategoryRules in priority order, and writes transactions in bulk.
  - Import of a sample CSV (provided in tests) results in the expected number of inserted transactions and correct category assignments.
- Queries & aggregates
  - Example queries (see Deliverables) produce correct monthly totals and per-category aggregates on a seeded dataset and on the sample import.
  - Query performance acceptable on target dataset sizes (define SLA, e.g., monthly aggregate < 200ms for 10k transactions on typical device).
- Rule engine
  - CategoryRule matches are deterministic and respect priority; regex and contains match types work as documented; invalid regex are rejected at rule-creation time.
- Backups & exports
  - DB export includes schema version and can be re-imported to restore data.
- Tests
  - Unit tests cover repositories and rule engine (>= 80% coverage for those modules).
  - Integration tests validate migration, seed, import, dedupe, and aggregate queries.
- Documentation
  - Schema documentation, example queries, and migration steps are included in the repository/docs.

## Entities
### Transaction
- Fields:
  - id (uuid, primary key)
  - date (ISO date string 'YYYY-MM-DD' representing transaction date)
  - description (string)
  - amount (integer, minor units e.g., cents; negative=expense, positive=income)
  - merchant (optional string)
  - categoryId (uuid, foreign key to Category, nullable)
  - rawCategory (optional string from CSV)
  - source (string, e.g., 'csv', 'manual')
  - sourceFingerprint (string, optional) — deterministic hash for deduplication
  - matchedRuleId (uuid, optional) — if assigned by rule engine
  - createdAt (ISO timestamp)
  - updatedAt (ISO timestamp)
- Notes:
  - Validate amount is integer; reject floats.
  - Normalize merchant and description on write (trim, collapse whitespace).
  - createdAt/updatedAt managed by repository.

### Category
- Fields:
  - id (uuid, primary key)
  - name (string, unique normalized; e.g., store normalizedName lowercase trimmed as unique key)
  - normalizedName (string, lowercase trimmed) — used for uniqueness and fast lookup
  - type (enum: 'expense'|'income'|null) (optional, helpful for UI filters)
  - createdAt, updatedAt
- Constraints:
  - unique(normalizedName)

### Budget
- Fields:
  - id (uuid, primary key)
  - month (string 'YYYY-MM', indexed)
  - monthStart (ISO date, optional)
  - categoryId (uuid, foreign key to Category)
  - amount (integer, minor units)
  - createdAt, updatedAt
- Constraints:
  - unique(month, categoryId)

### CategoryRule (optional MVP-lite)
- Fields:
  - id (uuid, primary key)
  - categoryId (uuid, fk)
  - matchType (enum: 'contains' | 'regex')
  - pattern (string)
  - priority (integer; lower = higher priority)
  - enabled (boolean)
  - createdAt, updatedAt
- Behavior:
  - At creation/update: validate pattern (for regex, compile test; for contains, store normalized pattern).
  - At evaluation: if enabled, evaluate in priority order until first match.

## Indexes
- transactions(date)
- transactions(categoryId, date)
- transactions(source, sourceFingerprint) (for import dedupe)
- categories(normalizedName) unique
- budgets(month, categoryId) unique constraint

Notes: For IndexedDB/Dexie, map these to primaryKey & indexed properties as appropriate. For SQLite, create corresponding INDEX statements.

## Migrations & Seed
- Initial migration (v1):
  - Create tables: Transactions, Categories, Budgets.
  - Create indexes specified above.
  - Seed Categories: Groceries, Rent, Utilities, Dining, Transport, Income, Uncategorized (insert with normalizedName).
  - Store schema version = 1 in metadata table.
- v2 (example):
  - Add CategoryRule table.
  - Add sourceFingerprint and matchedRuleId to Transactions (backfill optional).
  - Update schema version = 2.
- Migration runner:
  - Reads current schema version (0 if none).
  - Runs migration scripts sequentially to target version.
  - Runs inside storage transaction when supported.
- Seed runner:
  - Idempotent; checks for existing category normalizedName before inserting.

## Deliverables
- Schema definition + migration scripts for chosen storage(s) (SQL + Dexie schema JSON).
- StorageAdapter interface and implementations (Dexie and SQLite adapters or at least one target).
- Repository/DAO implementations for Transactions, Categories, Budgets, CategoryRules.
- CSV import pipeline implementation including deduplication and rule application.
- Seed script for default categories.
- Example queries (SQL and Dexie examples) for:
  - Monthly totals (sum of amount grouped by month)
    - SQL example:
      SELECT substr(date, 1, 7) AS month, SUM(amount) AS total_cents
      FROM Transactions
      GROUP BY month
      ORDER BY month DESC;
  - Per-category aggregates for a month:
    - SQL example:
      SELECT c.id AS categoryId, c.name, SUM(t.amount) AS total_cents
      FROM Transactions t
      LEFT JOIN Categories c ON t.categoryId = c.id
      WHERE substr(t.date,1,7) = '2026-01'
      GROUP BY c.id, c.name
      ORDER BY total_cents ASC;
  - Dexie (IndexedDB) pseudo-example:
    - db.transactions
      .where('date')
      .between('2026-01-01', '2026-01-31', true, true)
      .toArray()
      .then(rows => aggregateByCategory(rows));
- Tests:
  - Unit tests for repository methods, CSV import, rule engine.
  - Integration tests for migration and seeded data.
- Documentation:
  - README for data model, migration process and repository API usage.
  - Import guidance: CSV expected columns, dedupe behavior, sample CSV file.
