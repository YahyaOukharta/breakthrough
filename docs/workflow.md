# Workflow

Rule: nothing is submitted unless it beats the current version in a gate match.

## Tools

| Tool | Use |
|---|---|
| `build/referee A B -g 400 -n 100000 -j 8` | Match between two binaries. Random openings (`-o` plies), each played with both colours. `-n` nodes per move, or `-t` ms per move with `-n 0`. Prints a JSON line per game and a summary |
| `tools/league.py add NAME [SRC]` | Freeze a version (source in `league/src`, binary in `league/bots`) |
| `tools/league.py match A B -g 400` | Head-to-head with Elo ± error |
| `tools/league.py run` / `show` | Round robin and rating table |
| `tools/pack.py` | Build a submission, optionally with `-D FLAG=VALUE` variants |
| `tools/arena.py fetch` / `stats` | Own arena battles per opponent through the CodinGame API |

The referee mirrors the [official one](https://github.com/darkhorse64/CG_Breakthrough)
(same move order and protocol) and hands the opening to both bots through `BT_OPENING`.
The idea of a local league comes from [psyleague](https://github.com/FakePsyho/psyleague);
[cg-brutaltester](https://github.com/dreignier/cg-brutaltester) is the generic alternative.

## Testing method

1. **Fixed nodes** (`-n 100000`): deterministic, immune to machine load, many games in
   parallel. Default for every experiment.
2. **Real time** (`-n 0 -t 100`): before shipping, and whenever a change alters speed
   (net size, eval caching). Needs an idle machine and at most one game per core.
3. Fixed match length (300–600 games), no early stopping. ±35–40 Elo at 300–400 games:
   anything smaller is noise, so test small ideas as a batch.
4. Ship, then read the arena. Self-play Elo overstates the arena gain several times over,
   and one arena run (~90 games) is itself ±0.4 points.

More on engine testing:
[engine testing guide](https://dannyhammer.github.io/engine-testing-guide/print.html),
[Fishtest FAQ](https://github.com/official-stockfish/fishtest/wiki/Fishtest-faq).

## Cloud

A laptop generates ~0.17M positions per minute; the net wants 100M+.

| Tool | What | Rate seen |
|---|---|---|
| `tools/kaggle_gen.py` | self-play on Kaggle CPU kernels (4 vCPU each) | ~1.1M positions/min on 5 kernels |
| `tools/kaggle_train.py` | `train.py` on a Kaggle GPU | 108M positions × 30 epochs in 23 min (~17× an M1 GPU) |
| `tools/kaggle_match.py` | gate matches on Kaggle CPU | 300 games at fixed nodes in ~3 min; 400 games at 100 ms in ~20 min |
| `tools/modal_gen.py` | self-play on [Modal](https://modal.com) | 3–4M positions/min per 24-thread container |

Kaggle setup: `pip install kaggle`, user name in `~/.kaggle/user` (or `KAGGLE_USERNAME`),
API token in `~/.kaggle/access_token`. The tools create private datasets/kernels named
`bt-*` and keep their working files in `kaggle/` (not tracked).

```sh
python3 tools/kaggle_gen.py upload nets/current.bin               # engine + net as a private dataset
python3 tools/kaggle_gen.py push g15 5 4000 15000 current.bin 384 # 5 kernels
python3 tools/kaggle_gen.py fetch g15 5 g15                      # -> data/g15_*.bin
python3 tools/kaggle_train.py push n12 --gen g15:5 -- '/kaggle/input/**/k_*.bin' --hidden 384 --buckets 4 --epochs 30 --lam 0.6 --dedup --cosine
python3 tools/kaggle_match.py push gate out/new.cpp out/v3.0.cpp --games 400 --ms 100
```

## CodinGame specifics

- **Limit is 100k characters**, not bytes → weights as UTF-16 text ([nnue.md](nnue.md)).
- **No compiler flags** → `#pragma GCC optimize("O3,inline,omit-frame-pointer,unroll-loops")`
  and `#pragma GCC target("avx2,bmi,bmi2,popcnt,lzcnt")` before the includes
  ([forum](https://forum.codingame.com/t/c-and-the-o3-compilation-flag/1670),
  [pragma playground](https://tech.io/playgrounds/58302)).
- **Timing:** measured from when the referee starts sending input to when it reads the
  output ([forum](https://forum.codingame.com/t/timeouts-how-do-they-work/24504)).
  Start the clock after the first input line. 95 ms of the 100 ms is used; measured
  worst case ~96.4 ms at a 96 ms deadline.
- **Timeouts:** ~1% of arena games are lost on time regardless of the deadline (93, 95 or
  96 ms); the position replays fine locally, so it looks like the host pausing the
  process. Not solved.
- **Speed there:** ~4.0M nodes/s with the 384 net, depth 11–12 in the middlegame.
- **Arena noise:** a submission plays ~90 games. Resubmitting the same code moves the
  score by a few tenths, so do not resubmit a #1 for fun.
- Submitting: paste `out/submission.cpp` into the IDE, or use the
  [CodinGame API](https://www.codingame.com/api/v1/docs/api).

## Release checklist

1. `tools/pack.py` → check the character count (< 100k).
2. Gate vs the current version: fixed nodes, then 100 ms.
3. `tools/league.py add vX.Y out/vX.Y.cpp`.
4. One test game on CodinGame: read the stderr time log (max ms, nodes/s).
5. Submit, wait for 100%, record score and rank in [history.md](history.md).
