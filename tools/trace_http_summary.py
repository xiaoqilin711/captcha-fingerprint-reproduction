"""Summarize the HTTP request chain of a browser trace.

Associates request / response / body files per ``channelId`` and prints the
business requests (excluding browser-background noise), plus a JSON dump for
downstream tools.

Usage
-----
    python tools/trace_http_summary.py <traceOut-dir>
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from urllib.parse import urlparse

# Browser-background hosts (telemetry / component downloads), not business traffic.
BACKGROUND_HOSTS = {
    "location.services.mozilla.com",
    "detectportal.firefox.com",
    "services.addons.mozilla.org",
    "dl.google.com",
    "edgedl.me.gvt1.com",
    "incoming.telemetry.mozilla.org",
    "push.services.mozilla.com",
    "content-signature-2.cdn.mozilla.net",
    "shavar.services.mozilla.com",
    "ocsp.digicert.com",
    "r3.o.lencr.org",
    "pki.goog",
}


def _text(v) -> str:
    if isinstance(v, dict):
        return v.get("text") or ""
    return v or ""


def main(root: str) -> None:
    http_dir = os.path.join(root, "http")
    chans: dict = {}
    body_files: dict = defaultdict(set)

    for fn in os.listdir(http_dir):
        if not fn.endswith(".jsonl"):
            continue
        with open(os.path.join(http_dir, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = o.get("type")
                cid = o.get("channelId")
                if t == "http_request":
                    chans.setdefault(cid, {})["request"] = o
                elif t == "http_response":
                    chans.setdefault(cid, {})["response"] = o
                elif t in ("http_body", "http_body_decoded"):
                    fld = "body_file" if t == "http_body" else "decoded_file"
                    b = o.get("body") or o.get("value") or {}
                    fp = b.get("file") if isinstance(b, dict) else None
                    if fp:
                        body_files[cid].add(fp)
                        chans.setdefault(cid, {})[fld] = fp

    rows = []
    for cid, info in chans.items():
        req = info.get("request") or {}
        resp = info.get("response") or {}
        url = _text(req.get("url"))
        host = urlparse(url).netloc if url else ""
        if host in BACKGROUND_HOSTS or req.get("isBrowserBackground"):
            continue
        rows.append({
            "cid": cid,
            "method": _text(req.get("method")),
            "url": url,
            "status": resp.get("status"),
            "contentLength": resp.get("contentLength"),
            "contentType": _text(resp.get("contentType")),
            "body_files": sorted(body_files.get(cid, set())),
        })

    rows.sort(key=lambda r: r["cid"])
    for r in rows:
        print(f"[{r['cid']:>2}] {r['method']:4s} {r['status']} {r['url'][:110]}")
        for bf in r["body_files"]:
            print(f"        body: {bf}")

    out = os.path.join(root, "_http_summary.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n{len(rows)} business requests -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
