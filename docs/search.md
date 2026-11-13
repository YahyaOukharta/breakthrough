# Search

Negamax alpha-beta in `search()` / `qsearch()` / `think()` in [`bot.cpp`](../bot.cpp).
Each feature sits behind a `#define`, so a variant is one `-D` flag away:

```sh
python3 tools/pack.py -n nets/current.bin -H 384 -B 4 -D SE=0 -o out/no_se.cpp   # same bot without singular extensions
```

Elo numbers are self-play gate matches (300–600 games, ±35–40) against the version
before the change. Self-play Elo overstates arena gain by a lot; the sign is what matters.
Background for every term: [chessprogramming.org](https://www.chessprogramming.org/Search).

## What is in v3.0

| Feature | Flag (value) | Measured | Notes |
|---|---|---|---|
| Iterative deepening + [PVS](https://www.chessprogramming.org/Principal_Variation_Search) | – | base | depth 11–16 in 95 ms |
| [Transposition table](https://www.chessprogramming.org/Transposition_Table) | `TT_BITS` 21 | base | 2M entries × 16 bytes, always-replace if deeper or exact |
| Move ordering | – | base | hash move, captures (closest to our home first, undefended first), killers, history; quiet moves onto attacked unsupported squares last |
| Capture [quiescence](https://www.chessprogramming.org/Quiescence_Search) | – | base | plus up to 2 plies of full evasions when the opponent threatens a safe 7th-rank move |
| [LMR](https://www.chessprogramming.org/Late_Move_Reductions) | `LMR_DIV` 1.8 | base | `ln(depth)·ln(i)/1.8`; never reduce pushes to rank 6+ |
| [Futility pruning](https://www.chessprogramming.org/Futility_Pruning) | `FUT` 60 | +59 | depth ≤ 2 |
| [Reverse futility](https://www.chessprogramming.org/Reverse_Futility_Pruning) | `RFP` 60, `RFP_MAXD` 7 | +54, then +68 for depth 3 → 7 | margin `60·depth` |
| [Aspiration windows](https://www.chessprogramming.org/Aspiration_Windows) | `ASP` 30 | part of +85 batch | widen ×3 on fail |
| [Singular extensions](https://www.chessprogramming.org/Singular_Extensions) + multi-cut | `SE` 2, `SE_DEPTH` 6 | **+95** (+90 at equal time) | biggest single search gain |
| [Internal iterative reduction](https://www.chessprogramming.org/Internal_Iterative_Reductions) | `IIR` 4 | +9…23 alone | no hash move → depth −1 |
| [Late move pruning](https://www.chessprogramming.org/Futility_Pruning#MoveCountBasedPruning) | `LMP` 6, `LMP_D` 3 | +9…23 alone | skip quiet move `i ≥ 6 + depth²` |
| [Improving](https://www.chessprogramming.org/Improving) | `IMP` 1 | +9…23 alone | eval vs 2 plies ago, used in RFP and LMR |
| [History](https://www.chessprogramming.org/History_Heuristic) with gravity, maluses, 1-ply continuation history | `HIST2` 1 | +9…23 alone | `contHist[prev target][from][to]` |
| The four above together | | **+107** at equal time | took the bot from rank 7 to 1 |

Singular extension, the core of it:

```cpp
int sb = ttScore - SE * depth;                                   // "clearly worse than the hash move"
int v = search(own, opp, (depth - 1) / 2, sb - 1, sb, ply, false, ttMove);   // search without it
if (v < sb) singularExt = 1;        // nothing else comes close: extend the hash move
else if (sb >= beta) return sb;     // several moves beat beta: cut (multi-cut)
```

## What did not work

| Idea | Flag | Result | Why / note |
|---|---|---|---|
| [Null move](https://www.chessprogramming.org/Null_Move_Pruning) | `NMP` | −35 | The game is full of zugzwang; passing is often best |
| Race rule (exact runner detection) | `RACE` | −9, −10 | search already sees it |
| Threat extension | `TE` | −28, +12 | noise |
| Double singular extension | `SE_DBL` | −56 | |
| Negative singular extension | `SE_NEG` | −6 | |
| 2-entry TT buckets with aging | `TT2` | +14, +7 | within noise, not adopted |
| History-based LMR, razoring, bad-move pruning | `HLMR`, `RAZOR`, `BMP` | +12, +5, −14 | noise |
| Static eval stored in TT | `TTEVAL` | 0 | no speed gain on CodinGame |
| Retuning margins after v3.0 (LMR 1.0–2.2, LMP 4/9, RFP 45/80, FUT 90, IIR 3, SE 3, ASP) | | −35…+30, no slope | 400 games each at 100 ms; current values are on a plateau |
| [Best-first minimax with UCT](https://tech.io/playgrounds/55004) | `BFS` (`thinkBF`) | −9, −18, −7, −23 | equal to alpha-beta at best with the same net; code kept for experiments |

## Lessons

- Test at **fixed nodes** for speed and determinism, confirm at **real time** before
  shipping. Both agreed every time, but only real time shows a speed cost.
- Features worth +10–20 each are invisible in 300 games; batch them and test the batch.
- An unsound pruning (null move) is immediately visible; do not assume chess wisdom
  transfers.
- A "+30" from one 400-game match is noise until the neighbours of that value agree.
