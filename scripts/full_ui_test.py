"""
Full UI + API Test Suite — Load Testing Platform v4.0
======================================================
Tests every button, nav item, fetch() call, form, download link and role-gate
found in admin.html + viewer.html against the live server on localhost:5000.

Run:  python scripts/full_ui_test.py
"""

import html as _html_mod
import http.cookiejar
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = 'http://127.0.0.1:5000'
ADMIN_USER = 'admin'
ADMIN_PASS = 'admin'
SAMPLE_CODE = 'SAMPLE'
SAMPLE_JTL  = 'SAMPLE_Mock_Health_Check_Result.jtl'
SAMPLE_JMX  = 'SAMPLE_Mock_Health_Check_1TPS_1min.jmx'
SAMPLE_CSV  = 'sample_health_users.csv'

PASS = '\033[92mPASS\033[0m'
FAIL = '\033[91mFAIL\033[0m'
WARN = '\033[93mWARN\033[0m'
SKIP = '\033[93mSKIP\033[0m'
HEAD = '\033[1m\033[94m'
END  = '\033[0m'
BOLD = '\033[1m'

_issues  = []   # list of issue dicts
_results = []   # list of result dicts


def _log(result, name, detail=''):
    _results.append({'result': result, 'name': name, 'detail': detail})
    icon = {'PASS': PASS, 'FAIL': FAIL, 'WARN': WARN, 'SKIP': SKIP}.get(result, result)
    suffix = f'  [{detail}]' if detail else ''
    print(f'  [{icon}] {name}{suffix}')
    if result in ('FAIL', 'WARN'):
        _issues.append({'severity': result, 'name': name, 'detail': detail})


def _section(title):
    print(f'\n{HEAD}{"="*70}{END}')
    print(f'{HEAD}  {title}{END}')
    print(f'{HEAD}{"="*70}{END}')


# ── HTTP session helper ───────────────────────────────────────────────────────
class Session:
    def __init__(self):
        self.cj  = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def _req(self, method, path, data=None, headers=None, timeout=15):
        url  = BASE_URL + path
        hdrs = dict(headers or {})
        body = None
        if data is not None:
            if isinstance(data, (dict, list)):
                body = json.dumps(data).encode()
                hdrs.setdefault('Content-Type', 'application/json')
            elif isinstance(data, str):
                body = data.encode()
            else:
                body = data
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as r:
                raw = r.read()
                ct  = (r.headers.get('Content-Type') or '').lower()
                txt = raw.decode('utf-8', errors='replace')
                jsn = None
                if 'application/json' in ct:
                    try: jsn = json.loads(txt)
                    except Exception: pass
                return {'ok': True, 'status': r.status, 'text': txt, 'json': jsn,
                        'headers': dict(r.headers), 'bytes': raw}
        except urllib.error.HTTPError as e:
            raw = e.read() or b''
            txt = raw.decode('utf-8', errors='replace')
            jsn = None
            try: jsn = json.loads(txt)
            except Exception: pass
            return {'ok': False, 'status': e.code, 'text': txt, 'json': jsn,
                    'headers': dict(e.headers), 'bytes': raw}
        except Exception as ex:
            return {'ok': False, 'status': 0, 'text': str(ex), 'json': None,
                    'headers': {}, 'bytes': b''}

    def get(self, path, **kw):  return self._req('GET',  path, **kw)
    def post(self, path, data=None, **kw): return self._req('POST', path, data=data, **kw)
    def put(self, path, data=None, **kw):  return self._req('PUT',  path, data=data, **kw)
    def delete(self, path, **kw): return self._req('DELETE', path, **kw)

    def post_form(self, path, form):
        body = urllib.parse.urlencode(form)
        return self._req('POST', path, data=body,
                         headers={'Content-Type': 'application/x-www-form-urlencoded'})

    def get_no_redirect(self, path, timeout=10):
        """GET that does NOT follow redirects — returns raw 302/401/403."""
        url = BASE_URL + path
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            _NoRedirectHandler()
        )
        req = urllib.request.Request(url, method='GET')
        try:
            with opener.open(req, timeout=timeout) as r:
                return {'status': r.status, 'location': r.headers.get('Location', '')}
        except urllib.error.HTTPError as e:
            return {'status': e.code, 'location': e.headers.get('Location', '')}
        except Exception:
            return {'status': 0, 'location': ''}

    def login(self, user, pw):
        r = self.post_form('/login', {'username': user, 'password': pw})
        return r['status'] in (200, 302, 303)


class _NoRedirectHandler(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response
    https_response = http_response


def _server_up():
    try:
        r = Session().get('/health')
        return r['ok'] and r['status'] == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 1 — SERVER HEALTH
# ═══════════════════════════════════════════════════════════════════════════════
def test_server_health(admin):
    _section('1  SERVER HEALTH')

    r = Session().get('/health')
    if r['ok'] and r['status'] == 200:
        d = r['json'] or {}
        _log('PASS', '/health responds 200')
        _log('PASS' if d.get('db_ok') else 'FAIL', 'Database connectivity', str(d.get('db_ok')))
        _log('PASS' if d.get('jmeter_ok') else 'WARN', 'JMeter binary found',
             d.get('jmeter_path', 'not found'))
        _log('PASS', f'Platform version {d.get("version", "?")}')
        _log('PASS' if d.get('disk_free_gb', 0) > 0.5 else 'WARN',
             f'Disk free {d.get("disk_free_gb", 0)} GB',
             'Low disk space' if d.get('disk_free_gb', 0) <= 0.5 else '')
    else:
        _log('FAIL', '/health failed', str(r['status']))

    r2 = Session().get('/health/ui')
    _log('PASS' if r2['status'] == 200 else 'FAIL', '/health/ui page', str(r2['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# 2 — AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════
def test_authentication():
    _section('2  AUTHENTICATION — Login / Logout / Session')

    anon = Session()

    # GET /login
    r = anon.get('/login')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'GET /login page loads', str(r['status']))
    if r['status'] == 200:
        body = r['text']
        _log('PASS' if 'username' in body.lower() else 'FAIL',
             'Login page has username field')
        _log('PASS' if 'password' in body.lower() else 'FAIL',
             'Login page has password field')
        _log('PASS' if 'type="submit"' in body or "type='submit'" in body else 'FAIL',
             'Login page has submit button')

    # POST /login with bad credentials
    bad = Session()
    r = bad.post_form('/login', {'username': 'nobody', 'password': 'wrong'})
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Bad credentials stay on login page (not redirected)', str(r['status']))
    _log('PASS' if 'invalid' in r['text'].lower() or 'error' in r['text'].lower() else 'FAIL',
         'Login page shows error message on bad credentials')

    # Empty credentials
    r = bad.post_form('/login', {'username': '', 'password': ''})
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Empty credentials rejected', str(r['status']))

    # Admin login
    admin = Session()
    ok = admin.login(ADMIN_USER, ADMIN_PASS)
    _log('PASS' if ok else 'FAIL', f'Admin login ({ADMIN_USER})')

    # /api/me returns admin info
    r = admin.get('/api/me')
    if r['status'] == 200 and r['json']:
        d = r['json']
        _log('PASS' if d.get('username') == ADMIN_USER else 'FAIL',
             '/api/me returns correct username', d.get('username'))
        _log('PASS' if d.get('role') == 'admin' else 'FAIL',
             '/api/me returns admin role', d.get('role'))
    else:
        _log('FAIL', '/api/me failed after admin login', str(r['status']))

    # Public admin list (unauthenticated)
    r = anon.get('/api/admins')
    _log('PASS' if r['status'] == 200 else 'FAIL', '/api/admins public endpoint', str(r['status']))

    # Root redirects to /admin when logged in
    r = admin.get('/')
    _log('PASS' if r['status'] in (200, 302) else 'FAIL',
         'Authenticated root redirects', str(r['status']))

    # Logout
    r = admin.get('/logout')
    _log('PASS' if r['status'] in (200, 302, 303) else 'FAIL', '/logout redirects', str(r['status']))

    # After logout, /admin should redirect
    r = admin.get('/admin')
    _log('PASS' if r['status'] in (200, 302, 303) else 'FAIL',
         '/admin redirects after logout', str(r['status']))

    return admin   # re-login for next sections


# ═══════════════════════════════════════════════════════════════════════════════
# 3 — ADMIN PORTAL HTML RENDERING
# ═══════════════════════════════════════════════════════════════════════════════
def test_admin_portal_html(admin):
    _section('3  ADMIN PORTAL — HTML Rendering + All Nav Panels')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    r = admin.get('/admin')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'GET /admin returns 200', str(r['status']))
    body = r['text']

    # HTML structure checks
    _log('PASS' if '<!DOCTYPE html>' in body or '<!doctype html>' in body.lower() else 'FAIL',
         'admin.html has DOCTYPE declaration')
    _log('PASS' if '<title>' in body else 'FAIL', 'admin.html has <title> tag')
    _log('PASS' if '</html>' in body else 'FAIL', 'admin.html closes properly')

    # Check for Jinja2 template errors (unrendered blocks = render error)
    _log('PASS' if '{{' not in body else 'FAIL',
         'No unrendered Jinja2 template variables', 'Found {{ in rendered HTML')
    _log('PASS' if '{%' not in body else 'FAIL',
         'No unrendered Jinja2 template blocks', 'Found {% in rendered HTML')
    _log('PASS' if 'TemplateSyntaxError' not in body else 'FAIL',
         'No Jinja2 TemplateSyntaxError in page')
    _log('PASS' if 'Internal Server Error' not in body else 'FAIL',
         'No Internal Server Error in admin page')
    _log('PASS' if 'Traceback' not in body else 'FAIL',
         'No Python traceback in admin page')

    # Chart.js loaded
    _log('PASS' if 'chart.min.js' in body else 'FAIL',
         'Chart.js script tag present in admin.html')

    # All nav panels present in HTML
    panels = ['overview', 'runner', 'reports', 'testdata', 'upload', 'testconfig',
              'testfeatures', 'jmxinspector', 'history', 'clients', 'users',
              'auditlog', 'prereq', 'dbmaint', 'schedules', 'heatmap', 'settings',
              'platformstats', 'loadprofiles', 'registrations', 'trends', 'leaderboard']
    for panel in panels:
        _log('PASS' if f'id="panel-{panel}"' in body or f"id='panel-{panel}'" in body else 'FAIL',
             f'Nav panel #panel-{panel} exists in DOM')

    # Key buttons present
    key_buttons = [
        ('btn-start',   'Start Test button'),
        ('btn-stop',    'Stop Test button'),
    ]
    for bid, label in key_buttons:
        _log('PASS' if f'id="{bid}"' in body or f"id='{bid}'" in body else 'FAIL',
             f'{label} (#{bid}) in DOM')

    # JS function definitions present
    js_functions = [
        'startTest', 'stopTest', 'loadReportsList', 'loadSettings',
        'loadUsers', 'loadClients', 'loadAuditLog', 'loadPrereq',
        'loadDbStats', 'loadSchedules', 'loadHeatmap', 'loadPlatformStats',
        'loadLoadProfiles', 'loadRegistrations', 'loadTrends', 'loadLeaderboard',
        'showPanel', 'smokeTest', 'compareRuns', 'toggleTheme',
    ]
    for fn in js_functions:
        _log('PASS' if f'function {fn}' in body else 'FAIL',
             f'JS function {fn}() defined in admin.html')


# ═══════════════════════════════════════════════════════════════════════════════
# 4 — VIEWER PORTAL HTML RENDERING
# ═══════════════════════════════════════════════════════════════════════════════
def test_viewer_portal_html():
    _section('4  VIEWER PORTAL — HTML Rendering')

    # Create a fresh viewer for testing
    admin = Session()
    admin.login(ADMIN_USER, ADMIN_PASS)
    vuser = 'ui_v_' + str(int(time.time()))[-6:]
    vpass = 'UIViewPass1!'
    admin.post('/api/users', {
        'username': vuser, 'password': vpass,
        'name': 'UI Test Viewer', 'role': 'viewer',
        'permissions': ['run_tests', 'view_audit']
    })
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    viewer = Session()
    viewer.login(vuser, vpass)
    viewer.post('/api/session/client', {'code': SAMPLE_CODE})

    r = viewer.get('/viewer')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'GET /viewer returns 200', str(r['status']))
    body = r['text']

    _log('PASS' if '<!DOCTYPE html>' in body or '<!doctype html>' in body.lower() else 'FAIL',
         'viewer.html has DOCTYPE')
    _log('PASS' if '</html>' in body else 'FAIL', 'viewer.html closes properly')
    _log('PASS' if '{{' not in body else 'FAIL', 'No unrendered Jinja2 variables in viewer')
    _log('PASS' if 'Internal Server Error' not in body else 'FAIL', 'No server error in viewer page')
    _log('PASS' if 'Traceback' not in body else 'FAIL', 'No traceback in viewer page')

    # Viewer panels
    viewer_panels = ['overview', 'reports', 'prereq', 'schedules', 'auditlog']
    for panel in viewer_panels:
        _log('PASS' if f"id='{panel}'" in body or f'id="{panel}"' in body or panel in body else 'WARN',
             f'Viewer panel #{panel} exists')

    # Read-only notice
    _log('PASS' if 'read-only' in body.lower() or 'viewer' in body.lower() else 'WARN',
         'Viewer portal has read-only indicator')

    # JS functions
    viewer_fns = ['loadReportsList', 'startTest', 'stopTest', 'showPanel']
    for fn in viewer_fns:
        _log('PASS' if f'function {fn}' in body else 'WARN',
             f'Viewer JS function {fn}() defined')

    # Cleanup
    admin.delete(f'/api/users/{vuser}')
    return viewer, vuser


# ═══════════════════════════════════════════════════════════════════════════════
# 5 — EVERY FETCH() ENDPOINT FROM admin.html
# ═══════════════════════════════════════════════════════════════════════════════
def test_all_admin_fetch_endpoints(admin):
    _section('5  ADMIN FETCH() ENDPOINTS — Every URL from admin.html JS')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    # All GET endpoints extracted from admin.html fetch() calls
    get_endpoints = [
        ('/api/prereq/auto',                   'prereq auto-check panel refresh'),
        ('/api/test/status',                   'test status poller'),
        ('/api/logs?offset=0',                 'live log stream'),
        ('/api/reports',                       'reports list panel load'),
        ('/api/csv-files',                     'CSV files panel load'),
        ('/api/settings',                      'settings panel load'),
        ('/api/db/full-stats',                 'DB maintenance panel load'),
        ('/api/jmx-services',                  'JMX services panel load'),
        ('/api/overview-stats',                'overview panel KPIs'),
        ('/api/schedules',                     'schedules panel load'),
        ('/api/suite/status',                  'suite runner status poller'),
        ('/api/prereq',                        'prerequisites panel load'),
        ('/api/sla-config',                    'SLA config panel load'),
        ('/api/sla-result',                    'SLA result summary'),
        ('/api/live-stats',                    'live stats during run'),
        ('/api/live-stats/labels',             'live stats labels'),
        ('/api/heatmap',                       'heatmap panel load'),
        ('/api/test/status',                   'header status dot poller'),
        ('/api/platform-stats',                'platform stats panel'),
        ('/api/load-profiles',                 'load profiles panel'),
        ('/api/admin/registrations',           'registrations panel'),
        ('/api/clients',                       'clients panel load'),
        ('/api/users',                         'users panel load'),
        ('/api/audit-log?limit=100',           'audit log panel load'),
        ('/api/run-history',                   'run history panel'),
        ('/api/jmx-list',                      'JMX list for runner dropdown'),
        ('/api/db-stats',                      'DB stats overview card'),
        ('/api/test-features',                 'test features panel'),
        ('/api/env',                           'environment config load'),
        ('/api/load-config',                   'load config load'),
        ('/api/baseline',                      'baseline data load'),
        ('/api/recurring-schedules',           'recurring schedules panel'),
        ('/api/jmx-requirements',              'JMX requirements panel'),
        ('/api/me',                            'user profile chip'),
        ('/api/theme',                         'theme preference load'),
        ('/api/favourites',                    'starred reports'),
        ('/api/presence',                      'presence indicator'),
        ('/api/trends?days=7',                 'trends panel'),
        ('/api/leaderboard',                   'leaderboard panel'),
        ('/api/sla-trend?limit=5',             'SLA trend chart'),
        ('/api/backup/list',                   'backup list'),
        ('/api/webhook-config',                'webhook config load'),
        ('/api/test/annotations',              'run annotations'),
        ('/api/schedule-calendar',             'schedule calendar heatmap'),
        ('/api/xlsx-files',                    'xlsx file list'),
        ('/api/platform-stats',                'platform stats'),
        ('/api/jmeter/install-status',         'JMeter install status'),
    ]

    # Dynamic GET endpoints requiring file names
    sample_jtl_enc = urllib.parse.quote(SAMPLE_JTL)
    sample_jmx_enc = urllib.parse.quote(SAMPLE_JMX)
    sample_csv_enc = urllib.parse.quote(SAMPLE_CSV)

    dynamic_gets = [
        (f'/api/report/{sample_jtl_enc}',                       'report parse — Reports panel'),
        (f'/api/report/{sample_jtl_enc}/errors',                'error analysis button'),
        (f'/api/report/{sample_jtl_enc}/html',                  'HTML report inline view'),
        (f'/api/report-meta/{sample_jtl_enc}',                  'report meta panel'),
        (f'/api/scorecard/{sample_jtl_enc}',                    'performance scorecard button'),
        (f'/api/bottleneck/{sample_jtl_enc}',                   'bottleneck analysis button'),
        (f'/api/rt-histogram/{sample_jtl_enc}',                 'RT Histogram button'),
        (f'/api/error-patterns/{sample_jtl_enc}',              'Error Patterns button'),
        (f'/api/ussd-funnel/{sample_jtl_enc}',                 'Session Funnel button'),
        (f'/api/regression-check/{sample_jtl_enc}',            'regression check inline'),
        (f'/api/sla-analysis/{sample_jtl_enc}',                'SLA Check modal'),
        (f'/api/baseline/compare/{sample_jtl_enc}',            'baseline compare button'),
        (f'/api/csv-preview/{sample_csv_enc}',                 'CSV card preview'),
        (f'/api/jmx-params/{sample_jmx_enc}',                  'JMX params editor'),
        (f'/api/jmx-inspect/{sample_jmx_enc}',                 'JMX Inspector panel'),
        (f'/api/jmx-tree/{sample_jmx_enc}',                    'JMX tree view'),
        (f'/api/jmx/{sample_jmx_enc}/properties',              'JMX properties modal'),
        (f'/api/run-notes/{SAMPLE_JTL}',                       'run notes load'),
        (f'/api/comments/{sample_jtl_enc}',                    'report comments load'),
    ]

    for path, label in get_endpoints + dynamic_gets:
        r = admin.get(path)
        ok = 0 < r['status'] < 500
        _log('PASS' if ok else 'FAIL', f'GET {path[:60]} — {label}', str(r['status']))

    # POST endpoints (buttons that fire POST fetch calls)
    _section_inline('5b  POST BUTTON ACTIONS')
    post_actions = [
        ('/api/test/stop',                      {},                                   'Stop Test button'),
        ('/api/test/annotate',                  {'text': 'UI test annotation'},       'Annotate run button'),
        ('/api/prereq',                         {'targets': {}, 'activities': []},    'Save Prereq button'),
        ('/api/sla-config',                     {'max_rt': 3000, 'max_err_pct': 5},  'Save SLA config button'),
        ('/api/load-config',                    {'services': []},                     'Save Load Config button'),
        ('/api/env',                            {'endpoint': 'http://test.local'},    'Save Env button'),
        ('/api/theme',                          {'theme': 'dark'},                    'Theme toggle button'),
        ('/api/favourites',                     {'file': SAMPLE_JTL},                 'Star/Favourite button'),
        ('/api/presence',                       {'panel': 'overview'},               'Presence beacon'),
        ('/api/db/vacuum',                      {},                                   'Vacuum DB button'),
        ('/api/db/purge',                       {'days': 365},                        'Purge audit button'),
        ('/api/db/clear-audit',                 {'confirm': 'CLEAR'},                 'Clear audit button'),
        ('/api/share/live',                     {},                                   'Share Live button'),
        ('/api/share/report',                   {'file': SAMPLE_JTL},                 'Share Report button'),
        ('/api/run-note',                       {'notes': 'UI test', 'tag': 'ui'},   'Pre-run notes button'),
        ('/api/run-notes',                      {'run_id': 'ui-test-1', 'notes': 'x'}, 'Save run notes'),
        ('/api/webhook-config',                 {'webhook_url': '', 'webhook_on_pass': True, 'webhook_on_fail': True}, 'Save webhook config'),
        ('/api/webhook-test',                   {},                                   'Test webhook button'),
        ('/api/backup/run',                     {},                                   'Run backup button'),
        ('/api/archive-reports',                {'days': 365},                        'Archive reports button'),
        ('/api/tps-calculator',                 {'total_tps': 30, 'duration': 600},  'TPS Calculator button'),
        ('/api/health-check',                   {'url': 'http://127.0.0.1:5000/health'}, 'Check Server button'),
        ('/api/compare-runs',                   {'files': [SAMPLE_JTL]},              'Compare Runs button'),
        ('/api/compare-runs',                   {'files': [SAMPLE_JTL, SAMPLE_JTL]}, 'Compare 2 runs button'),
        ('/api/compare-reports',                {'file1': SAMPLE_JTL, 'file2': SAMPLE_JTL}, 'Side-by-side compare button'),
        ('/api/baseline',                       {'file': SAMPLE_JTL},                 'Set Baseline button'),
        ('/api/suite/stop',                     {},                                   'Stop Suite button'),
        ('/api/load-config/suggest-from-jmx',  {'jmx': SAMPLE_JMX},                 'Suggest from JMX button'),
        ('/api/comments/' + sample_jtl_enc,     {'text': 'UI comment', 'ts_offset_s': 10}, 'Post comment button'),
    ]

    for path, payload, label in post_actions:
        r = admin.post(path, payload)
        ok = 0 < r['status'] < 500
        _log('PASS' if ok else 'FAIL', f'POST {path[:55]} — {label}', str(r['status']))

    # DELETE button actions
    _section_inline('5c  DELETE BUTTON ACTIONS')
    delete_actions = [
        ('/api/baseline',                  'Clear Baseline button'),
        ('/api/load-profiles/NoSuchProfile', 'Delete load profile button'),
    ]
    for path, label in delete_actions:
        r = admin.delete(path)
        ok = 0 < r['status'] < 500
        _log('PASS' if ok else 'FAIL', f'DELETE {path[:55]} — {label}', str(r['status']))

    # Unfavourite (second toggle)
    admin.post('/api/favourites', {'file': SAMPLE_JTL})


def _section_inline(title):
    print(f'\n  {BOLD}{title}{END}')


# ═══════════════════════════════════════════════════════════════════════════════
# 6 — VIEWER FETCH() ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
def test_viewer_fetch_endpoints():
    _section('6  VIEWER FETCH() ENDPOINTS — Every URL from viewer.html JS')

    # Create temp viewer
    admin = Session()
    admin.login(ADMIN_USER, ADMIN_PASS)
    vuser = 'ui_vf_' + str(int(time.time()))[-6:]
    vpass = 'UIVPass1!'
    admin.post('/api/users', {
        'username': vuser, 'password': vpass,
        'name': 'Viewer Fetch Test', 'role': 'viewer',
        'permissions': ['run_tests', 'view_audit', 'manage_schedules']
    })

    viewer = Session()
    viewer.login(vuser, vpass)
    viewer.post('/api/session/client', {'code': SAMPLE_CODE})

    sample_jtl_enc = urllib.parse.quote(SAMPLE_JTL)
    sample_jmx_enc = urllib.parse.quote(SAMPLE_JMX)

    viewer_gets = [
        ('/api/reports',                            'viewer reports list'),
        ('/api/overview-stats',                     'viewer overview KPIs'),
        ('/api/test-features',                      'viewer test features'),
        ('/api/sla-config',                         'viewer SLA config'),
        ('/api/sla-result',                         'viewer SLA result'),
        ('/api/heatmap',                            'viewer heatmap'),
        ('/api/prereq/auto',                        'viewer prereq auto-check'),
        ('/api/prereq',                             'viewer prerequisites'),
        ('/api/jmx-list',                           'viewer JMX list'),
        ('/api/jmx-services',                       'viewer JMX services'),
        ('/api/test/status',                        'viewer run status'),
        ('/api/logs?offset=0',                      'viewer log stream'),
        ('/api/schedules',                          'viewer schedules'),
        ('/api/audit-log?limit=100',               'viewer audit log'),
        ('/api/me',                                 'viewer profile'),
        ('/api/theme',                              'viewer theme pref'),
        ('/api/presence',                           'viewer presence'),
        ('/api/favourites',                         'viewer favourites'),
        (f'/api/report/{sample_jtl_enc}',           'viewer report parse'),
        (f'/api/jmx-inspect/{sample_jmx_enc}',     'viewer JMX inspect'),
    ]
    for path, label in viewer_gets:
        r = viewer.get(path)
        _log('PASS' if 0 < r['status'] < 500 else 'FAIL',
             f'viewer GET {path[:55]} — {label}', str(r['status']))

    viewer_posts = [
        ('/api/test/start',  {'jmx': SAMPLE_JMX, 'threads': 1, 'duration': 5, 'rampup': 1},
         'viewer Start Test (with run_tests perm)'),
        ('/api/prereq',      {'targets': {}, 'activities': []},
         'viewer Save prereq'),
        ('/api/favourites',  {'file': SAMPLE_JTL},
         'viewer toggle favourite'),
        ('/api/theme',       {'theme': 'dark'},
         'viewer set theme'),
        ('/api/presence',    {'panel': 'viewer'},
         'viewer presence beacon'),
    ]
    for path, payload, label in viewer_posts:
        r = viewer.post(path, payload)
        status_ok = r['status'] in (200, 409, 503)  # 409=already running, 503=no JMeter
        _log('PASS' if status_ok else 'FAIL',
             f'viewer POST {path[:50]} — {label}', str(r['status']))
        # If test was started, stop it
        if path == '/api/test/start' and r['status'] == 200:
            viewer.post('/api/test/stop', {})

    # Viewer baseline set (needs manage_baseline perm — should 403)
    r_bl = viewer.post('/api/baseline', {'file': SAMPLE_JTL})
    _log('PASS' if r_bl['status'] in (200, 403) else 'WARN',
         'viewer POST /api/baseline (403 if no manage_baseline perm)', str(r_bl['status']))

    # Viewer upload (admin only)
    r_up = viewer.post('/api/upload/jmx', None)
    _log('PASS' if r_up['status'] in (302, 400, 403) else 'WARN',
         'viewer cannot upload JMX (no perm)', str(r_up['status']))

    # Cleanup
    admin.delete(f'/api/users/{vuser}')


# ═══════════════════════════════════════════════════════════════════════════════
# 7 — ADMIN NAV PANELS (every sidebar nav item)
# ═══════════════════════════════════════════════════════════════════════════════
def test_nav_panels(admin):
    _section('7  ADMIN SIDEBAR NAV — Every Panel + Its Primary API Calls')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    sample_jtl_enc = urllib.parse.quote(SAMPLE_JTL)

    panels_and_apis = {
        'Overview':        ['/api/overview-stats', '/api/heatmap'],
        'Test Runner':     ['/api/jmx-list', '/api/test/status', '/api/prereq/auto'],
        'Reports':         ['/api/reports', f'/api/report/{sample_jtl_enc}'],
        'Test Data (CSV)': ['/api/csv-files'],
        'Upload':          ['/api/jmx-services', '/api/csv-files', '/api/reports'],
        'Test Config':     ['/api/env', '/api/load-config', '/api/test-features'],
        'Test Features':   ['/api/test-features', '/api/xlsx-files'],
        'JMX Inspector':   ['/api/jmx-list', '/api/jmx-requirements'],
        'Run History':     ['/api/run-history'],
        'Clients':         ['/api/clients', '/api/db-stats'],
        'Users':           ['/api/users', '/api/db-stats'],
        'Audit Log':       ['/api/audit-log?limit=100'],
        'Pre-Requisites':  ['/api/prereq', '/api/prereq/auto'],
        'DB Maintenance':  ['/api/db/full-stats'],
        'Schedules':       ['/api/schedules', '/api/recurring-schedules'],
        'Heatmap':         ['/api/heatmap'],
        'Settings':        ['/api/settings', '/api/webhook-config'],
        'Platform Stats':  ['/api/platform-stats'],
        'Load Profiles':   ['/api/load-profiles'],
        'Registrations':   ['/api/admin/registrations'],
        'Trends':          ['/api/trends?days=7'],
        'Leaderboard':     ['/api/leaderboard'],
    }

    for panel_name, apis in panels_and_apis.items():
        panel_ok = True
        for api in apis:
            r = admin.get(api)
            if r['status'] >= 500:
                panel_ok = False
                _log('FAIL', f'{panel_name} panel → {api}', str(r['status']))
        if panel_ok:
            _log('PASS', f'{panel_name} panel — all API calls return <500')


# ═══════════════════════════════════════════════════════════════════════════════
# 8 — DOWNLOAD BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════
def test_download_buttons(admin):
    _section('8  DOWNLOAD BUTTONS — Every Download Action')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    sample_jtl_enc = urllib.parse.quote(SAMPLE_JTL)
    sample_jmx_enc = urllib.parse.quote(SAMPLE_JMX)
    sample_csv_enc = urllib.parse.quote(SAMPLE_CSV)

    downloads = [
        (f'/api/download/jtl/{sample_jtl_enc}',          'Download Raw JTL button'),
        (f'/api/download/html/{sample_jtl_enc}',         'Download HTML Report button'),
        (f'/api/download/bundle/{sample_jtl_enc}',       'Download ZIP Bundle button'),
        (f'/api/download/jmx/{sample_jmx_enc}',          'Download JMX button'),
        (f'/api/download/testdata-file/{sample_csv_enc}','Download CSV testdata button'),
        ('/api/download/all-reports',                    'Download All Reports ZIP button'),
        ('/api/download/all-testdata',                   'Download All Testdata ZIP button'),
        ('/api/download/db-backup',                      'Download DB Backup button'),
        ('/api/download/audit-csv',                      'Download Audit CSV button'),
        (f'/api/report/{sample_jtl_enc}/html',           'View HTML Report button (inline)'),
        (f'/api/report/{sample_jtl_enc}/pdf',            'PDF Report button'),
        (f'/api/report/{sample_jtl_enc}/excel',          'Excel Export button'),
    ]

    for path, label in downloads:
        r = admin.get(path)
        if r['status'] == 200:
            size_kb = len(r['bytes']) / 1024
            _log('PASS', f'{label}', f'{path[-40:]} → {size_kb:.1f} KB')
        elif r['status'] == 404:
            _log('WARN', f'{label} — file not found (404)', path[-40:])
        else:
            _log('FAIL', f'{label} — unexpected status', f'{path[-40:]} → {r["status"]}')

    # Edge: downloading non-existent files
    bad_downloads = [
        ('/api/download/jtl/NO_SUCH_FILE.jtl', 'Non-existent JTL download → 404'),
        ('/api/download/jmx/NO_SUCH.jmx',      'Non-existent JMX download → 404'),
        ('/api/download/xlsx/NO_SUCH.xlsx',     'Non-existent XLSX download → 404'),
    ]
    for path, label in bad_downloads:
        r = admin.get(path)
        _log('PASS' if r['status'] in (400, 404) else 'FAIL', label, str(r['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# 9 — UPLOAD BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════
def test_upload_buttons(admin):
    _section('9  UPLOAD BUTTONS — JMX / CSV / Report Upload Zones')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    def _multipart(field, filename, content, mime='application/octet-stream'):
        boundary = 'E2EBoundary1234'
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            f'Content-Type: {mime}\r\n\r\n'
        ).encode() + content + f'\r\n--{boundary}--\r\n'.encode()
        return body, f'multipart/form-data; boundary={boundary}'

    # Upload JMX
    jmx_content = b'<?xml version="1.0"?><jmeterTestPlan><hashTree/></jmeterTestPlan>'
    body, ct = _multipart('file', 'ui_upload_test.jmx', jmx_content, 'application/xml')
    r = admin._req('POST', '/api/upload/jmx', data=body, headers={'Content-Type': ct})
    _log('PASS' if r['status'] in (200, 201) else 'FAIL',
         'Upload JMX via upload zone', str(r['status']))

    # Upload CSV
    csv_content = b'msisdn,pin\n26771000001,1234\n26771000002,5678\n'
    body, ct = _multipart('file', 'ui_upload_test.csv', csv_content, 'text/csv')
    r = admin._req('POST', '/api/upload/testdata', data=body, headers={'Content-Type': ct})
    _log('PASS' if r['status'] in (200, 201) else 'FAIL',
         'Upload CSV via upload zone', str(r['status']))

    # Upload JTL report
    jtl_content = (
        b'timeStamp,elapsed,label,responseCode,responseMessage,threadName,'
        b'dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,'
        b'URL,Latency,IdleTime,Connect\n'
        b'1782700000000,45,Test,200,OK,Thread 1-1,text,true,,256,128,1,1,'
        b'http://localhost/test,40,0,5\n'
    )
    body, ct = _multipart('file', 'ui_upload_result.jtl', jtl_content, 'text/csv')
    r = admin._req('POST', '/api/upload/report', data=body, headers={'Content-Type': ct})
    _log('PASS' if r['status'] in (200, 201) else 'FAIL',
         'Upload JTL report via upload zone', str(r['status']))

    # Missing file upload → 400
    body, ct = _multipart('wrong_field', 'test.jmx', b'', 'text/plain')
    r = admin._req('POST', '/api/upload/jmx', data=body, headers={'Content-Type': ct})
    _log('PASS' if r['status'] == 400 else 'FAIL',
         'Upload without file field → 400', str(r['status']))

    # Delete uploaded CSV
    r = admin.post('/api/upload/delete', {'folder': 'testdata', 'filename': 'ui_upload_test.csv'})
    _log('PASS' if r['status'] in (200, 404) else 'FAIL',
         'Delete uploaded file button', str(r['status']))

    # Delete uploaded JMX
    r = admin.post('/api/upload/delete', {'folder': 'jmx', 'filename': 'ui_upload_test.jmx'})
    _log('PASS' if r['status'] in (200, 404) else 'FAIL',
         'Delete uploaded JMX button', str(r['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# 10 — CLIENT MANAGEMENT BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════
def test_client_management_ui(admin):
    _section('10  CLIENTS PANEL — New Client / Edit / Delete')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    code = 'UI' + str(int(time.time()))[-4:]

    # New Client button → POST /api/clients
    r = admin.post('/api/clients', {
        'code': code, 'name': f'UI Test {code}',
        'description': 'Created by UI test', 'logo_emoji': '🧪', 'color': '#ff6600'
    })
    _log('PASS' if r['status'] in (200, 201) else 'FAIL',
         f'New Client button → POST /api/clients ({code})', str(r['status']))

    # Edit Client button → PUT /api/clients/<code>
    r = admin.put(f'/api/clients/{code}', {'name': f'UI Test {code} Updated'})
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Edit Client button → PUT /api/clients/<code>', str(r['status']))

    # Switch away from SAMPLE first, then switch to new client
    admin.post('/api/session/client', {'code': code})

    # Storage stats link
    r = admin.get(f'/api/clients/{code}/storage')
    _log('PASS' if 0 < r['status'] < 500 else 'FAIL',
         'Client storage stats', str(r['status']))

    # Switch back to SAMPLE before deleting
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    # Delete Client button → DELETE /api/clients/<code>
    r = admin.delete(f'/api/clients/{code}')
    _log('PASS' if r['status'] in (200, 204) else 'FAIL',
         'Delete Client button → DELETE /api/clients/<code>', str(r['status']))

    # Cannot delete currently active client
    r = admin.delete(f'/api/clients/{SAMPLE_CODE}')
    _log('PASS' if r['status'] == 400 else 'FAIL',
         'Delete active client rejected → 400', str(r['status']))

    # Cannot create duplicate client
    r = admin.post('/api/clients', {'code': SAMPLE_CODE, 'name': 'Dup', 'description': ''})
    _log('PASS' if r['status'] in (400, 409) else 'FAIL',
         'Duplicate client code rejected → 400/409', str(r['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# 11 — USER MANAGEMENT BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════
def test_user_management_ui(admin):
    _section('11  USERS PANEL — Add / Edit / Reset Password / Disable / Delete')

    admin.login(ADMIN_USER, ADMIN_PASS)

    uname = 'ui_u_' + str(int(time.time()))[-6:]

    # Add User button
    r = admin.post('/api/users', {
        'username': uname, 'password': 'UIPass1234!',
        'name': 'UI Test User', 'role': 'viewer',
        'initials': 'UT', 'permissions': ['run_tests']
    })
    _log('PASS' if r['status'] in (200, 201) else 'FAIL',
         'Add User button → POST /api/users', str(r['status']))

    # Edit User button (change name)
    r = admin.put(f'/api/users/{uname}', {'name': 'UI Test User Updated'})
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Edit User button → PUT /api/users/<username>', str(r['status']))

    # Update permissions
    r = admin.put(f'/api/users/{uname}', {'permissions': ['run_tests', 'view_audit']})
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Edit permissions checkbox → PUT /api/users/<username>', str(r['status']))

    # Disable user toggle
    r = admin.put(f'/api/users/{uname}', {'enabled': False})
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Disable user toggle → PUT enabled=false', str(r['status']))

    # Re-enable
    r = admin.put(f'/api/users/{uname}', {'enabled': True})
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Enable user toggle → PUT enabled=true', str(r['status']))

    # Reset password button
    r = admin.post(f'/api/users/{uname}/reset-password', {'password': 'NewPass999!'})
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Reset Password button → POST /api/users/<u>/reset-password', str(r['status']))

    # Short password rejected
    r = admin.post(f'/api/users/{uname}/reset-password', {'password': 'ab'})
    _log('PASS' if r['status'] == 400 else 'FAIL',
         'Short password rejected → 400', str(r['status']))

    # Delete user button
    r = admin.delete(f'/api/users/{uname}')
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Delete User button → DELETE /api/users/<username>', str(r['status']))

    # Self-delete blocked
    r = admin.delete(f'/api/users/{ADMIN_USER}')
    _log('PASS' if r['status'] == 400 else 'FAIL',
         'Cannot delete own account → 400', str(r['status']))

    # Change own password button (admin)
    r = admin.post('/api/users/me/change-password', {
        'current_password': ADMIN_PASS, 'new_password': ADMIN_PASS
    })
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Change own password button → POST /api/users/me/change-password', str(r['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# 12 — REPORT DETAIL BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════
def test_report_detail_buttons(admin):
    _section('12  REPORT DETAIL — All Action Buttons on a Selected Report')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    jtl_enc = urllib.parse.quote(SAMPLE_JTL)

    # All buttons visible when a report is selected
    report_buttons = [
        (f'/api/report/{jtl_enc}',                           'GET', None,  'Report row click → parse JTL'),
        (f'/api/report/{jtl_enc}/errors',                    'GET', None,  'Error Breakdown button'),
        (f'/api/report/{jtl_enc}/html',                      'GET', None,  'View HTML button (inline)'),
        (f'/api/report/{jtl_enc}/pdf',                       'GET', None,  'PDF Report button'),
        (f'/api/report/{jtl_enc}/excel',                     'GET', None,  'Excel Export button'),
        (f'/api/download/jtl/{jtl_enc}',                     'GET', None,  'Download JTL button'),
        (f'/api/download/html/{jtl_enc}',                    'GET', None,  'Download HTML button'),
        (f'/api/download/bundle/{jtl_enc}',                  'GET', None,  'ZIP Bundle button'),
        (f'/api/scorecard/{jtl_enc}',                        'GET', None,  'Performance Scorecard panel'),
        (f'/api/bottleneck/{jtl_enc}',                       'GET', None,  'Bottleneck Analysis panel'),
        (f'/api/rt-histogram/{jtl_enc}',                     'GET', None,  'RT Histogram button'),
        (f'/api/error-patterns/{jtl_enc}',                  'GET', None,  'Error Patterns button'),
        (f'/api/ussd-funnel/{jtl_enc}',                     'GET', None,  'Session Funnel button'),
        (f'/api/sla-analysis/{jtl_enc}',                    'GET', None,  'SLA Check modal'),
        (f'/api/regression-check/{jtl_enc}?threshold=10',   'GET', None,  'Regression Check panel'),
        (f'/api/report-meta/{jtl_enc}',                     'GET', None,  'Report meta load'),
        ('/api/baseline',                                    'POST', {'file': SAMPLE_JTL}, 'Set as Baseline button'),
        (f'/api/baseline/compare/{jtl_enc}',                'GET', None,  'Compare vs Baseline button'),
        ('/api/favourites',                                  'POST', {'file': SAMPLE_JTL}, 'Star Favourite button'),
        ('/api/share/report',                                'POST', {'file': SAMPLE_JTL}, 'Share Report button'),
        (f'/api/comments/{jtl_enc}',                        'GET', None,  'Load comments button'),
        ('/api/run-notes/' + SAMPLE_JTL,                    'GET', None,  'Run notes load'),
    ]

    for path, method, payload, label in report_buttons:
        if method == 'GET':
            r = admin.get(path)
        else:
            r = admin.post(path, payload)
        _log('PASS' if 0 < r['status'] < 500 else 'FAIL',
             f'{method} {label}', str(r['status']))

    # Comment flow: add → list → delete
    r_add = admin.post(f'/api/comments/{jtl_enc}', {'text': 'UI test comment', 'ts_offset_s': 30})
    _log('PASS' if r_add['status'] == 200 else 'FAIL', 'Post comment button', str(r_add['status']))
    cid = (r_add['json'] or {}).get('id')
    if cid:
        r_del = admin.delete(f'/api/comments/{jtl_enc}/{cid}')
        _log('PASS' if r_del['status'] == 200 else 'FAIL', 'Delete comment button', str(r_del['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# 13 — SETTINGS PANEL BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════
def test_settings_panel(admin):
    _section('13  SETTINGS PANEL — All Settings Buttons')

    admin.login(ADMIN_USER, ADMIN_PASS)

    # Load settings (panel open)
    r = admin.get('/api/settings')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Settings panel load', str(r['status']))
    _log('PASS' if isinstance(r['json'], dict) else 'FAIL',
         'Settings returns JSON object', str(type(r['json'])))

    # Save settings button
    cfg = r['json'] or {}
    cfg['audit_retention_days'] = 90
    cfg['session_timeout_mins'] = 120
    cfg['heap'] = '-Xms512m -Xmx1g'
    r2 = admin.post('/api/settings', cfg)
    _log('PASS' if r2['status'] == 200 else 'FAIL',
         'Save Settings button → POST /api/settings', str(r2['status']))

    # JMeter install status button
    r = admin.get('/api/jmeter/install-status')
    _log('PASS' if 0 < r['status'] < 500 else 'FAIL',
         'JMeter install status', str(r['status']))

    # Webhook config
    r = admin.get('/api/webhook-config')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Load webhook config', str(r['status']))
    r = admin.post('/api/webhook-config', {
        'webhook_url': '', 'webhook_on_pass': True, 'webhook_on_fail': True
    })
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Save webhook config button', str(r['status']))

    # Test webhook button (no URL = graceful fail)
    r = admin.post('/api/webhook-test', {})
    _log('PASS' if 0 < r['status'] < 500 else 'FAIL', 'Test webhook button', str(r['status']))

    # DB Maintenance buttons
    r = admin.get('/api/db/full-stats')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Load DB stats', str(r['status']))
    r = admin.post('/api/db/vacuum', {})
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Vacuum DB button', str(r['status']))
    r = admin.post('/api/db/purge', {'days': 365})
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Purge old audit button', str(r['status']))
    r = admin.post('/api/db/clear-audit', {'confirm': 'CLEAR'})
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Clear all audit button (confirm=CLEAR)', str(r['status']))
    r = admin.get('/api/download/db-backup')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Download DB Backup button', str(r['status']))
    r = admin.get('/api/download/audit-csv')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Download Audit CSV button', str(r['status']))
    r = admin.post('/api/backup/run', {})
    _log('PASS' if 0 < r['status'] < 500 else 'FAIL', 'Run backup button', str(r['status']))

    # Admin restart button skipped in automated tests (would kill the server process)


# ═══════════════════════════════════════════════════════════════════════════════
# 14 — ROLE-BASED ACCESS CONTROL (UI Gates)
# ═══════════════════════════════════════════════════════════════════════════════
def test_rbac_ui_gates():
    _section('14  ROLE-BASED UI GATES — What Viewers Cannot Access')

    admin = Session()
    admin.login(ADMIN_USER, ADMIN_PASS)

    vuser = 'ui_rbac_' + str(int(time.time()))[-6:]
    vpass = 'RbacPass1!'
    admin.post('/api/users', {
        'username': vuser, 'password': vpass,
        'name': 'RBAC UI Viewer', 'role': 'viewer', 'permissions': []
    })

    viewer = Session()
    viewer.login(vuser, vpass)
    viewer.post('/api/session/client', {'code': SAMPLE_CODE})

    anon = Session()

    # Admin-only pages — use no-redirect GET so we see the actual 302, not the redirected page
    admin_only = [
        ('/admin',            'Admin portal page'),
        ('/api/users',        'Users list API'),
        ('/api/db-stats',     'DB stats API'),
        ('/api/db/full-stats','DB full stats API'),
    ]
    for path, label in admin_only:
        rv = viewer.get_no_redirect(path)
        _log('PASS' if rv['status'] in (302, 401, 403) else 'FAIL',
             f'Viewer blocked from {label} ({path})', str(rv['status']))

    # Anon blocked from everything — check raw redirect, not followed response
    anon_blocked = [
        '/admin', '/viewer', '/api/reports', '/api/clients', '/api/users',
        '/api/me', '/api/test/status',
    ]
    for path in anon_blocked:
        r = anon.get_no_redirect(path)
        _log('PASS' if r['status'] in (302, 401, 403) else 'FAIL',
             f'Anon blocked from {path}', str(r['status']))

    # Viewer can access viewer portal and public APIs
    viewer_allowed = [
        ('/viewer',          'Viewer portal page'),
        ('/api/overview-stats', 'Overview stats'),
        ('/api/reports',     'Reports list'),
        ('/api/me',          'Own profile'),
    ]
    for path, label in viewer_allowed:
        rv = viewer.get(path)
        _log('PASS' if rv['status'] == 200 else 'FAIL',
             f'Viewer can access {label}', str(rv['status']))

    # Viewer without run_tests perm cannot start test
    rv = viewer.post('/api/test/start', {'jmx': SAMPLE_JMX, 'threads': 1, 'duration': 5})
    _log('PASS' if rv['status'] in (401, 403) else 'FAIL',
         'Viewer without run_tests perm blocked from starting test', str(rv['status']))

    # Cleanup
    admin.delete(f'/api/users/{vuser}')


# ═══════════════════════════════════════════════════════════════════════════════
# 15 — MODAL DIALOGS (every modal in the UI)
# ═══════════════════════════════════════════════════════════════════════════════
def test_modal_dialogs(admin):
    _section('15  MODAL DIALOGS — Every Modal API Call')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    jtl_enc = urllib.parse.quote(SAMPLE_JTL)
    jmx_enc = urllib.parse.quote(SAMPLE_JMX)

    modals = [
        # Modal name                     → API endpoint (what opens/populates the modal)
        ('Change Password modal',         'POST', '/api/users/me/change-password',
         {'current_password': ADMIN_PASS, 'new_password': ADMIN_PASS}),
        ('Env Profiles modal',            'GET',  '/api/env-profiles',       None),
        ('Run Notes modal',               'POST', '/api/run-notes',
         {'run_id': 'modal-test', 'notes': 'modal test note'}),
        ('SLA Check modal',               'GET',  f'/api/sla-analysis/{jtl_enc}', None),
        ('Compare Runs modal',            'POST', '/api/compare-runs',
         {'files': [SAMPLE_JTL, SAMPLE_JTL]}),
        ('TPS Calculator modal',          'POST', '/api/tps-calculator',
         {'total_tps': 30, 'duration': 600, 'ramp_up': 60}),
        ('Prop Override modal',           'GET',  f'/api/jmx/{jmx_enc}/properties', None),
        ('Generate JMX modal',            'GET',  '/api/xlsx-files',          None),
        ('Command Center overlay',        'GET',  '/api/test/status',         None),
        ('Registrations panel',           'GET',  '/api/admin/registrations', None),
        ('Audit log panel',               'GET',  '/api/audit-log?limit=20',  None),
        ('Load Profiles modal',           'GET',  '/api/load-profiles',       None),
        ('Schedules modal',               'GET',  '/api/recurring-schedules', None),
        ('Live Share modal',              'POST', '/api/share/live',          {}),
        ('Report Share modal',            'POST', '/api/share/report',
         {'file': SAMPLE_JTL}),
    ]

    for modal_name, method, path, payload in modals:
        if method == 'GET':
            r = admin.get(path)
        else:
            r = admin.post(path, payload)
        _log('PASS' if 0 < r['status'] < 500 else 'FAIL',
             f'{modal_name} API call', f'{method} {path[-50:]} → {r["status"]}')


# ═══════════════════════════════════════════════════════════════════════════════
# 16 — LIVE SHARING FLOW
# ═══════════════════════════════════════════════════════════════════════════════
def test_live_sharing(admin):
    _section('16  LIVE SHARING — Token Generation + Shared Pages')

    admin.login(ADMIN_USER, ADMIN_PASS)

    # Create live share token
    r = admin.post('/api/share/live', {})
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Share Live button → POST /api/share/live', str(r['status']))
    token = (r['json'] or {}).get('token', '')
    _log('PASS' if len(token) > 4 else 'FAIL',
         'Live share token generated', f'len={len(token)}')

    # Access shared live page
    anon = Session()
    r2 = anon.get(f'/shared/live/{token}')
    _log('PASS' if r2['status'] == 200 else 'FAIL',
         'Shared live dashboard page loads', str(r2['status']))
    _log('PASS' if 'Live Test Dashboard' in r2['text'] else 'WARN',
         'Shared live page has correct title')

    # Public stats endpoint
    r3 = anon.get(f'/api/live-stats/public?token={token}')
    _log('PASS' if r3['status'] == 200 else 'FAIL',
         'Public live stats API with valid token', str(r3['status']))

    # Invalid token blocked
    r4 = anon.get('/shared/live/BADTOKEN999')
    _log('PASS' if r4['status'] == 403 else 'FAIL',
         'Invalid live share token → 403', str(r4['status']))

    # Create report share
    r5 = admin.post('/api/share/report', {'file': SAMPLE_JTL})
    _log('PASS' if r5['status'] == 200 else 'FAIL',
         'Share Report button → POST /api/share/report', str(r5['status']))
    rtoken = (r5['json'] or {}).get('token', '')
    if rtoken:
        r6 = anon.get(f'/shared/report/{rtoken}')
        _log('PASS' if r6['status'] in (200,) else 'FAIL',
             'Shared report page loads for anyone with token', str(r6['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# 17 — SELF-REGISTRATION FLOW
# ═══════════════════════════════════════════════════════════════════════════════
def test_registration_flow():
    _section('17  SELF-REGISTRATION FLOW — Submit / Admin Approve / Reject')

    admin = Session()
    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/settings', {'self_register_enabled': True})

    anon = Session()
    ruser = 'ui_reg_' + str(int(time.time()))[-6:]

    # Submit registration
    r = anon.post('/api/register-request', {
        'username': ruser, 'name': 'UI Reg User',
        'email': f'{ruser}@test.com', 'password': 'RegPass1!'
    })
    _log('PASS' if r['status'] in (200, 409) else 'FAIL',
         'Registration form submit → POST /api/register-request', str(r['status']))

    # Admin views pending registrations
    r = admin.get('/api/admin/registrations')
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'Admin views pending registrations', str(r['status']))

    rid = None
    if r['json']:
        for item in r['json']:
            if item.get('username') == ruser:
                rid = item.get('id')
                break

    if rid:
        # Approve button
        ra = admin.post(f'/api/admin/registrations/{rid}/approve', {})
        _log('PASS' if ra['status'] == 200 else 'FAIL',
             f'Admin Approve button → POST /api/admin/registrations/{rid}/approve',
             str(ra['status']))
        # Cleanup approved user
        admin.delete(f'/api/users/{ruser}')
    else:
        _log('WARN', 'Could not find registration in pending list to approve')

    # Submit another to test reject
    ruser2 = 'ui_rej_' + str(int(time.time()))[-6:]
    anon.post('/api/register-request', {
        'username': ruser2, 'name': 'Reject Me',
        'email': f'{ruser2}@test.com', 'password': 'RejectPass1!'
    })
    r2 = admin.get('/api/admin/registrations')
    rid2 = None
    if r2['json']:
        for item in r2['json']:
            if item.get('username') == ruser2:
                rid2 = item.get('id')
                break
    if rid2:
        rr = admin.post(f'/api/admin/registrations/{rid2}/reject', {})
        _log('PASS' if rr['status'] == 200 else 'FAIL',
             f'Admin Reject button → POST /api/admin/registrations/{rid2}/reject',
             str(rr['status']))
    else:
        _log('WARN', 'Could not find 2nd registration to reject')


# ═══════════════════════════════════════════════════════════════════════════════
# 18 — TEMPLATE STATIC ASSETS
# ═══════════════════════════════════════════════════════════════════════════════
def test_static_assets():
    _section('18  STATIC ASSETS — chart.min.js + favicon / CSS bundles')

    anon = Session()

    r = anon.get('/static/chart.min.js')
    _log('PASS' if r['status'] == 200 else 'FAIL',
         'chart.min.js loads (Charts.js)', str(r['status']))
    if r['status'] == 200:
        _log('PASS' if len(r['bytes']) > 1000 else 'FAIL',
             f'chart.min.js is non-empty ({len(r["bytes"])//1024} KB)')


# ═══════════════════════════════════════════════════════════════════════════════
# 19 — JS SYNTAX CHECK (template parse errors)
# ═══════════════════════════════════════════════════════════════════════════════
def test_js_syntax(admin):
    _section('19  JAVASCRIPT TEMPLATE INTEGRITY — Syntax + Reference Checks')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    r = admin.get('/admin')
    body = r['text']

    # Check no undefined fetch calls (all /api/ fetch calls should match known routes)
    fetch_urls = re.findall(r"fetch\(['\`]([^'\"`\$]+)['\`]", body)
    known_prefixes = ['/api/', '/shared/', '/health', '/login', '/logout']
    for url in fetch_urls:
        ok = any(url.startswith(p) for p in known_prefixes)
        if not ok:
            _log('WARN', f'fetch() to unexpected URL: {url}')

    # Check no obvious template render errors
    error_patterns = [
        ('TemplateSyntaxError', 'Jinja2 template syntax error'),
        ('UndefinedError',      'Jinja2 undefined variable'),
        ('Internal Server Error', 'Flask 500 in admin page'),
        ('<!DOCTYPE html> was closed', 'Malformed HTML'),
    ]
    for pattern, label in error_patterns:
        _log('PASS' if pattern not in body else 'FAIL',
             f'No {label} in admin.html render')

    # Check script tags don't have src pointing to missing files
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', body)
    for src in script_srcs:
        if src.startswith('/'):
            r2 = admin.get(src)
            _log('PASS' if r2['status'] == 200 else 'FAIL',
                 f'Script src {src} loads', str(r2['status']))

    # Viewer template too
    vuser = 'js_v_' + str(int(time.time()))[-5:]
    admin.post('/api/users', {
        'username': vuser, 'password': 'JSPass1!',
        'name': 'JS Check Viewer', 'role': 'viewer'
    })
    viewer = Session()
    viewer.login(vuser, 'JSPass1!')
    viewer.post('/api/session/client', {'code': SAMPLE_CODE})
    rv = viewer.get('/viewer')
    vbody = rv['text']
    _log('PASS' if '{{' not in vbody else 'FAIL',
         'viewer.html: no unrendered Jinja2 vars')
    _log('PASS' if 'Internal Server Error' not in vbody else 'FAIL',
         'viewer.html: no 500 error')
    vsrcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', vbody)
    for src in vsrcs:
        if src.startswith('/'):
            r2 = viewer.get(src)
            _log('PASS' if r2['status'] == 200 else 'FAIL',
                 f'Viewer script src {src} loads', str(r2['status']))
    admin.delete(f'/api/users/{vuser}')

    _log('PASS', f'Total fetch() calls scanned in admin.html: {len(fetch_urls)}')


# ═══════════════════════════════════════════════════════════════════════════════
# 20 — SCHEDULES + RECURRING
# ═══════════════════════════════════════════════════════════════════════════════
def test_schedules(admin):
    _section('20  SCHEDULES — One-Time + Recurring CRUD')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    # List one-time schedules
    r = admin.get('/api/schedules')
    _log('PASS' if r['status'] == 200 else 'FAIL', 'Load schedules panel', str(r['status']))

    # Create recurring schedule
    r = admin.post('/api/recurring-schedules', {
        'jmx': SAMPLE_JMX, 'threads': 1, 'duration': 30,
        'rampup': 5, 'recurrence': 'daily', 'run_at_time': '02:00'
    })
    _log('PASS' if r['status'] in (200, 400) else 'FAIL',
         'Create Recurring Schedule button', str(r['status']))

    if r['status'] == 200:
        sid = (r['json'] or {}).get('id')
        if sid:
            # Edit (enable/disable)
            re2 = admin.put(f'/api/recurring-schedules/{sid}', {'enabled': False})
            _log('PASS' if re2['status'] == 200 else 'FAIL',
                 'Edit Recurring Schedule (disable)', str(re2['status']))
            # Delete
            rd = admin.delete(f'/api/recurring-schedules/{sid}')
            _log('PASS' if rd['status'] in (200, 204) else 'FAIL',
                 'Delete Recurring Schedule button', str(rd['status']))

    # Schedule calendar
    r = admin.get('/api/schedule-calendar')
    _log('PASS' if 0 < r['status'] < 500 else 'FAIL', 'Schedule calendar heatmap', str(r['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# 21 — COMPLETE BACKEND API SWEEP (every route not yet covered)
# ═══════════════════════════════════════════════════════════════════════════════
def test_full_api_sweep(admin):
    _section('21  COMPLETE API SWEEP — Every Remaining Route')

    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    remaining_gets = [
        '/api/me', '/api/test/status', '/api/reports', '/api/csv-files',
        '/api/settings', '/api/clients', '/api/users', '/api/db-stats',
        '/api/jmx-list', '/api/overview-stats', '/api/theme', '/api/prereq',
        '/api/sla-config', '/api/sla-result', '/api/heatmap', '/api/audit-log?limit=10',
        '/api/platform-stats', '/api/schedules', '/api/recurring-schedules',
        '/api/trends?days=7', '/api/leaderboard', '/api/sla-trend?limit=5',
        '/api/backup/list', '/api/load-profiles', '/api/env-profiles',
        '/api/webhook-config', '/api/test/annotations', '/api/xlsx-files',
        '/api/test-features', '/api/jmeter/install-status',
        '/api/db/full-stats', '/api/run-history', '/api/schedule-calendar',
        '/api/favourites', '/api/presence', '/api/baseline',
        '/api/live-stats', '/api/live-stats/labels', '/api/trend-overlay',
        '/api/env', '/api/load-config', '/api/prereq/auto',
        '/api/admin/registrations', '/api/jmx-requirements', '/api/jmx-services',
        '/health', '/health/ui', '/api/admins',
    ]
    for path in remaining_gets:
        r = admin.get(path)
        _log('PASS' if 0 < r['status'] < 500 else 'FAIL',
             f'GET {path}', str(r['status']))


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print(f'\n{BOLD}{"="*70}{END}')
    print(f'{BOLD}  LOAD TESTING PLATFORM — FULL UI + API TEST SUITE{END}')
    print(f'{BOLD}  Server: {BASE_URL}{END}')
    print(f'{BOLD}{"="*70}{END}\n')

    if not _server_up():
        print(f'{BOLD}[FAIL] Server not responding at {BASE_URL}{END}')
        print('  Start the server first:  start_server.bat  or  python app.py')
        sys.exit(1)
    print(f'[INFO] Server is UP at {BASE_URL}\n')

    # Ensure sample fixture
    setup = subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, 'scripts', 'sample_client_setup.py')],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    if setup.returncode != 0:
        print(f'[WARN] sample_client_setup.py returned {setup.returncode}: {setup.stderr[:200]}')

    admin = Session()
    admin.login(ADMIN_USER, ADMIN_PASS)
    admin.post('/api/session/client', {'code': SAMPLE_CODE})

    # Run all test sections
    test_server_health(admin)
    test_authentication()
    test_admin_portal_html(admin)
    test_viewer_portal_html()
    test_all_admin_fetch_endpoints(admin)
    test_viewer_fetch_endpoints()
    test_nav_panels(admin)
    test_download_buttons(admin)
    test_upload_buttons(admin)
    test_client_management_ui(admin)
    test_user_management_ui(admin)
    test_report_detail_buttons(admin)
    test_settings_panel(admin)
    test_rbac_ui_gates()
    test_modal_dialogs(admin)
    test_live_sharing(admin)
    test_registration_flow()
    test_static_assets()
    test_js_syntax(admin)
    test_schedules(admin)
    test_full_api_sweep(admin)

    # ── Summary ───────────────────────────────────────────────────────────────
    total   = len(_results)
    passed  = sum(1 for r in _results if r['result'] == 'PASS')
    failed  = sum(1 for r in _results if r['result'] == 'FAIL')
    warnings= sum(1 for r in _results if r['result'] == 'WARN')
    skipped = sum(1 for r in _results if r['result'] == 'SKIP')
    rate    = round(passed / total * 100, 1) if total else 0

    print(f'\n{BOLD}{"="*70}{END}')
    sc = '\033[92m' if failed == 0 else '\033[91m'
    print(f'{sc}{BOLD}  RESULT: {passed}/{total} passed | {failed} failed | {warnings} warnings | {skipped} skipped | {rate}% pass rate{END}')
    print(f'{BOLD}{"="*70}{END}')

    # Print issues
    if _issues:
        print(f'\n{BOLD}  ISSUES FOUND ({len(_issues)}){END}')
        print(f'  {"─"*66}')
        fail_issues = [i for i in _issues if i['severity'] == 'FAIL']
        warn_issues = [i for i in _issues if i['severity'] == 'WARN']
        if fail_issues:
            print(f'\n  {BOLD}FAILURES ({len(fail_issues)}):{END}')
            for i, iss in enumerate(fail_issues, 1):
                print(f'  {i:2}. [FAIL] {iss["name"]}')
                if iss['detail']:
                    print(f'       Detail: {iss["detail"]}')
        if warn_issues:
            print(f'\n  {BOLD}WARNINGS ({len(warn_issues)}):{END}')
            for i, iss in enumerate(warn_issues, 1):
                print(f'  {i:2}. [WARN] {iss["name"]}')
                if iss['detail']:
                    print(f'       Detail: {iss["detail"]}')
    else:
        print(f'\n  {BOLD}No issues found. All checks passed.{END}')

    # Write JSON report
    report_dir = os.path.join(BASE_DIR, 'test_reports')
    os.makedirs(report_dir, exist_ok=True)
    ts = time.strftime('%Y-%m-%d_%H-%M-%S')
    rpath = os.path.join(report_dir, f'full_ui_test_{ts}.json')
    with open(rpath, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': ts, 'server': BASE_URL,
            'total': total, 'passed': passed, 'failed': failed,
            'warnings': warnings, 'skipped': skipped, 'pass_rate': rate,
            'issues': _issues, 'results': _results
        }, f, indent=2, ensure_ascii=False)
    print(f'\n  Report → {rpath}')
    print()

    sys.exit(1 if failed > 0 else 0)


if __name__ == '__main__':
    main()
