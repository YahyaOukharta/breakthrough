#!/usr/bin/env python3
"""Local league for Breakthrough bot versions (in the spirit of psyleague).

Every version is frozen (source + binary) under league/ and plays the previous versions
through the native referee (build/referee). All game results are appended to
league/results.jsonl; ratings are a Bradley-Terry fit over the whole history.

  league.py add NAME [SRC]         freeze SRC (default bot.cpp) as version NAME
  league.py run [-b NAME] [-g N]   play N games per pairing (NAME vs all, or all pairs)
  league.py match A B [-g N]       head-to-head only (A/B may be league names or paths)
  league.py show                   rating table
Common options: -n NODES (fixed nodes per move, default 100000; 0 = use time),
                -t MS (time per move when -n 0), -j THREADS, -o OPENING_PLIES
"""
import argparse, json, math, os, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAGUE = os.path.join(ROOT, "league")
BOTS = os.path.join(LEAGUE, "bots")
SRCS = os.path.join(LEAGUE, "src")
RESULTS = os.path.join(LEAGUE, "results.jsonl")
REFEREE = os.path.join(ROOT, "build", "referee")
CXX = [os.environ.get("CXX", "c++"), "-O3", "-std=c++17", "-march=native", "-DLOCAL"]


def build_referee():
    src = os.path.join(ROOT, "tools", "referee.cpp")
    if not os.path.exists(REFEREE) or os.path.getmtime(REFEREE) < os.path.getmtime(src):
        os.makedirs(os.path.dirname(REFEREE), exist_ok=True)
        subprocess.check_call(CXX + ["-pthread", "-o", REFEREE, src])


def bot_names():
    if not os.path.isdir(BOTS):
        return []
    return sorted(os.listdir(BOTS), key=lambda n: os.path.getmtime(os.path.join(BOTS, n)))


def resolve(name):
    p = os.path.join(BOTS, name)
    src = os.path.join(SRCS, name + ".cpp")
    if not os.path.exists(p) and os.path.exists(src):   # fresh clone: binaries are not tracked
        os.makedirs(BOTS, exist_ok=True)
        subprocess.check_call(CXX + ["-o", p, src])
    if os.path.exists(p):
        return p
    if os.path.exists(name):
        return os.path.abspath(name)
    sys.exit(f"unknown bot: {name}")


def cmd_add(a):
    os.makedirs(BOTS, exist_ok=True)
    os.makedirs(SRCS, exist_ok=True)
    dst = os.path.join(BOTS, a.name)
    if os.path.exists(dst):
        sys.exit(f"{a.name} already exists (versions are immutable)")
    src = a.src or os.path.join(ROOT, "bot.cpp")
    subprocess.check_call(CXX + ["-o", dst, src])
    shutil.copy(src, os.path.join(SRCS, a.name + ".cpp"))
    print(f"added {a.name}")


def play(a, na, nb, record=True):
    build_referee()
    cmd = [REFEREE, resolve(na), resolve(nb), "-g", str(a.games), "-j", str(a.threads),
           "-o", str(a.open), "-s", str(a.seed if a.seed else int(time.time() * 1000) % 2**31)]
    cmd += ["-n", str(a.nodes)] if a.nodes else ["-t", str(a.ms)]
    if getattr(a, "pa", None): cmd += ["-pa", a.pa]
    if getattr(a, "nb", None): cmd += ["-nb", str(a.nb)]
    if getattr(a, "pb", None): cmd += ["-pb", a.pb]
    out = subprocess.check_output(cmd, text=True)
    s = json.loads(out.strip().splitlines()[-1])
    rec = {"a": na, "b": nb, "wins_a": s["wins_a"], "wins_b": s["wins_b"], "faults_a": s["faults_a"],
           "faults_b": s["faults_b"], "white_wins": s["white_wins"], "games": s["games"],
           "nodes": s["nodes"], "ms": s["ms"], "avg_plies": s["avg_plies"], "time": int(time.time())}
    if record:
        with open(RESULTS, "a") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def elo_diff(w, l):
    n = w + l
    if n == 0:
        return 0.0, 0.0
    p = min(max((w + 0.5) / (n + 1), 1e-6), 1 - 1e-6)
    elo = -400 * math.log10(1 / p - 1)
    se = math.sqrt(p * (1 - p) / n)
    lo, hi = max(p - 1.96 * se, 1e-6), min(p + 1.96 * se, 1 - 1e-6)
    err = (-400 * math.log10(1 / hi - 1) + 400 * math.log10(1 / lo - 1)) / 2
    return elo, err


def report(r):
    n = r["wins_a"] + r["wins_b"]
    elo, err = elo_diff(r["wins_a"], r["wins_b"])
    pct = 100.0 * r["wins_a"] / n if n else 0
    f = f"  faults {r['faults_a']}/{r['faults_b']}" if r["faults_a"] or r["faults_b"] else ""
    print(f"{r['a']} vs {r['b']}: {r['wins_a']}-{r['wins_b']} ({pct:.1f}%)  elo {elo:+.0f} +/- {err:.0f}"
          f"  white {100.0 * r['white_wins'] / max(n, 1):.0f}%  plies {r['avg_plies']}{f}", flush=True)


def cmd_match(a):
    rec = os.path.exists(os.path.join(BOTS, a.a)) and os.path.exists(os.path.join(BOTS, a.b)) and not a.pa and not a.pb and not a.nb
    report(play(a, a.a, a.b, record=rec))


def cmd_run(a):
    names = bot_names()
    if a.bot:
        opp = [n for n in names if n != a.bot]
        if a.last:
            opp = opp[-a.last:]
        pairs = [(a.bot, n) for n in opp]
    else:
        pairs = [(x, y) for i, x in enumerate(names) for y in names[i + 1:]]
    for x, y in pairs:
        report(play(a, x, y))
    cmd_show(a)


def load_results():
    if not os.path.exists(RESULTS):
        return []
    return [json.loads(l) for l in open(RESULTS) if l.strip()]


def cmd_show(a):
    res = load_results()
    names = bot_names()
    idx = {n: i for i, n in enumerate(names)}
    k = len(names)
    w = [[0.0] * k for _ in range(k)]
    faults = [0] * k
    for r in res:
        if r["a"] in idx and r["b"] in idx:
            i, j = idx[r["a"]], idx[r["b"]]
            w[i][j] += r["wins_a"]
            w[j][i] += r["wins_b"]
            faults[i] += r["faults_a"]
            faults[j] += r["faults_b"]
    # Bradley-Terry (MM algorithm) with a weak prior: one win and one loss against a
    # virtual average player, which keeps unbeaten/winless bots finite.
    p = [1.0] * k
    for _ in range(500):
        np_ = []
        for i in range(k):
            wins = 1.0 + sum(w[i])
            den = 2.0 / (p[i] + 1.0)
            for j in range(k):
                n = w[i][j] + w[j][i]
                if n:
                    den += n / (p[i] + p[j])
            np_.append(wins / den)
        g = math.exp(sum(math.log(x) for x in np_) / k) if k else 1
        p = [x / g for x in np_]
    rows = []
    for n in names:
        i = idx[n]
        won, lost = sum(w[i]), sum(w[j][i] for j in range(k))
        rows.append((400 * math.log10(p[i]), n, int(won + lost), 100 * won / (won + lost) if won + lost else 0, faults[i]))
    base = rows[0][0] if rows else 0  # oldest version anchored at 0
    print(f"\n{'bot':<16}{'elo':>7}{'games':>8}{'win%':>7}{'faults':>8}")
    for elo, n, g, pct, f in sorted(rows, reverse=True):
        print(f"{n:<16}{elo - base:>7.0f}{g:>8}{pct:>7.1f}{f:>8}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("-g", "--games", type=int, default=200)
        p.add_argument("-n", "--nodes", type=int, default=100000)
        p.add_argument("-t", "--ms", type=int, default=50)
        p.add_argument("-j", "--threads", type=int, default=6)
        p.add_argument("-o", "--open", type=int, default=4)
        p.add_argument("-s", "--seed", type=int, default=0)
        p.add_argument("--pa"); p.add_argument("--pb"); p.add_argument("--nb", type=int)

    p = sub.add_parser("add"); p.add_argument("name"); p.add_argument("src", nargs="?"); p.set_defaults(f=cmd_add)
    p = sub.add_parser("run"); p.add_argument("-b", "--bot"); p.add_argument("--last", type=int, default=0)
    common(p); p.set_defaults(f=cmd_run)
    p = sub.add_parser("match"); p.add_argument("a"); p.add_argument("b"); common(p); p.set_defaults(f=cmd_match)
    p = sub.add_parser("show"); p.set_defaults(f=cmd_show)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
