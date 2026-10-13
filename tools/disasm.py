"""Disassemble a SpiderMonkey bytecode stream into readable pseudo-asm.

The opcode-semantics table below was recovered by reversing a custom VM
interpreter — a giant ``switch`` over opcode bytes that reads operands off a
local stack array. The table itself is SpiderMonkey's bytecode; the operand
counts come from counting how many stack slots each handler pops.

Inputs
------
bytecode.json : a JSON array of opcode bytes (extract from the VM dispatch table)
vm_func.js    : the extracted interpreter source, used to infer operand counts

The stack-array / index register names are module-level constants because they
differ between obfuscators; the defaults match the sample this tool was first
built against.

Usage
-----
    python tools/disasm.py <start-ip> <end-ip>
"""
from __future__ import annotations

import json
import re
import sys

# Local variable names inside the target VM interpreter. Adjust per sample.
STACK_ARRAY = "_0x1bffdb"   # local stack array
STACK_IDX = "_0x276d2a"     # stack index register


def load_bytecode(path: str = "bytecode.json") -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_interpreter(path: str = "vm_func.js") -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def operand_counts(src: str) -> dict:
    """For each ``case 0xNN`` handler, count stack pops -> operand count."""
    parts = re.findall(r"case 0x([0-9a-f]+):(.*?)break;", src, re.S)
    counts = {}
    for hx, body in parts:
        op = int(hx, 16)
        dbl = len(re.findall(rf"{STACK_ARRAY}\[\+\+{STACK_IDX},\+\+{STACK_IDX}\]", body))
        sgl = len(re.findall(rf"{STACK_ARRAY}\[\+\+{STACK_IDX}\]", body))
        counts[op] = sgl + dbl
    return counts


def disasm(bc: list, counts: dict, ip: int, end: int) -> None:
    while ip < end:
        if ip >= len(bc):
            print(f"{ip}: OUT")
            break
        op = bc[ip]
        n = counts.get(op, 0)
        ops = bc[ip + 1:ip + 1 + n]
        s = " ".join(str(x) for x in ops)
        if op == 0x33:
            ci, t, f = ops[0], ops[1], ops[2]
            s = f"JMPC r{ci}? +{t}->{ip + 2 + t} : +{f}->{ip + 3 + f}"
        elif op == 0x47: s = f"r{ops[0]}=r{ops[1]}===r{ops[2]}"
        elif op == 0x44: s = f"r{ops[0]}=r{ops[1]}[r{ops[2]}]"
        elif op == 0x4e: s = f"r{ops[0]}=r{ops[1]}[{ops[2]}]"
        elif op == 0x25: s = f"r{ops[0]}=r{ops[1]}[{ops[2]}],r{ops[3]}=r{ops[4]}[{ops[5]}]"
        elif op == 0x1a: s = f"r{ops[0]}={ops[1]}"
        elif op == 0x09: s = f"r{ops[0]}=r{ops[1]}"
        elif op == 0x20: s = f"r{ops[0]}=r{ops[1]}-r{ops[2]}"
        elif op == 0x11: s = f"r{ops[0]}=r{ops[1]}-{ops[2]}"
        elif op == 0x31: s = f"r{ops[0]}=r{ops[1]}+r{ops[2]}"
        elif op == 0x2b: s = f"r{ops[0]}=r{ops[1]}+{ops[2]}"
        elif op == 0x22: s = f"r{ops[0]}=r{ops[1]}*r{ops[2]}"
        elif op == 0x16: s = f"r{ops[0]}+=chr({ops[1]}),r{ops[2]}+=chr({ops[3]})"
        elif op == 0x3f: s = f"r{ops[0]}+=chr({ops[1]})"
        elif op == 0x40: s = f"r{ops[0]}+=chr({ops[1]}),r{ops[2]}=r{ops[3]}[r{ops[4]}]"
        elif op == 0x0c: s = f"r{ops[0]}='',r{ops[1]}+=chr({ops[2]})"
        elif op == 0x0e: s = f"r{ops[0]}=''"
        elif op == 0x1c: s = f"r{ops[0]}=r{ops[1]},r{ops[2]}=r{ops[3]}"
        elif op == 0x2a: s = f"r{ops[0]}[{ops[1]}]=r{ops[2]}"
        elif op == 0x13: s = f"r{ops[0]}[r{ops[1]}]=r{ops[2]}"
        elif op == 0x3e: s = f"r{ops[0]}+=chr({ops[1]}),r{ops[2]}={{}},r{ops[3]}=\"\""
        elif op == 0x53: s = f"r{ops[0]}={{}}"
        elif op == 0x4c: s = f"r{ops[0]}=Array({ops[1]})"
        elif op == 0x3a: s = f"r{ops[0]}=undefined"
        elif op == 0x10: s = f"r{ops[0]}=null"
        elif op == 0x01: s = f"r{ops[0]}=--r{ops[1]}"
        elif op == 0x18: s = f"r{ops[0]}=++r{ops[1]}"
        elif op == 0x2c: s = f"r{ops[0]}=RECURSE(N={ops[1]},args={ops[2:-1]},off={ops[-1]})"
        elif op == 0x0d: s = f"r{ops[0]}=RECURSE_d(N={ops[1]},args={ops[2:-2]})"
        elif op == 0x3c: s = f"return r{ops[0]}"
        elif op == 0x1f: s = f"r{ops[0]}=undefined,return r{ops[1]}"
        elif op == 0x1e: s = f"throw r{ops[0]}"
        elif op == 0x49: s = f"JMP +{ops[0]}->{ip + 2 + ops[0]}"
        elif op == 0x0f: s = f"r{ops[0]}=r{ops[1]}.call(undef)"
        elif op == 0x34: s = f"r{ops[0]}=r{ops[1]}.call(r{ops[2]},r{ops[3]},r{ops[4]},r{ops[5]})"
        elif op == 0x35: s = f"r{ops[0]}=r{ops[1]}>r{ops[2]}"
        elif op == 0x05: s = f"r{ops[0]}=r{ops[1]}<{ops[2]}"
        elif op == 0x2d: s = f"r{ops[0]}=r{ops[1]}<={ops[2]}"
        elif op == 0x29: s = f"r{ops[0]}=r{ops[1]}>={ops[2]}"
        elif op == 0x45: s = f"r{ops[0]}={ops[1]}-r{ops[2]}"
        elif op == 0x5b: s = f"r{ops[0]}=new r{ops[1]}(r{ops[2]},r{ops[3]})"
        elif op == 0x24: s = f"r{ops[0]}=!r{ops[1]}"
        elif op == 0x30: s = f"r{ops[0]}=r{ops[1]}=={ops[2]}"
        elif op == 0x32: s = f"r{ops[0]}=r{ops[1]}^r{ops[2]}"
        elif op == 0x08: s = f"r{ops[0]}=typeof r{ops[1]}"
        elif op == 0x0a: s = f"r{ops[0]}=new r{ops[1]}(r{ops[2]})"
        elif op == 0x0b: s = f"r{ops[0]}=r{ops[1]}.m(r{ops[2]},r{ops[3]},r{ops[4]})"
        elif op == 0x26: s = f"r{ops[0]}=r{ops[1]} in r{ops[2]}"
        elif op == 0x3b: s = f"r{ops[0]}=delete r{ops[1]}[r{ops[2]}]"
        elif op == 0x3d: s = f"r{ops[0]}=r{ops[1]}%r{ops[2]}"
        elif op == 0x4f: s = f"r{ops[0]}=r{ops[1]}<r{ops[2]}"
        elif op == 0x43: s = f"r{ops[0]}=r{ops[1]}.call(r{ops[2]},r{ops[3]})"
        elif op == 0x57: s = f"r{ops[0]}=r{ops[1]}.call(undef,r{ops[2]})"
        elif op == 0x58: s = f"r{ops[0]}=r{ops[1]}.call(undef,r{ops[2]},r{ops[3]},r{ops[4]})"
        elif op == 0x2f: s = f"r{ops[0]}=r{ops[1]}.call(undef,r{ops[2]}),r{ops[3]}=r{ops[4]}"
        print(f"{ip}: {op:3d} {s}")
        ip += 1 + n


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: python tools/disasm.py <start-ip> <end-ip>")
        raise SystemExit(2)
    bc = load_bytecode()
    src = load_interpreter()
    counts = operand_counts(src)
    disasm(bc, counts, int(sys.argv[1]), int(sys.argv[2]))


if __name__ == "__main__":
    main()
