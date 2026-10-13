"""Obfuscation-structure analysis helpers.

Three small utilities used while dissecting a string-array + rotation
self-check obfuscator:

  find_string_array(src)          — locate ``function _x(){var _y=[...]}`` and dump entries
  top_level_statement_marks(src)  — bracket-depth-0 semicolon positions (true statement boundaries)
  rotate_until_stable(entries, checksum, target, limit) — generic rotation convergence

The rotation/checksum *shape* here matches the real self-check recovered from
the target sample; the concrete checksum formula and target constant are
redacted and must be supplied by the caller via ``checksum``/``target``.

Usage
-----
    python tools/obfuscation.py <file.js>
"""
from __future__ import annotations

import re
import sys


def find_string_array(src: str) -> list[str]:
    """Extract the string-array literal of a string-array obfuscator.

    Matches ``function X(){var Y=[...]...}`` and returns the array entries.
    Returns an empty list when no array is found.
    """
    m = re.search(r"function\s+\w+\(\)\s*\{\s*var\s+\w+\s*=\s*\[(.*?)\];", src, re.S)
    if not m:
        return []
    raw = m.group(1)
    return re.findall(r"'([^']*)'", raw)


def top_level_statement_marks(src: str) -> list[int]:
    """Return character positions of semicolons at bracket depth 0.

    These are the *real* top-level statement boundaries — a cheap way to find
    injection points or split a giant minified file into logical statements.
    """
    depth = 0
    in_str = None
    escaped = False
    marks = []
    for i, ch in enumerate(src):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "'\"`":
            in_str = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            marks.append(i)
    return marks


def js_parse_int(s: str) -> float:
    """Imitate JS ``parseInt``: parse a leading numeric prefix, else NaN."""
    m = re.match(r"^([+-]?\d+)", s.strip())
    return int(m.group(1)) if m else float("nan")


def rotate_until_stable(entries: list[str], checksum, target, limit: int = 200) -> int | None:
    """Left-rotate ``entries`` until ``checksum(entries) == target``.

    Returns the rotation count, or ``None`` if it never converges within
    ``limit`` steps (i.e. the array was damaged and the self-check would loop
    forever). ``checksum`` must be a ``callable(list[str]) -> number``.
    """
    arr = entries[:]
    for rot in range(limit):
        if checksum(arr) == target:
            return rot
        arr = arr[1:] + arr[:1]
    return None


def _example_checksum(arr: list[str]) -> float:
    """Shape-only example of the recovered self-check polynomial.

    The real one weighted ``parseInt(arr[i])`` terms with alternating signs;
    the indices/coefficients/target are redacted. Keep the structure, drop the
    constants.
    """
    def f(i: int) -> float:
        return js_parse_int(arr[i])

    return (f(0) + f(1) / 2 * f(2) + -f(3) / 4 * -f(4))


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python tools/obfuscation.py <file.js>")
        raise SystemExit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        src = f.read()

    entries = find_string_array(src)
    marks = top_level_statement_marks(src)

    print(f"file size            : {len(src)}")
    print(f"string-array entries : {len(entries)}")
    for i, s in enumerate(entries[:20]):
        print(f"  [{i}] = {s!r}")
    if len(entries) > 20:
        print(f"  ... ({len(entries) - 20} more)")
    print(f"top-level statements : {len(marks)}")
    if marks:
        print(f"  first/last marks   : {marks[0]} / {marks[-1]}")


if __name__ == "__main__":
    main()
