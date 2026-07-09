import json
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENTS_DIR = os.path.join(BASE_DIR, 'clients')
DB_PATH = os.path.join(BASE_DIR, 'lt_platform.db')
SAMPLE_CODE = 'SAMPLE'


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _write_json_if_missing(path, data):
    if os.path.exists(path):
        return False
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return True


def _write_text_if_missing(path, text):
    if os.path.exists(path):
        return False
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return True


def ensure_sample_folders_and_files():
    sample_base = os.path.join(CLIENTS_DIR, SAMPLE_CODE)
    jmx_dir = os.path.join(sample_base, 'jmx')
    testdata_dir = os.path.join(sample_base, 'testdata')
    reports_dir = os.path.join(sample_base, 'reports')

    for d in (CLIENTS_DIR, sample_base, jmx_dir, testdata_dir, reports_dir):
        _ensure_dir(d)

    created = []

    readme = (
        'Client: Sample Mock Client (SAMPLE)\n\n'
        'This client is a local end-to-end testing fixture for the Load Testing Platform.\n'
        'It is intentionally configured to call the local Flask server health endpoint\n'
        'instead of any real external infrastructure.\n\n'
        'Mock server details:\n'
        '  protocol : http\n'
        '  host     : 127.0.0.1\n'
        '  port     : 5000\n'
        '  endpoint : /health\n'
    )
    if _write_text_if_missing(os.path.join(sample_base, 'README.txt'), readme):
        created.append('README.txt')

    env_data = {
        'protocol': 'http',
        'server': '127.0.0.1',
        'port': '5000',
        'login': 'mock_user',
        'password': 'mock_password',
        'sim_url': '/health',
        'test_plan_name': 'SAMPLE_Mock_Health_Check_1TPS_1min',
        'testdatapath': 'clients/SAMPLE/testdata',
        'reportpath': 'clients/SAMPLE/reports',
        'test_duration': '60',
        'ramp_up': '5',
        'notes': 'Local mock client for complete end-to-end validation.'
    }
    if _write_json_if_missing(os.path.join(sample_base, 'env.json'), env_data):
        created.append('env.json')

    load_cfg = {
        'services': [
            {
                'service_name': 'Mock Health Check',
                'enabled': True,
                'target_tps': 1,
                'threads': 1,
                'ramp_up': 5,
                'duration': 60,
                'load_pct': 100,
                'txn_count': 60
            }
        ]
    }
    if _write_json_if_missing(os.path.join(sample_base, 'load_config.json'), load_cfg):
        created.append('load_config.json')

    sla_cfg = {
        'p90_ms': 1000,
        'p95_ms': 2000,
        'error_pct': 1,
        'min_tps': 1,
        'per_label': {
            'Mock Health Check': {'p95_ms': 2000, 'error_pct': 1}
        }
    }
    if _write_json_if_missing(os.path.join(sample_base, 'sla_config.json'), sla_cfg):
        created.append('sla_config.json')

    prereq = {
        'targets': {'tps': '1', 'avg_sla': '1', 'peak': '2', 'duration': '60', 'err_sla': '1', 'p90_sla': '1000'},
        'environment': {'name': 'local-mock', 'endpoint': 'http://127.0.0.1:5000/health', 'build': 'sample-fixture', 'jmeter': 'Apache JMeter 5.5+', 'db': 'SQLite', 'servers': 'Local Flask server', 'tools': 'Platform dashboard'},
        'channels': ['API'],
        'iterations': '1',
        'hours': '1',
        'services': [{'name': 'Mock Health Check', 'channel': 'API', 'tps_pct': 100, 'threads': 1, 'csv': 'sample_health_users.csv', 'status': 'ready'}],
        'cl_services': [{'id': 'svc-up', 'title': 'Local Flask /health endpoint is reachable', 'done': True}],
        'cl_data': [{'id': 'csv-ready', 'title': 'Sample CSV data exists and is readable', 'done': True}],
        'cl_grafana': [{'id': 'dashboard-ready', 'title': 'Dashboard endpoints are reachable', 'done': True}],
        'activities': [{'activity': 'Run SAMPLE mock test', 'status': 'Done', 'day': '0', 'duration': '1 min', 'owner': 'tester', 'prereq': 'Flask app running', 'awr': '', 'remarks': 'Calls /health', 'ref': 'sample-jmx'}]
    }
    if _write_json_if_missing(os.path.join(sample_base, 'prereq.json'), prereq):
        created.append('prereq.json')

    csv_text = 'msisdn,scenario,expected_status\n26770000001,health_check,200\n26770000002,health_check,200\n26770000003,health_check,200\n'
    if _write_text_if_missing(os.path.join(testdata_dir, 'sample_health_users.csv'), csv_text):
        created.append('testdata/sample_health_users.csv')

    jmx_text = '''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.5">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="SAMPLE Mock Health Check" enabled="true">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="SAMPLE - 1 TPS Smoke" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller" enabled="true">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">-1</stringProp>
        </elementProp>
        <stringProp name="ThreadGroup.num_threads">1</stringProp>
        <stringProp name="ThreadGroup.ramp_time">5</stringProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">60</stringProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="Mock Health Check" enabled="true">
          <stringProp name="HTTPSampler.domain">127.0.0.1</stringProp>
          <stringProp name="HTTPSampler.port">5000</stringProp>
          <stringProp name="HTTPSampler.protocol">http</stringProp>
          <stringProp name="HTTPSampler.path">/health</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
            <collectionProp name="Arguments.arguments"/>
          </elementProp>
        </HTTPSamplerProxy>
        <hashTree>
          <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="Assert health response" enabled="true">
            <collectionProp name="Asserion.test_strings">
              <stringProp name="1">db_ok</stringProp>
            </collectionProp>
            <stringProp name="Assertion.test_field">Assertion.response_data</stringProp>
            <intProp name="Assertion.test_type">2</intProp>
          </ResponseAssertion>
          <hashTree/>
        </hashTree>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
'''
    if _write_text_if_missing(os.path.join(jmx_dir, 'SAMPLE_Mock_Health_Check_1TPS_1min.jmx'), jmx_text):
        created.append('jmx/SAMPLE_Mock_Health_Check_1TPS_1min.jmx')

    return sample_base, jmx_dir, testdata_dir, reports_dir, created


def ensure_sample_client_db(jmx_dir, testdata_dir, reports_dir):
    if not os.path.exists(DB_PATH):
        return False, 'Database not found. Start app once to initialize lt_platform.db.'

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT id FROM clients WHERE code=?', (SAMPLE_CODE,)).fetchone()
        if row:
            conn.execute(
                'UPDATE clients SET name=?, description=?, logo_emoji=?, color=?, enabled=?, jmx_dir=?, testdata_dir=?, reports_dir=? WHERE code=?',
                ('Sample Mock Client', 'Local end-to-end mock client for platform validation', 'T', '#22c55e', 1, jmx_dir, testdata_dir, reports_dir, SAMPLE_CODE)
            )
            conn.commit()
            return True, 'SAMPLE client already existed; refreshed paths and metadata.'

        conn.execute(
            'INSERT INTO clients (code,name,description,logo_emoji,color,enabled,jmx_dir,testdata_dir,reports_dir,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (SAMPLE_CODE, 'Sample Mock Client', 'Local end-to-end mock client for platform validation', 'T', '#22c55e', 1, jmx_dir, testdata_dir, reports_dir, 'script', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        return True, 'Inserted SAMPLE client into clients table.'
    finally:
        conn.close()


def main():
    sample_base, jmx_dir, testdata_dir, reports_dir, created = ensure_sample_folders_and_files()
    ok, msg = ensure_sample_client_db(jmx_dir, testdata_dir, reports_dir)

    print('SAMPLE SETUP COMPLETE')
    print(f'Base path: {sample_base}')
    print(f'DB status: {msg}')
    if created:
        print('Created files:')
        for item in created:
            print(f' - {item}')
    else:
        print('No files were created; all sample files already existed.')

    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
