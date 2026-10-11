# Fixed-depth 5-ply Elo test, 2026-10-11

All 1,200 games completed and passed validation. The game phase took **6.4
minutes** with 16 native workers; summary generation and validation brought
the total to 6.7 minutes. The game selector now displays **5 PLY (~1400 ELO)**.

| Depth | Games | Estimated Elo | 95% interval |
|---|---:|---:|---:|
| 4 ply, previous run | 1,200 | 1432 | 1413–1452 |
| 5 ply | 1,200 | **1406** | **1387–1425** |

The 5-ply engine scored 594/1200 points: 519 wins, 150 draws and 531 losses.
It scored 348.5/600 against Stockfish UCI_Elo 1320 and 245.5/600 against 1500.
The paired estimate for **5 ply minus 4 ply is −26 Elo**, with a 95% interval
of **−54 to +2**. The sample suggests a small regression, but does not establish
a strength difference at the 95% level. More nominal depth has not produced a
measured improvement here; the experiment does not identify its cause.

The test retained the same 300 opening positions, both colours, Stockfish 16
binary, anchors 1320/1500, 100 ms opponent move time, one opponent thread and
16 MB opponent hash. Each opening contributes four games. Regular move
selection uses zero weakness noise and completes nominal depth without a
move time cap or X16 clock simulation. The native backend executes the engine
C directly. Its host speed is different from the player's X16 waiting time;
the earlier measured X16 average for 5 ply was about 10.1 seconds per search.

Before launch, the optimized emulator and native engine agreed on all **108
depth-5 searches**: 72 cold positions and 36 searches across two sequences with
warm search tables. Moves, evaluations, completed depths and node counts
matched. This check took **53.0 seconds**; see [parity.json](parity.json).

The current engine binaries include the later Beginner/Easy implementation,
so their hashes differ from the previous 4-ply experiment. To verify that
regular play remained equivalent, the current native binary replayed the
entire previous dataset: **1,200 games and 51,739 searches**, with no
differences. See [depth4-compatibility.json](depth4-compatibility.json).
The comparison tool accepted that explicit full replay proof while retaining
its other checks for matching test conditions.

Confidence intervals use 20,000 bootstrap samples of whole opening groups,
seed 16, with the same sampled groups for both depths. They cover game/opening
sampling under these conditions, rather than uncertainty in the opponent's
rating calibration. These are local Stockfish-scale estimates, not certified
human ratings. See [comparisons.json](comparisons.json).

Validation confirmed all 1,200 legal PGNs, complete unique game identities,
correct results and summary totals, and 54,033 search traces. Mean completed
depth was 4.87; 2,589 searches stopped early for mates and 511 for forced moves.
Terminations were 1,050 checkmates, 133 threefold draws, 12 fifty-move draws
and five insufficient-material draws. There were no time forfeits or
move-limit draws. Evidence: [validation.json](validation.json).

Raw data: [configuration.json](configuration.json), [summary.json](summary.json),
[games.jsonl](games.jsonl), [PGNs](ply5.pgn), [run.log](run.log),
[job.json](job.json). Earlier results: [4 ply](../native-depth4-elo-2026-10-11/RESULTS.md)
and [2/3 ply](../native-depth-elo-2026-10-11/RESULTS.md).

```sh
PYTHONPATH=build/test-python python3 tools/depth_parity_test.py \
  --depth 5 --workers 8 \
  --warm-run docs/engine/native-depth4-elo-2026-10-11 \
  --out docs/engine/native-depth5-elo-2026-10-11/parity.json

PYTHONPATH=build/test-python python3 tools/native_replay_test.py \
  --run docs/engine/native-depth4-elo-2026-10-11 --allow-new-engine \
  --out docs/engine/native-depth5-elo-2026-10-11/depth4-compatibility.json

PYTHONPATH=build/test-python python3 tools/rate_difficulties.py \
  --native-engine tests/uci --depths 5 --games-per-opponent 600 --workers 16 \
  --openings docs/engine/native-depth-elo-2026-10-11/openings.json \
  --out docs/engine/native-depth5-elo-2026-10-11

PYTHONPATH=build/test-python python3 tools/compare_depth_runs.py \
  docs/engine/native-depth4-elo-2026-10-11 \
  docs/engine/native-depth5-elo-2026-10-11 \
  --compatibility-report docs/engine/native-depth5-elo-2026-10-11/depth4-compatibility.json \
  --out docs/engine/native-depth5-elo-2026-10-11/comparisons.json
```
