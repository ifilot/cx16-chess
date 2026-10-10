# Engine test results

All tests ran the real X16 program (`src/ENGINE.PRG`) in the AgentBridge
emulator at 8 MHz, with **10 seconds per move** (emulated X16 time), on
2026-10-10.

## Matches against Stockfish 16

Stockfish played with `UCI_LimitStrength` (0.1 s per move). Each opening
of `tools/match.py` was played with both colours. The games are in this
directory.

| Opponent | Games | Score | Rating estimate |
| --- | --- | --- | --- |
| Stockfish UCI_Elo 1320 | 48 | 31 = 65% | 1424 |
| Stockfish UCI_Elo 1500 | 48 | 15.5 = 32% | 1371 |

Estimated strength: **about 1400** on Stockfish's UCI_Elo scale.

## Quality of the moves

Every move of the 96 games analysed by Stockfish 16 at depth 12
(`tools/review_games.py --local`). Centipawn loss is how much worse a move
is than the best one; positions beyond 10 pawns are clipped.

| Games against | Moves | Average loss | Same move as Stockfish | Blunders (>= 3 pawns) | Mistakes (1-3) |
| --- | --- | --- | --- | --- | --- |
| Stockfish 1320 | 2164 | 45 cp | 37% | 60 | 220 |
| Stockfish 1500 | 2239 | 53 cp | 37% | 75 | 273 |

A spot check of earlier games with online engines (Lichess cloud
evaluation and chess-api.com, `tools/review_games.py` without `--local`)
gave similar numbers.

## Test suite

Win At Chess (300 tactical positions, `tests/epd/wac.epd`): **187 solved**
at 10 s per position. Details in `wac_10s.txt`.

## Search depth

| Position | 5 s | 10 s | 30 s |
| --- | --- | --- | --- |
| Openings, middlegames | 3-4 | 4-5 | 5-6 |
| Endgames | 4-9 | 5-11 | 7-15 |

(Plies of the main search; captures are searched beyond it and checks are
extended.) Speed is 400-1200 nodes per second.
