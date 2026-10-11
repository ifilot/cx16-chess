# Fixed-depth 4-ply Elo test, 2026-10-11

Raw PGNs, search records and logs are in [evidence.zip](evidence.zip).
Aggregate PGNs are reconstructed without duplicate storage; see the
[archive guide](../ARCHIVES.md).

All 1,200 games completed successfully. The game phase took 5.7 minutes with
16 native workers; summary generation and validation followed. The process
exited with status 0.

| Depth | Games | Estimated Elo | 95% interval |
|---|---:|---:|---:|
| 2 ply, earlier paired run | 1,200 | 1355 | 1335–1374 |
| 3 ply, earlier paired run | 1,200 | 1405 | 1386–1424 |
| 4 ply | 1,200 | **1432** | **1413–1452** |

The 4-ply engine scored 636/1200 points: 564 wins, 144 draws and 492 losses.
It scored 370.5/600 against Stockfish UCI_Elo 1320 and 265.5/600 against 1500.
The paired estimate for **4 ply minus 3 ply is +27 Elo**, with a 95% interval of
**+1 to +54**. This provides modest evidence of stronger play at 4 ply; the
interval barely excludes zero. The result should not be interpreted as a large
or precisely known improvement.

The same native engine binary, Stockfish 16 binary, two opponents, 100 ms
opponent move time, search limits and all 300 opening positions were retained
from the completed 2/3-ply run. Each opponent/colour combination contains 300
games. The native backend uses completed nominal depth with no move time cap
or X16 clock simulation. Host execution speed is not X16 waiting time.

Paired comparisons were calculated only after verifying identical test
conditions and validating both runs. The bootstrap uses 20,000 samples of whole
opening groups, seed 16, with the same sampled groups for each depth. Intervals
cover game/opening sampling under this test design, not opponent calibration.
These are local Stockfish-scale estimates rather than calibrated human ratings.
All pair comparisons are in [comparisons.json](comparisons.json).

Before launch, native C matched all 72 recorded X16 searches at depth 4:
moves, scores, completed depths and node counts. An additional two-sequence
check matched all 35 searches while retaining warm search tables and reversible
history. Evidence is in [parity.json](parity.json) and
[warm-parity.json](warm-parity.json). Engine and opponent hashes were verified
again after completion.

Validation confirmed all 1,200 legal PGNs, complete game identities without
missing or duplicate jobs, correct results and summary totals, and all 51,739
search traces. The 2,115 searches that stopped below target depth had found
mates. Mean completed depth was 3.93. Terminations: 1,056 checkmates, 127
threefold draws, 12 fifty-move draws and five insufficient-material draws.
There were no time forfeits or move-limit draws.

Raw data: [configuration.json](configuration.json), [summary.json](summary.json),
[validation.json](validation.json), [games.jsonl (archive)](evidence.zip),
[PGNs (archive)](evidence.zip), [run.log (archive)](evidence.zip). The shared opening suite and earlier
results are in [the 2/3-ply run](../native-depth-elo-2026-10-11/RESULTS.md).

```sh
PYTHONPATH=build/test-python python3 tools/rate_difficulties.py \
  --native-engine tests/uci --depths 4 --games-per-opponent 600 \
  --workers 16 --date 2026-10-11 \
  --openings docs/engine/native-depth-elo-2026-10-11/openings.json \
  --out docs/engine/native-depth4-elo-2026-10-11

PYTHONPATH=build/test-python python3 tools/compare_depth_runs.py \
  docs/engine/native-depth-elo-2026-10-11 \
  docs/engine/native-depth4-elo-2026-10-11 \
  --out docs/engine/native-depth4-elo-2026-10-11/comparisons.json
```
