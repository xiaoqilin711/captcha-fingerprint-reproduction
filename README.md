# captcha-fingerprint-reproduction

Runtime reverse-engineering of a **major vendor's click captcha**: a byte-level
reproduction of its proof-of-work challenge, a partial byte-level replay of its
environment fingerprint, and the tooling used to get there.

> The vendor, its domains, app ids, hashes and target scripts are **redacted**
> or excluded. What remains is the technique, the recovered algorithm and the
> verification methodology — the part that demonstrates reverse-engineering
> skill without redistributing anyone's proprietary code.

---

## Why this is non-trivial

The captcha is hardened at every stage of one verification round:

- **Prehandle** issues a client-side proof-of-work — you must burn CPU before
  you may even ask for the challenge.
- **Challenge** and **collector** scripts are heavily obfuscated: string-array
  + rotation self-check, a custom bytecode VM, and dynamic encrypted delivery.
- **Verify** cross-checks answer coordinates, an environment-fingerprint blob,
  an encrypted session token and the POW answer in one session-bound request.

"Just run it in Node" was never going to work. The collector had to be executed
in a patched SpiderMonkey runtime with an emulated event loop, and its output
diffed **byte-by-byte** against a real session capture before any algorithm
could be trusted.

## What is reproduced

The proof-of-work is the **primary result**: it is the only artifact that is
fully reproduced *and* independently re-runnable and tested. The fingerprint
work below is real but partial, and is listed second for that reason.

| Artifact | Status | Evidence |
|---|---|---|
| Proof-of-work scheme | **Fully reproduced** | recovered `pow_answer` matches the capture; `md5(pow_answer) == target` holds — runnable: `python -m pow.reproduce_pow` |
| Environment fingerprint (`eks` / `collect` prefix) | **Partially reproduced** | `eks` 44/44 bytes identical; `collect` fingerprint section 88/96 bytes identical — reproduced via `tools/diff_artifact.py` |
| Collector execution path | **Reproduced** | obfuscated collector runs to completion and emits both artifacts |

The interaction *trajectory* inside `collect` is session-specific and was not
reproduced — the honest line is drawn in [docs/case-study.md](docs/case-study.md).

## Project layout

```
.
├── driver/
│   └── driver.js              # SpiderMonkey env-patching driver (collector -> eks/collect)
├── pow/
│   └── reproduce_pow.py       # POW recovery — pure algorithm, runnable + tested
├── tools/
│   ├── disasm.py              # SpiderMonkey bytecode disassembler (custom VM)
│   ├── obfuscation.py         # string-array / rotation self-check / statement-boundary analysis
│   ├── trace_http_summary.py  # flatten a browser trace's HTTP request chain
│   ├── extract_assets.py      # reassemble response bodies from a trace
│   └── diff_artifact.py       # byte-level diff of two artifacts (eks / collect)
├── tests/
│   └── test_pow.py            # POW round-trip tests
├── docs/
│   └── case-study.md          # full write-up (desensitized)
├── pyproject.toml
└── LICENSE
```

## Quick start

The POW reproduction is pure Python and runs anywhere:

```bash
# round-trip demo: commit to a known nonce, then recover it
python -m pow.reproduce_pow

# or, after `pip install -e .`
pow-reproduce

# run the tests
pip install -e ".[dev]"
pytest
```

## Dependencies

- **xiaojianbang-browser-env** — the SpiderMonkey browser-environment framework
  used by `driver/driver.js`. **Install separately; it is not vendored here.**
- **SpiderMonkey** (the Firefox JS engine) — required by the framework above.
- The target's obfuscated scripts (`collector.js`, `frame.js`, `challenge.js`,
  `verify.js`) are **vendor-proprietary and intentionally excluded**. Fetch
  them from the live target at runtime; do not ask this repository for them.

## Scope and ethics

This is an educational / research reproduction of client-side algorithms from a
real product, kept desensitized and free of the vendor's code. No proprietary
script, capture data or credential is distributed. See
[docs/case-study.md](docs/case-study.md) for the full method and the explicit
list of what is and is not reproduced.

## License

[MIT](LICENSE)
