"""Byte-level diff of two captured artifacts (eks / collect / any blob).

The byte-for-byte match figures quoted in the case study are produced with this
tool: feed it the value emitted by the patched runtime and the value from the
real browser capture, and it reports the matching prefix/suffix, the first
divergence and a hex view of the mismatch.

Usage
-----
    python tools/diff_artifact.py <a> <b>               # raw text files
    python tools/diff_artifact.py <a> <b> --b64         # base64-encoded files
    python tools/diff_artifact.py <a> <b> --hex         # hex-encoded files
    python tools/diff_artifact.py <a> <b> --url         # URL-encoded (percent) files

Exit status is 0 when the two blobs are identical and 1 otherwise, so it can
gate a CI or acceptance step.
"""
from __future__ import annotations

import base64
import binascii
import sys
import urllib.parse
from typing import Dict, Optional

__all__ = ["decode", "diff_artifacts", "report", "main"]


def decode(data: str, fmt: str) -> bytes:
    if fmt == "b64":
        return base64.b64decode(data)
    if fmt == "url":
        return urllib.parse.unquote_plus(data).encode("utf-8")
    if fmt == "hex":
        return binascii.unhexlify(data)
    return data.encode("utf-8")


def diff_artifacts(a: bytes, b: bytes) -> Dict[str, object]:
    """Return a byte-level comparison of two blobs.

    Reports total lengths, the matching prefix/suffix lengths, the first
    divergence offset and the overall match rate (matched bytes / max length).
    """
    n = min(len(a), len(b))

    prefix = 0
    while prefix < n and a[prefix] == b[prefix]:
        prefix += 1

    suffix = 0
    while suffix < n - prefix and a[len(a) - 1 - suffix] == b[len(b) - 1 - suffix]:
        suffix += 1

    matched = prefix + suffix
    total = max(len(a), len(b), 1)
    return {
        "len_a": len(a),
        "len_b": len(b),
        "prefix_match": prefix,
        "suffix_match": suffix,
        "matched": matched,
        "match_rate": matched / total,
        "first_diff": prefix if prefix < n else None,
    }


def _hex_row(data: bytes, start: int, width: int = 16) -> str:
    return " ".join(f"{b:02x}" for b in data[start:start + width])


def report(a: bytes, b: bytes) -> str:
    d = diff_artifacts(a, b)
    total = max(d["len_a"], d["len_b"], 1)
    lines = [
        f"length          : a={d['len_a']}  b={d['len_b']}",
        f"matched         : {d['matched']} / {total}  ({d['match_rate']:.1%})",
        f"prefix match    : {d['prefix_match']} bytes",
        f"suffix match    : {d['suffix_match']} bytes",
    ]
    if d["first_diff"] is not None:
        fd = d["first_diff"]
        lines.append(f"first divergence: byte {fd}")
        lines.append(f"  a[{fd}:] {_hex_row(a, fd)}")
        lines.append(f"  b[{fd}:] {_hex_row(b, fd)}")
    else:
        lines.append("result          : identical")
    return "\n".join(lines)


def main() -> None:
    args = sys.argv[1:]
    fmt = "raw"
    if args and args[-1] in ("--b64", "--hex", "--url"):
        fmt = args[-1][2:]
        args = args[:-1]
    if len(args) != 2:
        print(__doc__)
        raise SystemExit(2)

    with open(args[0], encoding="utf-8") as f:
        a = decode(f.read().strip(), fmt)
    with open(args[1], encoding="utf-8") as f:
        b = decode(f.read().strip(), fmt)

    print(report(a, b))
    raise SystemExit(0 if a == b else 1)


if __name__ == "__main__":
    main()
