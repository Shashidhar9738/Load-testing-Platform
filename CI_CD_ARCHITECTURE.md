# CI/CD Architecture & Jenkins Integration

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│               Load Testing Platform (Flask App)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  INTERNAL CI/CD SCHEDULER (Background Thread)               │   │
│  │  ├─ Runs every 60 seconds                                   │   │
│  │  ├─ Checks ci_cd_suites table for due schedules            │   │
│  │  ├─ Triggers suites: daily @ 02:00, weekly @ Monday 02:00  │   │
│  │  ├─ Executes JMX files asynchronously                      │   │
│  │  ├─ Records results in ci_cd_run_history                   │   │
│  │  └─ Sends notifications (email/webhook on failure)         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  REST API ENDPOINTS (For Jenkins / External Tools)          │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  GET  /api/ci-cd/suites                                     │   │
│  │       └─ List all test suites for active client             │   │
│  │                                                              │   │
│  │  POST /api/ci-cd/suites                                     │   │
│  │       └─ Create new test suite (payload: JMX files, etc)    │   │
│  │                                                              │   │
│  │  POST /api/ci-cd/suites/<suite_id>/run                      │   │
│  │       └─ Manually trigger suite execution                   │   │
│  │       └─ Returns: run_id, status                            │   │
│  │                                                              │   │
│  │  GET  /api/ci-cd/runs/<run_id>                              │   │
│  │       └─ Get execution status & results                     │   │
│  │       └─ Returns: status, duration, metrics, artifacts     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  DATABASE TABLES                                             │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  ci_cd_suites                                               │   │
│  │  ├─ id, client, name, jmx_files (JSON)                      │   │
│  │  ├─ feature_file, schedule, retry_count                    │   │
│  │  ├─ enabled, created_by, last_run                          │   │
│  │  └─ notify_on_fail (email/webhook)                         │   │
│  │                                                              │   │
│  │  ci_cd_run_history                                          │   │
│  │  ├─ id, suite_id, client                                    │   │
│  │  ├─ status (running/completed/failed)                      │   │
│  │  ├─ start_time, end_time, duration_s                       │   │
│  │  ├─ success_count, error_count, total_requests             │   │
│  │  ├─ avg_rt_ms, p95_rt_ms, report_path                      │   │
│  │  └─ triggered_by (scheduler|manual|jenkins)                │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Option 1: Internal Scheduler Only (Current)

**How it works:**
1. Platform starts → `_ci_cd_scheduler()` thread begins
2. Every 60 seconds: checks `ci_cd_suites` for due schedules
3. If suite due → creates `ci_cd_run_history` record
4. Executes JMeter asynchronously
5. Updates run status & metrics when complete
6. No external dependencies

**Pros:**
- ✅ Self-contained, no Jenkins needed
- ✅ Simple to deploy
- ✅ Built-in monitoring dashboard

**Cons:**
- ⚠️ Limited to simple schedules (daily/hourly/weekly)
- ⚠️ No email notifications yet
- ⚠️ Executes on same machine as app

---

## Option 2: Jenkins Integration (External Orchestration)

**How it works:**
```
Jenkins Job (scheduled)
    ↓
Call: POST /api/ci-cd/suites/<suite_id>/run
    ↓ (with auth token)
    ↓
Platform receives request
    ↓
Creates ci_cd_run_history record
    ↓
Executes suite asynchronously
    ↓
Jenkins polls: GET /api/ci-cd/runs/<run_id>
    ↓
Gets status, metrics, artifacts
    ↓
Post-build actions (email, Slack, etc)
```

**Pros:**
- ✅ Flexible scheduling (cron, manual trigger, pipeline)
- ✅ Email/Slack notifications via Jenkins
- ✅ Centralized CI/CD orchestration
- ✅ Can distribute across multiple load test platforms

**Cons:**
- ⚠️ Requires Jenkins server
- ⚠️ Firewall rules needed (Jenkins → Platform)
- ⚠️ Extra toolchain to maintain

---

## API Endpoints for Jenkins/External Tools

### 1. Get CSRF Token (if needed)
```http
GET /api/csrf
Headers:
  Cookie: session=<session_id>

Response:
{
  "csrf_token": "a1b2c3d4e5f6g7h8..."
}
```

### 2. Create Test Suite
```http
POST /api/ci-cd/suites
Content-Type: application/json
Headers:
  Authorization: Bearer <API_TOKEN>  # Future: API key auth
  X-CSRF-Token: <csrf_token>

Request Body:
{
  "name": "Nightly Load Test",
  "description": "Full regression suite",
  "jmx_files": [
    "BTC_USSD_LoadTesting_5TPS_5min.jmx",
    "BTC_Upload_LoadTesting.jmx"
  ],
  "feature_file": "smoke_tests.feature",
  "schedule": "daily",           # daily|hourly|weekly
  "retry_count": 2,
  "notify_on_fail": "ops@company.com"
}

Response:
{
  "ok": true,
  "suite_id": "BTC_suite_a1b2c3d4",
  "message": "Suite 'Nightly Load Test' created successfully"
}
```

### 3. Trigger Suite Execution (Manual or from Jenkins)
```http
POST /api/ci-cd/suites/<suite_id>/run
Headers:
  Authorization: Bearer <API_TOKEN>
  X-CSRF-Token: <csrf_token>

Response:
{
  "ok": true,
  "run_id": "run_a1b2c3d4e5f6g7h8",
  "suite_name": "Nightly Load Test",
  "status": "started"
}
```

### 4. Get Execution Status & Results
```http
GET /api/ci-cd/runs/<run_id>
Headers:
  Authorization: Bearer <API_TOKEN>

Response:
{
  "run": {
    "id": "run_a1b2c3d4e5f6g7h8",
    "suite_id": "BTC_suite_a1b2c3d4",
    "client": "BTC",
    "status": "completed",          # running|completed|failed
    "start_time": "2026-06-30T15:20:00.000Z",
    "end_time": "2026-06-30T15:45:30.000Z",
    "duration_s": 1530,
    "total_requests": 45000,
    "success_count": 44850,
    "error_count": 150,
    "avg_rt_ms": 125.5,
    "p95_rt_ms": 450.2,
    "report_path": "/reports/run_a1b2c3d4e5f6g7h8.html",
    "triggered_by": "jenkins"
  }
}
```

---

## Example Jenkins Pipeline (Jenkinsfile)

```groovy
pipeline {
    agent any
    
    environment {
        PLATFORM_URL = "http://localhost:5000"
        SUITE_ID = "BTC_suite_a1b2c3d4"
        API_TOKEN = credentials('platform-api-token')  // Store in Jenkins Credentials
    }
    
    options {
        timeout(time: 2, unit: 'HOURS')
        timestamps()
    }
    
    stages {
        stage('Trigger Load Test') {
            steps {
                script {
                    echo "🚀 Triggering load test suite: ${SUITE_ID}"
                    
                    def response = sh(
                        script: '''
                            curl -X POST "${PLATFORM_URL}/api/ci-cd/suites/${SUITE_ID}/run" \
                              -H "Authorization: Bearer ${API_TOKEN}" \
                              -H "Content-Type: application/json" \
                              -s
                        ''',
                        returnStdout: true
                    ).trim()
                    
                    def json = readJSON text: response
                    env.RUN_ID = json.run_id
                    echo "✅ Test started with RUN_ID: ${env.RUN_ID}"
                }
            }
        }
        
        stage('Wait for Results') {
            steps {
                script {
                    echo "⏳ Waiting for test execution..."
                    
                    def maxAttempts = 120  // 60 minutes (30-sec polling)
                    def attempts = 0
                    def completed = false
                    
                    while (!completed && attempts < maxAttempts) {
                        sleep(30)  // Poll every 30 seconds
                        
                        def statusResponse = sh(
                            script: '''
                                curl -s "${PLATFORM_URL}/api/ci-cd/runs/${RUN_ID}" \
                                  -H "Authorization: Bearer ${API_TOKEN}"
                            ''',
                            returnStdout: true
                        ).trim()
                        
                        def statusJson = readJSON text: statusResponse
                        def status = statusJson.run.status
                        
                        echo "Status: ${status}"
                        
                        if (status == "completed" || status == "failed") {
                            completed = true
                            env.TEST_STATUS = status
                            env.TEST_DURATION = statusJson.run.duration_s
                            env.ERROR_COUNT = statusJson.run.error_count
                            env.AVG_RT = statusJson.run.avg_rt_ms
                            env.REPORT_PATH = statusJson.run.report_path
                        }
                        
                        attempts++
                    }
                    
                    if (!completed) {
                        error("❌ Test execution timed out after 60 minutes")
                    }
                }
            }
        }
        
        stage('Archive Results') {
            steps {
                script {
                    echo "📊 Test Results:"
                    echo "  Duration: ${env.TEST_DURATION} seconds"
                    echo "  Errors: ${env.ERROR_COUNT}"
                    echo "  Avg Response Time: ${env.AVG_RT} ms"
                    echo "  Report: ${env.REPORT_PATH}"
                    
                    // Download and archive report
                    sh '''
                        curl -o "load-test-report.html" \
                          "${PLATFORM_URL}${REPORT_PATH}" \
                          -H "Authorization: Bearer ${API_TOKEN}"
                    '''
                }
            }
        }
        
        stage('Quality Gate Check') {
            when {
                expression { env.ERROR_COUNT.toInteger() > 100 }
            }
            steps {
                script {
                    echo "⚠️ Quality gate FAILED: Errors > 100"
                    currentBuild.result = 'UNSTABLE'
                }
            }
        }
        
        stage('Notify') {
            steps {
                script {
                    def slackColor = env.TEST_STATUS == "completed" ? "good" : "danger"
                    slackSend(
                        color: slackColor,
                        message: """
                            Load Test: ${env.TEST_STATUS.toUpperCase()}
                            Duration: ${env.TEST_DURATION}s
                            Errors: ${env.ERROR_COUNT}
                            Avg RT: ${env.AVG_RT}ms
                        """
                    )
                }
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'load-test-report.html', 
                           allowEmptyArchive: true
            
            // Clean up
            sh 'rm -f load-test-report.html'
        }
        
        failure {
            echo "❌ Pipeline failed"
            // Send alert, create JIRA ticket, etc.
        }
    }
}
```

---

## Example Jenkins Job Configuration (via UI)

**Declarative:**
- Build trigger: `H 2 * * *` (daily at 2 AM)
- Script: Call the Jenkinsfile above
- Post-build: Archive reports, send notifications

**Freestyle (Legacy):**
1. Execute Shell:
   ```bash
   curl -X POST "http://localhost:5000/api/ci-cd/suites/BTC_suite_a1b2c3d4/run" \
     -H "Authorization: Bearer $PLATFORM_API_TOKEN" \
     > run_id.json
   ```

2. Poll: `GET /api/ci-cd/runs/<run_id>` every 30 seconds

3. Post-build: Parse results, archive artifacts

---

## Comparison: Internal vs Jenkins

| Feature | Internal Scheduler | Jenkins |
|---------|-------------------|---------|
| Setup Complexity | ⭐ Simple | ⭐⭐⭐ Complex |
| Scheduling Flexibility | ⭐⭐ Limited | ⭐⭐⭐⭐⭐ Powerful |
| Notifications | ⭐⭐ Basic | ⭐⭐⭐⭐ Rich |
| Distributed Execution | ❌ No | ✅ Yes (multi-agent) |
| Centralized Dashboard | ✅ Platform UI | ✅ Jenkins UI |
| Learning Curve | ⭐ Easy | ⭐⭐⭐ Steep |
| Operational Overhead | ⭐ Minimal | ⭐⭐⭐ Medium |

---

## Hybrid Approach (Recommended)

**Use both:**
1. **Internal Scheduler** → For simple recurring tests (daily/hourly)
2. **Jenkins** → For complex workflows, multi-platform runs, and integration with other tools

**Example:**
```
Jenkins → Calls /api/ci-cd/suites/<id>/run
       → Waits for results via /api/ci-cd/runs/<id>
       → If pass → Deploy to staging
       → If fail → Block deployment, notify team
       → Artifacts archived in Jenkins
```

---

## Security Considerations for Jenkins Integration

1. **API Authentication:**
   - Add Bearer token support to platform
   - Generate API tokens per CI/CD account
   - Store securely in Jenkins Credentials

2. **CSRF Protection:**
   - Disable CSRF for API endpoints (or use token in header)
   - Use `X-CSRF-Token` header for form endpoints

3. **Firewall:**
   - Jenkins → Platform: Allow inbound on port 5000
   - Or use VPN/SSH tunneling

4. **Audit Trail:**
   - Log all API calls in `audit_log` table
   - Track `triggered_by: "jenkins"` in run history

5. **Rate Limiting:**
   - Implement rate limiting on CI/CD endpoints
   - Prevent DoS attacks from rogue Jenkins jobs

---

## Next Steps

To add Jenkins integration to the platform:

1. ✅ **Already done:** API endpoints created
2. ❌ **TODO:** Add API token authentication
3. ❌ **TODO:** Add email notifications
4. ❌ **TODO:** Add webhook notifications (Slack, Teams)
5. ❌ **TODO:** Add retry logic with exponential backoff
6. ❌ **TODO:** Add test result parsing (JTL → JSON)

Would you like me to implement any of these?
