#!/usr/bin/env python3
"""
jtl_to_html_report.py

Generate a self-contained, searchable HTML report that shows the REQUEST and
RESPONSE for every sample in a JMeter results file.

Why this exists:
    JMeter's built-in HTML dashboard is aggregate-only (throughput / latency /
    percentiles / error-rate). It can NEVER show per-request request/response
    bodies. To debug services you need the raw request+response of each call.
    This tool reads an XML .jtl (saved with responseData + samplerData enabled)
    and renders one collapsible entry per sample, colour-coded pass/fail.

Input:
    - Preferred: an XML JMeter results file (testResults) saved with
      responseData=true, samplerData=true, response/requestHeaders=true.
      This is what the "View Results Tree - Full Capture (Req+Resp)" listener
      in the test plan produces.
    - Fallback: a CSV .jtl. CSV has no request/response bodies, so only the
      label / code / success / failureMessage can be shown (still useful for a
      quick pass/fail overview of older runs).

Usage:
    python tools/jtl_to_html_report.py results_full.xml -o report.html
    python tools/jtl_to_html_report.py results_full.xml            # -> results_full.report.html

Notes on size:
    "All samples" for a 30 TPS x 1 hour run (~108k samples) with full bodies can
    produce a very large HTML file that is slow to open in a browser. Each entry
    is collapsed by default (<details>) so the browser only lays out a body when
    you expand it, but the file itself is still large. Use --errors-only or
    --max-per-label on huge runs if the browser struggles.
"""

import argparse
import html
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict


SAMPLE_TAGS = ("httpSample", "sample")


def esc(text):
    return html.escape(text if text is not None else "", quote=False)


def child_text(elem, tag):
    """Direct-child element text by tag (ElementTree find searches direct children)."""
    c = elem.find(tag)
    if c is not None and c.text:
        return c.text
    return ""


def extract_sample(elem):
    """Pull the fields we care about from one <httpSample>/<sample> element."""
    a = elem.attrib
    url = child_text(elem, "java.net.URL") or a.get("URL", "")
    method = child_text(elem, "method")
    query = child_text(elem, "queryString")
    sampler_data = child_text(elem, "samplerData")
    req_headers = child_text(elem, "requestHeader")
    resp_headers = child_text(elem, "responseHeader")
    resp_data = child_text(elem, "responseData")
    cookies = child_text(elem, "cookies")

    # Assertions (may be several)
    assertions = []
    for ar in elem.findall("assertionResult"):
        name = child_text(ar, "name")
        failure = child_text(ar, "failure") == "true"
        error = child_text(ar, "error") == "true"
        msg = child_text(ar, "failureMessage")
        assertions.append((name, failure or error, msg))

    return {
        "label": a.get("lb", ""),
        "code": a.get("rc", ""),
        "message": a.get("rm", ""),
        "success": a.get("s", "") == "true",
        "elapsed": a.get("t", ""),
        "timestamp": a.get("ts", ""),
        "thread": a.get("tn", ""),
        "method": method,
        "url": url,
        "query": query,
        "sampler_data": sampler_data,
        "req_headers": req_headers,
        "resp_headers": resp_headers,
        "resp_data": resp_data,
        "cookies": cookies,
        "assertions": assertions,
    }


def render_block(title, body):
    if not body:
        return ""
    return (
        f'<div class="block"><div class="block-title">{esc(title)}</div>'
        f'<pre>{esc(body)}</pre></div>'
    )


def render_sample(idx, s):
    status = "pass" if s["success"] else "fail"
    badge = "PASS" if s["success"] else "FAIL"
    summary = (
        f'<span class="badge {status}">{badge}</span>'
        f'<span class="lbl">{esc(s["label"])}</span>'
        f'<span class="meta">code {esc(s["code"])} &middot; {esc(s["elapsed"])} ms'
        f' &middot; {esc(s["thread"])}</span>'
    )

    req_parts = []
    if s["method"] or s["url"]:
        req_parts.append(render_block("Request line", f'{s["method"]} {s["url"]}'.strip()))
    req_parts.append(render_block("Request headers", s["req_headers"]))
    req_parts.append(render_block("Query string", s["query"]))
    req_parts.append(render_block("Request data", s["sampler_data"]))
    if s["cookies"]:
        req_parts.append(render_block("Cookies", s["cookies"]))
    request_html = "".join(p for p in req_parts if p) or '<div class="empty">No request data captured (enable samplerData/requestHeaders).</div>'

    resp_parts = [
        render_block("Response headers", s["resp_headers"]),
        render_block("Response body", s["resp_data"]),
    ]
    if s["message"]:
        resp_parts.insert(0, render_block("Response message", s["message"]))
    response_html = "".join(p for p in resp_parts if p) or '<div class="empty">No response data captured (enable responseData).</div>'

    assert_html = ""
    if s["assertions"]:
        rows = []
        for name, failed, msg in s["assertions"]:
            cls = "fail" if failed else "pass"
            rows.append(
                f'<div class="assert {cls}"><b>{esc(name) or "(assertion)"}</b>'
                + (f'<pre>{esc(msg)}</pre>' if msg else " &mdash; ok")
                + "</div>"
            )
        assert_html = f'<div class="block"><div class="block-title">Assertions</div>{"".join(rows)}</div>'

    search_key = f'{s["label"]} {s["code"]} {s["thread"]} {badge}'.lower()

    return (
        f'<details class="sample {status}" data-status="{status}" '
        f'data-label="{esc(s["label"])}" data-search="{esc(search_key)}">'
        f'<summary>{summary}</summary>'
        f'<div class="body">'
        f'<div class="col"><h4>Request</h4>{request_html}</div>'
        f'<div class="col"><h4>Response</h4>{response_html}{assert_html}</div>'
        f'</div></details>\n'
    )


def is_xml(path):
    with open(path, "rb") as f:
        head = f.read(200).lstrip()
    return head.startswith(b"<?xml") or head.startswith(b"<testResults")


def process_xml(path, body_file, stats, opts):
    kept_per_label = defaultdict(int)
    idx = 0
    context = ET.iterparse(path, events=("end",))
    for event, elem in context:
        if elem.tag not in SAMPLE_TAGS:
            continue
        s = extract_sample(elem)
        # stats over ALL samples regardless of filtering
        stats["total"] += 1
        if s["success"]:
            stats["pass"] += 1
        else:
            stats["fail"] += 1
        stats["labels"][s["label"]][0 if s["success"] else 1] += 1

        keep = True
        if opts.errors_only and s["success"]:
            keep = False
        if keep and opts.max_per_label and s["success"]:
            if kept_per_label[s["label"]] >= opts.max_per_label:
                keep = False
            else:
                kept_per_label[s["label"]] += 1
        if keep:
            idx += 1
            body_file.write(render_sample(idx, s))
        elem.clear()  # free this sample's bodies from memory
    return idx


def process_csv(path, body_file, stats, opts):
    import csv
    idx = 0
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            success = str(row.get("success", "")).lower() == "true"
            s = {
                "label": row.get("label", ""),
                "code": row.get("responseCode", ""),
                "message": row.get("responseMessage", ""),
                "success": success,
                "elapsed": row.get("elapsed", ""),
                "timestamp": row.get("timeStamp", ""),
                "thread": row.get("threadName", ""),
                "method": "", "url": row.get("URL", ""), "query": "",
                # CSV JTLs saved with samplerData/responseData enabled (as the
                # Load Testing Platform now does) carry these columns.
                "sampler_data": row.get("samplerData", ""),
                "req_headers": row.get("requestHeaders", ""),
                "resp_headers": row.get("responseHeaders", ""),
                "resp_data": row.get("responseData", ""),
                "cookies": "",
                "assertions": [("Assertion", not success, row.get("failureMessage", ""))]
                if row.get("failureMessage") else [],
            }
            stats["total"] += 1
            if success:
                stats["pass"] += 1
            else:
                stats["fail"] += 1
            stats["labels"][s["label"]][0 if success else 1] += 1

            if opts.errors_only and success:
                continue
            idx += 1
            body_file.write(render_sample(idx, s))
    return idx


HEAD = """<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f5f7;color:#1a1a2e}}
  header{{position:sticky;top:0;background:#12244a;color:#fff;padding:14px 20px;z-index:10;box-shadow:0 2px 6px rgba(0,0,0,.2)}}
  header h1{{margin:0 0 8px;font-size:18px}}
  .stats span{{display:inline-block;margin-right:16px;font-size:13px}}
  .stats b{{font-size:15px}}
  .controls{{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
  .controls input,.controls select{{padding:6px 8px;border:1px solid #ccc;border-radius:4px;font-size:13px}}
  .controls button{{padding:6px 12px;border:0;border-radius:4px;cursor:pointer;font-size:13px;background:#2a4a8a;color:#fff}}
  .controls button.active{{background:#4caf50}}
  main{{padding:16px 20px}}
  details.sample{{background:#fff;border-radius:6px;margin-bottom:8px;border-left:5px solid #ccc;box-shadow:0 1px 2px rgba(0,0,0,.08)}}
  details.sample.pass{{border-left-color:#4caf50}}
  details.sample.fail{{border-left-color:#e53935}}
  summary{{cursor:pointer;padding:10px 12px;list-style:none;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
  summary::-webkit-details-marker{{display:none}}
  .badge{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;color:#fff}}
  .badge.pass{{background:#4caf50}} .badge.fail{{background:#e53935}}
  .lbl{{font-weight:600}} .meta{{color:#666;font-size:12px}}
  .body{{display:flex;gap:14px;padding:6px 14px 14px;flex-wrap:wrap}}
  .col{{flex:1;min-width:320px}}
  .col h4{{margin:8px 0 6px;font-size:13px;color:#12244a;border-bottom:1px solid #eee;padding-bottom:4px}}
  .block{{margin-bottom:8px}}
  .block-title{{font-size:11px;text-transform:uppercase;color:#888;margin-bottom:2px}}
  pre{{background:#0f1626;color:#d6e2ff;padding:8px 10px;border-radius:4px;overflow:auto;max-height:340px;white-space:pre-wrap;word-break:break-word;font-size:12px;margin:0}}
  .empty{{color:#999;font-style:italic;font-size:12px}}
  .assert{{margin-bottom:6px;font-size:12px}} .assert.fail b{{color:#e53935}} .assert.pass b{{color:#4caf50}}
  .hidden{{display:none!important}}
</style></head><body>
<header>
  <h1>{title}</h1>
  <div class="stats">
    <span>Total <b>{total}</b></span>
    <span style="color:#8ef">Pass <b>{npass}</b></span>
    <span style="color:#f99">Fail <b>{nfail}</b></span>
    <span>Rendered <b>{rendered}</b></span>
  </div>
  <div class="controls">
    <input id="q" type="text" placeholder="search label / code / thread..." oninput="applyFilter()">
    <select id="lbl" onchange="applyFilter()"><option value="">All labels</option>{label_opts}</select>
    <button id="b-all" class="active" onclick="setStatus('')">All</button>
    <button id="b-pass" onclick="setStatus('pass')">Pass</button>
    <button id="b-fail" onclick="setStatus('fail')">Fail</button>
    <button onclick="toggleAll(true)">Expand all</button>
    <button onclick="toggleAll(false)">Collapse all</button>
  </div>
</header>
<main id="list">
"""

TAIL = """</main>
<script>
var statusFilter='';
function setStatus(s){
  statusFilter=s;
  ['all','pass','fail'].forEach(function(k){document.getElementById('b-'+k).classList.remove('active');});
  document.getElementById('b-'+(s||'all')).classList.add('active');
  applyFilter();
}
function applyFilter(){
  var q=document.getElementById('q').value.toLowerCase();
  var lbl=document.getElementById('lbl').value;
  var items=document.querySelectorAll('details.sample');
  for(var i=0;i<items.length;i++){
    var el=items[i];
    var ok=true;
    if(statusFilter && el.getAttribute('data-status')!==statusFilter) ok=false;
    if(ok && lbl && el.getAttribute('data-label')!==lbl) ok=false;
    if(ok && q && el.getAttribute('data-search').indexOf(q)===-1) ok=false;
    el.classList.toggle('hidden', !ok);
  }
}
function toggleAll(open){
  var items=document.querySelectorAll('details.sample:not(.hidden)');
  for(var i=0;i<items.length;i++) items[i].open=open;
}
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="Render JMeter request/response into a searchable HTML report.")
    ap.add_argument("input", help="JMeter results file (.jtl/.xml). XML gives full request/response; CSV is pass/fail only.")
    ap.add_argument("-o", "--output", help="Output HTML file (default: <input>.report.html)")
    ap.add_argument("--errors-only", action="store_true", help="Only render failed samples.")
    ap.add_argument("--max-per-label", type=int, default=0, help="Cap successful samples rendered per label (0 = no cap). Failures always shown.")
    ap.add_argument("--title", default=None, help="Report title.")
    opts = ap.parse_args()

    if not os.path.isfile(opts.input):
        sys.exit(f"Input not found: {opts.input}")
    out = opts.output or (os.path.splitext(opts.input)[0] + ".report.html")
    title = opts.title or f"Request/Response Report - {os.path.basename(opts.input)}"

    stats = {"total": 0, "pass": 0, "fail": 0, "labels": defaultdict(lambda: [0, 0])}
    xml_mode = is_xml(opts.input)
    csv_has_bodies = False
    if not xml_mode:
        with open(opts.input, "r", encoding="utf-8", errors="ignore") as _f:
            csv_has_bodies = "responseData" in (_f.readline())
    print(f"[i] Input format: {'XML' if xml_mode else 'CSV'}"
          f" ({'full request/response' if xml_mode or csv_has_bodies else 'pass/fail only, no bodies'})")
    if not xml_mode and not csv_has_bodies:
        print("[!] This CSV has no responseData/samplerData columns. Run a test with full "
              "capture enabled (the platform now does this) for request/response bodies.")

    # Stream sample HTML to a temp file so we can put summary stats at the top.
    tmp = tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".htmlpart", delete=False)
    try:
        if xml_mode:
            rendered = process_xml(opts.input, tmp, stats, opts)
        else:
            rendered = process_csv(opts.input, tmp, stats, opts)
        tmp.flush()
        tmp.seek(0)

        label_opts = "".join(
            f'<option value="{html.escape(lbl, quote=True)}">{esc(lbl)} '
            f'(p{c[0]}/f{c[1]})</option>'
            for lbl, c in sorted(stats["labels"].items())
        )
        with open(out, "w", encoding="utf-8") as f:
            f.write(HEAD.format(
                title=esc(title), total=stats["total"], npass=stats["pass"],
                nfail=stats["fail"], rendered=rendered, label_opts=label_opts,
            ))
            for chunk in iter(lambda: tmp.read(1 << 20), ""):
                f.write(chunk)
            f.write(TAIL)
    finally:
        tmp.close()
        os.unlink(tmp.name)

    size_mb = os.path.getsize(out) / (1024 * 1024)
    print(f"[+] Wrote {out}  ({size_mb:.1f} MB)")
    print(f"    Total={stats['total']}  Pass={stats['pass']}  Fail={stats['fail']}  Rendered={rendered}")
    if size_mb > 150:
        print("[!] Large file - a browser may be slow. Consider --errors-only or --max-per-label 20.")


if __name__ == "__main__":
    main()
