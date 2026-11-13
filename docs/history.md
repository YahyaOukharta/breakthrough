# History

Built in about a day, 2026-11-12 → 13. "Local" is the gate match against the previous
version (self-play; inflated relative to the arena).

## Versions

| Version | Change | Local | Arena | Rank |
|---|---|---|---|---|
| stub | starter code, first legal move | | 10.23 | 299 |
| v1.0 | bitboard alpha-beta: PVS, TT, LMR, quiescence, static win rules, handcrafted eval | | 27.11 | 33 |
| v1.1 | futility, reverse futility, aspiration, stronger LMR, steeper advancement eval | +232 Elo | 27.46 | 31 |
| v2.0 | first net: 256 hidden, 3M positions played by v1.1 | 94% | 29.80 | 22 |
| v2.1 | net 1: 8.9M positions incl. self-play of net 0 | 95% | 32.95 | 22 |
| v2.2 | net 2 (15M); time budget 93 ms / 970 ms | 83% | 34.36 | 19 |
| v2.3 | net 3 (17.6M) | 63% | 37.67 | 13 |
| v2.4 | target = 60% result + 40% search score | 65.7% | 38.13 | 13 |
| v2.5 | net 5 (29M) + AVX2 inference (3.1M → 4.0M nodes/s) | 55% | 38.88 | 10 |
| v2.6 | mirror-tied hidden units, 43.5M positions | 56.7% | 39.47 | 10 |
| v2.7 | 384 hidden | 70% | 41.13 | 8 |
| v2.8 | 4 output buckets, 108M positions, dedup, 30 epochs cosine; 96 ms | 66.3% | 41.49 | 8 |
| v2.9 | singular extensions | 63.3% | 41.21 | 7 |
| v3.0 | IIR, late move pruning, improving, history upgrade, reverse futility to depth 7; net 10b (136M); 95 ms | +90 Elo at 100 ms | 44.25 | 1 |
| **v3.1** | net 11e: 640 hidden, mirror-tied, 166M unique positions; stored at half size (81.6k chars) | +52 Elo at 100 ms (800 games) | **44.23** | **1** |

v3.0 arena run: 72 wins, 18 losses, margin over #2 0.08 (inside arena noise). v3.1: again
72–18, margin 0.25. The arena score is relative, so a stronger bot at the top shows up as
a wider margin more than as a higher number. All sources (weights removed): [`versions/`](../versions).

## What mattered, in order

1. **A correct, fast alpha-beta with exact tactical rules** — starter → rank 33.
2. **Replacing the handcrafted eval with a net** — the handcrafted eval gained +232 Elo
   locally from tuning and +0.35 arena points. It was the ceiling. The net was not.
3. **The self-play loop** — each net generates data for the next; six generations took
   rank 22 → 10.
4. **Width at the right time** — 384 hidden cost 4% speed on CodinGame and gave a full
   rank bracket (10 → 8). 512 was too slow for the data available then.
5. **Search features that do not depend on null move** — singular extensions and the
   IIR/LMP/improving/history batch: rank 7 → 1 with the same class of net.
6. **Measuring everything** — about half of the ideas tried were neutral or negative
   (lists in [search.md](search.md) and [nnue.md](nnue.md)).

## Dead ends

- Tuning the handcrafted eval further.
- Null move pruning (zugzwang).
- More data for a 384 net beyond ~110M positions (width was the fix: 512 +42, 640 +52).
- Best-first minimax as a drop-in replacement for alpha-beta.
- Margin retuning after v3.0: flat.
- Learning from arena games: only one's own ~90 games per submission are available.
- Raising or lowering the deadline to fix the ~1% timeouts: no effect.
