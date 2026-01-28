# Section
Packaging, Local Deployment, and Documentation

## Summary
Provide an actionable, developer-friendly packaging and local-deployment plan plus the minimal documentation required for running the app locally and for simple end-user backups/exports. The immediate goal (MVP) is a reproducible developer flow (npm install && npm run dev) and a production web build that runs locally; a desktop-packaged app (Electron or similar) is optional and only pursued if already chosen. Deliverables include scripts, environment defaults, a README, and a short user guide.

## Design
- Development mode: standard Node + frontend dev server. Developers use:
  - npm install
  - npm run dev (starts frontend dev server and backend in dev mode, with hot reload if configured)
- Production local server mode:
  - npm run build (creates optimized frontend bundles)
  - npm run start (serves backend and static assets; single-node local server)
- Data persistence:
  - Single-file embedded DB (SQLite) for local deployments.
  - DB path configurable via environment variable DB_PATH (falls back to OS-appropriate default path).
  - Optional lightweight HTTP endpoint or CLI script to export data as CSV categorized by user-defined categories.
- Configuration:
  - .env.example with defaults for DB_PATH, PORT, NODE_ENV, LOG_LEVEL
  - CLI scripts for import/export/backup
- Packaging (optional, out-of-MVP unless chosen):
  - Use electron + electron-builder (or equivalent) to produce platform-specific installers. If chosen, packaging scripts are added (npm run package:desktop).
- Security & Permissions:
  - Ensure the DB file is created with file permissions restricted to the running user.
  - No auto-sync with external services in MVP; avoid storing credentials.

## Implementation Steps
1. Repository hygiene (1 day)
   - Add .env.example with variables:
     - DB_PATH=
     - PORT=3000
     - NODE_ENV=development
     - LOG_LEVEL=info
   - Add README skeleton (prereqs, run, import CSV, known limitations)
   - Add .gitignore entries for local DB and environment files (e.g., data/*.db, .env)
2. Data path behavior (0.5 day)
   - Implement config loader that resolves DB_PATH:
     - If process.env.DB_PATH is set → use it.
     - Else pick OS-default:
       - Windows: %APPDATA%/app-name/data.db
       - macOS: ~/Library/Application Support/app-name/data.db
       - Linux: ~/.local/share/app-name/data.db
     - Fall back to ./data/data.db if none resolvable.
   - Ensure the app creates directories as needed and sets restrictive file permissions (600).
3. Developer run script (0.5 day)
   - npm scripts:
     - "dev": concurrently start backend (nodemon) and frontend dev server
     - "build": build frontend
     - "start": start backend in production mode and serve built frontend
   - Document commands in README
4. Import/export/backup scripts (1 day)
   - create scripts/ directory with:
     - scripts/importCsv.js: accepts path to CSV, validates columns, inserts/updates DB records
     - scripts/exportCsv.js: exports full dataset or categorized CSV (accepts --category and --out flags)
     - scripts/backupDb.sh (POSIX) and backupDb.ps1 (Windows) that copy DB to timestamped file (and compress)
   - Add npm scripts:
     - "import:csv": node scripts/importCsv.js <file>
     - "export:csv": node scripts/exportCsv.js --out=<file> [--category=<name>]
     - "backup:db": ./scripts/backupDb.sh or powershell script on Windows
5. Production local server run (0.5 day)
   - Document recommended production local startup:
     - Build: npm run build
     - Start: DB_PATH=/path/to/data.db npm run start
     - Optionally run behind a simple process manager like PM2 (document example commands)
6. Optional: desktop packaging (2–4 days, out-of-MVP)
   - Add electron main process that serves built app and starts/communicates with backend, or bundle backend into the Electron process.
   - Add electron-builder configuration (package.json > build) and npm script:
     - "package:desktop": electron-builder --mac --win --linux (platform flags as needed)
   - Document limitations and platform testing requirements.
7. Tests & CI (1 day)
   - Add basic unit tests for config resolver (DB_PATH resolution), CSV importer validations, and export output format.
   - Add a CI job that runs npm install && npm run build && npm test to catch regressions.
8. Documentation completion (0.5–1 day)
   - Finalize README and a Basic User Guide markdown that includes:
     - Installation prerequisites
     - Developer run steps
     - Production local run steps
     - Import CSV sample and command
     - Backup instructions
     - Known limitations (single-user, no bank sync)
9. Verification and handover (0.5 day)
   - Acceptance checklist run: dev server, build+start, DB creation at default path, backup works, CSV import/export works, README covers all items.

Implementation notes (commands and examples):
- Install and dev:
  - npm ci
  - npm run dev
- Build and start production locally:
  - npm run build
  - DB_PATH=~/.local/share/app-name/data.db npm run start
- Import CSV:
  - npm run import:csv -- path/to/file.csv
- Export CSV:
  - npm run export:csv -- --out=out.csv --category=groceries
- Backup DB (POSIX example):
  - mkdir -p backups && cp "$DB_PATH" backups/data-$(date +%Y%m%dT%H%M%S).db && gzip backups/*.db

## Risks
- DB Corruption / File Locking
  - Risk: concurrent access, improper shutdown may corrupt DB.
  - Mitigation: use SQLite with a robust Node binding (better-sqlite3 recommended), ensure single writer pattern, commit transactions, provide clear backup instructions and periodic exports.
- Platform-specific path/permission issues
  - Risk: incorrect default DB locations, permissions preventing creation.
  - Mitigation: implement OS-aware path resolution, create directories with correct permissions, document manual DB_PATH override.
- Data loss via user error
  - Risk: users may delete DB or overwrite with import.
  - Mitigation: provide automated timestamped backups, warn on destructive imports (require --force flag), recommend exporting CSV before import.
- Security exposure if run on network
  - Risk: local server could be bound to 0.0.0.0 and exposed.
  - Mitigation: default to 127.0.0.1 binding, document how to change binding intentionally; log warnings if binding to 0.0.0.0.
- Desktop packaging complexity (scope creep)
  - Risk: packaging introduces platform-specific bugs and increases maintenance.
  - Mitigation: keep packaging optional, only proceed if product decision made; initially focus on web build and local server.
- Large CSV imports or heavy data
  - Risk: memory or performance issues on import.
  - Mitigation: implement streaming CSV parser, batch DB inserts, and validate sample sizes.

## Dependencies
- Runtime & build tools:
  - Node.js LTS (>=16 recommended)
  - npm (or yarn)
  - Git
- Database:
  - SQLite (no external service; Node binding such as better-sqlite3 or sqlite3)
- Optional packaging:
  - electron, electron-builder (if producing desktop binaries)
- Utilities:
  - concurrently (for dev), nodemon (backend dev hot reload), csv-parse / Papaparse (for CSV import/export), archiver or gzip (for backups)
- Process manager (optional for local production):
  - pm2 or systemd unit example documented
- CI:
  - GitHub Actions / GitLab CI runner to run build/test pipelines
- Platform considerations:
  - Windows PowerShell for backup script (provide .ps1)
  - POSIX shell for Linux/macOS scripts

## Acceptance Criteria
- Developer workflow
  - Running npm ci && npm run dev starts the app in development mode (frontend + backend) without manual config.
- Production local build & start
  - npm run build produces a static frontend bundle and npm run start serves the app locally.
- Configurable DB path
  - DB location can be overridden via DB_PATH environment variable.
  - Default DB path resolves to an OS-appropriate path and the app creates it automatically.
- Backup and export
  - Backup script produces timestamped DB copy and a compressed archive.
  - Export CSV script produces well-formed CSV(s) and supports optional category filtering.
- Import
  - Import script validates CSV structure and either inserts or rejects with clear errors; destructive operations require an explicit --force flag.
- Documentation & deliverables
  - README contains prerequisites, run instructions, import CSV example, backup instructions, and known limitations (no bank sync, single-user).
  - Basic User Guide markdown is present and covers common tasks: start, backup, import/export.
- Tests & CI
  - Basic tests for config resolution and CSV import/export run in CI and pass.
- Optional packaging (if undertaken)
  - Desktop packaging script produces installers for the targeted OS and installs the app such that it uses the same DB file location logic or a per-user app data path.
- Security & defaults
  - App binds to localhost by default and DB file permission is restricted to the running user.

## Local Deployment Options
- Option A: npm install && npm run dev (developer-focused)
  - Purpose: fast iteration; intended for developers and power users.
  - Behavior:
    - Starts backend on 127.0.0.1:PORT (default 3000)
    - Starts frontend dev server with hot reload and proxy to backend
  - How to use:
    - npm ci
    - cp .env.example .env (edit if needed)
    - npm run dev
  - Notes:
    - Suitable for local testing and development.
    - DB_PATH picks up .env or environment variable.
- Option B: packaged desktop-like local app (out of MVP unless already chosen)
  - Purpose: end-user-friendly, installer-based distribution.
  - Scope: out-of-MVP unless product decision chooses desktop packaging.
  - If chosen, minimum requirements:
    - Bundle backend and frontend in Electron or similar
    - Ensure DB is stored in per-user app data folder using same DB_PATH logic
    - Provide auto-update or clear upgrade instructions
  - Recommended approach if chosen:
    - Build frontend (npm run build)
    - Package backend + frontend with electron-builder
    - Test on each target OS and document installer behavior
  - Caveats:
    - Increases maintenance and test matrix overhead (Windows/macOS/Linux), so delay unless necessary.

## Data Storage
- Primary storage: single SQLite file.
- Default DB file locations (unless DB_PATH is set):
  - Windows: %APPDATA%/app-name/data.db
  - macOS: ~/Library/Application Support/app-name/data.db
  - Linux: ~/.local/share/app-name/data.db
  - Fallback: ./data/data.db (relative to install directory)
- DB file creation and permissions:
  - The app will create parent directories if they do not exist.
  - Set file permissions to owner-read/write only (POSIX: 600). On Windows, set ACLs to current user only if possible.
- Backups:
  - Provide scripts:
    - scripts/backupDb.sh (POSIX)
    - scripts/backupDb.ps1 (Windows)
  - Backup behavior:
    - Copy DB file to backups/data-YYYYMMDDTHHMMSS.db
    - Optionally gzip the archive backups/data-YYYYMMDDT...db.gz
    - Document recommended frequency and storage location (e.g., cloud or external drive)
- Export (CSV):
  - Provide scripts/exportCsv.js to export whole dataset or category-specific CSV:
    - Example: node scripts/exportCsv.js --out=transactions.csv --category=groceries
  - CSV format:
    - Required columns: date (ISO), amount (float), currency, category, description
  - Permissions & integrity:
    - Exports are read-only operations and will not lock the DB for writes beyond SQLite normal behavior.

## Documentation
- README must include:
  - Prerequisites:
    - Node.js LTS version, npm, Git
    - Recommended: SQLite CLI for manual inspection (optional)
  - How to run:
    - Developer run: npm ci && npm run dev
    - Build & start locally: npm run build && DB_PATH=/path/to/data.db npm run start
    - Import CSV example: npm run import:csv -- ./samples/sample.csv
    - Export CSV example: npm run export:csv -- --out=out.csv --category=groceries
    - Backup example: scripts/backupDb.sh (POSIX) or scripts/backupDb.ps1 (Windows)
  - How to import CSV:
    - Expected CSV header (date,amount,currency,category,description)
    - Example command and explanation of --force flag to overwrite
    - Validation errors and how to resolve them
  - Known limitations:
    - No bank sync or remote account integration in MVP
    - Single-user local app (no multi-user support)
    - Desktop packaging is optional and not part of MVP unless chosen
  - Security tips:
    - Keep DB backups in a secure location
    - Don’t run the local server bound to 0.0.0.0 unless intentionally exposing it
- Basic user guide (markdown):
  - Short manual for non-developer end users describing:
    - Installing Node (if not using packaged app)
    - Starting/stopping the local service
    - Where data is stored and how to make backups
    - How to import/export CSV and expected formats
    - Troubleshooting common errors (DB permissions, port in use)
- Additional docs:
  - .env.example with explanations for each variable
  - Developer notes on packaging if decision changes (how-to section if packaging chosen later)

## Deliverables
- Scripts:
  - package.json npm scripts: dev, build, start, import:csv, export:csv, backup:db
  - scripts/importCsv.js, scripts/exportCsv.js
  - scripts/backupDb.sh, scripts/backupDb.ps1
  - Optional: electron packaging scripts if packaging chosen
- Configuration:
  - .env.example with commented defaults
  - Config loader module handling DB_PATH and OS defaults
- Documentation:
  - README.md (complete per Documentation section)
  - basic-user-guide.md (short user-focused manual)
- Tests & CI:
  - Basic unit tests for config and CSV parsing
  - CI configuration file (GitHub Actions or CI system) that runs install, build, test
- Handover checklist:
  - Steps to verify each Acceptance Criteria item (pass/fail)
  - Notes on where to find DB and how to perform recovery/restore from a backup file
