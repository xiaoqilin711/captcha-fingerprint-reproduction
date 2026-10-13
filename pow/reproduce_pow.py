"""Recover the proof-of-work nonce for a click-captcha prehandle challenge.

Recovered from the target's obfuscated challenge script and verified 100%
against a real session capture. The scheme is:

    prehandle response issues  pow_cfg = {"prefix": P, "md5": H}
    the client enumerates u from 0 upward until
        md5(prefix + str(u)) == H
    then submits
        pow_answer    = prefix + str(u)
        pow_calc_time = elapsed ms

No secret is involved: this is a client-side rate-limit / anti-replay knob, not
a signature. The point of the reproduction is to show the exact scheme, its
byte-level correctness, and its cost profile.

The real capture's prefix, target hash and nonce are redacted. Everything here
runs self-consistently: :func:`make_challenge` commits to a known nonce and
:func:`solve_pow` recovers it, which proves a full round-trip without shipping
any vendor material.
"""
from __future__ import annotations

import hashlib
import time
from typing import Dict, Optional

__all__ = ["solve_pow", "make_challenge", "main"]


def solve_pow(prefix: str, target_md5: str, timeout_ms: int = 30_000) -> Dict[str, Optional[object]]:
    """Brute-force the smallest nonce ``u`` such that ``md5(prefix + str(u)) == target_md5``.

    Returns ``{"answer", "pow_answer", "duration_ms", "timeout"}``; on timeout
    ``answer``/``pow_answer`` are ``None``.
    """
    start = time.perf_counter()
    u = 0
    while True:
        candidate = prefix + str(u)
        if hashlib.md5(candidate.encode("utf-8")).hexdigest() == target_md5:
            return {
                "answer": u,
                "pow_answer": candidate,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "timeout": False,
            }
        u += 1
        if (time.perf_counter() - start) * 1000 > timeout_ms:
            return {
                "answer": None,
                "pow_answer": None,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "timeout": True,
            }


def make_challenge(answer: int) -> Dict[str, str]:
    """Build a self-consistent challenge: pick a prefix and commit to a known nonce.

    The prefix shape (16 hex chars + ``#``) mirrors the observed format; the
    concrete value is a placeholder, not the real one. Returns
    ``{"prefix", "target", "expected_answer"}``.
    """
    prefix = "7d3a1f9c4e6b8a25#"
    target = hashlib.md5((prefix + str(answer)).encode("utf-8")).hexdigest()
    return {"prefix": prefix, "target": target, "expected_answer": str(answer)}


def main() -> None:
    challenge = make_challenge(answer=371_905)
    prefix = challenge["prefix"]
    target = challenge["target"]
    expected = challenge["expected_answer"]

    result = solve_pow(prefix, target)

    print("challenge prefix :", prefix)
    print("challenge md5    :", target)
    print("expected nonce   :", expected)
    print("solved nonce     :", result["answer"])
    print("duration_ms      :", result["duration_ms"])

    assert str(result["answer"]) == expected, "round-trip failed"
    assert hashlib.md5(result["pow_answer"].encode("utf-8")).hexdigest() == target  # type: ignore[arg-type]
    print("round-trip verified: md5(pow_answer) == target")


if __name__ == "__main__":
    main()
