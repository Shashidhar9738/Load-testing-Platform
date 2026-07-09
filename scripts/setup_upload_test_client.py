"""
Creates the UPLOADTEST dummy client in the platform DB and populates
its folders with all the mock upload test data files.
Run from the project root: python scripts/setup_upload_test_client.py
"""

import json
import os
import shutil
import sqlite3
from datetime import datetime

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENTS_DIR  = os.path.join(BASE_DIR, 'clients')
DB_PATH      = os.path.join(BASE_DIR, 'lt_platform.db')
MOCK_FILES   = os.path.join(BASE_DIR, 'mock_server', 'testfiles')
CLIENT_CODE  = 'UPLOADTEST'
CLIENT_NAME  = 'Upload Test (Mock)'


def ensure_dirs():
    base         = os.path.join(CLIENTS_DIR, CLIENT_CODE)
    jmx_dir      = os.path.join(base, 'jmx')
    testdata_dir = os.path.join(base, 'testdata')
    reports_dir  = os.path.join(base, 'reports')
    for d in (base, jmx_dir, testdata_dir, reports_dir):
        os.makedirs(d, exist_ok=True)
    return base, jmx_dir, testdata_dir, reports_dir


def copy_test_files(jmx_dir, testdata_dir, reports_dir):
    copied = []

    # JMX files  → clients/UPLOADTEST/jmx/
    for fname in os.listdir(MOCK_FILES):
        src = os.path.join(MOCK_FILES, fname)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext == '.jmx':
            dst = os.path.join(jmx_dir, fname)
            shutil.copy2(src, dst)
            copied.append(f'jmx/{fname}')
        elif ext == '.csv' and fname != 'upload_params.csv':
            dst = os.path.join(testdata_dir, fname)
            shutil.copy2(src, dst)
            copied.append(f'testdata/{fname}')
        elif ext == '.jtl':
            dst = os.path.join(reports_dir, fname)
            shutil.copy2(src, dst)
            copied.append(f'reports/{fname}')

    # Also copy the BTC upload JMX test plan into UPLOADTEST jmx dir
    btc_jmx = os.path.join(CLIENTS_DIR, 'BTC', 'jmx', 'BTC_Upload_LoadTesting.jmx')
    if os.path.exists(btc_jmx):
        dst = os.path.join(jmx_dir, 'UPLOADTEST_Upload_LoadTesting.jmx')
        shutil.copy2(btc_jmx, dst)
        copied.append('jmx/UPLOADTEST_Upload_LoadTesting.jmx')

    # copy upload_params.csv as testdata too (useful reference)
    params_src = os.path.join(MOCK_FILES, 'upload_params.csv')
    if os.path.exists(params_src):
        dst = os.path.join(testdata_dir, 'upload_params.csv')
        shutil.copy2(params_src, dst)
        copied.append('testdata/upload_params.csv')

    return copied


def write_config_files(base, jmx_dir, testdata_dir, reports_dir):
    env_data = {
        'protocol': 'http',
        'server': '127.0.0.1',
        'port': '5001',
        'login': '',
        'password': '',
        'sim_url': '/api/upload/jmx',
        'test_plan_name': 'UPLOADTEST_Upload_LoadTesting',
        'testdatapath': testdata_dir.replace('\\', '/'),
        'reportpath': reports_dir.replace('\\', '/'),
        'test_duration': '300',
        'ramp_up': '30',
        'notes': 'Dummy client for upload load testing against mock server on port 5001.'
    }
    with open(os.path.join(base, 'env.json'), 'w') as f:
        json.dump(env_data, f, indent=2)

    load_cfg = {
        'services': [
            {'service_name': 'Upload JMX',       'enabled': True, 'target_tps': 2, 'threads': 2,  'ramp_up': 30, 'duration': 300, 'load_pct': 33, 'txn_count': 600},
            {'service_name': 'Upload Test Data',  'enabled': True, 'target_tps': 3, 'threads': 3,  'ramp_up': 30, 'duration': 300, 'load_pct': 50, 'txn_count': 900},
            {'service_name': 'Upload Report JTL', 'enabled': True, 'target_tps': 1, 'threads': 1,  'ramp_up': 10, 'duration': 300, 'load_pct': 17, 'txn_count': 300},
        ]
    }
    with open(os.path.join(base, 'load_config.json'), 'w') as f:
        json.dump(load_cfg, f, indent=2)

    sla_cfg = {
        'p90_ms': 500,
        'p95_ms': 1000,
        'error_pct': 1,
        'min_tps': 1,
        'per_label': {
            'Upload JMX':       {'p95_ms': 1000, 'error_pct': 1},
            'Upload Test Data':  {'p95_ms': 1000, 'error_pct': 1},
            'Upload Report JTL': {'p95_ms': 1000, 'error_pct': 1},
        }
    }
    with open(os.path.join(base, 'sla_config.json'), 'w') as f:
        json.dump(sla_cfg, f, indent=2)

    prereq = {
        'targets': {'tps': '6', 'avg_sla': '500', 'peak': '10', 'duration': '300', 'err_sla': '1', 'p90_sla': '500'},
        'environment': {
            'name': 'mock-upload-server',
            'endpoint': 'http://127.0.0.1:5001',
            'build': 'mock-v1',
            'jmeter': 'Apache JMeter 5.6.3',
            'db': 'None (mock)',
            'servers': 'Mock Upload Server (localhost:5001)',
            'tools': 'Platform dashboard + JMeter'
        },
        'channels': ['HTTP'],
        'iterations': '1',
        'hours': '1',
        'services': [
            {'name': 'Upload JMX',       'channel': 'HTTP', 'tps_pct': 33, 'threads': 2, 'csv': 'upload_params.csv', 'status': 'ready'},
            {'name': 'Upload Test Data',  'channel': 'HTTP', 'tps_pct': 50, 'threads': 3, 'csv': 'upload_params.csv', 'status': 'ready'},
            {'name': 'Upload Report JTL', 'channel': 'HTTP', 'tps_pct': 17, 'threads': 1, 'csv': 'upload_params.csv', 'status': 'ready'},
        ],
        'cl_services': [
            {'id': 'mock-up',  'title': 'Mock server running on localhost:5001', 'done': True},
            {'id': 'health',   'title': 'GET /health returns 200',              'done': True},
        ],
        'cl_data': [
            {'id': 'jmx-ready', 'title': 'sample_plan_small.jmx exists in jmx/',         'done': True},
            {'id': 'csv-ready', 'title': 'sample_data_50rows.csv exists in testdata/',    'done': True},
            {'id': 'jtl-ready', 'title': 'sample_report_upload.jtl exists in reports/',  'done': True},
        ],
        'cl_grafana': [
            {'id': 'health-check', 'title': 'Mock /health endpoint is reachable', 'done': True}
        ],
        'activities': [
            {'activity': 'Start mock server',         'status': 'Done', 'day': '1', 'duration': '1 min',  'owner': 'tester', 'prereq': '', 'awr': '', 'remarks': 'start_mock_server.bat', 'ref': ''},
            {'activity': 'Run upload load test',      'status': 'Pending', 'day': '1', 'duration': '5 min', 'owner': 'tester', 'prereq': 'Mock server running', 'awr': '', 'remarks': 'UPLOADTEST_Upload_LoadTesting.jmx', 'ref': ''},
            {'activity': 'Review results in platform','status': 'Pending', 'day': '1', 'duration': '—',    'owner': 'tester', 'prereq': 'Test complete',        'awr': '', 'remarks': '',                                      'ref': ''},
        ]
    }
    with open(os.path.join(base, 'prereq.json'), 'w') as f:
        json.dump(prereq, f, indent=2)


def register_in_db(jmx_dir, testdata_dir, reports_dir):
    if not os.path.exists(DB_PATH):
        return False, 'lt_platform.db not found — start the platform once first, then re-run this script.'
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT id FROM clients WHERE code=?', (CLIENT_CODE,)).fetchone()
        if row:
            conn.execute(
                'UPDATE clients SET name=?,description=?,logo_emoji=?,color=?,enabled=?,jmx_dir=?,testdata_dir=?,reports_dir=? WHERE code=?',
                (CLIENT_NAME, 'Dummy client for upload file load testing (mock server)', '📤', '#f59e0b', 1,
                 jmx_dir, testdata_dir, reports_dir, CLIENT_CODE)
            )
            conn.commit()
            return True, f'{CLIENT_CODE} already existed — updated paths and metadata.'
        conn.execute(
            'INSERT INTO clients (code,name,description,logo_emoji,color,enabled,jmx_dir,testdata_dir,reports_dir,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (CLIENT_CODE, CLIENT_NAME, 'Dummy client for upload file load testing (mock server)', '📤', '#f59e0b', 1,
             jmx_dir, testdata_dir, reports_dir, 'script', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        return True, f'Inserted {CLIENT_CODE} into clients table.'
    finally:
        conn.close()


def main():
    print(f'Setting up dummy client: {CLIENT_CODE} — {CLIENT_NAME}')
    base, jmx_dir, testdata_dir, reports_dir = ensure_dirs()
    print(f'  Folders created under: {base}')

    copied = copy_test_files(jmx_dir, testdata_dir, reports_dir)
    print(f'  Copied {len(copied)} test file(s):')
    for f in copied:
        print(f'    {f}')

    write_config_files(base, jmx_dir, testdata_dir, reports_dir)
    print('  Config files written (env.json, load_config.json, sla_config.json, prereq.json)')

    ok, msg = register_in_db(jmx_dir, testdata_dir, reports_dir)
    print(f'  DB: {msg}')

    if not ok:
        raise SystemExit(1)

    print()
    print('Done! Select "UPLOADTEST" client in the platform to use it.')
    print(f'Mock server target: http://127.0.0.1:5001')


if __name__ == '__main__':
    main()
