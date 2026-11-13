# Breakthrough bot

A bot for the [CodinGame Breakthrough arena](https://www.codingame.com/multiplayer/bot-programming/breakthrough):
bitboard alpha-beta search with a small NNUE-style neural evaluation, trained from
self-play, all in one C++ file under the 100k-character limit.

**Result:** rank **1 / 381** (score 44.25) on 2026-11-13 as `yhyoxx`, version `v3.0`
([`versions/v3.0.cpp`](versions/v3.0.cpp) is the submitted source, without its weights).

> The sources in `versions/` do not embed their network weights. The trained nets are
> kept separately in [`tools/nets/`](tools/nets).

| Stage | Arena score | Rank |
|---|---|---|
| Starter code | 10.23 | 299 |
| Alpha-beta + handcrafted eval (v1.1) | 27.46 | 31 |
| First neural eval (v2.0) | 29.80 | 22 |
| Six self-play generations, 256 → 384 hidden (v2.7) | 41.13 | 8 |
| Bigger data, output buckets (v2.8) | 41.49 | 8 |
| Search upgrades + newest net (v3.0) | 44.25 | 1 |

Full version table: [docs/history.md](docs/history.md).

## The game

8x8 board, 16 pawns each. A pawn moves one step forward (straight or diagonal) and
captures diagonally only. First pawn on the far row wins. 1000 ms for the first turn,
100 ms after. [Rules](https://en.wikipedia.org/wiki/Breakthrough_%28board_game%29),
[official referee](https://github.com/darkhorse64/CG_Breakthrough).

## How it works

```
 self-play (bot.cpp, BT_GEN)  ──►  data/*.bin  ──►  tools/train.py  ──►  tools/nets/*.bin
          ▲                                                                  │
          └──────────── stronger net plays the next generation ◄─────────────┤
                                                                             ▼
 CodinGame  ◄──  out/submission.cpp  ◄──  tools/pack.py (embed net)  ◄──  gate match
                                                                     (referee / league)
```

- **Engine** — two bitboards, the side to move always moves "up", so there is one code
  path and no colour. → [docs/engine.md](docs/engine.md)
- **Search** — iterative deepening PVS with a transposition table, LMR, futility
  prunings, singular extensions, history heuristics. Every feature has a measured Elo.
  → [docs/search.md](docs/search.md)
- **Evaluation** — 128 inputs → 384 hidden (shared by both perspectives, SCReLU) → 4
  output heads picked by pawn count; int16, incrementally updated, AVX2.
  → [docs/nnue.md](docs/nnue.md)
- **Workflow** — own native referee, a local league, fixed-length gate matches, cloud
  data generation and GPU training. Nothing ships without beating the previous version.
  → [docs/workflow.md](docs/workflow.md)

## Quick start

Needs a C++17 compiler; Python 3 with `numpy` (packing) and `torch` (training).

```sh
make                 # build/bot (engine + local tools) and build/referee
make perft           # move generator check: 6182818

# the handcrafted-eval versions are complete: play v1.1 against v1.0 (20k nodes per move)
c++ -O3 -std=c++17 -march=native -o build/v1.0 versions/v1.0.cpp
c++ -O3 -std=c++17 -march=native -o build/v1.1 versions/v1.1.cpp
./build/referee build/v1.1 build/v1.0 -g 200 -n 20000 -j 8
```

One full improvement cycle (generation 0 uses the handcrafted eval; later ones add
`BT_NET=tools/nets/current.bin`):

```sh
# 1. self-play data: 2000 games, 3000 nodes per move, seed 1
mkdir -p data nets
BT_GEN=2000:3000:1:data/g0_1.bin ./build/bot

# 2. train (the recipe of the v3.0 net)
python3 tools/train.py -o tools/nets/new.bin 'data/g*_*.bin' --hidden 384 --buckets 4 \
        --epochs 30 --lam 0.6 --dedup --cosine --no-side

# 3. pack into a single-file submission, 4. gate against the previous best
python3 tools/pack.py -n tools/nets/new.bin -H 384 -B 4 -o out/new.cpp
python3 tools/league.py add cand out/new.cpp
python3 tools/league.py match cand build/v1.1 -g 400 -n 100000
```

## Layout

| Path | What |
|---|---|
| `bot.cpp` | The whole engine: search, evaluation, data generator (`#ifdef LOCAL`) |
| `tools/nets/` | Trained nets (`.bin`), with a table of sizes and versions |
| `versions/` | Every submitted version as a single file. v1.x are complete; v2.0+ have the weight literal cut (they show the code, they do not compile) |
| `tools/referee.cpp` | Fast native referee, mirrors the official Java one |
| `tools/league.py` | Freeze versions, play matches, Elo |
| `tools/train.py` | PyTorch trainer, exports the int16 net |
| `tools/pack.py` | Builds the submission: embeds the net, strips local code |
| `tools/strip_net.py` | Copies submissions without their weights (how `versions/` is made) |
| `tools/kaggle_*.py`, `tools/modal_gen.py` | Data generation, training and gate matches in the cloud |
| `tools/arena.py` | Download own arena battles through the CodinGame API |
| `docs/` | How each part works, what was measured, what to try next |

## Docs

1. [Engine](docs/engine.md) — board, move generation, static win rules
2. [Search](docs/search.md) — every technique, with code pointers and Elo
3. [NNUE](docs/nnue.md) — architecture, quantization, data, training, embedding
4. [Workflow](docs/workflow.md) — testing, cloud, CodinGame specifics
5. [History](docs/history.md) — versions, what worked, what did not
6. [Future](docs/future.md) — open ideas
7. [Resources](docs/resources.md) — papers, posts and code this is built on
