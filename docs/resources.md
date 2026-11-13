# Resources

What this bot was built from. Grouped by what they were used for.

## The game on CodinGame

- [Breakthrough arena](https://www.codingame.com/multiplayer/bot-programming/breakthrough) and its [forum thread](https://forum.codingame.com/t/community-puzzle-breakthrough/137971)
- [Official referee source](https://github.com/darkhorse64/CG_Breakthrough) (darkhorse64) — rules, move order, time limits
- [Breakthrough on Wikipedia](https://en.wikipedia.org/wiki/Breakthrough_%28board_game%29)
- [CodinGame API docs](https://www.codingame.com/api/v1/docs/api)

## CodinGame bot craft

- Tom Alard, [Fighting for #1 in the Ultimate Tic-Tac-Toe arena](https://tomalard.github.io/posts/fighting-for-1-in-the-ultimate-tic-tac-toe-arena/) — NNUE in a CodinGame bot end to end: buckets, data, UTF-16 weights, AVX2
- reCurse, [Spring Challenge 2021 post-mortem](https://forum.codingame.com/t/spring-challenge-2021-feedbacks-strategies/190849/67) and [gist](https://gist.github.com/reCurs3/fea106bea9c55389706e959b97f956c0)
- jacek, [Best-first minimax search with UCT](https://tech.io/playgrounds/55004) and [Inputs for neural networks for board games](https://tech.io/playgrounds/157341)
- marchete, [CGZero](https://github.com/marchete/CGZero) and the [Oware AlphaZero playground](https://www.codingame.com/playgrounds/58137/alphazero-like-implementation-for-oware-abapa-game-codingame/final-words)
- Forum: [neural network resources](https://forum.codingame.com/t/neural-network-ressources/1667), [how timeouts work](https://forum.codingame.com/t/timeouts-how-do-they-work/24504), [C++ and -O3](https://forum.codingame.com/t/c-and-the-o3-compilation-flag/1670)
- [Using pragma for compile optimization](https://tech.io/playgrounds/58302)
- Testing: [psyleague](https://github.com/FakePsyho/psyleague), [cg-brutaltester](https://github.com/dreignier/cg-brutaltester)

## Search

- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page): [singular extensions](https://www.chessprogramming.org/Singular_Extensions), [LMR](https://www.chessprogramming.org/Late_Move_Reductions), [history heuristic](https://www.chessprogramming.org/History_Heuristic), [improving](https://www.chessprogramming.org/Improving), [correction history](https://www.chessprogramming.org/Static_Evaluation_Correction_History), [best-first minimax](https://www.chessprogramming.org/Best-First_Minimax_Search)
- [Engine testing guide](https://dannyhammer.github.io/engine-testing-guide/print.html), [Fishtest FAQ](https://github.com/official-stockfish/fishtest/wiki/Fishtest-faq), [SPSA tuning workloads](https://github.com/AndyGrant/OpenBench/wiki/SPSA-Tuning-Workloads)
- [Viridithas](https://github.com/cosmobobak/viridithas) — a readable modern engine

## NNUE and training

- [NNUE on the Chess Programming Wiki](https://www.chessprogramming.org/NNUE)
- [Stockfish nnue-pytorch guide](https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md) and [training data notes](https://github.com/official-stockfish/nnue-pytorch/wiki/Training-datasets)
- [bullet](https://github.com/jw1912/bullet) — NNUE trainer; its examples show SCReLU and output buckets
- [NNUE notes (asteri.sm)](https://asteri.sm/files/2024-06-01-nnue.html) — SCReLU int16 trick
- [NNUEs and where to find them](https://slama.dev/prokopakop/nnues-and-where-to-find-them/) — a from-scratch log with Elo per step
- [Lc0 blog on NNUE training](https://lczero.org/blog/2021/04/joking-ftw-seriously/) — result/score blending
- [Egaroucid technology notes](https://www.egaroucid.nyanyan.dev/en/technology/explanation/) (Othello)
- [Texel's tuning method](https://www.chessprogramming.org/Texel%27s_Tuning_Method)

## Breakthrough research

- Lorentz & Horey, [Programming Breakthrough](https://www.researchgate.net/publication/290565002_Programming_Breakthrough)
- Lorentz & Zosa, [Machine learning in the game of Breakthrough](https://link.springer.com/chapter/10.1007/978-3-319-71649-7_12)
- Baier & Winands, [MCTS-minimax hybrids](https://dke.maastrichtuniversity.nl/m.winands/documents/mcts-minimax_hybrids_final.pdf) and the [JAIR article on heuristic evaluations in MCTS](https://jair.org/index.php/jair/article/view/11208)
- Lanctot et al., [MCTS with heuristic evaluations using implicit minimax backups](https://arxiv.org/abs/1406.0486)
- Cohen-Solal & Cazenave, [Minimax strikes back](https://arxiv.org/abs/2012.10700) (value-only nets with best-first minimax)
- Saffidine, Jouandeau & Cazenave, [Solving Breakthrough with race patterns and job-level proof number search](https://www.lamsade.dauphine.fr/~cazenave/papers/solving.pdf)

## Other engines looked at

- [OpenSpiel Breakthrough](https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/games/breakthrough/breakthrough.cc)
- [Breakthrough-Web](https://github.com/MartinMSPedersen/Breakthrough-Web), [Pehz63/Breakthrough](https://github.com/Pehz63/Breakthrough)
- [Simple AI for the game of Breakthrough](https://www.codeproject.com/articles/37024/simple-ai-for-the-game-of-breakthrough)

## Compute

- [Kaggle notebooks/API](https://www.kaggle.com/docs/api), [Modal](https://modal.com/docs)
