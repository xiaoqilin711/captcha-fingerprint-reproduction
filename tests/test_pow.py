"""Round-trip tests for the recovered proof-of-work scheme."""
import hashlib

from pow.reproduce_pow import make_challenge, solve_pow


def test_trivial_nonce():
    ch = make_challenge(answer=0)
    r = solve_pow(ch["prefix"], ch["target"])
    assert r["timeout"] is False
    assert r["answer"] == 0


def test_large_nonce_round_trip():
    ch = make_challenge(answer=371_905)
    r = solve_pow(ch["prefix"], ch["target"])
    assert r["timeout"] is False
    assert str(r["answer"]) == ch["expected_answer"]
    assert hashlib.md5(r["pow_answer"].encode("utf-8")).hexdigest() == ch["target"]


def test_timeout():
    # A target that can never match within the tiny budget -> timeout.
    r = solve_pow("abcdef#", "0" * 32, timeout_ms=50)
    assert r["timeout"] is True
    assert r["answer"] is None
    assert r["pow_answer"] is None
