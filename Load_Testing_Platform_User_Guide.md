# Centralized Load Testing Platform - User Guide

Platform: Centralized Load Testing Platform (Multi-client)
Version: v4.0 (implementation-aligned)
Last Updated: 2026-06-29
Default URL: http://localhost:5000
Default Admin: gauravjain / 0987654321
Default Viewer: viewer / viewer@123

## Initial Setup

### Prerequisites

Only one thing must be manually installed before the first launch:

| Requirement | Version | Auto-installed? | Notes |
|-------------|---------|-----------------|-------|
| Python | 3.8+ | No | Must be on your PATH. `START.bat` checks for it and exits with an error if missing. |
| Java (OpenJDK 11) | 11+ | **Yes** | Downloaded automatically at first launch if not already present. |
| Apache JMeter | 5.6.3 | **Yes** | Downloaded automatically at first launch if not already present. |

Install Python from https://www.python.org/downloads/ — everything else is handled for you.

### What Happens at First Launch

1. `START.bat` (or `start_server.bat`) installs all Python dependencies from `requirements.txt`.
2. `app.py` starts and runs `_startup_auto_configure()` before accepting any requests.

**Step A — Java auto-install**

The startup routine checks for Java in this order:
- Path saved in `settings.json` (from a previous install)
- `JAVA_HOME` environment variable
- System `PATH`
- Project-local `jdk-*\` folders (created by a previous auto-install)
- Common system locations (`C:\Program Files\Java`, `C:\Program Files\Eclipse Adoptium`, `/usr/bin/java`, etc.)

If Java is not found, it **automatically downloads OpenJDK 11 (~185 MB)** from Adoptium (Eclipse Temurin) for your OS and architecture:
- Windows x64: ZIP archive
- Linux x64 / ARM64: tar.gz archive
- macOS x64 / ARM64: tar.gz archive

The JDK is extracted into the project folder as `jdk-11.x.x\`, `JAVA_HOME` is set for the running process, and the home path is saved to `settings.json`.

**Step B — JMeter auto-install** (runs after Java is ready)

The startup routine checks for JMeter in this order:
- Path saved in `settings.json`
- `apache-jmeter-5.6.3\bin\` inside the project folder
- System `PATH`
- Common system locations (`C:\apache-jmeter-*`, `/opt/jmeter`, etc.)

If JMeter is not found, it **automatically downloads JMeter 5.6.3 (~80 MB)** from:  
`https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.zip`

The ZIP is extracted into the project folder as `apache-jmeter-5.6.3\` — no admin/root rights required. The binary path is saved to `settings.json`.

**Both downloads only run once.** On all subsequent starts both tools are detected instantly and no download occurs. Both installs are recorded in the audit log (`JAVA_INSTALLED`, `JMETER_INSTALLED`).

### If an Auto-Download Fails

If either download fails (e.g. no internet access or a proxy block), the server still starts but test runs will not work. To retry or install manually:

| Tool | Retry via UI | Manual alternative |
|------|-------------|-------------------|
| Java | **Admin → Settings → Auto-Install Java** | Install Java 11+ and set `JAVA_HOME`, or add `java` to your PATH |
| JMeter | **Admin → Settings → Auto-Install JMeter** | Install JMeter and set the binary path in Settings |

You can check the current status of both tools at any time via **Admin → Pre-Requisites**.

### Verifying the Setup

After the first launch, confirm everything is ready:

1. Open http://localhost:5000 and sign in.
2. Go to **Admin → Pre-Requisites** — Java and JMeter should both show as detected.
3. Run a quick smoke test via **Admin → Run Test** to confirm end-to-end execution works.

---

## Quick Start (First 10 Minutes)

Use this section if you are new to the platform.

1. Start the application
- Run: `python app.py` (or use `start_server.bat`)
- Open: http://localhost:5000

2. Sign in
- For full setup and management, use the Admin account.
- For read-focused usage, use a Viewer account.

3. Select your active client
- Use the client selector in the header.
- All files, runs, and analytics are scoped to the selected client.

4. Run your first smoke test
- Go to Admin -> Run Test
- Select a JMX plan
- Keep default thread/ramp-up/duration values for a quick check
- Start test and watch live metrics

5. Open and read the report
- Go to Reports
- Open the newest JTL result
- Review TPS, Avg RT, P90/P95/P99, and Error %

6. Share or export
- Export HTML/PDF/Excel as needed
- Use report sharing for stakeholder access

## Quick Start by Role

### Manager / Lead
- Use Overview, Reports, Trends, Leaderboard, Platform Stats
- Focus on SLA result, regressions, and top bottlenecks

### Performance Engineer
- Use Run Test, Test Data, Upload, JMX Inspector, Test Config
- Focus on live TPS/latency/error and transaction-level analysis

### Tester / Viewer
- Use Viewer dashboard and permission-enabled panels
- Review reports, SLA result, and heatmap

## 1. What This Platform Does

This platform centralizes JMeter-based load testing for multiple clients. It supports:
- Test execution and live monitoring
- JTL report analytics and exports (HTML/PDF/Excel/JTL/ZIP)
- Baseline management and regression checks
- CSV and JMX management
- Test-feature ingestion from Excel and JMX generation
- User/client administration and self-registration approval
- Scheduling (one-time, recurring, and suite runs)
- Audit, collaboration, sharing, webhooks, backup, and health tooling

## 2. Access and Roles

### Login Routes
- `/login` for sign-in
- `/admin` for admin dashboard
- `/viewer` for viewer dashboard

### Roles
- `admin`: full access
- `viewer`: read/write access controlled by permissions

### Viewer Permission Keys
- `run_tests`
- `upload_files`
- `manage_schedules`
- `view_audit`
- `manage_baseline`
- `download_jtl`

Note: Admin bypasses permission checks.

## 3. Admin Portal - Complete Feature List

Admin sidebar panels:
1. Overview
2. Run Test
3. Reports
4. Test Data
5. Upload
6. Test Config
7. Test Features
8. JMX Inspector
9. History
10. Clients
11. Users
12. Audit Log
13. Pre-Requisites
14. DB Maintenance
15. Schedule
16. Heatmap
17. Settings
18. Platform Stats
19. Load Profiles
20. Registrations
21. Trends
22. Leaderboard

### 3.1 Overview
- KPI summary for JMX count, report count, CSV count, status, last run, and active client
- CSV count badge on the Test Data nav item and the overview KPI card both reflect the live count of CSV files in the active client's testdata folder
- Performance trend chart
- Quick jump from test-plan cards to Run Test panel

### 3.2 Run Test and Live Monitoring
- Start/stop test runs
- Parameter override and JMX requirement analysis
- Live stats stream (TPS, response time, errors)
- Live log streaming
- Test status polling
- Run notes and annotations

### 3.3 Reports and Deep Analytics
- Report list and detail view
- Metrics: throughput, averages, percentiles, min/max, errors, code distribution
- Report-derived analytics:
  - scorecard
  - bottleneck
  - response-time histogram
  - error patterns
  - USSD funnel
  - SLA analysis
  - regression check
  - baseline comparison
  - metadata
- Export/download options:
  - HTML
  - PDF
  - Excel
  - JTL
  - report bundle ZIP
  - all reports ZIP

### 3.4 Test Data and CSV Tools
- Lists all CSV files in the active client's testdata folder; each card shows filename, row count, column headers, and a 3-row preview
- CSV preview modal
- CSV edit
- CSV row check and validation
- CSV generation (`/api/generate-csv`)
- Download individual CSV or all CSV files as a ZIP
- The nav badge and overview KPI card display the correct live count of CSV files

### 3.5 Upload and File Management
- Upload JMX test plan files (.jmx)
- Upload CSV testdata files (multiple files supported)
- Upload report files (.jtl or .html)
- Each upload section lists existing files for the active client with download (⬇) and delete (🗑) actions
- Existing JMX files: listed with file size; individual download supported
- Existing CSV files: listed with filename; individual download supported
- Existing Reports: lists both .jtl and .html report files with file size; download links resolve to the correct endpoint based on file extension
- Delete any uploaded file via the 🗑 button; the action is logged in the Upload Log
- Upload Log at the bottom records all upload and delete actions for the session

### 3.6 Test Config, Environment, and SLA
- Environment config (`/api/env`)
- Load config (`/api/load-config`)
- Import/suggest load config from Excel/JMX
- SLA config and SLA result
- Environment profiles create/list/delete/activate

### 3.7 Test Features and JMX Generation
- Detect available Excel files
- Parse test-feature workbook sheets
- Generate JMX from feature definitions
- Download feature XLSX

### 3.8 JMX Tooling
- JMX list and inspect
- JMX tree and properties
- JMX params read/write
- JMX edit and property override
- JMX requirements and service extraction

### 3.9 History and Comparison
- Run history
- Compare runs
- Compare reports
- Trend overlay and trend APIs
- SLA trend

### 3.10 Client Administration
- List clients
- Create client (with folders)
- Update client
- Delete client (protected constraints)
- Client storage view
- Active client switching

### 3.11 User Administration
- List users
- Create/update/delete users
- Reset user password
- Self password change
- Admin list lookup

### 3.12 Registration Workflow
- Public registration request endpoint
- Admin registration queue
- Approve or reject registration

### 3.13 Audit, Collaboration, Presence
- Audit log retrieval/search
- Report comments add/delete/list
- Run notes add/get
- Presence tracking (`/api/presence`)
- Favorites and theme preferences

### 3.14 Sharing
- Share live run tokenized link
- Share report tokenized link
- Public live stats/report access via token

### 3.15 Scheduling and Suite Execution
- One-time schedules CRUD
- Recurring schedules CRUD
- Suite start/status/stop
- Schedule calendar and heatmap

### 3.16 DB and Ops Maintenance
- DB stats and full stats
- Vacuum, purge, clear audit
- DB backup and audit CSV download
- Backup run/list
- Archive reports

### 3.17 Settings and Integrations
- General settings persistence
- JMeter install status/install endpoint
- Webhook config and test webhook
- Server check and health-check endpoints
- Admin restart endpoint

### 3.18 Analytics Panels
- Platform stats
- Load profiles CRUD
- Trends
- Leaderboard

## 4. Viewer Portal - Complete Feature List

Viewer always-available sidebar panels:
1. Overview
2. Reports
3. Test Config
4. SLA Results
5. Pre-Requisites
6. Heatmap
7. Metrics Guide
8. JMX Inspector

Permission-gated viewer panels:
9. Run Test (`run_tests`)
10. Upload Files (`upload_files`)
11. Schedules (`manage_schedules`)
12. Audit Log (`view_audit`)

### Viewer Capabilities
- Read-only analytics and report exploration by default
- Optional execution/upload/schedule/audit features via permissions
- Optional report action buttons based on permissions:
  - Download JTL + ZIP if `download_jtl`
  - Set baseline if `manage_baseline`
- Theme switch, presence/favorites integration, and AI chat support
- Change password support

## 5. API Feature Groups (Implementation Inventory)

Authentication/session:
- login/logout/me/session-client

Execution:
- test start/stop/status/live-stats/logs/annotations/suite endpoints

Reports and analytics:
- report detail/errors/html/pdf/excel/meta/scorecard/bottleneck/histogram/error-patterns/funnel/sla-analysis/regression

Baseline:
- baseline get/set/delete/compare

Files:
- jmx/csv/reports/xlsx list, preview/edit, upload/delete, downloads

Configuration:
- env/load-config/sla-config/theme/favourites/env-profiles/load-profiles

Scheduling:
- schedules, recurring schedules, schedule calendar, heatmap

Admin management:
- clients/users/admins/audit/db-maintenance/settings/restart

Registration and sharing:
- register-request/admin approvals/share live/report endpoints

Ops and integration:
- health/health-ui/check-server/health-check/webhook/backup/archive/jmeter install

## 6. Typical Workflows

### A. Run and Analyze a Test (Admin or permitted Viewer)
1. Select active client
2. Pick JMX and configure runtime values
3. Start test and monitor live KPIs/logs
4. Stop or let test complete
5. Open report and review percentiles/errors/SLA
6. Export HTML/PDF/Excel or share report link

### B. Onboard a New Client
1. Create client in Clients panel
2. Upload client JMX/CSV/JTL/XLSX artifacts
3. Configure environment/load/SLA values
4. Validate pre-requisites and run smoke test

### C. Controlled Viewer Access
1. Create viewer user
2. Assign only required permission keys
3. Validate viewer-only nav visibility and actions

## 7. Operational Notes

- Keep one active server instance to avoid stale behavior during validation.
- **Java (OpenJDK 11) and JMeter 5.6.3 are both automatically downloaded at first launch** — no manual installation required. Java is installed first (step 1), then JMeter (step 2), since JMeter depends on Java. On all subsequent starts both are detected instantly. If either is missing after setup, use **Admin → Settings → Auto-Install** to retry, or check status in **Admin → Pre-Requisites**.
- For production use, run behind a production WSGI server rather than Flask dev server.

## 8. Quick Endpoint Health Checks

- `GET /health`
- `GET /health/ui`
- `GET /api/check-server`
- `POST /api/health-check`

## 9. Current Scope Statement

This guide is generated from implemented routes and UI panels in:
- `app.py`
- `templates/admin.html`
- `templates/viewer.html`

It is intentionally implementation-accurate for the current codebase state.

## 10. Suggested Screenshots for This Guide

Add these screenshots to make the guide easier for non-technical readers:

1. Login screen
2. Admin dashboard overview (KPI cards)
3. Run Test panel (before start)
4. Live monitoring state (during test)
5. Report detail page (charts + percentile metrics)
6. Viewer dashboard (default panels)
7. Settings panel (JMeter/webhook area)
8. Clients and Users panels

Tip: keep image names consistent, for example: `01-login.png`, `02-admin-overview.png`, `03-run-test.png`.

## 11. Changelog

### 2026-06-29
- **Nav highlight bug fixed**: Clicking History, Clients, Users, or any panel after JMX Inspector was highlighting the wrong sidebar item. Root cause: `jmxinspector` was missing from the panel-to-index map in `showPanel()`. All nav items now highlight correctly.
- **Upload panel — Reports list fixed**: Existing reports were not appearing in the Upload panel. Two issues were resolved:
  1. The `/api/reports` backend was only scanning for `.jtl` files; it now includes `.html` files as well.
  2. The frontend was reading `f.filename` but the API returns `f.name`; corrected to `f.name`.
- **Test Data count fixed**: The CSV file count in the nav badge and Overview KPI card was always showing 0. Root cause: the admin page route was not computing or passing `csv_files` to the template. The route now correctly computes and passes the CSV file list.

## 12. Glossary (Plain English)

- JMeter: Tool used to generate load and measure performance.
- JMX: JMeter test plan file.
- JTL: JMeter result file (raw run output).
- TPS: Transactions per second (throughput).
- RT: Response time (how long a request takes).
- P90/P95/P99: Percentile latency values used to understand tail performance.
- SLA: Service level target (for example max latency or max error rate).
- Baseline: A reference run used for comparison.
- Regression: Performance getting worse compared to baseline.
- Heatmap: Visual view of run activity by time/day.
