# Case Study: Reverse-Engineering a Major Vendor's Click Captcha

Runtime dissection of a production click-based captcha: from an obfuscated
collector to a byte-level reproduction of its proof-of-work and a partial
byte-level replay of its environment fingerprint.

> All vendor-specific domains, app ids, hashes, tokens and the target scripts
> themselves are redacted or excluded from this repository. The techniques,
> the recovered algorithm and the verification methodology are real.

---

## 1. Target and scope

The target is a production captcha deployed by a large vendor. It is
**click-based** (select the correct objects on an image), not a slider. A single
verification round goes through several deliberately hardened stages:

| Stage | What it does | Hardening |
|---|---|---|
| Prehandle | Returns config + a **proof-of-work** challenge | Client must burn CPU before it is allowed to ask for the challenge image |
| Challenge | Serves the obfuscated frame + challenge script | Heavy obfuscation, string-array + rotation self-check |
| Collector | Assembles the **environment fingerprint** + interaction trajectory into one blob | Obfuscated, delivered as encrypted/encoded payload |
| Verify | Submits answer coordinates + fingerprint blob + encrypted session token + POW answer | Session-bound, every field cross-checked |

This repository reproduces the two stages that are **pure client-side
algorithms** — the POW and the environment fingerprint — and ships the tooling
that was used to reach them.

---

## 2. Method in three layers

The work proceeded from "what does the traffic look like" down to "what is the
exact algorithm":

1. **Runtime capture** — a browser trace records every HTTP request/response
   plus DOM/script activity for one real session. `tools/trace_http_summary.py`
   flattens the request chain; `tools/extract_assets.py` reassembles the
   response bodies (scripts, JSON, images).

2. **Environment patching** — the obfuscated collector is executed inside
   `xiaojianbang-browser-env`'s SpiderMonkey runtime with a minimal DOM
   scaffold (`driver/driver.js`). The virtual event loop is drained so the
   script reaches the point where it exports its fingerprint blob and session
   token. This converts "static obfuscated source" into "runnable code that
   produces observable output".

3. **Algorithm recovery** — once the collector runs and its outputs can be
   diffed against the capture byte-by-byte, individual algorithms (POW, the
   fingerprint serialization) are extracted and re-implemented in plain code.

The key discipline throughout: **every claim is pinned to a byte-level diff
against the same session's capture**, not to "it looks right".

---

## 3. Proof-of-work recovery (fully reproduced)

The prehandle response issues a small challenge:

```
pow_cfg = {"prefix": P, "md5": H}
```

The client enumerates a nonce `u` from `0` upward until

```
md5(P + str(u)) == H
```

and then submits

```
pow_answer    = P + str(u)
pow_calc_time = elapsed ms
```

There is no secret here — this is a client-side rate-limit / anti-replay knob,
not a signature. What made it non-trivial was **finding** the scheme inside an
obfuscated challenge script and proving it was *this* scheme and not a variant.

Verification (against a real prehandle/verify pair from the capture):

- the recovered `pow_answer` matched the capture's submitted value exactly;
- `md5(pow_answer) == target` holds, confirming the whole round-trip.

`pow/reproduce_pow.py` re-implements the scheme and proves a self-consistent
round-trip without shipping any capture material (`make_challenge` commits to a
known nonce, `solve_pow` recovers it).

---

## 4. Environment-fingerprint replay (partially reproduced)

The collector exports two artifacts on a global (`TDC`):

- `eks` — an encrypted session token emitted on startup;
- `collect` — the environment-fingerprint + trajectory payload.

Running the collector under the patched SpiderMonkey runtime with a fixed
fingerprint profile, and diffing against the capture:

| Artifact | Result |
|---|---|
| `eks` | first **44 / 44 bytes identical** |
| `collect` (fingerprint section) | **88 / 96 bytes identical** |

The matching prefix covers the environment fingerprint (navigator, screen,
viewport, feature flags, seeded crypto state). The remaining bytes are the
**interaction trajectory** — the actual click sequence and timing — which is
session-specific and was **not** reproduced at this stage.

This is an honest line: the *environment fingerprint* serialization was
reproduced, the *trajectory* was not.

---

## 5. Obfuscation techniques encountered

The target combined several independent layers, which is why "just run it in
Node" was never going to work:

- **String-array + rotation self-check** — string literals are lifted into an
  array; a checksum over the array gates a rotation loop, so the script hangs
  if the array is damaged. (`tools/obfuscation.py` reproduces the analysis.)
- **Custom VM interpreter** — hot functions are compiled to SpiderMonkey
  bytecode and interpreted by a giant `switch` over opcodes.
  (`tools/disasm.py` is the disassembler that recovered the opcode semantics.)
- **Dynamic encrypted delivery** — the collector is not a static file; it is
  delivered as an encoded/encrypted payload whose decryption key rides in the
  request URL. (Documented here; the decryption itself is a work-in-progress.)

---

## 6. Tooling

| Tool | Purpose |
|---|---|
| `driver/driver.js` | Run the obfuscated collector in SpiderMonkey, drain the event loop, emit `eks`/`collect` for diffing |
| `pow/reproduce_pow.py` | Recover the POW nonce; full round-trip demo + tests |
| `tools/disasm.py` | Disassemble the custom VM's bytecode into readable pseudo-asm |
| `tools/obfuscation.py` | String-array extraction, top-level statement marks, rotation self-check analysis |
| `tools/trace_http_summary.py` | Flatten a browser trace's HTTP request chain |
| `tools/extract_assets.py` | Reassemble response bodies (scripts / JSON / images) from a trace |

---

## 7. Current status and known gaps

Reproduced and verified:

- [x] POW scheme — recovered, re-implemented, byte-level verified.
- [x] Environment-fingerprint serialization — partial byte-level match
      (see the 88/96 above).
- [x] Collector execution path — obfuscated script runs to completion under
      patched SpiderMonkey and emits both artifacts.

Not yet reproduced (in dependency order):

- [ ] Collector decryption (dynamic encrypted delivery).
- [ ] Full `collect` serialization including the interaction trajectory.
- [ ] Click-coordinate recognition (image understanding of the challenge).
- [ ] End-to-end fresh-session orchestration.

The line between "reproduced" and "not reproduced" is drawn deliberately: a
reproduction that only matches the static environment fingerprint is a useful,
honest artifact — but it is **not** the same as an end-to-end bypass, and no
such claim is made here.
