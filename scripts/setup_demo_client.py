"""
setup_demo_client.py
Creates a complete DEMO client (DemoBank Mobile Money) with:
  - Realistic CSV test data  (8 services, 100 rows each)
  - 2 JMX test plans        (5 TPS smoke + 10 TPS load)
  - 2 pre-generated JTL results with mixed pass/fail data
  - env.json, load_config.json, sla_config.json, prereq.json
  - AI narrative + RCA saved in meta.json
  - Client registered in the platform database
Run:  python scripts/setup_demo_client.py
"""

import csv, io, json, math, os, random, sqlite3, time
from datetime import datetime, timedelta

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENTS_DIR = os.path.join(BASE_DIR, 'clients')
DB_PATH     = os.path.join(BASE_DIR, 'lt_platform.db')
CODE        = 'DEMO'

random.seed(42)

# ── helpers ───────────────────────────────────────────────────────────────────
def _mkdir(p):
    os.makedirs(p, exist_ok=True)

def _write(path, text, overwrite=True):
    if not overwrite and os.path.exists(path):
        return False
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    return True

def _write_json(path, obj, overwrite=True):
    if not overwrite and os.path.exists(path):
        return False
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)
    return True

# ── CSV test data ─────────────────────────────────────────────────────────────
def _msisdn(start, n):
    return [str(71000000 + start + i) for i in range(n)]

def _pin():
    return str(random.randint(1000, 9999))

def _amount(lo, hi):
    return str(round(random.uniform(lo, hi), 2))

def make_csv_files(testdata_dir):
    msisdns   = _msisdn(0, 100)
    receivers = _msisdn(200, 100)
    agents    = _msisdn(500, 20)
    billers   = ['ZESCO', 'DSTV', 'WATER', 'RATES', 'NWASCO']
    merchants = ['SHOPRITE', 'SPAR', 'GAME', 'CHOPPIES', 'PICK_N_PAY']

    files = {
        'P2P_Transfer.csv': [
            ['msisdn', 'receiver_msisdn', 'amount', 'pin'],
            *[[msisdns[i], receivers[i], _amount(10, 500), _pin()] for i in range(100)]
        ],
        'Balance_Enquiry.csv': [
            ['msisdn', 'pin'],
            *[[msisdns[i], _pin()] for i in range(100)]
        ],
        'Airtime_TopUp_Self.csv': [
            ['msisdn', 'amount', 'pin'],
            *[[msisdns[i], _amount(5, 50), _pin()] for i in range(100)]
        ],
        'Airtime_TopUp_Others.csv': [
            ['msisdn', 'beneficiary_msisdn', 'amount', 'pin'],
            *[[msisdns[i], receivers[i], _amount(5, 50), _pin()] for i in range(100)]
        ],
        'Cash_In.csv': [
            ['msisdn', 'agent_msisdn', 'amount', 'pin'],
            *[[msisdns[i], agents[i % 20], _amount(50, 2000), _pin()] for i in range(100)]
        ],
        'Cash_Out.csv': [
            ['msisdn', 'agent_msisdn', 'amount', 'pin'],
            *[[msisdns[i], agents[i % 20], _amount(50, 1000), _pin()] for i in range(100)]
        ],
        'Bill_Payment.csv': [
            ['msisdn', 'biller_code', 'account_number', 'amount', 'pin'],
            *[[msisdns[i], billers[i % 5], str(100000 + i), _amount(50, 500), _pin()] for i in range(100)]
        ],
        'Merchant_Payment.csv': [
            ['msisdn', 'merchant_code', 'amount', 'pin'],
            *[[msisdns[i], merchants[i % 5], _amount(20, 300), _pin()] for i in range(100)]
        ],
    }

    created = []
    for fname, rows in files.items():
        buf = io.StringIO()
        w   = csv.writer(buf)
        w.writerows(rows)
        if _write(os.path.join(testdata_dir, fname), buf.getvalue()):
            created.append(fname)
    return created

# ── JMX files ─────────────────────────────────────────────────────────────────
def _jmx(plan_name, tps, duration_s, ramp_s, services):
    tg_xml = ''
    for svc in services:
        svc_threads = max(1, round(tps * svc['pct'] / 100 * 1.5))
        tg_xml += f'''
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup"
          testname="{svc['name']}" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController"
            guiclass="LoopControlPanel" testclass="LoopController" enabled="true">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">-1</stringProp>
        </elementProp>
        <stringProp name="ThreadGroup.num_threads">{svc_threads}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">{ramp_s}</stringProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">{duration_s}</stringProp>
      </ThreadGroup>
      <hashTree>
        <CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet"
            testname="CSV - {svc['csv']}" enabled="true">
          <stringProp name="filename">${{testdatapath}}/{svc['csv']}</stringProp>
          <stringProp name="variableNames">{svc['vars']}</stringProp>
          <stringProp name="delimiter">,</stringProp>
          <boolProp name="ignoreFirstLine">true</boolProp>
          <boolProp name="recycle">true</boolProp>
          <boolProp name="stopThread">false</boolProp>
          <stringProp name="shareMode">shareMode.all</stringProp>
        </CSVDataSet>
        <hashTree/>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy"
            testname="{svc['name']}" enabled="true">
          <stringProp name="HTTPSampler.domain">${{server}}</stringProp>
          <stringProp name="HTTPSampler.port">${{port}}</stringProp>
          <stringProp name="HTTPSampler.protocol">${{protocol}}</stringProp>
          <stringProp name="HTTPSampler.path">/health</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
            <collectionProp name="Arguments.arguments"/>
          </elementProp>
        </HTTPSamplerProxy>
        <hashTree>
          <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion"
              testname="Assert 200" enabled="true">
            <collectionProp name="Asserion.test_strings">
              <stringProp name="1">200</stringProp>
            </collectionProp>
            <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>
            <intProp name="Assertion.test_type">8</intProp>
          </ResponseAssertion>
          <hashTree/>
        </hashTree>
      </hashTree>'''

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan"
        testname="{plan_name}" enabled="true">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments">
        <collectionProp name="Arguments.arguments">
          <elementProp name="protocol" elementType="Argument">
            <stringProp name="Argument.name">protocol</stringProp>
            <stringProp name="Argument.value">http</stringProp>
          </elementProp>
          <elementProp name="server" elementType="Argument">
            <stringProp name="Argument.name">server</stringProp>
            <stringProp name="Argument.value">127.0.0.1</stringProp>
          </elementProp>
          <elementProp name="port" elementType="Argument">
            <stringProp name="Argument.name">port</stringProp>
            <stringProp name="Argument.value">5000</stringProp>
          </elementProp>
          <elementProp name="testdatapath" elementType="Argument">
            <stringProp name="Argument.name">testdatapath</stringProp>
            <stringProp name="Argument.value">clients/DEMO/testdata</stringProp>
          </elementProp>
        </collectionProp>
      </elementProp>
    </TestPlan>
    <hashTree>{tg_xml}
    </hashTree>
  </hashTree>
</jmeterTestPlan>
'''

SERVICES = [
    {'name': 'TC - P2P Transfer',          'pct': 30, 'csv': 'P2P_Transfer.csv',        'vars': 'msisdn,receiver_msisdn,amount,pin'},
    {'name': 'TC - Balance Enquiry',        'pct': 25, 'csv': 'Balance_Enquiry.csv',      'vars': 'msisdn,pin'},
    {'name': 'TC - Airtime TopUp Self',     'pct': 15, 'csv': 'Airtime_TopUp_Self.csv',   'vars': 'msisdn,amount,pin'},
    {'name': 'TC - Airtime TopUp Others',   'pct': 10, 'csv': 'Airtime_TopUp_Others.csv', 'vars': 'msisdn,beneficiary_msisdn,amount,pin'},
    {'name': 'TC - Cash In',                'pct': 8,  'csv': 'Cash_In.csv',              'vars': 'msisdn,agent_msisdn,amount,pin'},
    {'name': 'TC - Cash Out',               'pct': 7,  'csv': 'Cash_Out.csv',             'vars': 'msisdn,agent_msisdn,amount,pin'},
    {'name': 'TC - Bill Payment',           'pct': 3,  'csv': 'Bill_Payment.csv',         'vars': 'msisdn,biller_code,account_number,amount,pin'},
    {'name': 'TC - Merchant Payment',       'pct': 2,  'csv': 'Merchant_Payment.csv',     'vars': 'msisdn,merchant_code,amount,pin'},
]

def make_jmx_files(jmx_dir):
    plans = [
        ('DEMO_MobileMoney_5TPS_5min',  5,  300, 30),
        ('DEMO_MobileMoney_10TPS_10min',10, 600, 60),
    ]
    created = []
    for name, tps, dur, ramp in plans:
        path = os.path.join(jmx_dir, f'{name}.jmx')
        if _write(path, _jmx(name, tps, dur, ramp, SERVICES)):
            created.append(f'{name}.jmx')
    return created

# ── Synthetic JTL data ────────────────────────────────────────────────────────
JTL_HEADER = 'timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect\n'

def _jtl_row(ts_ms, elapsed, label, success, fail_msg=''):
    rc   = '200' if success else random.choice(['500', '503', '408', '0'])
    msg  = 'OK'  if success else random.choice(['Internal Server Error', 'Service Unavailable', 'Connection timed out'])
    grp  = random.randint(1, 3)
    all_ = random.randint(grp, grp + 4)
    lat  = max(1, elapsed - random.randint(1, 20))
    return (f'{ts_ms},{elapsed},{label},{rc},{msg},Thread Group 1-{random.randint(1,5)},'
            f'text,{str(success).lower()},{fail_msg},{random.randint(300,2000)},200,'
            f'{grp},{all_},http://127.0.0.1:5000/health,{lat},0,5\n')

def _svc_profile(name, pct, base_avg, base_p95, err_rate):
    return {'name': name, 'pct': pct, 'base_avg': base_avg,
            'base_p95': base_p95, 'err_rate': err_rate}

SVC_PROFILES_5TPS = [
    _svc_profile('TC - P2P Transfer',        30, 420,  1800, 0.02),
    _svc_profile('TC - Balance Enquiry',      25, 180,   600, 0.005),
    _svc_profile('TC - Airtime TopUp Self',   15, 310,  1200, 0.01),
    _svc_profile('TC - Airtime TopUp Others', 10, 350,  1400, 0.015),
    _svc_profile('TC - Cash In',               8, 480,  2000, 0.03),
    _svc_profile('TC - Cash Out',              7, 510,  2100, 0.025),
    _svc_profile('TC - Bill Payment',          3, 620,  2500, 0.04),
    _svc_profile('TC - Merchant Payment',      2, 290,  1100, 0.01),
]

SVC_PROFILES_10TPS = [
    _svc_profile('TC - P2P Transfer',        30, 680,  3200, 0.06),
    _svc_profile('TC - Balance Enquiry',      25, 240,   900, 0.01),
    _svc_profile('TC - Airtime TopUp Self',   15, 490,  2100, 0.03),
    _svc_profile('TC - Airtime TopUp Others', 10, 540,  2400, 0.04),
    _svc_profile('TC - Cash In',               8, 820,  4100, 0.08),
    _svc_profile('TC - Cash Out',              7, 910,  4500, 0.09),
    _svc_profile('TC - Bill Payment',          3, 1100, 5200, 0.12),
    _svc_profile('TC - Merchant Payment',      2, 450,  1900, 0.02),
]

def _elapsed_for(profile, t_frac):
    """Generate a realistic elapsed time with ramp effect."""
    ramp = min(1.0, t_frac / 0.15)          # ramp up over first 15%
    jitter = random.gauss(1.0, 0.25)
    base   = profile['base_avg'] * ramp * max(0.4, jitter)
    # occasionally generate a slow outlier
    if random.random() < 0.05:
        base *= random.uniform(3, 6)
    return max(50, int(base))

def make_jtl(reports_dir, fname, total_tps, duration_s, profiles, start_offset_hours=2):
    """Generate a synthetic JTL with realistic distribution."""
    start_ms = int((time.time() - start_offset_hours * 3600) * 1000)
    rows     = []
    interval = 1000 // total_tps          # ms between samples at full TPS

    t_ms = start_ms
    while (t_ms - start_ms) < duration_s * 1000:
        t_frac = (t_ms - start_ms) / (duration_s * 1000)
        for profile in profiles:
            # How many of this service at this tick?
            count = max(0, round(profile['pct'] / 100 * total_tps * (interval / 1000)))
            for _ in range(max(1, count)):
                elapsed = _elapsed_for(profile, t_frac)
                success = random.random() > profile['err_rate']
                fail_msg = ''
                if not success:
                    fail_msg = random.choice([
                        'Expected: 200 | Actual: 500',
                        'Expected: db_ok | Actual: timeout',
                        'Connection refused',
                        'Expected: SUCCESS | Actual: INSUFFICIENT_FUNDS',
                        'Response code was not 200 but 503',
                    ])
                rows.append(_jtl_row(t_ms + random.randint(0, interval), elapsed,
                                     profile['name'], success, fail_msg))
        t_ms += interval

    random.shuffle(rows)  # mix service rows as they'd appear in a real run
    path = os.path.join(reports_dir, fname)
    _write(path, JTL_HEADER + ''.join(rows))
    return len(rows)

def make_meta(reports_dir, jtl_fname, narrative, rca):
    meta = {
        'narrative': narrative,
        'narrative_ts': datetime.now().strftime('%d %b %Y %H:%M'),
        'rca': rca,
        'rca_ts': datetime.now().strftime('%d %b %Y %H:%M'),
    }
    _write_json(os.path.join(reports_dir, jtl_fname.replace('.jtl', '.meta.json')), meta)

# ── Config files ──────────────────────────────────────────────────────────────
def make_configs(base):
    env = {
        'protocol': 'http',
        'server': '127.0.0.1',
        'port': '5000',
        'login': 'demo_user',
        'password': 'demo_pass',
        'sim_url': '/health',
        'test_plan_name': 'DEMO_MobileMoney_5TPS_5min',
        'testdatapath': 'clients/DEMO/testdata',
        'reportpath':   'clients/DEMO/reports',
        'test_duration': '300',
        'ramp_up': '30',
        'notes': 'DemoBank smoke test — targets local /health endpoint',
    }
    _write_json(os.path.join(base, 'env.json'), env)

    load_cfg = {
        'services': [
            {'service_name': 'TC - P2P Transfer',        'enabled': True,  'target_tps': 1.5, 'threads': 3,  'ramp_up': 30, 'duration': 300, 'load_pct': 30, 'csv_file': 'P2P_Transfer.csv',        'csv_vars': 'msisdn,receiver_msisdn,amount,pin'},
            {'service_name': 'TC - Balance Enquiry',      'enabled': True,  'target_tps': 1.25,'threads': 2,  'ramp_up': 30, 'duration': 300, 'load_pct': 25, 'csv_file': 'Balance_Enquiry.csv',      'csv_vars': 'msisdn,pin'},
            {'service_name': 'TC - Airtime TopUp Self',   'enabled': True,  'target_tps': 0.75,'threads': 1,  'ramp_up': 30, 'duration': 300, 'load_pct': 15, 'csv_file': 'Airtime_TopUp_Self.csv',   'csv_vars': 'msisdn,amount,pin'},
            {'service_name': 'TC - Airtime TopUp Others', 'enabled': True,  'target_tps': 0.5, 'threads': 1,  'ramp_up': 30, 'duration': 300, 'load_pct': 10, 'csv_file': 'Airtime_TopUp_Others.csv', 'csv_vars': 'msisdn,beneficiary_msisdn,amount,pin'},
            {'service_name': 'TC - Cash In',              'enabled': True,  'target_tps': 0.4, 'threads': 1,  'ramp_up': 30, 'duration': 300, 'load_pct': 8,  'csv_file': 'Cash_In.csv',              'csv_vars': 'msisdn,agent_msisdn,amount,pin'},
            {'service_name': 'TC - Cash Out',             'enabled': True,  'target_tps': 0.35,'threads': 1,  'ramp_up': 30, 'duration': 300, 'load_pct': 7,  'csv_file': 'Cash_Out.csv',             'csv_vars': 'msisdn,agent_msisdn,amount,pin'},
            {'service_name': 'TC - Bill Payment',         'enabled': True,  'target_tps': 0.15,'threads': 1,  'ramp_up': 30, 'duration': 300, 'load_pct': 3,  'csv_file': 'Bill_Payment.csv',         'csv_vars': 'msisdn,biller_code,account_number,amount,pin'},
            {'service_name': 'TC - Merchant Payment',     'enabled': False, 'target_tps': 0.1, 'threads': 1,  'ramp_up': 30, 'duration': 300, 'load_pct': 2,  'csv_file': 'Merchant_Payment.csv',     'csv_vars': 'msisdn,merchant_code,amount,pin'},
        ]
    }
    _write_json(os.path.join(base, 'load_config.json'), load_cfg)

    sla = {
        'p90_ms':    2000,
        'p95_ms':    3000,
        'error_pct': 2.0,
        'min_tps':   4.0,
        'per_label': {
            'TC - P2P Transfer':        {'p95_ms': 3000, 'error_pct': 3.0},
            'TC - Balance Enquiry':      {'p95_ms': 1000, 'error_pct': 1.0},
            'TC - Airtime TopUp Self':   {'p95_ms': 2000, 'error_pct': 2.0},
            'TC - Airtime TopUp Others': {'p95_ms': 2500, 'error_pct': 2.0},
            'TC - Cash In':              {'p95_ms': 3500, 'error_pct': 4.0},
            'TC - Cash Out':             {'p95_ms': 3500, 'error_pct': 4.0},
            'TC - Bill Payment':         {'p95_ms': 4000, 'error_pct': 5.0},
            'TC - Merchant Payment':     {'p95_ms': 2000, 'error_pct': 2.0},
        }
    }
    _write_json(os.path.join(base, 'sla_config.json'), sla)

    prereq = {
        'targets': {
            'tps': '5', 'avg_sla': '500', 'peak': '10',
            'duration': '300', 'err_sla': '2', 'p90_sla': '2000'
        },
        'environment': {
            'name': 'DemoBank-UAT',
            'endpoint': 'http://127.0.0.1:5000',
            'build': 'v2.4.1-demo',
            'jmeter': 'Apache JMeter 5.6.3',
            'db': 'PostgreSQL 14 (mock)',
            'servers': '2-node cluster, 4vCPU 16GB each',
            'tools': 'Platform dashboard + Grafana (mock)'
        },
        'channels': ['USSD', 'API'],
        'iterations': '2',
        'hours': '4',
        'services': [
            {'name': 'TC - P2P Transfer',        'channel': 'USSD', 'tps_pct': 30, 'threads': 3, 'csv': 'P2P_Transfer.csv',        'status': 'ready'},
            {'name': 'TC - Balance Enquiry',      'channel': 'USSD', 'tps_pct': 25, 'threads': 2, 'csv': 'Balance_Enquiry.csv',      'status': 'ready'},
            {'name': 'TC - Airtime TopUp Self',   'channel': 'USSD', 'tps_pct': 15, 'threads': 1, 'csv': 'Airtime_TopUp_Self.csv',   'status': 'ready'},
            {'name': 'TC - Airtime TopUp Others', 'channel': 'USSD', 'tps_pct': 10, 'threads': 1, 'csv': 'Airtime_TopUp_Others.csv', 'status': 'ready'},
            {'name': 'TC - Cash In',              'channel': 'API',  'tps_pct': 8,  'threads': 1, 'csv': 'Cash_In.csv',              'status': 'ready'},
            {'name': 'TC - Cash Out',             'channel': 'API',  'tps_pct': 7,  'threads': 1, 'csv': 'Cash_Out.csv',             'status': 'ready'},
            {'name': 'TC - Bill Payment',         'channel': 'USSD', 'tps_pct': 3,  'threads': 1, 'csv': 'Bill_Payment.csv',         'status': 'pending'},
            {'name': 'TC - Merchant Payment',     'channel': 'API',  'tps_pct': 2,  'threads': 1, 'csv': 'Merchant_Payment.csv',     'status': 'pending'},
        ],
        'cl_services': [
            {'id': 'svc-p2p',     'title': 'P2P Transfer endpoint reachable',       'done': True},
            {'id': 'svc-bal',     'title': 'Balance Enquiry endpoint reachable',     'done': True},
            {'id': 'svc-airt',    'title': 'Airtime endpoints reachable',            'done': True},
            {'id': 'svc-cash',    'title': 'Cash In / Cash Out endpoints reachable', 'done': True},
            {'id': 'svc-bill',    'title': 'Bill Payment endpoint reachable',        'done': False},
            {'id': 'svc-merch',   'title': 'Merchant Payment endpoint ready',        'done': False},
        ],
        'cl_data': [
            {'id': 'csv-p2p',   'title': 'P2P_Transfer.csv loaded (100 rows)',       'done': True},
            {'id': 'csv-bal',   'title': 'Balance_Enquiry.csv loaded (100 rows)',    'done': True},
            {'id': 'csv-airt',  'title': 'Airtime CSV files loaded',                 'done': True},
            {'id': 'csv-cash',  'title': 'Cash In / Out CSV files loaded',           'done': True},
            {'id': 'csv-bill',  'title': 'Bill_Payment.csv loaded',                  'done': True},
            {'id': 'csv-merch', 'title': 'Merchant_Payment.csv loaded',              'done': True},
        ],
        'cl_grafana': [
            {'id': 'grafana-ok', 'title': 'Grafana dashboard accessible',           'done': False},
            {'id': 'awr-ok',     'title': 'AWR reporting configured',               'done': False},
        ],
        'activities': [
            {'activity': 'Smoke test — 5 TPS, 5 min',  'status': 'Done',    'day': '1', 'duration': '5 min',  'owner': 'demo_user', 'prereq': 'CSV + JMX ready', 'awr': '', 'remarks': 'Baseline run',      'ref': 'DEMO_MobileMoney_5TPS_5min.jmx'},
            {'activity': 'Load test — 10 TPS, 10 min', 'status': 'Done',    'day': '1', 'duration': '10 min', 'owner': 'demo_user', 'prereq': 'Smoke test passed', 'awr': '', 'remarks': 'Degradation seen', 'ref': 'DEMO_MobileMoney_10TPS_10min.jmx'},
            {'activity': 'Soak test — 5 TPS, 60 min',  'status': 'Pending', 'day': '2', 'duration': '60 min', 'owner': 'demo_user', 'prereq': 'Load test passed',  'awr': '', 'remarks': '',                'ref': ''},
        ]
    }
    _write_json(os.path.join(base, 'prereq.json'), prereq)

# ── DB registration ───────────────────────────────────────────────────────────
def register_client(jmx_dir, testdata_dir, reports_dir):
    if not os.path.exists(DB_PATH):
        return False, 'Database not found — start app.py once first.'
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT id FROM clients WHERE code=?', (CODE,)).fetchone()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if row:
            conn.execute(
                'UPDATE clients SET name=?,description=?,logo_emoji=?,color=?,enabled=?,jmx_dir=?,testdata_dir=?,reports_dir=? WHERE code=?',
                ('DemoBank Mobile Money','Full-featured demo client for platform testing','💳','#6366f1',1,jmx_dir,testdata_dir,reports_dir,CODE)
            )
            msg = 'DEMO client already existed — refreshed.'
        else:
            conn.execute(
                'INSERT INTO clients (code,name,description,logo_emoji,color,enabled,jmx_dir,testdata_dir,reports_dir,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (CODE,'DemoBank Mobile Money','Full-featured demo client for platform testing','💳','#6366f1',1,jmx_dir,testdata_dir,reports_dir,'setup_script',now)
            )
            msg = 'DEMO client inserted.'
        conn.commit()
        return True, msg
    finally:
        conn.close()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    base         = os.path.join(CLIENTS_DIR, CODE)
    jmx_dir      = os.path.join(base, 'jmx')
    testdata_dir = os.path.join(base, 'testdata')
    reports_dir  = os.path.join(base, 'reports')
    for d in (base, jmx_dir, testdata_dir, reports_dir):
        _mkdir(d)

    print(f'\n{"="*60}')
    print(f'  DEMO Client Setup — DemoBank Mobile Money')
    print(f'{"="*60}')
    print(f'  Base: {base}\n')

    # CSV files
    csv_created = make_csv_files(testdata_dir)
    print(f'[CSV]     {len(csv_created)} test data files  → {testdata_dir}')

    # JMX files
    jmx_created = make_jmx_files(jmx_dir)
    print(f'[JMX]     {len(jmx_created)} test plan files  → {jmx_dir}')

    # Config files
    make_configs(base)
    print(f'[CONFIG]  env.json / load_config.json / sla_config.json / prereq.json')

    # JTL — smoke run (5 TPS, 5 min, ~1 500 samples, low errors)
    smoke_jtl = 'DEMO_run_5TPS_5min.jtl'
    n1 = make_jtl(reports_dir, smoke_jtl, 5, 300, SVC_PROFILES_5TPS, start_offset_hours=4)
    make_meta(reports_dir, smoke_jtl,
        narrative=(
            "The DemoBank 5 TPS smoke test ran for 5 minutes and completed with an overall error "
            "rate below 3%, confirming baseline stability across all 8 transaction types. "
            "P2P Transfer and Balance Enquiry, which together account for 55% of the load, "
            "responded within SLA targets. "
            "Bill Payment showed the highest P95 at ~2 500 ms, approaching the 3 000 ms SLA threshold. "
            "Recommendation: address the Bill Payment latency spike before scaling to 10 TPS."
        ),
        rca=(
            "**Overall Verdict**\nSmoke test PASSED. System is stable at 5 TPS with minor latency "
            "concerns in high-value transactions.\n\n"
            "**Critical Issues**\n"
            "⚠️ TC - Bill Payment: P95 = 2 500 ms, approaching the 3 000 ms SLA limit. "
            "Top failure: `Expected: 200 | Actual: 500` — likely a downstream payment gateway timeout.\n"
            "⚠️ TC - Cash Out: error rate 2.5%, above the 2% SLA. "
            "Failures cluster around `INSUFFICIENT_FUNDS` — test data may need refreshing.\n\n"
            "**Root Cause Hypothesis**\n"
            "Bill Payment latency is likely caused by a synchronous call to the biller integration "
            "layer with no circuit breaker. Cash Out failures are data-driven (expired PIN records).\n\n"
            "**Healthy Transactions**\n"
            "✅ TC - Balance Enquiry: avg 180 ms, 0.5% error rate — well within SLA.\n"
            "✅ TC - Airtime TopUp Self: avg 310 ms, 1% error rate — stable.\n"
            "✅ TC - P2P Transfer: avg 420 ms, 2% error rate — within budget.\n\n"
            "**Top Recommendations**\n"
            "1. Add a 2s timeout + retry on the Bill Payment biller gateway call.\n"
            "2. Refresh Cash Out CSV with valid PINs to eliminate data-driven failures.\n"
            "3. Set Cash Out P95 SLA to 2 100 ms to detect future regressions earlier."
        )
    )
    print(f'[JTL]     {smoke_jtl}  ({n1:,} samples, 5 TPS / 5 min)')

    # JTL — load run (10 TPS, 10 min, ~6 000 samples, higher errors)
    load_jtl = 'DEMO_run_10TPS_10min.jtl'
    n2 = make_jtl(reports_dir, load_jtl, 10, 600, SVC_PROFILES_10TPS, start_offset_hours=2)
    make_meta(reports_dir, load_jtl,
        narrative=(
            "The DemoBank 10 TPS load test ran for 10 minutes and revealed significant performance "
            "degradation compared to the 5 TPS baseline. Overall error rate climbed to 5.8%, "
            "driven primarily by Cash Out (9%), Cash In (8%), and Bill Payment (12%). "
            "P95 response time for Bill Payment exceeded 5 200 ms — nearly double the 3 000 ms SLA. "
            "Recommendation: the system is not ready for 10 TPS production traffic; "
            "focus on optimising Cash Out, Cash In, and Bill Payment before the next load cycle."
        ),
        rca=(
            "**Overall Verdict**\nLoad test FAILED at 10 TPS. Multiple services breached SLA. "
            "The system saturates between 5 and 10 TPS.\n\n"
            "**Critical Issues**\n"
            "⚠️ TC - Bill Payment: P95 = 5 200 ms (SLA: 3 000 ms), error rate 12%. "
            "All failures return HTTP 503 — the biller integration layer is overloaded.\n"
            "⚠️ TC - Cash Out: P95 = 4 500 ms, error rate 9%. "
            "Connection timeouts dominate — the agent service thread pool is exhausted.\n"
            "⚠️ TC - Cash In: P95 = 4 100 ms, error rate 8%. "
            "Similar pattern to Cash Out — same shared agent service.\n"
            "⚠️ TC - P2P Transfer: error rate jumped to 6% from 2% at 5 TPS — "
            "core ledger contention suspected.\n\n"
            "**Root Cause Hypothesis**\n"
            "Agent service (shared by Cash In and Cash Out) has a fixed thread pool of ~5 workers. "
            "At 10 TPS the queue depth grows unbounded, causing timeouts. "
            "Bill Payment is single-threaded behind a synchronous biller API with no load shedding. "
            "P2P ledger write locks are contended at higher concurrency.\n\n"
            "**Healthy Transactions**\n"
            "✅ TC - Balance Enquiry: avg 240 ms, 1% error — read-only path still stable.\n"
            "✅ TC - Merchant Payment: avg 450 ms, 2% error — acceptable.\n\n"
            "**Top Recommendations**\n"
            "1. Scale agent service thread pool from 5 to 20 and add a queue depth alarm.\n"
            "2. Introduce async processing for Bill Payment with a 3 s SLA timeout.\n"
            "3. Investigate P2P ledger locking — consider optimistic concurrency or batching.\n"
            "4. Re-run 10 TPS after fixes before any production deployment."
        )
    )
    print(f'[JTL]     {load_jtl}  ({n2:,} samples, 10 TPS / 10 min)')

    # Register in DB
    ok, msg = register_client(jmx_dir, testdata_dir, reports_dir)
    print(f'[DB]      {msg}')

    print(f'\n{"="*60}')
    print('  Setup complete!  Switch to the DEMO client in the platform.')
    print('  All features are ready to test:')
    print('    Reports      → open either JTL to see charts, AI narrative & RCA')
    print('    Run Test     → pick DEMO_MobileMoney_5TPS_5min.jmx and start')
    print('    Test Data    → 8 CSV files with 100 rows each')
    print('    JMX Inspector→ inspect either .jmx file')
    print('    AI Chat      → open a report then click "Ask AI"')
    print('    Compare Runs → select both JTLs and click Compare')
    print(f'{"="*60}\n')

if __name__ == '__main__':
    main()
