# Future work

State at the time of writing: v3.0 is #1 by a margin inside arena noise. Search margins
are on a plateau and a 384 net is saturated by the data, so the next gain has to come
from a bigger evaluation or a structurally different idea.

## In progress / first in line

- [ ] **Wider net.** A 512-wide net (4 buckets, 4 buckets, 166M unique positions) has
  the best validation loss so far (0.4904 vs 0.4937 for 384), but 512 untied is 107k
  characters and ~29% slower. First real-time gate (400 games, 100 ms): **+33 ± 34** vs v3.0,
  promising but not proven. Train **512 and 640 mirror-tied** (`train.py --sym`), pack
  with `pack.py -S` (half storage, fits), and gate at 100 ms per move, not fixed nodes.
- [ ] **Speed for wide nets.** The cost of width is the output layer and the accumulator
  update. Try: evaluation cache keyed by hash, int8 output weights, updating both
  perspectives in one pass, pairwise multiplication instead of SCReLU.
- [ ] **Second hidden layer** (e.g. 2×384 → 16 → 1 per bucket), the standard next step
  after a single-layer NNUE.

## Search

- [ ] **Correction history**: learn the eval's systematic error per pawn structure
  ([cpw](https://www.chessprogramming.org/Static_Evaluation_Correction_History)).
- [ ] **SPSA tuning** of all margins at once instead of one-at-a-time matches
  ([OpenBench notes](https://github.com/AndyGrant/OpenBench/wiki/SPSA-Tuning-Workloads)).
- [ ] **SPRT** instead of fixed-length gates to spend games where they are needed
  ([guide](https://dannyhammer.github.io/engine-testing-guide/print.html)).
- [ ] **Best-first search, upgraded**: mix minimax and average backups, use net-derived
  priors, reuse the tree between turns (the reuse test was never run on an idle machine).
  References: [jacek's playground](https://tech.io/playgrounds/55004),
  [MCTS-minimax hybrids](https://dke.maastrichtuniversity.nl/m.winands/documents/mcts-minimax_hybrids_final.pdf),
  [Athénan / Descent](https://arxiv.org/abs/2012.10700).
- [ ] **Capture history** and 2-ply continuation history.
- [ ] **Opening book** computed offline for the first plies (the 1000 ms first turn
  already searches deep, so the expected gain is small).

## Data and training

- [ ] **Rescore old data** with the newest net at more nodes instead of generating new games.
- [ ] Sweep `--lam` (0.4 / 0.6 / 0.75) and a result weight that rises during training
  (`--lam-ply` exists); refit the score scale (200) by logistic regression.
- [ ] More nodes per move for the teacher (3000 → 10000) for a smaller, cleaner set.
- [ ] A policy/ordering head to sort quiet moves.

## Testing

- [ ] A **gate opponent with a different style** (e.g. the best-first variant or an old
  net with the new search): self-play against the direct ancestor overstates gains.
- [ ] Find the cause of the ~1% arena timeouts (bot prints nothing on the fatal turn).

## Known limits

- 100k characters: 384×4 buckets uses 89k. Anything wider needs tied weights or a denser
  encoding (more than 16 bits per character is possible with full Unicode).
- Shipping a precompiled binary inside a script is treated as cheating in CodinGame
  contests ([discussion](https://forum.codingame.com/t/what-is-needed-to-allow-cg-send-binary-for-contests/114686));
  not used here.
