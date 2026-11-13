# Engine

Everything is in [`bot.cpp`](../bot.cpp). Line references are to function names; search
the file for them.

## Board

Two 64-bit integers: `own` and `opp`. Bit `rank*8 + file`, a1 = bit 0.

The side to move always moves **up**. After a move the board is flipped vertically
(`__builtin_bswap64`) and the two bitboards are swapped:

```cpp
U64 no = (own ^ (1ULL << f)) | (1ULL << t), np = opp & ~(1ULL << t);   // make move
child = search(flip(np), flip(no), ...);                              // opponent now "own", moving up
```

No colour, no unmake, one code path. A position is 16 bytes, which is also the training
record and the hash key input.

## Move generation

Three shifts (`genMoves`): straight `own << 8` onto empty squares, diagonals `<< 7` and
`<< 9` (masked against file wrap) onto anything that is not own. A move is
`from | to << 6` in a `uint16_t`. `genCaptures` keeps only diagonals that hit an enemy.

Check: `BT_PERFT=5 ./build/bot` prints `6182818`.

## Static win and loss rules

Breakthrough ends tactically, so the search knows a few exact results without searching
(top of `search` and `qsearch`):

| Situation (side to move = own) | Result |
|---|---|
| Own pawn on rank 7 | win next move |
| Enemy pawn one step from our home row, and we cannot capture it (or there are two) | loss |
| Exactly one such pawn and we can capture it | reply is **forced**: only captures of it are generated, depth +1 |
| We have a move onto rank 7 that cannot be captured (`safe7`) and no enemy threat | win in 3 plies |

Wins are scored `WIN - ply`, so shorter wins rank higher.

`race()` (flag `RACE`, off) is an exact rule for a pawn whose forward cone is empty of
enemies. It is correct but measured neutral: the search finds these anyway.

## Handcrafted evaluation

`sideScore`: pawn value by rank (`100,100,118,142,180,240,340`), bonus for a supported
pawn, penalty for an attacked unsupported one. It got the bot to rank ~31 and no
further; it is still used when no net is loaded and produced the very first training
data. Everything after is the [neural evaluation](nnue.md).

## Protocol and time

Per turn the referee sends the opponent's move (or `None`), a count, and the legal moves.
The bot keeps its own board, searches until a hard deadline (970 ms first turn, 95 ms
after) and prints the move **before** any diagnostics. The clock starts when the first
input line of the turn has been read.

- No soft stop: an unfinished iteration still returns a move at least as good as the
  previous iteration's (its best move is searched first).
- The transposition table is allocated and touched at start-up, so no page fault can land
  inside a 100 ms turn.
- The chosen move is checked against the legal list; on mismatch the first legal move is
  played (never seen in practice, cheap insurance).

Environment knobs for local runs are listed at the top of `bot.cpp`
(`BT_NODES`, `BT_MS`, `BT_OPENING`, `BT_NET`, `BT_GEN`, `BT_PERFT`).
