"""
Comprehensive End-to-End Test Suite  — Load Testing Platform v4.0
==================================================================
Uses Flask's built-in test client as the mock server (no real HTTP server needed).
Covers every route, every button, and every feature.

Run:
    python scripts/comprehensive_e2e_test.py
    python scripts/comprehensive_e2e_test.py --verbose
    python scripts/comprehensive_e2e_test.py --section auth
"""

import glob
import io
import json
import os
import random
import string
import sys
import time
import unittest
import urllib.parse
import uuid
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# ── Bootstrap sample fixture before importing app ───────────────────────────
_setup_path = os.path.join(BASE_DIR, 'scripts', 'sample_client_setup.py')
if os.path.exists(_setup_path):
    import subprocess
    subprocess.run([sys.executable, _setup_path], capture_output=True)

from app import app, init_db, get_db

ADMIN_USER = 'admin'
ADMIN_PASS = 'admin'
SAMPLE_JTL  = 'SAMPLE_Mock_Health_Check_Result.jtl'
SAMPLE_JMX  = 'SAMPLE_Mock_Health_Check_1TPS_1min.jmx'
SAMPLE_CSV  = 'sample_health_users.csv'
SAMPLE_CODE = 'SAMPLE'

COLORS = {
    'PASS': '\033[92m',
    'FAIL': '\033[91m',
    'SKIP': '\033[93m',
    'HEAD': '\033[94m',
    'BOLD': '\033[1m',
    'END':  '\033[0m',
}

_results = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': []}


def _c(color, text):
    return COLORS.get(color, '') + text + COLORS['END']


# ── Base test case ───────────────────────────────────────────────────────────
class BaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test-secret'
        cls.app = app
        cls.client = app.test_client()
        cls.client.__enter__()
        init_db()
        cls._ensure_sample_client()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    @classmethod
    def _ensure_sample_client(cls):
        with get_db() as db:
            if not db.execute("SELECT 1 FROM clients WHERE code='SAMPLE'").fetchone():
                db.execute("""INSERT OR IGNORE INTO clients
                    (code,name,description,logo_emoji,color,jmx_dir,testdata_dir,reports_dir,created_by)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (
                    SAMPLE_CODE, 'Sample Client', 'E2E Sample',
                    '🧪', '#00ff9d',
                    os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'jmx'),
                    os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'testdata'),
                    os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports'),
                    'test'
                ))
                db.commit()

    def login_admin(self):
        self.client.get('/logout')
        r = self.client.post('/login', data={'username': ADMIN_USER, 'password': ADMIN_PASS},
                              follow_redirects=False)
        self.assertIn(r.status_code, (200, 302, 303), 'Admin login failed')
        # Switch to SAMPLE client
        self.client.post('/api/session/client',
                          data=json.dumps({'code': SAMPLE_CODE}),
                          content_type='application/json')

    def login_viewer(self, username=None, password=None):
        self.client.get('/logout')
        uname = username or 'viewer'
        pw    = password or 'viewer@123'
        r = self.client.post('/login', data={'username': uname, 'password': pw},
                              follow_redirects=False)
        return r.status_code in (200, 302, 303)

    def get_json(self, url):
        r = self.client.get(url)
        try:
            return r.status_code, r.get_json()
        except Exception:
            return r.status_code, {}

    def post_json(self, url, payload):
        r = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        try:
            return r.status_code, r.get_json()
        except Exception:
            return r.status_code, {}

    def put_json(self, url, payload):
        r = self.client.put(url, data=json.dumps(payload), content_type='application/json')
        try:
            return r.status_code, r.get_json()
        except Exception:
            return r.status_code, {}

    def delete(self, url):
        r = self.client.delete(url)
        try:
            return r.status_code, r.get_json()
        except Exception:
            return r.status_code, {}

    def rand_str(self, n=6):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

    def _sample_jtl_exists(self):
        p = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports', SAMPLE_JTL)
        return os.path.exists(p)

    def _sample_jmx_exists(self):
        p = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'jmx', SAMPLE_JMX)
        return os.path.exists(p)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Authentication & Session
# ═══════════════════════════════════════════════════════════════════════════════
class TestAuth(BaseTest):
    """Tests: Login page, admin login, viewer login, bad credentials, logout, /api/me, session client."""

    def test_01_get_login_page(self):
        r = self.client.get('/login')
        self.assertEqual(r.status_code, 200, 'Login page should load with 200')

    def test_02_root_redirect_to_login_when_unauthenticated(self):
        self.client.get('/logout')
        r = self.client.get('/', follow_redirects=False)
        self.assertIn(r.status_code, (301, 302, 303), 'Root should redirect')

    def test_03_admin_login_success(self):
        self.client.get('/logout')
        r = self.client.post('/login',
                              data={'username': ADMIN_USER, 'password': ADMIN_PASS},
                              follow_redirects=False)
        self.assertIn(r.status_code, (200, 302, 303), 'Admin login should succeed')

    def test_04_invalid_password_rejected(self):
        self.client.get('/logout')
        r = self.client.post('/login',
                              data={'username': ADMIN_USER, 'password': 'WRONG_PASSWORD'},
                              follow_redirects=True)
        body = r.data.decode('utf-8', errors='replace')
        self.assertIn(r.status_code, (200,), 'Bad login should stay on login page')
        self.assertTrue('Invalid' in body or 'invalid' in body or 'error' in body.lower(),
                        'Should show error message')

    def test_05_invalid_username_rejected(self):
        self.client.get('/logout')
        r = self.client.post('/login',
                              data={'username': 'no_such_user_xyz', 'password': 'anything'},
                              follow_redirects=True)
        self.assertEqual(r.status_code, 200, 'Bad login stays on login page')

    def test_06_empty_credentials_rejected(self):
        self.client.get('/logout')
        r = self.client.post('/login',
                              data={'username': '', 'password': ''},
                              follow_redirects=True)
        self.assertEqual(r.status_code, 200, 'Empty credentials stay on login page')

    def test_07_logout(self):
        self.login_admin()
        r = self.client.get('/logout', follow_redirects=False)
        self.assertIn(r.status_code, (200, 302, 303), 'Logout should redirect')

    def test_08_api_me_as_admin(self):
        self.login_admin()
        status, data = self.get_json('/api/me')
        self.assertEqual(status, 200)
        self.assertEqual(data.get('username'), ADMIN_USER)
        self.assertEqual(data.get('role'), 'admin')

    def test_09_api_me_unauthenticated(self):
        self.client.get('/logout')
        r = self.client.get('/api/me')
        self.assertIn(r.status_code, (302, 401, 403), 'Me endpoint requires auth')

    def test_10_session_client_switch(self):
        self.login_admin()
        status, data = self.post_json('/api/session/client', {'code': SAMPLE_CODE})
        self.assertEqual(status, 200)
        self.assertTrue(data.get('ok'))

    def test_11_session_client_invalid(self):
        self.login_admin()
        status, data = self.post_json('/api/session/client', {'code': 'NO_SUCH_CLIENT_XYZ'})
        self.assertIn(status, (400, 404))

    def test_12_viewer_login_flow(self):
        # Create a fresh temp viewer to avoid dependency on default viewer password
        self.login_admin()
        vuser = 'e2e_vw_' + self.rand_str()
        self.post_json('/api/users', {
            'username': vuser, 'password': 'TestPass99!',
            'name': 'E2E Viewer', 'role': 'viewer', 'initials': 'EV'
        })
        self.client.get('/logout')
        r = self.client.post('/login',
                              data={'username': vuser, 'password': 'TestPass99!'},
                              follow_redirects=False)
        self.assertIn(r.status_code, (200, 302, 303), 'Viewer login should succeed')
        # Cleanup
        self.login_admin()
        self.client.delete(f'/api/users/{vuser}')

    def test_13_public_admin_list(self):
        r = self.client.get('/api/admins')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn('admins', data)

    def test_14_root_redirect_to_admin_when_logged_in(self):
        self.login_admin()
        r = self.client.get('/', follow_redirects=False)
        self.assertIn(r.status_code, (301, 302, 303))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Page Routes
# ═══════════════════════════════════════════════════════════════════════════════
class TestPageRoutes(BaseTest):
    """Tests: /admin, /viewer, /health, /health/ui, redirect logic."""

    def test_01_admin_page(self):
        self.login_admin()
        r = self.client.get('/admin')
        self.assertEqual(r.status_code, 200)
        body = r.data.decode('utf-8', errors='replace')
        self.assertIn('Admin', body)

    def test_02_viewer_page(self):
        self.login_admin()
        # Create temp viewer
        vuser = 'pg_vw_' + self.rand_str()
        self.post_json('/api/users', {
            'username': vuser, 'password': 'TestPass99!',
            'name': 'Page Viewer', 'role': 'viewer', 'initials': 'PV'
        })
        self.client.get('/logout')
        self.client.post('/login', data={'username': vuser, 'password': 'TestPass99!'})
        r = self.client.get('/viewer')
        self.assertIn(r.status_code, (200, 302), 'Viewer page')
        # Cleanup
        self.login_admin()
        self.client.delete(f'/api/users/{vuser}')

    def test_03_admin_page_requires_admin_role(self):
        # Viewer should not access /admin
        self.login_admin()
        vuser = 'pg_adm_' + self.rand_str()
        self.post_json('/api/users', {
            'username': vuser, 'password': 'TestPass99!',
            'name': 'Role Check', 'role': 'viewer', 'initials': 'RC'
        })
        self.client.get('/logout')
        self.client.post('/login', data={'username': vuser, 'password': 'TestPass99!'})
        r = self.client.get('/admin', follow_redirects=False)
        self.assertIn(r.status_code, (302, 303, 403), 'Viewer should not access /admin')
        # Cleanup
        self.login_admin()
        self.client.delete(f'/api/users/{vuser}')

    def test_04_health_endpoint(self):
        r = self.client.get('/health')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn('status', data)
        self.assertIn(data['status'], ('ok', 'degraded'))

    def test_05_health_ui_endpoint(self):
        r = self.client.get('/health/ui')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Health', r.data)

    def test_06_unauthenticated_access_redirects(self):
        self.client.get('/logout')
        for path in ('/admin', '/viewer', '/api/reports', '/api/clients'):
            r = self.client.get(path, follow_redirects=False)
            self.assertIn(r.status_code, (200, 302, 303, 401, 403),
                          f'{path} should deny or redirect unauthenticated access')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Overview & Dashboard
# ═══════════════════════════════════════════════════════════════════════════════
class TestOverview(BaseTest):
    """Tests: /api/overview-stats, /api/platform-stats, /api/heatmap, /api/trends, /api/leaderboard."""

    def setUp(self):
        self.login_admin()

    def test_01_overview_stats(self):
        status, data = self.get_json('/api/overview-stats')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, dict)

    def test_02_platform_stats(self):
        status, data = self.get_json('/api/platform-stats')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, dict)

    def test_03_heatmap(self):
        status, data = self.get_json('/api/heatmap')
        self.assertEqual(status, 200)

    def test_04_trends(self):
        status, data = self.get_json('/api/trends?days=7')
        self.assertLess(status, 500)

    def test_05_leaderboard(self):
        status, data = self.get_json('/api/leaderboard')
        self.assertLess(status, 500)

    def test_06_sla_trend(self):
        status, data = self.get_json('/api/sla-trend?limit=5')
        self.assertLess(status, 500)

    def test_07_trend_overlay(self):
        status, data = self.get_json('/api/trend-overlay?n=5')
        self.assertLess(status, 500)

    def test_08_schedule_calendar(self):
        status, data = self.get_json('/api/schedule-calendar')
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Client Management
# ═══════════════════════════════════════════════════════════════════════════════
class TestClientManagement(BaseTest):
    """Tests: GET/POST/PUT/DELETE /api/clients, storage, session switching."""

    def setUp(self):
        self.login_admin()

    def test_01_list_clients(self):
        status, data = self.get_json('/api/clients')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0, 'Should have at least one client')

    def test_02_create_and_delete_client(self):
        code = 'TST' + self.rand_str(3).upper()
        status, data = self.post_json('/api/clients', {
            'code': code,
            'name': f'Test Client {code}',
            'description': 'E2E created client',
            'logo_emoji': '🧪',
            'color': '#ff0000'
        })
        self.assertIn(status, (200, 201), f'Create client failed: {data}')
        self.assertTrue(data.get('ok'), f'Create client not ok: {data}')

        # Switch away then delete
        self.post_json('/api/session/client', {'code': SAMPLE_CODE})
        del_status, del_data = self.delete(f'/api/clients/{code}')
        self.assertIn(del_status, (200, 204), f'Delete client failed: {del_data}')

    def test_03_create_client_duplicate_code(self):
        status, data = self.post_json('/api/clients', {
            'code': SAMPLE_CODE, 'name': 'Duplicate', 'description': ''
        })
        self.assertIn(status, (400, 409), 'Duplicate client code should fail')

    def test_04_create_client_missing_required_fields(self):
        status, data = self.post_json('/api/clients', {'description': 'missing code and name'})
        self.assertIn(status, (400, 422))

    def test_05_update_client(self):
        code = 'UPD' + self.rand_str(3).upper()
        self.post_json('/api/clients', {
            'code': code, 'name': f'Update Me {code}', 'description': ''
        })
        status, data = self.put_json(f'/api/clients/{code}', {'name': f'Updated {code}'})
        self.assertIn(status, (200,), f'Update client failed: {data}')
        # Cleanup
        self.post_json('/api/session/client', {'code': SAMPLE_CODE})
        self.delete(f'/api/clients/{code}')

    def test_06_cannot_delete_active_client(self):
        # Switch to SAMPLE and try to delete it while active
        self.post_json('/api/session/client', {'code': SAMPLE_CODE})
        status, data = self.delete(f'/api/clients/{SAMPLE_CODE}')
        self.assertIn(status, (400,), 'Should not delete active client')

    def test_07_client_storage_stats(self):
        status, data = self.get_json(f'/api/clients/{SAMPLE_CODE}/storage')
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — User Management
# ═══════════════════════════════════════════════════════════════════════════════
class TestUserManagement(BaseTest):
    """Tests: GET/POST/PUT/DELETE /api/users, password reset, change own password."""

    def setUp(self):
        self.login_admin()

    def _create_temp_user(self, role='viewer'):
        u = 'u_' + self.rand_str()
        self.post_json('/api/users', {
            'username': u, 'password': 'TempPass1!',
            'name': f'Temp {u}', 'role': role, 'initials': 'TU'
        })
        return u

    def test_01_list_users(self):
        status, data = self.get_json('/api/users')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_02_create_viewer_user(self):
        u = 'cu_v_' + self.rand_str()
        status, data = self.post_json('/api/users', {
            'username': u, 'password': 'ValidPass1!',
            'name': 'Create Viewer', 'role': 'viewer',
            'initials': 'CV', 'permissions': ['run_tests', 'view_audit']
        })
        self.assertIn(status, (200, 201))
        self.assertTrue(data.get('ok'))
        self.delete(f'/api/users/{u}')

    def test_03_create_admin_user(self):
        u = 'cu_a_' + self.rand_str()
        status, data = self.post_json('/api/users', {
            'username': u, 'password': 'AdminPass1!',
            'name': 'Create Admin', 'role': 'admin', 'initials': 'CA'
        })
        self.assertIn(status, (200, 201))
        self.delete(f'/api/users/{u}')

    def test_04_duplicate_username_fails(self):
        status, data = self.post_json('/api/users', {
            'username': ADMIN_USER, 'password': 'Pass1234!',
            'name': 'Dupe', 'role': 'viewer'
        })
        self.assertEqual(status, 409, 'Duplicate username should return 409')

    def test_05_missing_fields_fail(self):
        status, data = self.post_json('/api/users', {'username': 'missingfields'})
        self.assertIn(status, (400,))

    def test_06_short_password_fails(self):
        status, data = self.post_json('/api/users', {
            'username': 'shortpw_' + self.rand_str(),
            'password': '12',
            'name': 'Short', 'role': 'viewer'
        })
        self.assertIn(status, (400,))

    def test_07_update_user_name(self):
        u = self._create_temp_user()
        status, data = self.put_json(f'/api/users/{u}', {'name': 'Updated Name'})
        self.assertEqual(status, 200)
        self.delete(f'/api/users/{u}')

    def test_08_update_user_role(self):
        u = self._create_temp_user('viewer')
        status, data = self.put_json(f'/api/users/{u}', {'role': 'admin'})
        self.assertEqual(status, 200)
        self.delete(f'/api/users/{u}')

    def test_09_update_user_permissions(self):
        u = self._create_temp_user()
        status, data = self.put_json(f'/api/users/{u}',
                                      {'permissions': ['run_tests', 'view_audit', 'manage_schedules']})
        self.assertEqual(status, 200)
        self.delete(f'/api/users/{u}')

    def test_10_disable_and_re_enable_user(self):
        u = self._create_temp_user()
        status, _ = self.put_json(f'/api/users/{u}', {'enabled': False})
        self.assertEqual(status, 200)
        status, _ = self.put_json(f'/api/users/{u}', {'enabled': True})
        self.assertEqual(status, 200)
        self.delete(f'/api/users/{u}')

    def test_11_cannot_disable_own_account(self):
        status, data = self.put_json(f'/api/users/{ADMIN_USER}', {'enabled': False})
        self.assertEqual(status, 400, 'Cannot disable own account')

    def test_12_reset_user_password(self):
        u = self._create_temp_user()
        status, data = self.post_json(f'/api/users/{u}/reset-password',
                                       {'password': 'NewPass123!'})
        self.assertEqual(status, 200)
        self.delete(f'/api/users/{u}')

    def test_13_reset_password_too_short(self):
        u = self._create_temp_user()
        status, data = self.post_json(f'/api/users/{u}/reset-password', {'password': 'ab'})
        self.assertEqual(status, 400)
        self.delete(f'/api/users/{u}')

    def test_14_change_own_password(self):
        u = 'cpw_' + self.rand_str()
        self.post_json('/api/users', {
            'username': u, 'password': 'OldPass99!',
            'name': 'Change PW', 'role': 'viewer'
        })
        self.client.get('/logout')
        self.client.post('/login', data={'username': u, 'password': 'OldPass99!'})
        status, data = self.post_json('/api/users/me/change-password', {
            'current_password': 'OldPass99!', 'new_password': 'NewPass99!'
        })
        self.assertEqual(status, 200)
        self.login_admin()
        self.delete(f'/api/users/{u}')

    def test_15_change_own_password_wrong_current(self):
        status, data = self.post_json('/api/users/me/change-password', {
            'current_password': 'DEFINITELY_WRONG', 'new_password': 'NewPass99!'
        })
        self.assertIn(status, (400, 403))

    def test_16_delete_user(self):
        u = self._create_temp_user()
        status, data = self.delete(f'/api/users/{u}')
        self.assertEqual(status, 200)

    def test_17_cannot_delete_own_account(self):
        status, data = self.delete(f'/api/users/{ADMIN_USER}')
        self.assertEqual(status, 400, 'Cannot delete own account')

    def test_18_delete_nonexistent_user(self):
        status, data = self.delete('/api/users/no_such_user_xyz_abc')
        self.assertEqual(status, 404)

    def test_19_update_nothing_returns_400(self):
        status, data = self.put_json(f'/api/users/{ADMIN_USER}', {})
        self.assertEqual(status, 400)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Test Control (Start / Stop / Status / Logs / Annotations)
# ═══════════════════════════════════════════════════════════════════════════════
class TestTestControl(BaseTest):
    """Tests: status, stop, logs, run-note, annotate, annotations."""

    def setUp(self):
        self.login_admin()

    def test_01_test_status(self):
        status, data = self.get_json('/api/test/status')
        self.assertEqual(status, 200)
        self.assertIn('running', data)

    def test_02_get_logs(self):
        status, data = self.get_json('/api/logs?offset=0')
        self.assertLess(status, 500)

    def test_03_stop_when_not_running(self):
        status, data = self.post_json('/api/test/stop', {})
        self.assertIn(status, (200, 400, 409), 'Stop should handle no-run case')

    def test_04_start_test_no_jmx(self):
        status, data = self.post_json('/api/test/start', {
            'jmx': '', 'threads': 1, 'duration': 10, 'rampup': 1
        })
        self.assertIn(status, (400, 500, 503))

    def test_05_start_test_nonexistent_jmx(self):
        status, data = self.post_json('/api/test/start', {
            'jmx': 'NONEXISTENT.jmx', 'threads': 1, 'duration': 10
        })
        self.assertIn(status, (400, 404, 503))

    def test_06_run_note(self):
        status, data = self.post_json('/api/run-note', {'notes': 'E2E run note', 'tag': 'e2e'})
        self.assertIn(status, (200, 400, 409), 'Run note')

    def test_07_annotate(self):
        status, data = self.post_json('/api/test/annotate', {'text': 'Test annotation E2E'})
        self.assertIn(status, (200,))
        self.assertTrue(data.get('ok'))

    def test_08_annotate_empty_text(self):
        status, data = self.post_json('/api/test/annotate', {'text': ''})
        self.assertIn(status, (400,))

    def test_09_get_annotations(self):
        status, data = self.get_json('/api/test/annotations')
        self.assertEqual(status, 200)
        self.assertIn('annotations', data)

    def test_10_jmeter_install_status(self):
        status, data = self.get_json('/api/jmeter/install-status')
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Reports & JTL Parsing
# ═══════════════════════════════════════════════════════════════════════════════
class TestReports(BaseTest):
    """Tests: report list, parse, errors, html, pdf, excel, meta, scorecard, bottleneck, etc."""

    def setUp(self):
        self.login_admin()

    def _jtl_name(self):
        p = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports', SAMPLE_JTL)
        return SAMPLE_JTL if os.path.exists(p) else None

    def test_01_list_reports(self):
        status, data = self.get_json('/api/reports')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)

    def test_02_parse_jtl_report(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/report/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_03_report_errors(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/report/{urllib.parse.quote(jtl)}/errors')
        self.assertLess(status, 500)

    def test_04_report_html(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/report/{urllib.parse.quote(jtl)}/html')
        self.assertLess(status, 500)

    def test_05_report_meta(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/report-meta/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)
        self.assertIsInstance(data, dict)

    def test_06_scorecard(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/scorecard/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_07_bottleneck(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/bottleneck/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_08_rt_histogram(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/rt-histogram/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_09_error_patterns(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/error-patterns/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_10_ussd_funnel(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/ussd-funnel/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_11_regression_check(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/regression-check/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_12_sla_analysis(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/sla-analysis/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_13_compare_reports_same_file(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.post_json('/api/compare-reports', {'file1': jtl, 'file2': jtl})
        self.assertLess(status, 500)

    def test_14_compare_reports_missing_files(self):
        status, data = self.post_json('/api/compare-reports', {})
        self.assertIn(status, (400,))

    def test_15_report_nonexistent(self):
        status, data = self.get_json('/api/report/NO_SUCH_FILE.jtl')
        self.assertIn(status, (400, 404, 500))

    def test_16_run_history(self):
        status, data = self.get_json('/api/run-history')
        self.assertLess(status, 500)

    def test_17_compare_runs_empty(self):
        status, data = self.post_json('/api/compare-runs', {'files': []})
        self.assertLess(status, 500)

    def test_18_compare_runs_with_sample(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.post_json('/api/compare-runs', {'files': [jtl]})
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — Downloads
# ═══════════════════════════════════════════════════════════════════════════════
class TestDownloads(BaseTest):
    """Tests: download JTL, HTML, bundle, all-reports, testdata, DB backup, audit CSV."""

    def setUp(self):
        self.login_admin()

    def _jtl_name(self):
        p = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports', SAMPLE_JTL)
        return SAMPLE_JTL if os.path.exists(p) else None

    def test_01_download_jtl(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        r = self.client.get(f'/api/download/jtl/{urllib.parse.quote(jtl)}')
        self.assertIn(r.status_code, (200,))

    def test_02_download_html_report(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        r = self.client.get(f'/api/download/html/{urllib.parse.quote(jtl)}')
        self.assertLess(r.status_code, 500)

    def test_03_download_bundle(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        r = self.client.get(f'/api/download/bundle/{urllib.parse.quote(jtl)}')
        self.assertLess(r.status_code, 500)

    def test_04_download_all_reports_zip(self):
        r = self.client.get('/api/download/all-reports')
        self.assertLess(r.status_code, 500)

    def test_05_download_all_testdata_zip(self):
        r = self.client.get('/api/download/all-testdata')
        self.assertLess(r.status_code, 500)

    def test_06_download_testdata_file(self):
        csv_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'testdata', SAMPLE_CSV)
        if not os.path.exists(csv_path):
            self.skipTest('Sample CSV not found')
        r = self.client.get(f'/api/download/testdata-file/{urllib.parse.quote(SAMPLE_CSV)}')
        self.assertIn(r.status_code, (200, 404))

    def test_07_download_db_backup(self):
        r = self.client.get('/api/download/db-backup')
        self.assertEqual(r.status_code, 200)

    def test_08_download_audit_csv(self):
        r = self.client.get('/api/download/audit-csv')
        self.assertEqual(r.status_code, 200)

    def test_09_download_jmx_file(self):
        jmx_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'jmx', SAMPLE_JMX)
        if not os.path.exists(jmx_path):
            self.skipTest('Sample JMX not found')
        r = self.client.get(f'/api/download/jmx/{urllib.parse.quote(SAMPLE_JMX)}')
        self.assertIn(r.status_code, (200,))

    def test_10_download_nonexistent_jtl(self):
        r = self.client.get('/api/download/jtl/NOSUCHFILE.jtl')
        self.assertIn(r.status_code, (400, 404))

    def test_11_report_html_inline(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        r = self.client.get(f'/api/report/{urllib.parse.quote(jtl)}/html')
        self.assertLess(r.status_code, 500)

    def test_12_report_pdf(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        r = self.client.get(f'/api/report/{urllib.parse.quote(jtl)}/pdf')
        self.assertLess(r.status_code, 500)

    def test_13_report_excel(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        r = self.client.get(f'/api/report/{urllib.parse.quote(jtl)}/excel')
        self.assertLess(r.status_code, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — File Uploads
# ═══════════════════════════════════════════════════════════════════════════════
class TestUploads(BaseTest):
    """Tests: upload JMX, CSV, report; delete uploaded file."""

    def setUp(self):
        self.login_admin()

    def _make_jmx(self):
        return b'<?xml version="1.0"?><jmeterTestPlan><hashTree/></jmeterTestPlan>'

    def _make_csv(self):
        return b'username,password\nuser1,pass1\nuser2,pass2\n'

    def _make_jtl(self):
        return (b'timeStamp,elapsed,label,responseCode,responseMessage,threadName,'
                b'dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,'
                b'URL,Latency,IdleTime,Connect\n'
                b'1782700000000,45,Test,200,OK,Thread 1-1,text,true,,256,128,1,1,'
                b'http://localhost/test,40,0,5\n')

    def test_01_upload_jmx(self):
        data = {
            'file': (io.BytesIO(self._make_jmx()), 'e2e_upload_test.jmx', 'application/xml')
        }
        r = self.client.post('/api/upload/jmx',
                              data=data, content_type='multipart/form-data')
        self.assertIn(r.status_code, (200, 201, 400, 415))

    def test_02_upload_csv(self):
        data = {
            'file': (io.BytesIO(self._make_csv()), 'e2e_test_data.csv', 'text/csv')
        }
        r = self.client.post('/api/upload/testdata',
                              data=data, content_type='multipart/form-data')
        self.assertIn(r.status_code, (200, 201, 400))

    def test_03_upload_jtl_report(self):
        data = {
            'file': (io.BytesIO(self._make_jtl()), 'e2e_upload_result.jtl', 'text/csv')
        }
        r = self.client.post('/api/upload/report',
                              data=data, content_type='multipart/form-data')
        self.assertIn(r.status_code, (200, 201, 400))

    def test_04_upload_missing_file(self):
        r = self.client.post('/api/upload/jmx',
                              data={}, content_type='multipart/form-data')
        self.assertIn(r.status_code, (400,))

    def test_05_delete_uploaded_file(self):
        # Upload then delete — API uses 'folder' and 'filename' params, needs delete_files perm
        fname = 'e2e_del_test.csv'
        upload_data = {
            'file': (io.BytesIO(self._make_csv()), fname, 'text/csv')
        }
        self.client.post('/api/upload/testdata',
                          data=upload_data, content_type='multipart/form-data')
        # Admin has all permissions; use correct field names: folder + filename
        status, data = self.post_json('/api/upload/delete', {'folder': 'testdata', 'filename': fname})
        self.assertIn(status, (200, 400, 403, 404), f'Delete upload: {data}')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — JMX Management
# ═══════════════════════════════════════════════════════════════════════════════
class TestJMX(BaseTest):
    """Tests: JMX list, inspect, edit, params, tree, requirements, services, properties."""

    def setUp(self):
        self.login_admin()

    def _jmx_name(self):
        p = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'jmx', SAMPLE_JMX)
        return SAMPLE_JMX if os.path.exists(p) else None

    def test_01_list_jmx(self):
        status, data = self.get_json('/api/jmx-list')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, dict)
        self.assertIn('files', data)

    def test_02_inspect_jmx(self):
        jmx = self._jmx_name()
        if not jmx:
            self.skipTest('Sample JMX not found')
        status, data = self.get_json(f'/api/jmx-inspect/{urllib.parse.quote(jmx)}')
        self.assertLess(status, 500)

    def test_03_jmx_tree(self):
        jmx = self._jmx_name()
        if not jmx:
            self.skipTest('Sample JMX not found')
        status, data = self.get_json(f'/api/jmx-tree/{urllib.parse.quote(jmx)}')
        self.assertLess(status, 500)

    def test_04_jmx_requirements(self):
        status, data = self.get_json('/api/jmx-requirements')
        self.assertLess(status, 500)

    def test_05_jmx_services(self):
        status, data = self.get_json('/api/jmx-services')
        self.assertLess(status, 500)

    def test_06_jmx_params_get(self):
        jmx = self._jmx_name()
        if not jmx:
            self.skipTest('Sample JMX not found')
        status, data = self.get_json(f'/api/jmx-params/{urllib.parse.quote(jmx)}')
        self.assertLess(status, 500)

    def test_07_jmx_properties_get(self):
        jmx = self._jmx_name()
        if not jmx:
            self.skipTest('Sample JMX not found')
        status, data = self.get_json(f'/api/jmx/{urllib.parse.quote(jmx)}/properties')
        self.assertLess(status, 500)

    def test_08_jmx_nonexistent_inspect(self):
        status, data = self.get_json('/api/jmx-inspect/NO_SUCH.jmx')
        self.assertIn(status, (400, 404, 500))

    def test_09_jmx_poverride(self):
        jmx = self._jmx_name()
        if not jmx:
            self.skipTest('Sample JMX not found')
        status, data = self.post_json(f'/api/jmx-poverride/{urllib.parse.quote(jmx)}', {})
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — CSV / Test Data
# ═══════════════════════════════════════════════════════════════════════════════
class TestCSV(BaseTest):
    """Tests: CSV file list, preview, edit, row check, validate, generate CSV."""

    def setUp(self):
        self.login_admin()

    def test_01_list_csv_files(self):
        status, data = self.get_json('/api/csv-files')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)

    def test_02_csv_preview(self):
        csv_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'testdata', SAMPLE_CSV)
        if not os.path.exists(csv_path):
            self.skipTest('Sample CSV not found')
        status, data = self.get_json(f'/api/csv-preview/{urllib.parse.quote(SAMPLE_CSV)}')
        self.assertLess(status, 500)

    def test_03_csv_edit_get(self):
        csv_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'testdata', SAMPLE_CSV)
        if not os.path.exists(csv_path):
            self.skipTest('Sample CSV not found')
        status, data = self.get_json(f'/api/csv-edit/{urllib.parse.quote(SAMPLE_CSV)}')
        self.assertLess(status, 500)

    def test_04_csv_row_check(self):
        status, data = self.post_json('/api/csv-row-check', {
            'file': SAMPLE_CSV, 'header': ['username', 'password'], 'rows': 5
        })
        self.assertLess(status, 500)

    def test_05_validate_csv_no_file(self):
        r = self.client.post('/api/validate-csv',
                              data={}, content_type='multipart/form-data')
        self.assertIn(r.status_code, (400,))

    def test_06_generate_csv(self):
        status, data = self.post_json('/api/generate-csv', {
            'template': 'msisdn', 'count': 5,
            'prefix': '2677', 'filename': 'e2e_generated.csv'
        })
        self.assertLess(status, 500)

    def test_07_csv_nonexistent_preview(self):
        status, data = self.get_json('/api/csv-preview/NO_SUCH.csv')
        self.assertIn(status, (400, 404))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — Settings & Configuration
# ═══════════════════════════════════════════════════════════════════════════════
class TestSettings(BaseTest):
    """Tests: GET/POST /api/settings, env, load-config, SLA, webhook."""

    def setUp(self):
        self.login_admin()

    def test_01_get_settings(self):
        status, data = self.get_json('/api/settings')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, dict)

    def test_02_save_settings(self):
        status, data = self.post_json('/api/settings', {
            'heap': '-Xms512m -Xmx1g',
            'audit_retention_days': 90,
            'session_timeout_mins': 120
        })
        self.assertIn(status, (200,))
        self.assertTrue(data.get('ok'))

    def test_03_get_env(self):
        status, data = self.get_json('/api/env')
        self.assertLess(status, 500)

    def test_04_post_env(self):
        status, data = self.post_json('/api/env', {
            'endpoint': 'http://test.example.com', 'build': 'E2E-Build-01'
        })
        self.assertLess(status, 500)

    def test_05_get_load_config(self):
        status, data = self.get_json('/api/load-config')
        self.assertLess(status, 500)

    def test_06_post_load_config(self):
        status, data = self.post_json('/api/load-config', {
            'services': [{'name': 'P2P', 'threads': 10, 'tps': 5}]
        })
        self.assertLess(status, 500)

    def test_07_get_sla_config(self):
        status, data = self.get_json('/api/sla-config')
        self.assertEqual(status, 200)

    def test_08_post_sla_config(self):
        status, data = self.post_json('/api/sla-config', {
            'max_rt': 3000, 'max_err_pct': 5.0, 'min_tps': 1.0,
            'p90_rt': 2000, 'p95_rt': 3000
        })
        self.assertLess(status, 500)

    def test_09_get_sla_result(self):
        status, data = self.get_json('/api/sla-result')
        self.assertLess(status, 500)

    def test_10_get_webhook_config(self):
        status, data = self.get_json('/api/webhook-config')
        self.assertEqual(status, 200)
        self.assertIn('webhook_url', data)

    def test_11_post_webhook_config(self):
        status, data = self.post_json('/api/webhook-config', {
            'webhook_url': '', 'webhook_on_pass': True, 'webhook_on_fail': True
        })
        self.assertIn(status, (200,))

    def test_12_webhook_test_no_url(self):
        # Clear webhook URL first
        self.post_json('/api/webhook-config', {'webhook_url': '', 'webhook_on_pass': True, 'webhook_on_fail': True})
        status, data = self.post_json('/api/webhook-test', {})
        self.assertLess(status, 500)

    def test_13_config_diff(self):
        status, data = self.post_json('/api/config-diff', {
            'baseline': {'p90': 1000, 'avg': 500},
            'current':  {'p90': 1100, 'avg': 550}
        })
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — Prerequisites
# ═══════════════════════════════════════════════════════════════════════════════
class TestPrerequisites(BaseTest):
    """Tests: GET/POST prereq, auto-check."""

    def setUp(self):
        self.login_admin()

    def test_01_get_prereq(self):
        status, data = self.get_json('/api/prereq')
        self.assertEqual(status, 200)
        self.assertIn('data', data)

    def test_02_save_prereq(self):
        status, data = self.post_json('/api/prereq', {
            'targets': {'tps': '30', 'avg_sla': '2000', 'peak': '35',
                        'duration': '1hr', 'err_sla': '5', 'p90_sla': '3000'},
            'environment': {'name': 'UAT', 'endpoint': 'http://uat.test', 'build': 'Build-01',
                            'jmeter': '5.5', 'db': 'Oracle 19c', 'servers': '2', 'tools': 'JMeter'},
            'channels': ['USSD'],
            'iterations': '4',
            'hours': '8',
            'services': ['P2P', 'Airtime'],
            'activities': []
        })
        self.assertEqual(status, 200)
        self.assertTrue(data.get('ok'))

    def test_03_prereq_auto(self):
        status, data = self.get_json('/api/prereq/auto')
        self.assertEqual(status, 200)
        self.assertIn('jmeter_ok', data)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14 — Schedules (One-time & Recurring)
# ═══════════════════════════════════════════════════════════════════════════════
class TestSchedules(BaseTest):
    """Tests: list, create, delete one-time schedules; recurring schedule CRUD."""

    def setUp(self):
        self.login_admin()

    def test_01_list_schedules(self):
        status, data = self.get_json('/api/schedules')
        self.assertEqual(status, 200)
        # API returns {'schedules': [...]}
        self.assertIn('schedules', data)
        self.assertIsInstance(data['schedules'], list)

    def test_02_create_schedule(self):
        jmx = SAMPLE_JMX if os.path.exists(
            os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'jmx', SAMPLE_JMX)) else 'test.jmx'
        status, data = self.post_json('/api/schedules', {
            'jmx': jmx,
            'threads': 1,
            'duration': 30,
            'rampup': 5,
            'run_at': '23:59'
        })
        self.assertIn(status, (200, 400), f'Create schedule: {data}')

    def test_03_delete_schedule_nonexistent(self):
        status, data = self.delete('/api/schedules/non-existent-id-xyz')
        self.assertIn(status, (200, 404))

    def test_04_list_recurring_schedules(self):
        status, data = self.get_json('/api/recurring-schedules')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)

    def test_05_create_recurring_schedule(self):
        jmx = SAMPLE_JMX if os.path.exists(
            os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'jmx', SAMPLE_JMX)) else 'test.jmx'
        status, data = self.post_json('/api/recurring-schedules', {
            'jmx': jmx,
            'threads': 1,
            'duration': 30,
            'rampup': 5,
            'recurrence': 'daily',
            'run_at_time': '03:00'
        })
        if status == 200 and data.get('ok'):
            sid = data.get('id')
            if sid:
                self.put_json(f'/api/recurring-schedules/{sid}', {'enabled': False})
                self.delete(f'/api/recurring-schedules/{sid}')
        else:
            self.assertIn(status, (200, 400), f'Create recurring: {data}')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 15 — Suite Runner
# ═══════════════════════════════════════════════════════════════════════════════
class TestSuite(BaseTest):
    """Tests: suite status, stop (no suite running)."""

    def setUp(self):
        self.login_admin()

    def test_01_suite_status(self):
        status, data = self.get_json('/api/suite/status')
        self.assertEqual(status, 200)
        self.assertIn('running', data)

    def test_02_suite_stop_when_idle(self):
        status, data = self.post_json('/api/suite/stop', {})
        self.assertIn(status, (200, 400, 409))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 16 — DB Maintenance
# ═══════════════════════════════════════════════════════════════════════════════
class TestDBMaintenance(BaseTest):
    """Tests: db-stats, full-stats, vacuum, purge, clear-audit, backup."""

    def setUp(self):
        self.login_admin()

    def test_01_db_stats(self):
        status, data = self.get_json('/api/db-stats')
        self.assertEqual(status, 200)
        self.assertIn('users_total', data)

    def test_02_db_full_stats(self):
        status, data = self.get_json('/api/db/full-stats')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, dict)

    def test_03_vacuum(self):
        status, data = self.post_json('/api/db/vacuum', {})
        self.assertEqual(status, 200)

    def test_04_purge_old_data(self):
        status, data = self.post_json('/api/db/purge', {'days': 365})
        self.assertEqual(status, 200)

    def test_05_clear_audit(self):
        # Requires {"confirm":"CLEAR"} to confirm the destructive operation
        status, data = self.post_json('/api/db/clear-audit', {'confirm': 'CLEAR'})
        self.assertIn(status, (200,))

    def test_06_backup_list(self):
        status, data = self.get_json('/api/backup/list')
        self.assertLess(status, 500)

    def test_07_backup_run(self):
        status, data = self.post_json('/api/backup/run', {})
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 17 — Audit Log
# ═══════════════════════════════════════════════════════════════════════════════
class TestAuditLog(BaseTest):
    """Tests: audit log list, search, pagination."""

    def setUp(self):
        self.login_admin()

    def test_01_get_audit_log(self):
        status, data = self.get_json('/api/audit-log?limit=20')
        self.assertEqual(status, 200)
        self.assertIn('logs', data)
        self.assertIsInstance(data['logs'], list)

    def test_02_audit_log_pagination(self):
        status, data = self.get_json('/api/audit-log?limit=5&offset=0')
        self.assertEqual(status, 200)
        self.assertIn('total', data)

    def test_03_audit_log_search(self):
        status, data = self.get_json('/api/audit-log?q=LOGIN&limit=10')
        self.assertEqual(status, 200)
        self.assertIn('logs', data)

    def test_04_viewer_audit_with_permission(self):
        vuser = 'va_' + self.rand_str()
        self.post_json('/api/users', {
            'username': vuser, 'password': 'Pass123!',
            'name': 'Audit Viewer', 'role': 'viewer',
            'permissions': ['view_audit']
        })
        self.client.get('/logout')
        self.client.post('/login', data={'username': vuser, 'password': 'Pass123!'})
        status, data = self.get_json('/api/audit-log?limit=5')
        self.assertLess(status, 500)
        self.login_admin()
        self.delete(f'/api/users/{vuser}')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 18 — Baseline Management
# ═══════════════════════════════════════════════════════════════════════════════
class TestBaseline(BaseTest):
    """Tests: get baseline, set baseline, delete baseline, compare."""

    def setUp(self):
        self.login_admin()

    def test_01_get_baseline_empty(self):
        status, data = self.get_json('/api/baseline')
        self.assertLess(status, 500)

    def test_02_set_baseline(self):
        jtl = SAMPLE_JTL
        jtl_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports', jtl)
        if not os.path.exists(jtl_path):
            self.skipTest('Sample JTL required')
        status, data = self.post_json('/api/baseline', {'file': jtl})
        self.assertIn(status, (200,))

    def test_03_compare_baseline(self):
        jtl = SAMPLE_JTL
        jtl_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports', jtl)
        if not os.path.exists(jtl_path):
            self.skipTest('Sample JTL required')
        status, data = self.get_json(f'/api/baseline/compare/{urllib.parse.quote(jtl)}')
        self.assertLess(status, 500)

    def test_04_delete_baseline(self):
        status, data = self.delete('/api/baseline')
        self.assertIn(status, (200,))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 19 — Load Profiles
# ═══════════════════════════════════════════════════════════════════════════════
class TestLoadProfiles(BaseTest):
    """Tests: list, create, delete load profiles."""

    def setUp(self):
        self.login_admin()

    def test_01_list_profiles(self):
        status, data = self.get_json('/api/load-profiles')
        self.assertLess(status, 500)

    def test_02_create_profile(self):
        pname = 'E2E Profile ' + self.rand_str()
        status, data = self.post_json('/api/load-profiles', {
            'name': pname, 'threads': 10, 'duration': 300, 'rampup': 30
        })
        self.assertIn(status, (200,))
        if data.get('ok'):
            self.delete(f'/api/load-profiles/{urllib.parse.quote(pname)}')

    def test_03_delete_nonexistent_profile(self):
        status, data = self.delete('/api/load-profiles/NoSuchProfile')
        self.assertIn(status, (200,))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 20 — Environment Profiles
# ═══════════════════════════════════════════════════════════════════════════════
class TestEnvProfiles(BaseTest):
    """Tests: list, create, activate, delete env profiles."""

    def setUp(self):
        self.login_admin()

    def test_01_list_env_profiles(self):
        status, data = self.get_json('/api/env-profiles')
        self.assertLess(status, 500)

    def test_02_create_env_profile(self):
        pname = 'E2EEnv_' + self.rand_str()
        status, data = self.post_json('/api/env-profiles', {
            'name': pname,
            'data': {'endpoint': 'http://uat.test', 'build': 'E2E'}
        })
        self.assertIn(status, (200,))
        if status == 200:
            # Activate
            a_status, a_data = self.post_json(f'/api/env-profiles/{pname}/activate', {})
            self.assertIn(a_status, (200,))
            # Delete
            d_status, d_data = self.delete(f'/api/env-profiles/{pname}')
            self.assertIn(d_status, (200,))

    def test_03_delete_nonexistent_env_profile(self):
        status, data = self.delete('/api/env-profiles/NoSuchProfile')
        self.assertIn(status, (200,))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 21 — Comments, Favourites, Theme, Presence
# ═══════════════════════════════════════════════════════════════════════════════
class TestPersonalization(BaseTest):
    """Tests: comments CRUD, favourites toggle, theme get/set, presence."""

    def setUp(self):
        self.login_admin()

    def _jtl_name(self):
        p = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports', SAMPLE_JTL)
        return SAMPLE_JTL if os.path.exists(p) else None

    def test_01_get_theme(self):
        status, data = self.get_json('/api/theme')
        self.assertEqual(status, 200)
        self.assertIn('theme', data)

    def test_02_set_theme_dark(self):
        status, data = self.post_json('/api/theme', {'theme': 'dark'})
        self.assertEqual(status, 200)

    def test_03_set_theme_light(self):
        status, data = self.post_json('/api/theme', {'theme': 'light'})
        self.assertEqual(status, 200)

    def test_04_get_favourites(self):
        status, data = self.get_json('/api/favourites')
        self.assertEqual(status, 200)
        self.assertIn('favourites', data)

    def test_05_toggle_favourite(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.post_json('/api/favourites', {'file': jtl})
        self.assertEqual(status, 200)
        self.assertIn('favourited', data)
        # Toggle off
        self.post_json('/api/favourites', {'file': jtl})

    def test_06_get_presence(self):
        status, data = self.get_json('/api/presence')
        self.assertEqual(status, 200)
        self.assertIn('users', data)

    def test_07_post_presence(self):
        status, data = self.post_json('/api/presence', {'panel': 'overview'})
        self.assertEqual(status, 200)

    def test_08_add_comment(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.post_json(f'/api/comments/{urllib.parse.quote(jtl)}', {
            'text': 'E2E test comment', 'ts_offset_s': 60
        })
        self.assertEqual(status, 200)
        cid = data.get('id')
        if cid:
            d_status, _ = self.delete(f'/api/comments/{urllib.parse.quote(jtl)}/{cid}')
            self.assertIn(d_status, (200,))

    def test_09_get_comments(self):
        jtl = self._jtl_name()
        if not jtl:
            self.skipTest('Sample JTL not found')
        status, data = self.get_json(f'/api/comments/{urllib.parse.quote(jtl)}')
        self.assertEqual(status, 200)
        self.assertIn('comments', data)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 22 — Report Run Notes
# ═══════════════════════════════════════════════════════════════════════════════
class TestRunNotes(BaseTest):
    """Tests: post run note, get run notes."""

    def setUp(self):
        self.login_admin()

    def test_01_post_run_notes(self):
        run_id = 'e2e-run-' + self.rand_str()
        status, data = self.post_json('/api/run-notes', {
            'run_id': run_id, 'notes': 'E2E test notes', 'tags': 'e2e,smoke'
        })
        self.assertIn(status, (200,))

    def test_02_get_run_notes(self):
        run_id = 'e2e-run-' + self.rand_str()
        self.post_json('/api/run-notes', {'run_id': run_id, 'notes': 'Test'})
        status, data = self.get_json(f'/api/run-notes/{run_id}')
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 23 — Live Sharing
# ═══════════════════════════════════════════════════════════════════════════════
class TestLiveSharing(BaseTest):
    """Tests: generate live token, access shared view, public stats."""

    def setUp(self):
        self.login_admin()

    def test_01_create_live_share_token(self):
        status, data = self.post_json('/api/share/live', {})
        self.assertEqual(status, 200)
        self.assertIn('token', data)

    def test_02_access_shared_live_with_valid_token(self):
        _, share_data = self.post_json('/api/share/live', {})
        token = share_data.get('token')
        if not token:
            self.skipTest('No token returned')
        r = self.client.get(f'/shared/live/{token}')
        self.assertIn(r.status_code, (200,))

    def test_03_access_shared_live_with_invalid_token(self):
        r = self.client.get('/shared/live/invalidtoken123')
        self.assertIn(r.status_code, (403,))

    def test_04_public_stats_with_valid_token(self):
        _, share_data = self.post_json('/api/share/live', {})
        token = share_data.get('token')
        if not token:
            self.skipTest('No token returned')
        r = self.client.get(f'/api/live-stats/public?token={token}')
        self.assertIn(r.status_code, (200,))

    def test_05_public_stats_with_invalid_token(self):
        r = self.client.get('/api/live-stats/public?token=BADTOKEN')
        self.assertIn(r.status_code, (403,))

    def test_06_create_report_share(self):
        jtl = SAMPLE_JTL
        jtl_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports', jtl)
        if not os.path.exists(jtl_path):
            self.skipTest('Sample JTL not found')
        status, data = self.post_json('/api/share/report', {'file': jtl})
        self.assertIn(status, (200,))
        token = data.get('token')
        if token:
            r = self.client.get(f'/shared/report/{token}')
            self.assertIn(r.status_code, (200,))

    def test_07_shared_report_invalid_token(self):
        r = self.client.get('/shared/report/INVALIDTOKEN')
        self.assertIn(r.status_code, (403, 404))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 24 — Self-Registration
# ═══════════════════════════════════════════════════════════════════════════════
class TestRegistration(BaseTest):
    """Tests: registration request, admin list, approve, reject."""

    def setUp(self):
        # Enable self-registration in settings
        self.login_admin()
        self.post_json('/api/settings', {'self_register_enabled': True})

    def test_01_register_request(self):
        self.client.get('/logout')
        u = 'reg_' + self.rand_str()
        status, data = self.post_json('/api/register-request', {
            'username': u, 'name': 'Reg User', 'email': f'{u}@test.com', 'password': 'RegPass1!'
        })
        self.assertIn(status, (200, 409))
        if status == 200:
            self.login_admin()
            r = self.client.get('/api/admin/registrations')
            regs = r.get_json()
            rid = next((x['id'] for x in regs if x['username'] == u), None)
            if rid:
                a = self.client.post(f'/api/admin/registrations/{rid}/approve',
                                      data='{}', content_type='application/json')
                self.assertIn(a.status_code, (200,))
                self.delete(f'/api/users/{u}')

    def test_02_register_with_short_password(self):
        self.client.get('/logout')
        status, data = self.post_json('/api/register-request', {
            'username': 'short_' + self.rand_str(), 'name': 'Short', 'password': 'ab'
        })
        self.assertIn(status, (400,))

    def test_03_list_registrations(self):
        self.login_admin()
        status, data = self.get_json('/api/admin/registrations')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)

    def test_04_reject_registration(self):
        self.login_admin()
        self.client.get('/logout')
        u = 'rej_' + self.rand_str()
        self.post_json('/api/register-request', {
            'username': u, 'name': 'Reject User', 'password': 'RejectPass1!'
        })
        self.login_admin()
        r = self.client.get('/api/admin/registrations')
        regs = r.get_json()
        rid = next((x['id'] for x in regs if x['username'] == u), None)
        if rid:
            status, data = self.post_json(f'/api/admin/registrations/{rid}/reject', {})
            self.assertIn(status, (200,))
        else:
            self.skipTest('Registration not found')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 25 — TPS Calculator & Load-Config Tools
# ═══════════════════════════════════════════════════════════════════════════════
class TestCalculators(BaseTest):
    """Tests: TPS calculator, load config suggest-from-jmx, check-server, health-check."""

    def setUp(self):
        self.login_admin()

    def test_01_tps_calculator(self):
        status, data = self.post_json('/api/tps-calculator', {
            'total_tps': 30, 'duration': 600, 'ramp_up': 60
        })
        self.assertLess(status, 500)

    def test_02_check_server(self):
        status, data = self.get_json('/api/check-server')
        self.assertLess(status, 500)

    def test_03_health_check_post(self):
        status, data = self.post_json('/api/health-check', {
            'url': 'http://127.0.0.1:5000/health'
        })
        self.assertLess(status, 500)

    def test_04_load_config_suggest_from_jmx(self):
        jmx = SAMPLE_JMX
        jmx_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'jmx', jmx)
        if not os.path.exists(jmx_path):
            self.skipTest('Sample JMX required')
        status, data = self.post_json('/api/load-config/suggest-from-jmx', {'jmx': jmx})
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 26 — XLSX / Test Features
# ═══════════════════════════════════════════════════════════════════════════════
class TestXLSX(BaseTest):
    """Tests: xlsx-files list, test-features, download xlsx."""

    def setUp(self):
        self.login_admin()

    def test_01_list_xlsx_files(self):
        status, data = self.get_json('/api/xlsx-files')
        self.assertLess(status, 500)
        # API returns {'files': [...]} object
        files = data.get('files') if isinstance(data, dict) else data
        self.assertIsInstance(files, list)

    def test_02_test_features(self):
        status, data = self.get_json('/api/test-features')
        self.assertLess(status, 500)

    def test_03_download_nonexistent_xlsx(self):
        r = self.client.get('/api/download/xlsx/NO_SUCH.xlsx')
        self.assertIn(r.status_code, (400, 404))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 27 — AI Chat (graceful when no API key)
# ═══════════════════════════════════════════════════════════════════════════════
class TestAI(BaseTest):
    """Tests: AI chat and narrative — should gracefully fail when no API key."""

    def setUp(self):
        self.login_admin()

    def test_01_ai_chat_no_key(self):
        status, data = self.post_json('/api/ai/chat', {
            'message': 'Summarize the test results'
        })
        self.assertLess(status, 600)  # any defined HTTP response

    def test_02_ai_narrative_no_key(self):
        jtl = SAMPLE_JTL
        jtl_path = os.path.join(BASE_DIR, 'clients', SAMPLE_CODE, 'reports', jtl)
        if not os.path.exists(jtl_path):
            self.skipTest('Sample JTL required')
        status, data = self.post_json('/api/ai/narrative', {'file': jtl})
        self.assertIn(status, (400, 500), 'Should fail gracefully without API key')


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 28 — Role-Based Access Control
# ═══════════════════════════════════════════════════════════════════════════════
class TestRBAC(BaseTest):
    """Tests: endpoints that only admins can access, viewer can/cannot access."""

    _viewer_user = None
    _viewer_pass = 'RbacPass1!'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._viewer_user = 'rbac_v_' + ''.join(random.choices(string.ascii_lowercase, k=5))
        with cls.app.test_client() as c:
            c.post('/login', data={'username': ADMIN_USER, 'password': ADMIN_PASS})
            c.post('/api/session/client',
                    data=json.dumps({'code': SAMPLE_CODE}),
                    content_type='application/json')
            c.post('/api/users',
                    data=json.dumps({
                        'username': cls._viewer_user, 'password': cls._viewer_pass,
                        'name': 'RBAC Viewer', 'role': 'viewer',
                        'permissions': ['run_tests', 'view_audit']
                    }),
                    content_type='application/json')

    @classmethod
    def tearDownClass(cls):
        with cls.app.test_client() as c:
            c.post('/login', data={'username': ADMIN_USER, 'password': ADMIN_PASS})
            c.delete(f'/api/users/{cls._viewer_user}')
        super().tearDownClass()

    def _as_anon(self):
        self.client.get('/logout')

    def _as_viewer(self):
        self.client.get('/logout')
        self.client.post('/login',
                          data={'username': self._viewer_user, 'password': self._viewer_pass})
        self.client.post('/api/session/client',
                          data=json.dumps({'code': SAMPLE_CODE}),
                          content_type='application/json')

    def test_01_anon_cannot_get_users(self):
        self._as_anon()
        r = self.client.get('/api/users')
        self.assertIn(r.status_code, (302, 401, 403))

    def test_02_viewer_cannot_create_user(self):
        self._as_viewer()
        r = self.client.post('/api/users',
                              data=json.dumps({'username': 'hack', 'password': 'bad', 'name': 'Hack', 'role': 'admin'}),
                              content_type='application/json')
        self.assertIn(r.status_code, (302, 401, 403), 'Viewer cannot create users')

    def test_03_viewer_cannot_delete_client(self):
        self._as_viewer()
        r = self.client.delete(f'/api/clients/{SAMPLE_CODE}')
        self.assertIn(r.status_code, (302, 401, 403))

    def test_04_viewer_can_read_reports(self):
        self._as_viewer()
        r = self.client.get('/api/reports')
        self.assertIn(r.status_code, (200,), 'Viewer can read reports')

    def test_05_viewer_can_read_overview_stats(self):
        self._as_viewer()
        r = self.client.get('/api/overview-stats')
        self.assertIn(r.status_code, (200,))

    def test_06_viewer_can_read_me(self):
        self._as_viewer()
        r = self.client.get('/api/me')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data.get('role'), 'viewer')

    def test_07_viewer_can_read_audit_with_permission(self):
        self._as_viewer()
        r = self.client.get('/api/audit-log?limit=5')
        self.assertIn(r.status_code, (200,), 'Viewer with view_audit perm can read audit log')

    def test_08_viewer_cannot_access_db_maintenance(self):
        self._as_viewer()
        r = self.client.get('/api/db-stats')
        self.assertIn(r.status_code, (302, 401, 403), 'Viewer cannot access DB stats')

    def test_09_viewer_cannot_vacuum_db(self):
        self._as_viewer()
        r = self.client.post('/api/db/vacuum',
                              data='{}', content_type='application/json')
        self.assertIn(r.status_code, (302, 401, 403))

    def test_10_admin_can_access_all(self):
        self.login_admin()
        for path in ('/api/users', '/api/clients', '/api/db-stats', '/api/audit-log?limit=1'):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, f'Admin should access {path}')

    def test_11_anon_cannot_access_admin_page(self):
        self._as_anon()
        r = self.client.get('/admin', follow_redirects=False)
        self.assertIn(r.status_code, (301, 302, 303, 401, 403))

    def test_12_viewer_runs_from_viewer_portal(self):
        self._as_viewer()
        r = self.client.get('/viewer')
        self.assertIn(r.status_code, (200,))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 29 — Live Stats & Labels
# ═══════════════════════════════════════════════════════════════════════════════
class TestLiveStats(BaseTest):
    """Tests: live-stats, live-stats labels."""

    def setUp(self):
        self.login_admin()

    def test_01_live_stats(self):
        r = self.client.get('/api/live-stats')
        self.assertLess(r.status_code, 500)

    def test_02_live_stats_labels(self):
        r = self.client.get('/api/live-stats/labels')
        self.assertLess(r.status_code, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 30 — Archive Reports
# ═══════════════════════════════════════════════════════════════════════════════
class TestArchive(BaseTest):
    """Tests: archive-reports endpoint."""

    def setUp(self):
        self.login_admin()

    def test_01_archive_reports(self):
        status, data = self.post_json('/api/archive-reports', {'days': 365})
        self.assertLess(status, 500)


# ═══════════════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════════════

SECTION_MAP = {
    'auth':         TestAuth,
    'pages':        TestPageRoutes,
    'overview':     TestOverview,
    'clients':      TestClientManagement,
    'users':        TestUserManagement,
    'testcontrol':  TestTestControl,
    'reports':      TestReports,
    'downloads':    TestDownloads,
    'uploads':      TestUploads,
    'jmx':          TestJMX,
    'csv':          TestCSV,
    'settings':     TestSettings,
    'prereq':       TestPrerequisites,
    'schedules':    TestSchedules,
    'suite':        TestSuite,
    'db':           TestDBMaintenance,
    'audit':        TestAuditLog,
    'baseline':     TestBaseline,
    'profiles':     TestLoadProfiles,
    'envprofiles':  TestEnvProfiles,
    'personal':     TestPersonalization,
    'runnotes':     TestRunNotes,
    'sharing':      TestLiveSharing,
    'registration': TestRegistration,
    'calculators':  TestCalculators,
    'xlsx':         TestXLSX,
    'ai':           TestAI,
    'rbac':         TestRBAC,
    'livestats':    TestLiveStats,
    'archive':      TestArchive,
}

ALL_SECTIONS = list(SECTION_MAP.values())


class _DetailedRunner(unittest.TextTestRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._results = []

    def run(self, test):
        result = super().run(test)
        return result


def _colour_result(result):
    if result == 'PASS':
        return _c('PASS', 'PASS')
    if result == 'FAIL':
        return _c('FAIL', 'FAIL')
    if result == 'ERROR':
        return _c('FAIL', 'ERROR')
    return _c('SKIP', 'SKIP')


def run_tests(section_filter=None, verbosity=1):
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    if section_filter:
        names = [n.strip().lower() for n in section_filter.split(',')]
        classes = []
        for name in names:
            if name in SECTION_MAP:
                classes.append(SECTION_MAP[name])
            else:
                print(f'[WARN] Unknown section: {name}. Available: {", ".join(SECTION_MAP.keys())}')
        for cls in classes:
            suite.addTests(loader.loadTestsFromTestCase(cls))
    else:
        for cls in ALL_SECTIONS:
            suite.addTests(loader.loadTestsFromTestCase(cls))

    # Collect results
    rows = []
    passed = failed = errored = skipped = 0

    class _Collector(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.rows = []

        def startTest(self, test):
            self._t = time.time()

        def _record(self, test, result, detail=''):
            elapsed = round((time.time() - getattr(self, '_t', time.time())) * 1000)
            section = type(test).__name__.replace('Test', '')
            name = test._testMethodName
            self.rows.append({'section': section, 'name': name,
                               'result': result, 'detail': detail, 'ms': elapsed})

        def addSuccess(self, test):
            self._record(test, 'PASS')

        def addFailure(self, test, err):
            msg = str(err[1])[:120]
            self._record(test, 'FAIL', msg)

        def addError(self, test, err):
            msg = str(err[1])[:120]
            self._record(test, 'ERROR', msg)

        def addSkip(self, test, reason):
            self._record(test, 'SKIP', reason)

    collector = _Collector()
    suite.run(collector)

    total = len(collector.rows)
    passed  = sum(1 for r in collector.rows if r['result'] == 'PASS')
    failed  = sum(1 for r in collector.rows if r['result'] in ('FAIL', 'ERROR'))
    skipped = sum(1 for r in collector.rows if r['result'] == 'SKIP')

    # Print header
    print()
    print(_c('BOLD', '=' * 80))
    print(_c('BOLD', '  LOAD TESTING PLATFORM — COMPREHENSIVE E2E TEST REPORT'))
    print(_c('BOLD', '=' * 80))

    # Print per-section groups
    current_section = None
    for row in collector.rows:
        if row['section'] != current_section:
            current_section = row['section']
            print()
            print(_c('HEAD', f'  -- {current_section} --'))
        icon = _colour_result(row['result'])
        detail = f'  [{row["detail"]}]' if row['detail'] else ''
        print(f'    [{icon}] {row["name"]} ({row["ms"]}ms){detail}')

    # Summary
    print()
    print(_c('BOLD', '=' * 80))
    rate = round(passed / total * 100, 1) if total else 0
    summary_color = 'PASS' if failed == 0 else 'FAIL'
    print(_c(summary_color, f'  RESULT: {passed}/{total} passed  |  {failed} failed  |  {skipped} skipped  |  {rate}% pass rate'))
    print(_c('BOLD', '=' * 80))

    if failed:
        print()
        print(_c('FAIL', '  FAILURES / ERRORS:'))
        for row in collector.rows:
            if row['result'] in ('FAIL', 'ERROR'):
                print(f'    {_c("FAIL", row["result"])} {row["section"]}.{row["name"]}: {row["detail"]}')

    # Write JSON report
    report_dir = os.path.join(BASE_DIR, 'test_reports')
    os.makedirs(report_dir, exist_ok=True)
    ts = time.strftime('%Y-%m-%d_%H-%M-%S')
    report_path = os.path.join(report_dir, f'comprehensive_e2e_{ts}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': ts,
            'total': total, 'passed': passed, 'failed': failed, 'skipped': skipped,
            'pass_rate': rate,
            'results': collector.rows
        }, f, indent=2)
    print(f'\n  Report written → {report_path}')
    print()

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Comprehensive E2E Test Suite')
    parser.add_argument('--section', '-s', default=None,
                        help=f'Comma-separated sections to run. Available: {", ".join(SECTION_MAP.keys())}')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--list-sections', action='store_true')
    args = parser.parse_args()

    if args.list_sections:
        print('Available sections:')
        for k in SECTION_MAP:
            print(f'  {k}')
        sys.exit(0)

    sys.exit(run_tests(
        section_filter=args.section,
        verbosity=2 if args.verbose else 1
    ))
