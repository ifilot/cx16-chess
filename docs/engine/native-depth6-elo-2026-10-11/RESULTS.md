# Fixed-depth 6-ply Elo test, 2026-10-11

Raw PGNs, search records and logs are in [evidence.zip](evidence.zip).
Aggregate PGNs are reconstructed without duplicate storage; see the
[archive guide](../ARCHIVES.md).

All 1,200 games completed and passed validation. The game phase took **6.9
minutes** with 16 native workers, or 7.2 minutes including summary generation
and validation. The selector now displays **6 PLY (~1450 ELO)**.

| Depth | Games | Estimated Elo | 95% interval |
|---|---:|---:|---:|
| 4 ply, previous run | 1,200 | 1432 | 1413–1452 |
| 5 ply, previous run | 1,200 | 1406 | 1387–1425 |
| 6 ply | 1,200 | **1464** | **1446–1482** |

The 6-ply engine scored 687/1200 points: 612 wins, 150 draws and 438 losses.
It scored 382/600 against Stockfish UCI_Elo 1320 and 305/600 against 1500.
The paired estimates are **+58 Elo over 5 ply** (95% interval **+30 to +86**)
and **+32 Elo over 4 ply** (**+7 to +57**). Both intervals exclude zero,
supporting stronger play at 6 ply under these benchmark conditions. These are
separate pairwise intervals, without adjustment for multiple comparisons.
The nearest-50 labels for 4 and 6 ply both read ~1450 despite this difference.

The same 300 openings, both colours, Stockfish 16 binary, anchors 1320/1500,
100 ms opponent move time, one opponent thread and 16 MB opponent hash were
retained. Each opening contributes four games. The native backend executes
the regular engine C with zero weakness noise, no move time cap and no X16
clock simulation. Its host speed differs from player waiting time: the
previous measured X16 average at 6 ply was about 26.2 seconds per search.

Before launch, native C matched all **108 depth-6 emulator searches**: 72 cold
positions and 36 searches across two sequences retaining warm search tables.
Moves, scores, completed depths and node counts agreed. This check took
**267.4 seconds**, including booting eight optimized emulator workers.
See [parity.json](parity.json). The newly added AUTOBOOT.X16 initially launched
the graphical game ahead of ENGINE.PRG. The headless bridge now uses an empty
temporary boot directory, which resolves that startup interaction.

The engine binaries match the completed 5-ply run. For comparison with the
older 4-ply binaries, the existing full replay proof verifies identical regular
search behavior across all 1,200 historical games and 51,739 searches. The
comparison tool explicitly uses that [compatibility proof](../native-depth5-elo-2026-10-11/depth4-compatibility.json)
while checking the remaining conditions. Engine hashes were checked again
after the tournament.

Intervals use 20,000 bootstrap samples of whole opening groups, seed 16,
with matching sampled groups for each depth. They cover game/opening sampling
under this design, not uncertainty in the opponent rating calibration. These
are local Stockfish-scale estimates rather than certified human Elo ratings.
See [comparisons.json](comparisons.json).

Validation confirmed all 1,200 legal PGNs, complete unique game identities,
correct results and summary totals, and **53,963 search traces**. Mean completed
depth was 5.79: 3,086 searches stopped early for mates and 478 for forced moves.
Terminations were 1,050 checkmates, 132 threefold draws and 18 fifty-move draws.
There were no time forfeits or move-limit draws.

Raw data: [configuration.json](configuration.json), [summary.json](summary.json),
[validation.json](validation.json), [games.jsonl (archive)](evidence.zip), [PGNs (archive)](evidence.zip),
[run.log (archive)](evidence.zip), [job.json](job.json).

```sh
PYTHONPATH=build/test-python python3 tools/depth_parity_test.py \
  --depth 6 --workers 8 \
  --warm-run docs/engine/native-depth5-elo-2026-10-11 \
  --out docs/engine/native-depth6-elo-2026-10-11/parity.json

PYTHONPATH=build/test-python python3 tools/rate_difficulties.py \
  --native-engine tests/uci --depths 6 --games-per-opponent 600 --workers 16 \
  --openings docs/engine/native-depth-elo-2026-10-11/openings.json \
  --out docs/engine/native-depth6-elo-2026-10-11

PYTHONPATH=build/test-python python3 tools/compare_depth_runs.py \
  docs/engine/native-depth4-elo-2026-10-11 \
  docs/engine/native-depth5-elo-2026-10-11 \
  docs/engine/native-depth6-elo-2026-10-11 \
  --compatibility-report docs/engine/native-depth5-elo-2026-10-11/depth4-compatibility.json \
  --out docs/engine/native-depth6-elo-2026-10-11/comparisons.json
```
