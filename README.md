# Load Testing Platform

Centralized performance testing repository for managing JMeter load tests across multiple clients.

## Requirements

- Python 3.9+
- Apache JMeter 5.5 — install at `C:\apache-jmeter-5.5\`
- Windows 10/11

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Start the server (double-click or run from terminal)
start_server.bat

# 3. Open browser
http://localhost:5000
```

Default credentials:

| Username   | Password    | Role   |
|------------|-------------|--------|
| gauravjain | 0987654321  | Admin  |
| viewer     | viewer@123  | Viewer |

> Change these immediately after first login via **Users** tab.

### Credential Management

If a user (including `viewer`) cannot log in because the password was changed from the default:

1. Log in as **admin** (`gauravjain` or any admin account).
2. Go to the **Users** tab.
3. Click the edit icon next to the user.
4. Enter and confirm a new password, then save.
5. Share the updated password with the user through a secure channel.

If the admin password is also unknown, reset it directly in the database.
**The app uses Werkzeug's password hashing — do not use plain `hashlib.sha256`**, or the login will fail.

```bash
python -c "
from werkzeug.security import generate_password_hash
import sqlite3, getpass
pw = getpass.getpass('New admin password: ')
h  = generate_password_hash(pw)
db = sqlite3.connect('lt_platform.db')
db.execute(\"UPDATE users SET password=? WHERE username='gauravjain'\", (h,))
db.commit(); db.close()
print('Password updated.')
"
```

Run this from the project root while the server is stopped.

## Project Structure

```
load-testing-platform/
├── app.py                  # Flask application (main entry point)
├── requirements.txt        # Python dependencies
├── start_server.bat        # Windows startup script
├── templates/              # HTML templates
│   ├── login.html
│   ├── admin.html          # Main admin portal (9 tabs)
│   └── viewer.html         # Read-only viewer portal
├── static/                 # Static assets
└── clients/                # One folder per client (auto-created)
    └── <CLIENT_CODE>/
        ├── jmx/            # JMeter test plans (.jmx)
        ├── testdata/       # CSV data files for tests
        └── reports/        # JTL results + HTML reports (auto-generated)
```

Generated on first run (not committed):
- `lt_platform.db` — SQLite database (users, clients, audit log)
- `.ltconfig.json` — JMeter path and heap settings

## Adding a New Client

1. Log in as admin → go to **Clients** tab
2. Click **New Client**
3. Fill in client code (e.g. `MTN`), name, and optional custom directory paths
4. Upload JMX files into `clients/<CODE>/jmx/`
5. Upload test data CSVs into `clients/<CODE>/testdata/`

## End-to-End Testing

This repository includes a complete local sample client fixture and a smoke test suite.

### 1) Ensure sample client fixture exists

```bash
python scripts/sample_client_setup.py
```

This script is idempotent. It ensures:
- `clients/SAMPLE/` folder structure
- Mock environment and load/SLA config files
- Sample JMX and CSV test data
- `SAMPLE` row in the `clients` database table

### 2) Run full smoke checks

```bash
python scripts/e2e_smoke_test.py
```

The smoke suite validates:
- Login pages and role-based portal access
- Core admin/viewer API routes
- Report/JMX parsing routes
- Presence of all sample client assets

If `viewer` default password was changed in your local DB, viewer-default-login is auto-skipped as non-fatal.

### One-click Windows runner

You can execute the smoke tests from the `scripts/` directory:

```bat
cd scripts
python comprehensive_e2e_test.py
```

Results are printed to the console. For a timestamped log redirect output:

```bat
python scripts\comprehensive_e2e_test.py > test_reports\smoke_%date:~-4,4%%date:~-7,2%%date:~-10,2%.log 2>&1
```

## Features

- **Multi-client** — each client has isolated JMX, test data, and reports
- **Run Tests** — start/stop JMeter with per-service thread configuration
- **Reports** — parse JTL results with TPS, percentile, and error charts
- **Run History & Trends** — compare multiple runs side by side
- **Downloads** — HTML report, raw JTL, ZIP bundle, full backup
- **User Management** — role-based access (admin / viewer), SQLite-backed
- **Audit Log** — every action logged with user, timestamp, IP
- **DB Maintenance** — vacuum, purge, backup, export audit CSV

## JMeter Path

If JMeter is installed at a non-default location, update it in **Settings** tab or edit `.ltconfig.json`:

```json
{
  "jmeter_bin": "C:\\apache-jmeter-5.5\\bin\\jmeter.bat",
  "heap": "-Xms512m -Xmx1g",
  "audit_retention_days": 90
}
```
