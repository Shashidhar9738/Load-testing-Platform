import json
import os
import random
import string
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = 'http://127.0.0.1:5000'


class Runner:
    def __init__(self):
        self.checks = []

    def check(self, name, ok, detail=''):
        self.checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    def summary(self):
        failures = [c for c in self.checks if not c['ok']]
        return {
            'total': len(self.checks),
            'passed': len(self.checks) - len(failures),
            'failed': len(failures),
            'failures': failures,
        }


class Session:
    def __init__(self, base_url):
        self.base = base_url
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def request(self, method, path, data=None, headers=None):
        url = self.base + path
        body = None
        hdrs = headers.copy() if headers else {}

        if data is not None:
            if isinstance(data, (dict, list)):
                body = json.dumps(data).encode('utf-8')
                hdrs.setdefault('Content-Type', 'application/json')
            elif isinstance(data, str):
                body = data.encode('utf-8')
            else:
                body = data

        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with self.opener.open(req, timeout=20) as r:
                raw = r.read()
                text = raw.decode('utf-8', errors='replace')
                ctype = (r.headers.get('Content-Type') or '').lower()
                parsed = None
                if 'application/json' in ctype:
                    try:
                        parsed = json.loads(text)
                    except Exception:
                        parsed = None
                return {'ok': True, 'status': r.status, 'text': text, 'json': parsed, 'headers': dict(r.headers)}
        except urllib.error.HTTPError as e:
            raw = e.read()
            text = raw.decode('utf-8', errors='replace') if raw else ''
            parsed = None
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            return {'ok': False, 'status': e.code, 'text': text, 'json': parsed, 'headers': dict(e.headers)}
        except Exception as e:
            return {'ok': False, 'status': 0, 'text': str(e), 'json': None, 'headers': {}}

    def get(self, path):
        return self.request('GET', path)

    def post_form(self, path, form_dict):
        body = urllib.parse.urlencode(form_dict)
        return self.request('POST', path, body, headers={'Content-Type': 'application/x-www-form-urlencoded'})

    def post_json(self, path, obj):
        return self.request('POST', path, obj)

    def put_json(self, path, obj):
        return self.request('PUT', path, obj)

    def delete(self, path):
        return self.request('DELETE', path)



def wait_for_server(timeout_s=35):
    deadline = time.time() + timeout_s
    probe = Session(BASE_URL)
    while time.time() < deadline:
        r = probe.get('/health')
        if r['ok'] and r['status'] == 200:
            return True
        time.sleep(1)
    return False



def rand_user(prefix):
    suffix = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return f'{prefix}_{suffix}'



def run():
    os.chdir(BASE_DIR)
    rr = Runner()

    # Ensure sample fixture exists first.
    setup_cmd = [sys.executable, os.path.join('scripts', 'sample_client_setup.py')]
    setup_run = subprocess.run(setup_cmd, capture_output=True, text=True)
    rr.check('sample_client_setup.py exits 0', setup_run.returncode == 0, setup_run.stdout[-300:])

    # Start server process.
    server_cmd = [sys.executable, 'app.py']
    server = subprocess.Popen(server_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        up = wait_for_server()
        rr.check('server started and /health responds', up)
        if not up:
            summary = rr.summary()
            print(json.dumps(summary, indent=2))
            return 1

        anon = Session(BASE_URL)
        admin = Session(BASE_URL)

        # Public checks
        r = anon.get('/login')
        rr.check('GET /login', r['ok'] and r['status'] == 200, str(r['status']))

        # Admin login journey
        r = admin.post_form('/login', {'username': 'gauravjain', 'password': '0987654321'})
        rr.check('POST /login (admin)', r['status'] in (200, 302), str(r['status']))

        r = admin.get('/admin')
        rr.check('GET /admin', r['ok'] and r['status'] == 200, str(r['status']))

        # Switch client to SAMPLE
        r = admin.post_json('/api/session/client', {'code': 'SAMPLE'})
        rr.check('POST /api/session/client SAMPLE', r['ok'] and r['status'] == 200, str(r['status']))

        # Core admin API checks (representative for all major panels/buttons)
        core_paths = [
            '/api/me', '/api/overview-stats', '/api/reports', '/api/csv-files', '/api/jmx-list',
            '/api/test-features', '/api/prereq', '/api/prereq/auto', '/api/settings', '/api/clients',
            '/api/users', '/api/audit-log?limit=20', '/api/db-stats', '/api/db/full-stats',
            '/api/schedules', '/api/recurring-schedules', '/api/heatmap', '/api/platform-stats',
            '/api/load-profiles', '/api/leaderboard', '/api/trends?days=7', '/api/sla-config',
            '/api/sla-result', '/api/theme', '/api/favourites', '/api/presence', '/api/webhook-config',
            '/api/backup/list', '/api/sla-trend?limit=5'
        ]
        for p in core_paths:
            r = admin.get(p)
            rr.check(f'GET {p}', r['status'] < 500, str(r['status']))

        # Exercise registration flow end-to-end.
        reg_user = rand_user('reg')
        r = anon.post_json('/api/register-request', {
            'name': 'E2E Registration User',
            'username': reg_user,
            'email': f'{reg_user}@example.com',
            'password': 'TempPass123!'
        })
        rr.check('POST /api/register-request', r['status'] in (200, 409), str(r['status']))

        r = admin.get('/api/admin/registrations')
        rr.check('GET /api/admin/registrations', r['ok'] and r['status'] == 200, str(r['status']))

        reg_id = None
        if r['json'] and isinstance(r['json'], list):
            for item in r['json']:
                if item.get('username') == reg_user:
                    reg_id = item.get('id')
                    break
        if reg_id:
            a = admin.post_json(f'/api/admin/registrations/{reg_id}/approve', {})
            rr.check('POST /api/admin/registrations/<id>/approve', a['status'] == 200, str(a['status']))
            # Cleanup approved temp user.
            d = admin.delete(f'/api/users/{reg_user}')
            rr.check('DELETE temp approved registration user', d['status'] in (200, 404), str(d['status']))
        else:
            rr.check('registration appears in pending list', False, 'Could not find pending registration entry')

        # Create deterministic viewer user for E2E (avoids drift in default viewer password).
        e2e_viewer = rand_user('e2ev')
        viewer_pw = 'ViewerPass123!'
        perms = ['run_tests', 'view_audit', 'manage_schedules', 'download_jtl', 'manage_baseline']
        c = admin.post_json('/api/users', {
            'username': e2e_viewer,
            'password': viewer_pw,
            'name': 'E2E Viewer',
            'role': 'viewer',
            'initials': 'EV',
            'permissions': perms
        })
        rr.check('POST /api/users (create temp viewer)', c['status'] in (200, 409), str(c['status']))

        viewer = Session(BASE_URL)
        r = viewer.post_form('/login', {'username': e2e_viewer, 'password': viewer_pw})
        rr.check('POST /login (temp viewer)', r['status'] in (200, 302), str(r['status']))

        r = viewer.get('/viewer')
        rr.check('GET /viewer (temp viewer)', r['status'] in (200, 302), str(r['status']))

        viewer_paths = [
            '/api/me', '/api/overview-stats', '/api/reports', '/api/test-features', '/api/sla-config',
            '/api/sla-result', '/api/heatmap', '/api/prereq', '/api/test/status', '/api/logs?offset=0',
            '/api/schedules', '/api/audit-log?limit=20', '/api/theme', '/api/favourites', '/api/presence'
        ]
        for p in viewer_paths:
            r = viewer.get(p)
            rr.check(f'viewer GET {p}', r['status'] < 500, str(r['status']))

        # SAMPLE-specific dynamic endpoint checks.
        reports = admin.get('/api/reports')
        sample_report = None
        if reports['json'] and isinstance(reports['json'], list) and reports['json']:
            sample_report = reports['json'][0].get('name')
        rr.check('at least one report exists for active SAMPLE client', bool(sample_report), sample_report or 'none')

        if sample_report:
            dyn = [
                f'/api/report/{urllib.parse.quote(sample_report)}',
                f'/api/report/{urllib.parse.quote(sample_report)}/errors',
                f'/api/report/{urllib.parse.quote(sample_report)}/html',
                f'/api/report-meta/{urllib.parse.quote(sample_report)}',
                f'/api/scorecard/{urllib.parse.quote(sample_report)}',
                f'/api/bottleneck/{urllib.parse.quote(sample_report)}',
                f'/api/rt-histogram/{urllib.parse.quote(sample_report)}',
                f'/api/error-patterns/{urllib.parse.quote(sample_report)}',
                f'/api/ussd-funnel/{urllib.parse.quote(sample_report)}',
                f'/api/regression-check/{urllib.parse.quote(sample_report)}',
            ]
            for p in dyn:
                r = admin.get(p)
                rr.check(f'GET {p}', r['status'] < 500, str(r['status']))

        # JMX inspect and run-control behavior check.
        jmxs = admin.get('/api/jmx-list')
        sample_jmx = None
        if jmxs['json'] and isinstance(jmxs['json'], dict):
            files = jmxs['json'].get('files') or []
            if isinstance(files, list) and files:
                sample_jmx = files[0]
        rr.check('at least one JMX exists for active SAMPLE client', bool(sample_jmx), sample_jmx or 'none')

        if sample_jmx:
            iq = admin.get(f'/api/jmx-inspect/{urllib.parse.quote(sample_jmx)}')
            rr.check('GET /api/jmx-inspect/<sample>', iq['status'] < 500, str(iq['status']))

            sr = admin.post_json('/api/test/start', {
                'jmx': sample_jmx,
                'threads': 1,
                'duration': 30,
                'rampup': 1,
                'out_name': 'e2e_live_run'
            })
            # Acceptable outcomes:
            # - 200 started
            # - 503 jmeter missing/installing
            rr.check('POST /api/test/start SAMPLE', sr['status'] in (200, 503, 409), str(sr['status']))

            if sr['status'] == 200:
                st = admin.get('/api/test/status')
                rr.check('GET /api/test/status after start', st['status'] == 200, str(st['status']))
                sp = admin.post_json('/api/test/stop', {})
                rr.check('POST /api/test/stop after start', sp['status'] == 200, str(sp['status']))

        # Cleanup temp viewer user.
        dd = admin.delete(f'/api/users/{e2e_viewer}')
        rr.check('DELETE temp viewer user', dd['status'] in (200, 404), str(dd['status']))

        summary = rr.summary()
        print(json.dumps(summary, indent=2))
        return 1 if summary['failed'] else 0

    finally:
        try:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=8)
                except Exception:
                    server.kill()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(run())
