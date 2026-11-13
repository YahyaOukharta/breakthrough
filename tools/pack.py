#!/usr/bin/env python3
"""Build the single-file CodinGame submission.

  pack.py [-n NET.bin] [-H hidden] [-D NAME=VALUE ...] [-o out/submission.cpp] [SRC]

Strips `#ifdef LOCAL ... #endif` blocks, bakes -D overrides in as #defines, and embeds the
net as a UTF-16 string literal (one character per int16 weight; CodinGame's 100k limit
counts characters, not bytes).
"""
import argparse, os, re, sys
import numpy as np

OFF = 27756  # value + OFF stays in [256, 0xD800): no controls, quotes or surrogates
ap = argparse.ArgumentParser()
ap.add_argument("src", nargs="?", default="bot.cpp")
ap.add_argument("-n", "--net")
ap.add_argument("-H", "--hidden", type=int, default=256)
ap.add_argument("-B", "--buckets", type=int, default=1)
ap.add_argument("-D", action="append", default=[])
ap.add_argument("-S", "--sym", action="store_true", help="mirror-tied net: store half the units")
ap.add_argument("-o", "--out", default="out/submission.cpp")
a = ap.parse_args()

s = open(a.src, encoding="utf-8").read()
s = re.sub(r"#ifdef LOCAL\n.*?\n#endif\n", "", s, flags=re.S)
defs = "".join(f"#define {d.replace('=', ' ', 1)}\n" for d in a.D)
net = ""
if a.net:
    h = a.hidden
    raw = open(a.net, "rb").read()
    nb = a.buckets
    n16 = 128 * h + h + 2 * h * nb
    assert len(raw) == n16 * 2 + 4 * nb, f"net size mismatch for hidden={h} buckets={nb}"
    v = np.frombuffer(raw[:n16 * 2], dtype="<i2").astype(np.int64)
    if a.sym:
        k = h // 2
        W, B, O = v[:128 * h].reshape(128, h), v[128 * h:129 * h], v[129 * h:].reshape(nb, 2, h)
        mir = np.arange(128) ^ 7
        assert (W[mir, k:] == W[:, :k]).all() and (B[k:] == B[:k]).all() and (O[:, :, k:] == O[:, :, :k]).all(), "net is not mirror-tied"
        v = np.concatenate([W[:, :k].reshape(-1), B[:k], O[:, :, :k].reshape(-1)])
    obs = np.frombuffer(raw[n16 * 2:], dtype="<i4").astype(np.int64)
    v = np.concatenate([v, np.stack([obs >> 14, obs & 16383], axis=1).reshape(-1)])
    assert np.abs(v).max() <= 27500, "weight out of encodable range"
    codes = v + OFF
    codes[(codes == 0x2028) | (codes == 0x2029)] += 2  # avoid line/paragraph separators
    text = "".join(map(chr, codes.tolist()))
    symdef = '#define NN_SYM 1\n' if a.sym else ''
    net = f'#define NN_EMBED 1\n#define NN_OFF {OFF}\n#define NN_H {h}\n#define NN_B {nb}\n{symdef}static const char16_t NN_DATA[] = u"{text}";\n'
assert "//@NET_DATA@" in s
s = s.replace("//@NET_DATA@", "//@NET_DATA@" if not net else "")
if net:
    # NN_H must be defined before its first use; the data goes where the marker was.
    s = s.replace("#ifndef NN_H", net + "#ifndef NN_H", 1)
if defs:
    i = s.index("#include")
    s = s[:i] + defs + s[i:]
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
open(a.out, "w", encoding="utf-8").write(s)
print(f"{a.out}: {len(s)} chars, {len(s.encode('utf-8'))} bytes")
