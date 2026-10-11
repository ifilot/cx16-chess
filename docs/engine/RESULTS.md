# Engine evidence and current difficulty calibration

The game uses the following approximate local Stockfish benchmark ratings,
rounded to 50 Elo. These are not certified human or online ratings. X16 move
times are measured sample averages at 8 MHz, not limits; complex positions can
require substantially longer.

| Game level | Search | Approximate Elo | Average X16 move | Calibration report |
| --- | --- | ---: | ---: | --- |
| Beginner | Weakened 1 ply, noise 350 | 800 | 0.4 s | [Final weak calibration](weak-calibration-2026-10-11/RESULTS.md) |
| Easy | Weakened 1 ply, noise 50 | 1100 | 0.4 s | [Final weak calibration](weak-calibration-2026-10-11/RESULTS.md) |
| Casual | 1 ply | 1200 | 0.4 s | [1-ply assessment](native-depth1-elo-2026-10-11/RESULTS.md) |
| Medium | 2 ply | 1350 | 0.7 s | [2/3-ply assessment](native-depth-elo-2026-10-11/RESULTS.md) |
| Challenging | 3 ply | 1400 | 1.5 s | [2/3-ply assessment](native-depth-elo-2026-10-11/RESULTS.md) |
| Strong | 4 ply | 1450 | 4 s | [4-ply assessment](native-depth4-elo-2026-10-11/RESULTS.md) |
| Deep | 6 ply | 1450 | 26 s | [6-ply assessment](native-depth6-elo-2026-10-11/RESULTS.md) |
| Very Hard | 7 ply | 1600 | 60 s | [7/8-ply assessment](native-depth78-elo-2026-10-11/RESULTS.md) |
| Analysis | 8 ply | 1750 | 204 s | [7/8-ply assessment](native-depth78-elo-2026-10-11/RESULTS.md) |

Each regular depth and final weakened preset has 1,200 assessment games.
The reports retain exact estimates, uncertainty intervals, test conditions,
paired comparisons, and native/X16 parity evidence. The earlier weak-engine
candidates and pilot runs are preserved within the calibration directory.
Five ply remains playable in legacy saves but is omitted from the game ladder:
the [5-ply assessment](native-depth5-elo-2026-10-11/RESULTS.md) showed no measured
improvement over 3 ply. Search depth is not a guarantee of increasing strength.

## Timing and implementation evidence

- [Fixed-depth X16 waiting-time measurements](fixed-depth-2026-10-11/RESULTS.md).
- [7/8-ply timing samples and long-search observations](native-depth78-elo-2026-10-11/RESULTS.md).
- [Emulator performance and worker measurements](emulator-performance-2026-10-11/RESULTS.md).

## Historical experiments

These reports record earlier engine settings and sample sizes. Their original
measurements are preserved; descriptions of then-available game levels should
be read in that historical context.

- [Original timed matches, move-quality review, and tactical tests](LEGACY.md).
- [First time-capped difficulty sample](difficulty-2026-10-10/RESULTS.md).
- [Extended time-capped comparison](difficulty-2026-10-11/RESULTS.md).
- [Initial fixed-depth emulator probe](fixed-depth-elo-2026-10-11/RESULTS.md).
- [Earlier weak-engine candidate](weak-calibration-2026-10-11/candidate-300-results.md).

## Raw evidence

Completed game records, individual PGNs, and run logs are bundled per run in
`evidence.zip`. Reports, summaries, configurations, opening suites, and audits
remain directly readable. Aggregate PGNs are reconstructed exactly from the
individual archived games, avoiding duplicate game storage.

See the [archive guide](ARCHIVES.md) for verification, replay, restoration,
and recording new experiments. Consolidation changes storage only: every
original evidence byte and all reported results are retained.
