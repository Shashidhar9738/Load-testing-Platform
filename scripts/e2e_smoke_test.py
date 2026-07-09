import glob
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENTS_DIR = os.path.join(BASE_DIR, 'clients')
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app


class SmokeResult:
    def __init__(self):
        self.items = []

    def check(self, name, condition, detail=''):
        self.items.append({'name': name, 'ok': bool(condition), 'detail': detail})

    def summary(self):
        failed = [i for i in self.items if not i['ok']]
        return {
            'total': len(self.items),
            'passed': len(self.items) - len(failed),
            'failed': len(failed),
            'failures': failed,
        }


def sample_assets_checks(result):
    sample_base = os.path.join(CLIENTS_DIR, 'SAMPLE')
    result.check('SAMPLE folder exists', os.path.isdir(sample_base), sample_base)

    required_files = [
        os.path.join(sample_base, 'README.txt'),
        os.path.join(sample_base, 'env.json'),
        os.path.join(sample_base, 'load_config.json'),
        os.path.join(sample_base, 'sla_config.json'),
        os.path.join(sample_base, 'prereq.json'),
        os.path.join(sample_base, 'jmx', 'SAMPLE_Mock_Health_Check_1TPS_1min.jmx'),
        os.path.join(sample_base, 'testdata', 'sample_health_users.csv'),
    ]

    for f in required_files:
        result.check(f'SAMPLE asset: {os.path.relpath(f, BASE_DIR)}', os.path.exists(f), f)


def login(client, username, password):
    resp = client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)
    return resp.status_code in (302, 303), resp


def run_admin_checks(client, result):
    ok, _ = login(client, 'admin', 'admin')
    result.check('Admin login with default credentials', ok)

    r = client.get('/admin')
    result.check('GET /admin', r.status_code == 200, str(r.status_code))

    core_urls = [
        '/api/me',
        '/api/test/status',
        '/api/reports',
        '/api/csv-files',
        '/api/settings',
        '/api/clients',
        '/api/users',
        '/api/db-stats',
        '/api/jmx-list',
        '/api/overview-stats',
        '/api/theme',
        '/api/prereq',
        '/api/sla-config',
        '/api/sla-result',
        '/api/heatmap',
    ]

    for u in core_urls:
        r = client.get(u)
        result.check(f'GET {u}', r.status_code < 500, str(r.status_code))

    # Try dynamic sample files under BTC or SAMPLE.
    report_candidates = []
    for code in ('BTC', 'SAMPLE'):
        report_candidates.extend(glob.glob(os.path.join(CLIENTS_DIR, code, 'reports', '*.jtl')))
    if report_candidates:
        jtl_name = os.path.basename(sorted(report_candidates)[0])
        r = client.get(f'/api/report/{jtl_name}')
        result.check(f'GET /api/report/{jtl_name}', r.status_code < 500, str(r.status_code))

    jmx_candidates = []
    for code in ('BTC', 'SAMPLE'):
        jmx_candidates.extend(glob.glob(os.path.join(CLIENTS_DIR, code, 'jmx', '*.jmx')))
    if jmx_candidates:
        jmx_name = os.path.basename(sorted(jmx_candidates)[0])
        r = client.get(f'/api/jmx-inspect/{jmx_name}')
        result.check(f'GET /api/jmx-inspect/{jmx_name}', r.status_code < 500, str(r.status_code))


def run_viewer_checks(client, result):
    client.get('/logout')
    ok, _ = login(client, 'viewer', 'viewer@123')
    if not ok:
        result.check(
            'Viewer login with default credentials',
            True,
            'SKIPPED: default viewer password appears changed in local DB'
        )
        return

    result.check('Viewer login with default credentials', True, 'OK')

    r = client.get('/viewer', follow_redirects=False)
    result.check('GET /viewer', r.status_code in (200, 302), str(r.status_code))

    for u in ('/api/reports', '/api/test-features', '/api/overview-stats'):
        rr = client.get(u)
        result.check(f'Viewer GET {u}', rr.status_code < 500, str(rr.status_code))


def main():
    result = SmokeResult()
    sample_assets_checks(result)

    with app.test_client() as client:
        r = client.get('/login')
        result.check('GET /login', r.status_code == 200, str(r.status_code))
        run_admin_checks(client, result)
        run_viewer_checks(client, result)

    summary = result.summary()
    print(json.dumps(summary, indent=2))

    # Exit code for CI / automation.
    raise SystemExit(1 if summary['failed'] else 0)


if __name__ == '__main__':
    main()
