#!/usr/bin/env python3
"""Run self-play data generation on Kaggle CPU kernels (4 vCPUs each).

  kaggle_gen.py upload NET.bin              refresh the private dataset (bot.cpp + net)
  kaggle_gen.py push TAG N GAMES SEED NET HID [NODES]
                                            start N kernels bt-TAG-1..N, GAMES per process
  kaggle_gen.py status TAG N
  kaggle_gen.py fetch TAG N PREFIX          download finished outputs to data/PREFIX_<seed>.bin
Account: ~/.kaggle/user (user name) and ~/.kaggle/access_token (API token, never printed).
"""
import glob, json, os, re, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROF = os.environ.get("BT_KP", "1")   # credential profile: 1 = default, N = files with suffix _N
_SUF = "" if PROF == "1" else f"_{PROF}"
USER = os.environ.get("KAGGLE_USERNAME") or open(os.path.expanduser(f"~/.kaggle/user{_SUF}")).read().strip()
TOKFILE = f"~/.kaggle/access_token{_SUF}"
SFX = "" if PROF == "1" else f"_p{PROF}"
ENV = {**os.environ, "KAGGLE_API_TOKEN": open(os.path.expanduser(TOKFILE)).read().strip(),
       "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ["PATH"]}


def kg(*a):
    return subprocess.run(["kaggle", *a], env=ENV, capture_output=True, text=True)


def upload(net):
    d = os.path.join(ROOT, "kaggle", "engine" + SFX)
    new = not os.path.isdir(d)
    os.makedirs(d, exist_ok=True)
    json.dump({"title": "bt-engine", "id": f"{USER}/bt-engine", "licenses": [{"name": "CC0-1.0"}]},
              open(os.path.join(d, "dataset-metadata.json"), "w"))
    shutil.copy(os.path.join(ROOT, "bot.cpp"), d)
    shutil.copy(net, d)
    r = kg("datasets", "create", "-p", d) if new else kg("datasets", "version", "-p", d, "-m", "update")
    print((r.stdout + r.stderr).strip().splitlines()[-1])


def push(tag, n, games, seed, net, hid, nodes=3000):
    tpl = open(os.path.join(ROOT, "tools", "kaggle_gen_kernel.py")).read()
    for i in range(1, n + 1):
        d = os.path.join(ROOT, "kaggle", f"k{SFX}_{tag}_{i}")
        os.makedirs(d, exist_ok=True)
        s = re.sub(r"GAMES, NODES, SEED, NET, HID = .*", f'GAMES, NODES, SEED, NET, HID = {games}, {nodes}, {seed + 10 * i}, "{net}", {hid}', tpl)
        open(os.path.join(d, "gen.py"), "w").write(s)
        json.dump({"id": f"{USER}/bt-{tag}-{i}", "title": f"bt-{tag}-{i}", "code_file": "gen.py", "language": "python",
                   "kernel_type": "script", "is_private": True, "enable_gpu": False, "enable_internet": False,
                   "dataset_sources": [f"{USER}/bt-engine"]}, open(os.path.join(d, "kernel-metadata.json"), "w"))
        r = kg("kernels", "push", "-p", d)
        print(i, (r.stdout + r.stderr).strip().splitlines()[-1][:110], flush=True)


def status(tag, n):
    out = []
    for i in range(1, n + 1):
        r = kg("kernels", "status", f"{USER}/bt-{tag}-{i}")
        m = re.search(r"KernelWorkerStatus\.(\w+)", r.stdout + r.stderr)
        out.append(m.group(1) if m else "?")
    print(" ".join(out))
    return out


def fetch(tag, n, prefix):
    st = status(tag, n)
    for i in range(1, n + 1):
        if st[i - 1] != "COMPLETE":
            continue
        d = os.path.join(ROOT, "kaggle", "out", f"{tag}{SFX}_{i}")
        if os.path.isdir(d):
            continue
        os.makedirs(d)
        kg("kernels", "output", f"{USER}/bt-{tag}-{i}", "-p", d)
        for f in glob.glob(os.path.join(d, "k_*.bin")):
            shutil.move(f, os.path.join(ROOT, "data", f"{prefix}_{os.path.basename(f)[2:]}"))
        print("fetched", i, flush=True)


if __name__ == "__main__":
    c, a = sys.argv[1], sys.argv[2:]
    if c == "upload": upload(a[0])
    elif c == "push": push(a[0], int(a[1]), int(a[2]), int(a[3]), a[4], int(a[5]), int(a[6]) if len(a) > 6 else 3000)
    elif c == "status": status(a[0], int(a[1]))
    elif c == "fetch": fetch(a[0], int(a[1]), a[2])
