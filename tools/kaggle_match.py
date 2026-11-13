#!/usr/bin/env python3
"""Play gate matches on Kaggle CPU kernels (fixed nodes per move, so hardware speed is irrelevant).

  kaggle_match.py push NAME A.cpp B.cpp [A2.cpp B2.cpp ...] [--games 300] [--nodes 100000]
  kaggle_match.py status NAME
  kaggle_match.py fetch NAME
Sources are packed single-file bots (out/*.cpp). Each pairing is one kernel bt-match-NAME-i.
"""
import glob, json, os, re, shutil, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROF = os.environ.get("BT_KP", "1")   # credential profile: 1 = default, N = files with suffix _N
_SUF = "" if PROF == "1" else f"_{PROF}"
USER = os.environ.get("KAGGLE_USERNAME") or open(os.path.expanduser(f"~/.kaggle/user{_SUF}")).read().strip()
TOKFILE = f"~/.kaggle/access_token{_SUF}"
SFX = "" if PROF == "1" else f"_p{PROF}"
ENV = {**os.environ, "KAGGLE_API_TOKEN": open(os.path.expanduser(TOKFILE)).read().strip(),
       "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ["PATH"]}
SCRIPT = '''import glob, os, subprocess
A, B, GAMES, NODES, MS = "%s", "%s", %d, %d, %d
d = os.path.dirname(glob.glob("/kaggle/input/**/referee.cpp", recursive=True)[0])
cc = ["g++", "-O3", "-std=c++17", "-march=native", "-pthread"]
subprocess.check_call(cc + ["-o", "/tmp/referee", d + "/referee.cpp"])
subprocess.check_call(cc + ["-o", "/tmp/a", d + "/" + A])
subprocess.check_call(cc + ["-o", "/tmp/b", d + "/" + B])
# MS > 0: real time control (2 games at once on 4 vCPUs so every bot has a core to itself)
mode = ["-j", "2", "-n", "0", "-t", str(MS), "-f", str(3 * MS), "-x", "20"] if MS else ["-j", "4", "-n", str(NODES)]
out = subprocess.check_output(["/tmp/referee", "/tmp/a", "/tmp/b", "-g", str(GAMES), "-s", "777"] + mode, text=True)
print("RESULT", A, B, out.strip().splitlines()[-1], flush=True)
'''


def kg(*a):
    return subprocess.run(["kaggle", *a], env=ENV, capture_output=True, text=True)


def push(name, files, games, nodes, ms=0):
    d = os.path.join(ROOT, "kaggle", "matchsrc" + SFX)
    os.makedirs(d, exist_ok=True)
    new = not os.path.exists(os.path.join(d, "dataset-metadata.json"))
    json.dump({"title": "bt-match", "id": f"{USER}/bt-match", "licenses": [{"name": "CC0-1.0"}]},
              open(os.path.join(d, "dataset-metadata.json"), "w"))
    shutil.copy(os.path.join(ROOT, "tools", "referee.cpp"), d)
    for f in files:
        shutil.copy(f, d)
    r = kg("datasets", "create", "-p", d) if new else kg("datasets", "version", "-p", d, "-m", name)
    print((r.stdout + r.stderr).strip().splitlines()[-1][:120])
    for _ in range(40):
        time.sleep(6)
        if "ready" in (kg("datasets", "status", f"{USER}/bt-match").stdout):
            break
    time.sleep(10)
    for i in range(0, len(files), 2):
        k = os.path.join(ROOT, "kaggle", f"m{SFX}_{name}_{i // 2 + 1}")
        os.makedirs(k, exist_ok=True)
        open(os.path.join(k, "match.py"), "w").write(SCRIPT % (os.path.basename(files[i]), os.path.basename(files[i + 1]), games, nodes, ms))
        json.dump({"id": f"{USER}/bt-match-{name}-{i // 2 + 1}", "title": f"bt-match-{name}-{i // 2 + 1}", "code_file": "match.py",
                   "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": False,
                   "enable_internet": False, "dataset_sources": [f"{USER}/bt-match"]}, open(os.path.join(k, "kernel-metadata.json"), "w"))
        r = kg("kernels", "push", "-p", k)
        print(i // 2 + 1, (r.stdout + r.stderr).strip().splitlines()[-1][:110], flush=True)


def kernels(name):
    return sorted(glob.glob(os.path.join(ROOT, "kaggle", f"m{SFX}_{name}_*")))


def status(name):
    st = []
    for k in kernels(name):
        r = kg("kernels", "status", f"{USER}/bt-match-{name}-{k.rsplit('_', 1)[1]}")
        m = re.search(r"KernelWorkerStatus\.(\w+)", r.stdout + r.stderr)
        st.append(m.group(1) if m else "?")
    print(" ".join(st))
    return st


def fetch(name):
    for k in kernels(name):
        i = k.rsplit("_", 1)[1]
        d = os.path.join(ROOT, "kaggle", "out", f"m{SFX}_{name}_{i}")
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        kg("kernels", "output", f"{USER}/bt-match-{name}-{i}", "-p", d)
        for f in glob.glob(os.path.join(d, "*.log")):
            txt = open(f).read()
            m = re.search(r'RESULT (\S+) (\S+) (\{.*?\})', txt.replace('\\"', '"'))
            if not m:
                print(i, "no result:", txt[-300:]); continue
            s = json.loads(m.group(3))
            import math
            w, l = s["wins_a"], s["wins_b"]
            p = (w + 0.5) / (w + l + 1)
            se = math.sqrt(p * (1 - p) / (w + l))
            elo = -400 * math.log10(1 / p - 1)
            err = (-400 * math.log10(1 / min(p + 1.96 * se, .999) - 1) + 400 * math.log10(1 / max(p - 1.96 * se, .001) - 1)) / 2
            print(f"{m.group(1)} vs {m.group(2)}: {w}-{l} ({100 * w / (w + l):.1f}%)  elo {elo:+.0f} +/- {err:.0f}  faults {s['faults_a']}/{s['faults_b']}" + (f"  [{s['ms']} ms/move]" if not s["nodes"] else ""))


if __name__ == "__main__":
    c, name, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    if c == "push":
        games, nodes, ms, files = 300, 100000, 0, []
        i = 0
        while i < len(rest):
            if rest[i] == "--games": games = int(rest[i + 1]); i += 2
            elif rest[i] == "--nodes": nodes = int(rest[i + 1]); i += 2
            elif rest[i] == "--ms": ms = int(rest[i + 1]); i += 2
            else: files.append(rest[i]); i += 1
        push(name, files, games, nodes, ms)
    elif c == "status": status(name)
    elif c == "fetch": fetch(name)
