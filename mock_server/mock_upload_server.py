"""
Mock Upload Server — port 5001
Simulates the Load Testing Platform's file-upload endpoints without auth or DB.
Use this as the JMeter target when load-testing the upload feature.
"""

import os
import time
import uuid
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_JMX    = {'.jmx'}
ALLOWED_CSV    = {'.csv'}
ALLOWED_REPORT = {'.jtl', '.html'}

_stats = {"total": 0, "jmx": 0, "testdata": 0, "report": 0, "errors": 0}

INDEX_HTML = """<!DOCTYPE html>
<html>
<head><title>Mock Upload Server</title>
<style>body{font-family:monospace;background:#0d1117;color:#e6edf3;padding:40px;max-width:700px;margin:auto;}
h1{color:#58a6ff;}table{width:100%;border-collapse:collapse;margin-top:16px;}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid #30363d;}
th{color:#8b949e;font-size:12px;text-transform:uppercase;}
.method{background:#1f6feb;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;}
.get{background:#238636;}.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;}
.up{background:#238636;color:#fff;}.down{background:#b62324;color:#fff;}
</style></head>
<body>
<h1>📤 Mock Upload Server</h1>
<p>Status: <span class="badge up">RUNNING</span> &nbsp; Port: 5001 &nbsp; Client: <strong>UPLOADTEST</strong></p>
<table>
<tr><th>Method</th><th>Endpoint</th><th>Accepts</th></tr>
<tr><td><span class="method get">GET</span></td><td>/health</td><td>Live stats &amp; counters</td></tr>
<tr><td><span class="method">POST</span></td><td>/api/upload/jmx</td><td>.jmx files (field: file)</td></tr>
<tr><td><span class="method">POST</span></td><td>/api/upload/testdata</td><td>.csv files (field: file, multi)</td></tr>
<tr><td><span class="method">POST</span></td><td>/api/upload/report</td><td>.jtl / .html (field: file, multi)</td></tr>
<tr><td><span class="method">POST</span></td><td>/api/upload/delete</td><td>JSON {folder, filename}</td></tr>
<tr><td><span class="method get">GET</span></td><td>/api/files/&lt;folder&gt;</td><td>folder = jmx / testdata / reports</td></tr>
</table>
<p style="margin-top:24px;color:#8b949e;font-size:13px;">JMeter target for UPLOADTEST client upload load testing.</p>
</body></html>"""


def _safe_filename(name: str) -> str:
    name = os.path.basename(name or "")
    import re
    name = re.sub(r'[^\w\s\-\.]', '', name).strip()
    return name or "upload"


@app.route("/")
def index():
    from flask import Response
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/health")
def health():
    return jsonify(ok=True, stats=_stats, uptime=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


@app.route("/api/upload/jmx", methods=["POST"])
def upload_jmx():
    if "file" not in request.files:
        _stats["errors"] += 1
        return jsonify(error="No file in request."), 400
    f = request.files["file"]
    fname = _safe_filename(f.filename)
    ext = os.path.splitext(fname)[1].lower()
    if ext not in ALLOWED_JMX:
        _stats["errors"] += 1
        return jsonify(error=f"Only .jmx files allowed, got: {ext}"), 400
    data = f.read()
    size_kb = round(len(data) / 1024, 1)
    _stats["total"] += 1
    _stats["jmx"]   += 1
    return jsonify(ok=True, filename=fname, size_kb=size_kb)


@app.route("/api/upload/testdata", methods=["POST"])
def upload_testdata():
    files = request.files.getlist("file")
    if not files or (len(files) == 1 and files[0].filename == ""):
        _stats["errors"] += 1
        return jsonify(error="No files in request."), 400
    saved, errors = [], []
    for f in files:
        fname = _safe_filename(f.filename)
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ALLOWED_CSV:
            errors.append(f"{f.filename}: only .csv files allowed")
            _stats["errors"] += 1
            continue
        data = f.read()
        size_kb = round(len(data) / 1024, 1)
        saved.append({"filename": fname, "size_kb": size_kb})
        _stats["total"]    += 1
        _stats["testdata"] += 1
    return jsonify(ok=True, saved=saved, errors=errors)


@app.route("/api/upload/report", methods=["POST"])
def upload_report():
    files = request.files.getlist("file")
    if not files or (len(files) == 1 and files[0].filename == ""):
        _stats["errors"] += 1
        return jsonify(error="No files in request."), 400
    saved, errors = [], []
    for f in files:
        fname = _safe_filename(f.filename)
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ALLOWED_REPORT:
            errors.append(f"{f.filename}: only .jtl/.html files allowed")
            _stats["errors"] += 1
            continue
        data = f.read()
        size_kb = round(len(data) / 1024, 1)
        saved.append({"filename": fname, "size_kb": size_kb})
        _stats["total"]  += 1
        _stats["report"] += 1
    return jsonify(ok=True, saved=saved, errors=errors)


@app.route("/api/upload/delete", methods=["POST"])
def upload_delete():
    data = request.json or {}
    folder   = data.get("folder", "")
    filename = data.get("filename", "")
    if not folder or not filename:
        return jsonify(error="folder and filename are required."), 400
    return jsonify(ok=True, deleted=f"{folder}/{filename}")


@app.route("/api/files/<folder>")
def list_files(folder):
    allowed = {"jmx", "testdata", "reports"}
    if folder not in allowed:
        return jsonify(error="Unknown folder."), 400
    return jsonify(files=[])


if __name__ == "__main__":
    print("Mock Upload Server starting on http://localhost:5001")
    print(f"Upload dir: {UPLOAD_DIR}")
    print("Endpoints:")
    print("  GET  /health")
    print("  POST /api/upload/jmx       (field: file, type: .jmx)")
    print("  POST /api/upload/testdata  (field: file, type: .csv, multi-file)")
    print("  POST /api/upload/report    (field: file, type: .jtl/.html, multi-file)")
    app.run(host="0.0.0.0", port=5001, threaded=True, debug=False)
