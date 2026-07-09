# CI/CD API Quick Start Guide

## Overview

The Load Testing Platform exposes REST API endpoints that allow Jenkins (or any external tool) to:
1. **Create test suites** (define which JMX files to run + schedule)
2. **Trigger execution** (manually start a test)
3. **Monitor progress** (poll for status & results)
4. **Archive artifacts** (download reports)

---

## Authentication

**Current:** No authentication (TODO: add Bearer token support)

**Planned:** Bearer token via `Authorization: Bearer <API_TOKEN>` header

```bash
# For now, just call the endpoints directly
# Future: add token validation
```

---

## API Examples (using curl)

### 1. Create a CI/CD Test Suite

**Endpoint:** `POST /api/ci-cd/suites`

```bash
curl -X POST "http://localhost:5000/api/ci-cd/suites" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Nightly Regression Suite",
    "description": "Full product regression test",
    "jmx_files": [
      "BTC_USSD_LoadTesting_5TPS_5min.jmx",
      "BTC_Upload_LoadTesting.jmx"
    ],
    "feature_file": "smoke_tests.feature",
    "schedule": "daily",
    "retry_count": 2,
    "notify_on_fail": "ops@company.com"
  }'
```

**Response:**
```json
{
  "ok": true,
  "suite_id": "BTC_suite_a1b2c3d4",
  "message": "Suite 'Nightly Regression Suite' created successfully"
}
```

---

### 2. List All CI/CD Suites

**Endpoint:** `GET /api/ci-cd/suites`

```bash
curl -X GET "http://localhost:5000/api/ci-cd/suites" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "suites": [
    {
      "id": "BTC_suite_a1b2c3d4",
      "client": "BTC",
      "name": "Nightly Regression Suite",
      "description": "Full product regression test",
      "jmx_files": "[\"BTC_USSD_LoadTesting_5TPS_5min.jmx\", \"BTC_Upload_LoadTesting.jmx\"]",
      "feature_file": "smoke_tests.feature",
      "schedule": "daily",
      "enabled": 1,
      "retry_count": 2,
      "notify_on_fail": "ops@company.com",
      "created_by": "admin",
      "created_at": "2026-06-30 15:20:00",
      "last_run": "2026-06-30 15:45:30"
    }
  ]
}
```

---

### 3. Trigger Suite Execution (from Jenkins)

**Endpoint:** `POST /api/ci-cd/suites/<suite_id>/run`

```bash
SUITE_ID="BTC_suite_a1b2c3d4"

curl -X POST "http://localhost:5000/api/ci-cd/suites/${SUITE_ID}/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Response:**
```json
{
  "ok": true,
  "run_id": "run_a1b2c3d4e5f6g7h8",
  "suite_name": "Nightly Regression Suite",
  "status": "started"
}
```

---

### 4. Check Execution Status

**Endpoint:** `GET /api/ci-cd/runs/<run_id>`

```bash
RUN_ID="run_a1b2c3d4e5f6g7h8"

curl -X GET "http://localhost:5000/api/ci-cd/runs/${RUN_ID}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Response (while running):**
```json
{
  "run": {
    "id": "run_a1b2c3d4e5f6g7h8",
    "suite_id": "BTC_suite_a1b2c3d4",
    "client": "BTC",
    "status": "running",
    "start_time": "2026-06-30T15:20:00.000Z",
    "end_time": null,
    "duration_s": null,
    "total_requests": 12450,
    "success_count": 12400,
    "error_count": 50,
    "avg_rt_ms": 145.2,
    "p95_rt_ms": 520.5,
    "report_path": "/download/report/run_a1b2c3d4e5f6g7h8.html",
    "triggered_by": "jenkins"
  }
}
```

**Response (completed):**
```json
{
  "run": {
    "id": "run_a1b2c3d4e5f6g7h8",
    "suite_id": "BTC_suite_a1b2c3d4",
    "client": "BTC",
    "status": "completed",
    "start_time": "2026-06-30T15:20:00.000Z",
    "end_time": "2026-06-30T15:45:30.000Z",
    "duration_s": 1530,
    "total_requests": 45000,
    "success_count": 44850,
    "error_count": 150,
    "avg_rt_ms": 125.5,
    "p95_rt_ms": 450.2,
    "report_path": "/download/report/run_a1b2c3d4e5f6g7h8.html",
    "triggered_by": "jenkins"
  }
}
```

---

## Bash Script Example: Jenkins Job

```bash
#!/bin/bash

# Load Testing Platform CI/CD Integration Script
# Usage: ./run_load_test.sh <SUITE_ID>

set -e

SUITE_ID="${1:-BTC_suite_a1b2c3d4}"
PLATFORM_URL="http://localhost:5000"
API_TOKEN="${PLATFORM_API_TOKEN}"  # Set in Jenkins
TIMEOUT_SECS=3600
POLL_INTERVAL=30

echo "🚀 Starting load test: $SUITE_ID"

# 1. Trigger execution
echo "Triggering suite execution..."
RESPONSE=$(curl -s -X POST "${PLATFORM_URL}/api/ci-cd/suites/${SUITE_ID}/run" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json")

RUN_ID=$(echo $RESPONSE | jq -r '.run_id')
echo "✅ Test started: $RUN_ID"

# 2. Monitor execution
echo "Monitoring execution..."
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT_SECS ]; do
    STATUS_RESPONSE=$(curl -s "${PLATFORM_URL}/api/ci-cd/runs/${RUN_ID}" \
      -H "Authorization: Bearer ${API_TOKEN}")
    
    STATUS=$(echo $STATUS_RESPONSE | jq -r '.run.status')
    ERRORS=$(echo $STATUS_RESPONSE | jq -r '.run.error_count // "—"')
    REQUESTS=$(echo $STATUS_RESPONSE | jq -r '.run.total_requests // "—"')
    AVG_RT=$(echo $STATUS_RESPONSE | jq -r '.run.avg_rt_ms // "—"')
    
    printf "[%2d:%02d] Status: %-12s | Requests: %6s | Errors: %4s | Avg RT: %7s ms\n" \
        $((ELAPSED / 60)) $((ELAPSED % 60)) "$STATUS" "$REQUESTS" "$ERRORS" "$AVG_RT"
    
    if [ "$STATUS" = "completed" ]; then
        echo "✅ Test completed"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "❌ Test failed"
        exit 1
    fi
    
    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

if [ $ELAPSED -ge $TIMEOUT_SECS ]; then
    echo "❌ Test timed out"
    exit 1
fi

# 3. Get final results
FINAL_RESPONSE=$(curl -s "${PLATFORM_URL}/api/ci-cd/runs/${RUN_ID}" \
  -H "Authorization: Bearer ${API_TOKEN}")

DURATION=$(echo $FINAL_RESPONSE | jq -r '.run.duration_s')
ERRORS=$(echo $FINAL_RESPONSE | jq -r '.run.error_count')
SUCCESS=$(echo $FINAL_RESPONSE | jq -r '.run.success_count')
AVG_RT=$(echo $FINAL_RESPONSE | jq -r '.run.avg_rt_ms')
P95_RT=$(echo $FINAL_RESPONSE | jq -r '.run.p95_rt_ms')
REPORT=$(echo $FINAL_RESPONSE | jq -r '.run.report_path')

echo ""
echo "═══════════════════════════════════════════"
echo "  RESULTS"
echo "═══════════════════════════════════════════"
echo "Duration:       $DURATION seconds"
echo "Successful:     $SUCCESS"
echo "Errors:         $ERRORS"
echo "Avg RT:         $AVG_RT ms"
echo "P95 RT:         $P95_RT ms"
echo "Report:         ${PLATFORM_URL}${REPORT}"
echo "═══════════════════════════════════════════"

# 4. Quality gates
ERROR_PCT=$((ERRORS * 100 / (SUCCESS + ERRORS)))
if [ $ERROR_PCT -gt 5 ]; then
    echo "❌ Error rate ${ERROR_PCT}% exceeds 5% threshold"
    exit 1
fi

if [ $(echo "$AVG_RT > 500" | bc) -eq 1 ]; then
    echo "⚠️  Avg response time ${AVG_RT}ms exceeds 500ms"
fi

echo "✅ All checks passed"
```

---

## Database Schema: CI/CD Tables

### ci_cd_suites

```sql
CREATE TABLE ci_cd_suites (
    id              TEXT PRIMARY KEY,
    client          TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    jmx_files       TEXT NOT NULL,        -- JSON array: ["file1.jmx", "file2.jmx"]
    feature_file    TEXT,                 -- Optional BDD test file
    schedule        TEXT NOT NULL,        -- daily|hourly|weekly
    enabled         INTEGER DEFAULT 1,
    notify_on_fail  TEXT DEFAULT '',      -- Email or webhook URL
    retry_count     INTEGER DEFAULT 0,    -- 0-3
    created_by      TEXT DEFAULT 'system',
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    last_run        TEXT,
    UNIQUE(client, name)
);
```

**Sample Data:**
```sql
INSERT INTO ci_cd_suites VALUES (
    'BTC_suite_a1b2c3d4',
    'BTC',
    'Nightly Regression Suite',
    'Full product regression test',
    '["BTC_USSD_LoadTesting_5TPS_5min.jmx", "BTC_Upload_LoadTesting.jmx"]',
    'smoke_tests.feature',
    'daily',
    1,
    'ops@company.com',
    2,
    'admin',
    '2026-06-30 14:00:00',
    '2026-06-30 15:45:30'
);
```

---

### ci_cd_run_history

```sql
CREATE TABLE ci_cd_run_history (
    id              TEXT PRIMARY KEY,
    suite_id        TEXT NOT NULL,
    client          TEXT NOT NULL,
    status          TEXT DEFAULT 'running',  -- running|completed|failed
    start_time      TEXT NOT NULL,
    end_time        TEXT,
    duration_s      INTEGER,
    total_requests  INTEGER DEFAULT 0,
    success_count   INTEGER DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    avg_rt_ms       REAL DEFAULT 0,
    p95_rt_ms       REAL DEFAULT 0,
    report_path     TEXT,
    triggered_by    TEXT DEFAULT 'scheduler',  -- scheduler|manual|jenkins
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (suite_id) REFERENCES ci_cd_suites(id)
);

CREATE INDEX idx_cicd_suite ON ci_cd_run_history(suite_id);
```

**Sample Data:**
```sql
INSERT INTO ci_cd_run_history VALUES (
    'run_a1b2c3d4e5f6g7h8',
    'BTC_suite_a1b2c3d4',
    'BTC',
    'completed',
    '2026-06-30T15:20:00.000Z',
    '2026-06-30T15:45:30.000Z',
    1530,
    45000,
    44850,
    150,
    125.5,
    450.2,
    '/download/report/run_a1b2c3d4e5f6g7h8.html',
    'jenkins',
    '2026-06-30 15:20:00'
);
```

---

## Testing the API Locally

```bash
# 1. Create a suite
curl -X POST "http://localhost:5000/api/ci-cd/suites" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Suite",
    "jmx_files": ["test.jmx"],
    "schedule": "daily"
  }'

# Copy the suite_id from response

# 2. List suites
curl "http://localhost:5000/api/ci-cd/suites"

# 3. Trigger execution
curl -X POST "http://localhost:5000/api/ci-cd/suites/<suite_id>/run"

# Copy the run_id from response

# 4. Check status (repeat)
curl "http://localhost:5000/api/ci-cd/runs/<run_id>"
```

---

## Jenkins Configuration Checklist

- [ ] Install Jenkins plugins: `Pipeline`, `Slack Notification`, `Log Parser`
- [ ] Store platform URL in Jenkins Credentials: `platform-url`
- [ ] Store API token in Jenkins Credentials: `platform-api-token`
- [ ] Configure Slack webhook (optional): `SLACK_WEBHOOK_URL`
- [ ] Create Jenkins job/pipeline with the provided Jenkinsfile
- [ ] Set build trigger: `H 2 * * *` (daily at 2 AM)
- [ ] Configure post-build actions: archive reports, send notifications
- [ ] Test with manual run

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 404 Not Found | Suite ID doesn't exist. Check `/api/ci-cd/suites` |
| 500 Error | Check platform logs: `python app.py` output |
| Timeout | Increase `TIMEOUT_MINUTES` parameter in Jenkins |
| No results | Wait longer or check if test is actually running |
| Auth fails | Set `PLATFORM_API_TOKEN` env var in Jenkins |

---

## Next Steps

1. **Test locally** with curl commands
2. **Create Jenkins job** using provided Jenkinsfile
3. **Schedule daily runs** via Jenkins cron trigger
4. **Monitor dashboard** on platform UI
5. **Add notifications** (Slack/email)
6. **Integrate with pipeline** (deploy on pass, block on fail)
