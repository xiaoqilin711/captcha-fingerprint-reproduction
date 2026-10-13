"""Extract key response bodies (scripts / JSON / images) from a browser trace.

Reassembles ``http_body`` / ``http_body_decoded`` chunks per ``channelId`` and
writes each to a named file. The channel-id -> filename mapping below is an
anonymized example from one capture session; replace it with the ids from your
own ``_http_summary.json``.

Usage
-----
    python tools/extract_assets.py <traceOut-dir> <output-dir>
"""
from __future__ import annotations

import binascii
import json
import os
import sys
from collections import defaultdict

# Example channelId -> output filename (anonymized). Tune per capture.
NAMES = {
    13: "01_captcha.html",
    12884901891: "02_iframe_api.js",
    12884901893: "03_frame.js",
    12884901894: "04_prehandle.json",
    12884901895: "05_challenge.html",
    15032385540: "06_verify.js",
    15032385541: "07_challenge.js",
    15032385543: "08_collector.js",
    15032385546: "09_img1.bin",
    15032385547: "10_img0.bin",
    15032385549: "11_verify_response.json",
}


def _read_body_value(b, root: str) -> bytes:
    """Read a body value: inline text/hex or an external file. Returns bytes."""
    if not isinstance(b, dict):
        return b""
    if b.get("inline"):
        if b.get("text") is not None:
            return b["text"].encode("utf-8")
        if b.get("hex") is not None:
            return binascii.unhexlify(b["hex"])
        return b""
    fp = b.get("file")
    if fp:
        full = os.path.join(root, fp.replace("/", os.sep))
        if os.path.isfile(full):
            with open(full, "rb") as f:
                return f.read()
    return b""


def _sniff(head: bytes) -> str:
    if head[:4] == b"\x89PNG":
        return "PNG"
    if head[:2] == b"\xff\xd8":
        return "JPEG"
    if head[:4] == b"GIF8":
        return "GIF"
    return "text"


def main(root: str, out: str) -> None:
    http_dir = os.path.join(root, "http")
    os.makedirs(out, exist_ok=True)

    decoded: dict = defaultdict(list)
    raw: dict = defaultdict(list)
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
                except Exception:
                    continue
                t = o.get("type")
                cid = o.get("channelId")
                b = o.get("body") or {}
                data = _read_body_value(b, root)
                if t == "http_body_decoded":
                    decoded[cid].append((o.get("decodedOffset", 0), data))
                elif t == "http_body":
                    raw[cid].append((o.get("offset", o.get("sourceOffset", 0)), data))

    for cid, name in NAMES.items():
        chunks = decoded.get(cid) or raw.get(cid)
        if not chunks:
            print(f"  [missing] cid={cid} {name}")
            continue
        chunks.sort(key=lambda x: x[0])
        data = b"".join(c[1] for c in chunks)
        with open(os.path.join(out, name), "wb") as f:
            f.write(data)
        print(f"  [ok] {name}  {len(data)} bytes  {_sniff(data[:16])}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
