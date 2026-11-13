#!/usr/bin/env python3
"""Copy packed submissions without their network weights (for publishing).

  strip_net.py league/src/*.cpp -o versions/

The weight literal is cut to its first 48 characters and an #error explains how to
rebuild, so the published file documents the code but does not compile into a bot.
"""
import argparse, os, re

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("-o", "--out", required=True)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
MSG = ('#error "Network weights are not included. Train a net (docs/nnue.md) and build a '
       'submission with tools/pack.py."\n')
for f in a.files:
    s = open(f, encoding="utf-8").read()
    s, n = re.subn(r'(NN_DATA\[\] = u")([^"]{48})[^"]*(";\n)', lambda m: m.group(1) + m.group(2) + "..." + m.group(3) + MSG, s)
    open(os.path.join(a.out, os.path.basename(f)), "w", encoding="utf-8").write(s)
    print(f"{os.path.basename(f)}: {'weights removed' if n else 'no net'} ({len(s)} chars)")
