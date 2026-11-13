# Neural evaluation (NNUE style)

A tiny network that is cheap enough to run millions of times per second because its
first layer is updated incrementally. Good introductions:
[chessprogramming.org/NNUE](https://www.chessprogramming.org/NNUE),
the [Stockfish NNUE guide](https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md),
[bullet's docs](https://github.com/jw1912/bullet).

## Architecture

```
 side to move frame:  128 bits ─┐                       ┌─ SCReLU ─┐
                                ├─ W (128 × 384), b ────┤          ├─ · O[bucket] + bias ─► logit
 other side's frame:  128 bits ─┘   (same weights)      └─ SCReLU ─┘
```

- **Inputs (128):** own pawn on square (64) + enemy pawn on square (64), in the frame
  where that side moves up.
- **Two perspectives, shared weights:** one accumulator for the side to move, one for
  the other side (same position, flipped). Output weights differ per perspective.
- **Activation:** SCReLU, `clamp(x, 0, 1)²`.
- **Output buckets (4):** separate output head by number of pawns on the board,
  `(pawns − 1) · 4 / 32`. Worth about +20 Elo.
- **Output:** win-probability logit of the side to move; `× NN_SCALE (200)` gives search
  units, so 200 ≈ one logit.

v3.0 net: 384 hidden, 4 buckets, 52k weights (`tools/nets/n10b.bin`).

## Quantization and inference

`int16` everywhere. Hidden weights × `QA = 255`, output weights × `QB = 64`
(clamped to ±1.98 in training so `v·w` fits int16).

```cpp
int32_t v = clamp(acc[i], 0, QA);
s += (v * o[i]) * v;                       // (v·w)·v keeps the first product in 16 bits
eval = (s / QA + bias) * NN_SCALE / (QA * QB);
```

`nnEval` has a hand-written AVX2 path (`_mm256_mullo_epi16` + `_mm256_madd_epi16`), +28%
nodes/s on CodinGame. Enable it in the submission with pragmas at the top of the file
(`#pragma GCC target("avx2,...")`), since compiler flags cannot be set there.

## Incremental update

A move changes 2 inputs (3 with a capture), so the child accumulator is the parent's
plus/minus a few weight rows (`accEnsure`). Because the board flips every ply, the
mover's accumulator becomes the child's "other side" one and vice versa.

Updates are **lazy**: the search only records the move in `accSt[ply+1]`; the
accumulator is computed when (and if) that node is evaluated. Nodes cut by the hash
table or static rules never pay for it.

## Training data

Built into the engine (`runGen`, `genPlay`; `#ifdef LOCAL`):

```sh
BT_NET=tools/nets/current.bin BT_GEN=2000:3000:1:data/g15_1.bin ./build/bot    # games:nodes:seed:file
```

- 4–12 random opening plies, then both sides search with a **fixed node budget**
  (3000 nodes). Openings the search already scores as decided (|score| > 700) are dropped.
- Positions with a static result (forced capture, safe 7th-rank move) are not recorded:
  the net never sees them in play either.
- Record (24 bytes): `own, opp, search score, game result, ply, flags`
  (bit 0: best move is a capture, bit 1: from a "side game" branched off a random move).

Each generation is played by the newest net; the first one by the handcrafted eval.

## Training

[`tools/train.py`](../tools/train.py), PyTorch. The whole data set sits on the GPU as 16
bytes per position; inputs are unpacked there, so an epoch over 100M positions takes
about a minute on a cloud GPU.

```sh
python3 tools/train.py -o tools/nets/new.bin 'data/g*_*.bin' --hidden 384 --buckets 4 \
        --epochs 30 --lam 0.6 --dedup --cosine --no-side
```

| Option | What | Effect |
|---|---|---|
| `--lam 0.6` | target = 0.6·game result + 0.4·sigmoid(search score / 200) | +112 Elo vs +70 for result only; 0.3 was worse |
| `--dedup` | merge identical positions, average their targets | 23–28% of positions are duplicates |
| `--cosine`, `--epochs 30` | cosine decay to lr/400 | long, low-lr tail helped (+97 with dedup and more data) |
| `--buckets 4` | output heads by pawn count | ~+20 |
| `--sym` | tie hidden units in left-right mirrored pairs | exact mirror symmetry, half the free weights; small plus at 256, and halves storage (`pack.py -S`) |
| `--no-side` | drop side-game positions | main-line data alone was slightly better |
| `--quiet` | drop positions whose best move is a capture | no effect |

Loss: binary cross-entropy on the logit. Adam, lr 2e-3, batch 16384. Without `--sym`
left-right mirroring is applied as augmentation.

## What moved the needle

| Change | Elo (self-play, vs previous) |
|---|---|
| Handcrafted → first net (3M positions) | 94% win rate |
| Generations 1–6 (9M → 44M positions) | +506, +274, +92, +112, +35, +30 |
| 256 → 384 hidden | +147 at equal nodes, only 4% slower |
| 44M → 108M positions, mostly from a stronger teacher | +87 |
| + dedup, 30 epochs cosine, output buckets | +97 → +117 |
| 108M → 136M / 216M positions at 384 | 0…+20: **capacity is now the limit** |
| 512 hidden at 44M positions | +39 at equal nodes but −29% speed: rejected then |
| 8 buckets instead of 4 (166M positions) | −17 |

Rule of thumb seen here: a stronger teacher beats more data from the same teacher; more
data stops helping once the net is full; then width is the next lever, paid for in speed
and characters.

## Embedding into the source

CodinGame counts **characters**, not bytes. [`tools/pack.py`](../tools/pack.py) stores
one int16 per UTF-16 code unit (`value + 27756`, which stays clear of control characters,
quotes and surrogates) in a `u"..."` literal. 384×4 costs ~52k of the 100k characters;
the code itself ~37k.

- 512 untied does not fit (107k). Mirror-tied nets are stored at half size with
  `pack.py -S` and expanded at start-up (`NN_SYM` in `loadEmbedded`), so 512 or 640 tied
  fit.
- `pack.py` also strips `#ifdef LOCAL` blocks and bakes `-D` overrides in.
