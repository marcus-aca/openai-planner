# Section
CSV Import Pipeline

## Summary
Build a robust CSV import pipeline that lets users upload bank/transaction CSV files, preview the data, map columns if necessary, validate and normalize rows into a canonical transaction model, deduplicate incoming transactions against existing DB records, and persist validated transactions with clear summary reporting. The MVP supports common date and amount formats, provides a simple mapping UI or enforces a required header schema, and returns counts for imported, skipped (duplicates), and error rows.

Goals:
- Reliable handling of typical CSVs (tens to low hundreds of thousands of rows).
- Predictable deduplication using a stable fingerprint.
- Good UX: preview, mapping UI, clear error messages.
- Tests and monitoring to ensure correctness and performance.

Constraints:
- MVP will support a bounded set of date/amount formats (see Functional Requirements).
- Large imports may run as background jobs if necessary; streaming and chunked DB writes are required to avoid OOM.

## Design
High-level flow:
1. User uploads CSV via UI.
2. Frontend parses CSV minimally to show preview (row count, first N rows, detected columns) and to allow column mapping. Large files should be uploaded directly to backend (or to presigned storage) with streaming.
3. Backend ingests CSV via streaming parser, applies mapping, validates & normalizes each row into a canonical transaction model, computes a fingerprint, and decides: insert, skip (duplicate), or flag (error).
4. Inserts are batched and persisted in transactional chunks; duplicates are skipped or flagged according to user preference.
5. At completion, return an import summary and an errors report; provide a UI to review flagged rows.

Canonical transaction model (example fields):
- id (DB generated)
- occurred_at (ISO date/time)
- description (string)
- amount_cents (integer, signed)
- currency (3-letter code, default USD if unspecified)
- merchant (optional)
- source_filename
- fingerprint (string, e.g., SHA256)
- imported_by (user id)
- imported_at (timestamp)

Fingerprint algorithm (MVP):
- Normalize fields:
  - date -> YYYY-MM-DD (UTC or account timezone)
  - description -> trimmed, collapse whitespace, lowercase
  - amount -> amount in cents (integer)
  - merchant (optional) -> normalized like description
- Concatenate normalized values with separator, compute SHA256, store hex.
- Configurable to include or exclude merchant for dedupe sensitivity.

Validation rules (MVP):
- Required: date, description, amount.
- Date parsing supports MM/DD/YYYY and YYYY-MM-DD (with sensible fallback and explicit format override by user).
- Amount parsing supports optional currency symbols, thousands separators (commas), and negative values in parentheses or with leading minus.
- Rows failing validation are recorded with row number and error reason; user can download error CSV.

UX:
- Preview screen: detected columns, row count, first N rows (N configurable, default 10), suggested mappings.
- Mapping UI: dropdown per canonical field to select CSV column or mark as constant/default.
- Option to choose duplicate handling: auto-skip, flag for review, or always insert (for power users).
- Progress indicator and final summary with details.

Scalability:
- Use streaming CSV parsing and chunked DB writes (e.g., 1k rows per transaction).
- For very large files, process as background job (enqueue, process asynchronously, notify user on completion).

Security:
- Enforce file size limits and content type checks.
- Sanitize inputs; limit accepted columns and row sizes.
- Authentication/authorization on upload endpoint.

Observability:
- Log import start/end, row counts, errors, duplicates skipped.
- Metrics for import durations, rows/sec, failure rates.

## Implementation Steps
1. Choose stack/libraries
   - Frontend CSV preview/parser: PapaParse (browser) or minimal preview via streaming.
   - Backend CSV parser: csv-parse (Node), fast-csv, or equivalent streaming parser.
   - Date parsing: date-fns or Luxon for deterministic parsing.
   - Hashing: native crypto (SHA256).
   - Currency/amount: parse to integer cents (custom routine + optional library).
2. Frontend: upload & preview UI
   - Implement file select / drag-and-drop.
   - Immediately parse first N rows client-side to show preview (columns, first rows, row count estimate).
   - Show suggested column mappings using header heuristics (e.g., header contains "date", "amount", "desc").
   - Provide mapping UI (dropdowns per canonical field), format override (choose date format), and duplicate handling option.
   - Validate file size before upload; for large files, upload to backend with streaming or to presigned storage.
3. Backend: upload endpoint(s)
   - Endpoint to accept file upload or presigned callback.
   - Authenticate/authorize request.
   - Accept mapping metadata (column -> field mapping), duplicate handling choice, import id.
   - If file is small, accept in-memory streaming; for large files, accept multipart/form-data streaming or a reference to storage.
4. Backend: ingestion worker
   - Stream-parse CSV row-by-row applying mapping.
   - For each row:
     - Trim and map columns to canonical fields.
     - Parse date using provided format or heuristics; normalize to ISO date (store date only or date+time).
     - Parse amount:
       - Remove currency symbols and whitespace.
       - Replace parentheses with negative sign.
       - Remove thousands separators (commas).
       - Parse as decimal and convert to integer cents (use rounding rule: round to nearest cent).
     - Normalize description/merchant (trim, collapse spaces, lowercase).
     - Validate required fields.
     - Compute fingerprint (SHA256 of concatenated normalized values).
   - Deduplication:
     - For each row, check fingerprint existence with efficient query/index (index on fingerprint).
     - Optionally check similar matches (same date & amount & fuzzy description) if configured.
     - Act according to user choice: skip insert, flag row as duplicate, or insert a duplicate.
   - Batched persistence:
     - Accumulate valid non-duplicate rows into batches (configurable batch size e.g., 500–1000).
     - Use DB transactions per batch. On batch error, retry once and then fail the batch, recording row-level errors.
     - Save per-row import metadata (source_filename, row_number, fingerprint).
   - Error handling:
     - Record row-level errors to an errors table or file for download.
     - Do not abort the entire import on single-row errors; continue but record summary.
   - Finalize:
     - Commit any remaining batches.
     - Produce an import summary (total rows, imported, skipped duplicates, errors with counts).
     - Notify user (UI polling or push notification).
5. Tests and QA
   - Unit tests for parsing/normalization (dates, amounts, description normalization).
   - Integration tests simulating uploads with sample CSV fixtures (including large and malformed files).
   - End-to-end tests covering preview, mapping, upload, background processing, and final summary.
6. Monitoring and metrics
   - Track import durations, rows processed, error rates, memory usage.
   - Alerts on import failures and slow processing.
7. Rollout and feature flags
   - Release mapping UI and strict header schema behind feature flags if desired.
   - Start with smaller allowed file sizes; iterate to increase limits after monitoring.

## Risks
- Memory/time OOM for very large files
  - Mitigation: streaming parsing, chunked writes, enforce file size limits, process in background jobs.
- Incorrect date/amount parsing due to ambiguous formats or locales
  - Mitigation: explicit format override in UI, heuristics with fallback, robust parsing tests, log ambiguous rows for review.
- False positives/negatives in deduplication
  - Mitigation: normalize consistently, allow configuration to include/exclude merchant, provide "flag" mode to review duplicates manually.
- Partial failures causing inconsistent state
  - Mitigation: batch transactions, idempotent imports via import_id + fingerprint, durable error records, retries.
- Malicious or malformed CSV content (e.g., CSV injection, giant fields)
  - Mitigation: sanitize inputs, enforce max columns and max field length, escape outputs in UI, validate content-type.
- Performance bottlenecks on DB fingerprint lookups for large imports
  - Mitigation: ensure fingerprint column is indexed, use bulk upsert techniques or in-memory dedupe set for current import, temporary dedupe cache (Bloom filter) to avoid DB hits for obvious duplicates within the same import.
- UX confusion about mapping and formats
  - Mitigation: clear defaults, suggested mappings, inline help, downloadable error CSV with row numbers and reasons.

## Dependencies
- Frontend
  - PapaParse (or equivalent) for client-side preview.
  - UI components for mapping and progress (existing component library).
- Backend
  - Streaming CSV parser (csv-parse / fast-csv).
  - Date parsing library (date-fns or Luxon).
  - Crypto library for SHA256 (native).
  - Database with support for transactions and indexed fingerprint column (Postgres recommended).
  - Optional background job system (e.g., Sidekiq/Resque/Worker queue) for large imports.
  - Storage for uploaded files if using presigned uploads (S3 or equivalent).
- Ops
  - Monitoring/alerting (Prometheus, Datadog).
  - CI for running automated tests and fixtures.

## Acceptance Criteria
- Functionality
  - Users can upload a CSV and see a preview: detected columns, row count estimate, and first 10 rows.
  - The system accepts either a required header schema or allows user mapping via a simple dropdown UI.
  - Date formats supported at minimum: MM/DD/YYYY, YYYY-MM-DD; UI allows selecting a format override.
  - Amount parsing handles currency symbols, commas, negative parentheses, and converts to integer cents accurately.
  - Required fields (date, description, amount) are validated. Invalid rows are captured with row number and a clear error message.
  - Fingerprint-based deduplication is implemented: fingerprint = normalized(date, description, amount) hashed with SHA256; duplicates are either skipped or flagged based on user choice.
  - Import summary returned: total rows, imported count, skipped duplicates, errors count; errors downloadable as CSV with row numbers and messages.
  - Batch DB writes with transactions are used; no full import should leave the DB in a partially committed inconsistent state for successfully committed batches.
- Performance & Scalability
  - The pipeline can process a 100k-row CSV without exceeding memory on standard instance (using streaming and batching).
  - Fingerprint index exists and deduplication checks execute with acceptable latency (target: database lookups amortized to < 1 ms per check under normal load; validate with load tests).
- Reliability & Observability
  - All imports are logged with start/end, row counts, and error summaries.
  - Metrics for import duration and error rates are emitted.
  - Automated tests covering parsing, normalization, deduplication, and end-to-end import scenarios exist and pass in CI.
- Security
  - File uploads are limited in size and validated for content type.
  - Users cannot import on behalf of other users (authorization enforced).
- UX
  - Preview and mapping UI are responsive and provide actionable defaults and help text.
  - Users can optionally review flagged duplicates and error rows before finalizing if “flag” mode is selected.

## Functional Requirements
- Upload CSV file.
- Parse rows into normalized transactions.
- Validate required fields (date, description, amount).
- Handle common formats:
  - Date parsing (MM/DD/YYYY, YYYY-MM-DD)
  - Amount parsing (commas, currency symbol, negative parentheses)
- Show preview: row count, first N rows, detected columns.

Additional specifics:
- Default preview N = 10 (configurable).
- Error reporting must include row number, raw row data (or columns), and error reason.
- System should support specifying a file-level default currency if columns do not include it.

## Deduplication (MVP)
- Compute a fingerprint per transaction using normalized fields:
  - Normalization steps:
    - date -> ISO YYYY-MM-DD (use account timezone if applicable)
    - description -> trim, collapse multiple spaces to single, lowercase, remove non-printable characters
    - amount -> cents integer (remove currency symbols, thousands separators, parentheses -> negative)
    - merchant -> same normalization as description (optional inclusion)
  - Concatenate normalized fields with a delimiter (e.g., '|') and compute SHA256 hex string.
- Dedup logic:
  - Check DB index on fingerprint.
  - If fingerprint exists:
    - If user selected "auto-skip": skip inserting row and increment skipped count.
    - If user selected "flag": record row as duplicate in errors/flags table for manual review.
    - If user selected "always-insert": insert regardless.
- Within-import duplicates:
  - Track seen fingerprints in a memory-efficient set (e.g., Bloom filter + secondary exact set for the import) to avoid repeated DB lookups for duplicates inside the same import.

## Column Mapping Approach
- MVP option A: Require a specific CSV header schema
  - Pros: simplest implementation; fewer mapping errors.
  - Cons: less flexible for users with differing exports.
  - Use when you control CSV generation or for onboarding templates.
- MVP option B: Simple mapping UI (dropdowns) if headers differ
  - Pros: more flexible; better UX for varied sources.
  - Implementation notes:
    - Use header heuristics to suggest mappings automatically (e.g., headers containing "date", "amount", "desc", "merchant").
    - Allow users to set constant values for missing columns (e.g., default currency).
    - Persist mappings per user/account for future imports from the same source.
- Recommendation: Implement option B for MVP if user base imports from multiple sources; fallback to option A as a stricter mode for power users or template uploads.

## Implementation Steps
1. Choose CSV parser (e.g., PapaParse on frontend, csv-parse on backend).
2. Build upload endpoint/UI:
   - Frontend preview and mapping UI with heuristics and format overrides.
   - Backend endpoints for synchronous small imports and asynchronous large imports (accept mapping metadata).
3. Validate and normalize rows:
   - Implement date/amount normalization functions and unit tests.
   - Implement description/merchant normalization and fingerprint computation.
4. Deduplicate:
   - Index fingerprint in DB.
   - Implement within-import dedupe cache and DB checks per row, honoring user preference (skip/flag/insert).
5. Persist in a single DB transaction per batch:
   - Define batch size, transactional semantics, and retry policy.
   - Ensure idempotency by import_id + fingerprint.
6. Error handling & reporting:
   - Collect row-level errors, write to errors table or file, expose downloadable CSV.
   - Provide final import summary endpoint.
7. Tests:
   - Automated tests with sample CSV fixtures covering success, duplicates, malformed rows, large files.
8. Monitoring & roll-out:
   - Add metrics, logging, and feature flags; monitor initial runs before full rollout.

## Deliverables
- Import screen with:
  - File upload / drag-and-drop.
  - Preview (row count, first N rows, detected columns).
  - Mapping UI with suggested mappings and format overrides.
  - Duplicate handling options (auto-skip, flag, always-insert).
  - Progress indicator and final summary.
- Backend endpoints and worker:
  - Upload endpoints (sync for small files, async/background for large).
  - Streaming CSV ingestion, validation, normalization, deduplication, batched persistence.
  - Error reporting and import summary endpoint.
- Database changes:
  - transactions table updates (fingerprint column + index).
  - import_runs table for tracking imports and statuses.
  - import_errors table or storage for row-level error reports.
- Automated tests:
  - Unit tests for parsing and normalization.
  - Integration/e2e tests with CSV fixtures including edge cases.
- Documentation:
  - User-facing docs for acceptable CSV formats and mapping UI.
  - Developer docs for fingerprint algorithm, batch size configuration, and deployment considerations.
- Monitoring:
  - Metrics and logs for import performance and error rates.
