# Fixed-depth 1-ply Elo test, 2026-10-11

Raw PGNs, search records and logs are in [evidence.zip](evidence.zip).
Aggregate PGNs are reconstructed without duplicate storage; see the
[archive guide](../ARCHIVES.md).

All 1,200 games completed and passed validation. The game phase took 4.9
minutes with 16 native workers, followed by summary calculation and validation.
The process exited with status 0.

| Depth | Games | Estimated Elo | 95% interval |
|---|---:|---:|---:|
| **1 ply** | 1,200 | **1184** | **1163–1205** |
| 2 ply, earlier paired run | 1,200 | 1355 | 1335–1374 |
| 3 ply, earlier paired run | 1,200 | 1405 | 1386–1424 |
| 4 ply, earlier paired run | 1,200 | 1432 | 1413–1452 |

The 1-ply engine scored 272.5/1200 points (22.71%): 154 wins, 237 draws and
809 losses. It scored 156.5/600 against Stockfish UCI_Elo 1320 and 116/600
against 1500. The paired advantage of **2 ply over 1 ply is +171 Elo**, with a
95% interval of **+141 to +199**. This clearly separates the two depths under
the benchmark conditions. All paired comparisons are recorded in
[comparisons.json](comparisons.json).

The same native engine binary, Stockfish 16 binary, 300 opening positions,
opponent settings and 100 ms opponent move time were retained from the 2–4-ply
tests. Each opponent/colour combination contains 300 games. Both colours were
played for each opening against each opponent. The runner now accepts depths
1 through 6; no engine algorithms were changed.

Before launch, depth-1 searches, evaluations and perft counts matched the X16
engine on all 11 standard parity positions. An additional 35 searches across
two move sequences matched moves, scores, depths and node counts while
retaining warm search tables and reversible history. Evidence is in
[parity.log (archive)](evidence.zip) and [warm-parity.json](warm-parity.json). All engine
and opponent binary hashes were checked before and after the run.

Validation confirmed all 1,200 legal PGNs, complete game identities without
missing or duplicate jobs, correct results and summary totals, and all 43,027
search records. Every recorded search completed nominal depth 1 with no move
time cap. Check extensions and quiescence remain active beyond nominal depth.
Terminations: 963 checkmates, 220 threefold draws, ten stalemates, four
fifty-move draws and three insufficient-material draws. No time forfeits or
move-limit draws occurred.

Intervals use 20,000 opening-group bootstrap samples with seed 16. Paired
comparisons use the same sampled opening groups across depths. The native
backend records host time and does not simulate the X16 game clock.

Ratings describe this local limited-strength Stockfish benchmark, not calibrated
human strength. The 1-ply estimate lies below the lowest opponent anchor, 1320,
and therefore relies on extrapolating the assumed Elo score model. Statistical
intervals cover game/opening sampling, not calibration error.

Raw data: [configuration.json](configuration.json), [summary.json](summary.json),
[validation.json](validation.json), [games.jsonl (archive)](evidence.zip),
[PGNs (archive)](evidence.zip), [run.log (archive)](evidence.zip). Earlier results:
[2/3 ply](../native-depth-elo-2026-10-11/RESULTS.md) and
[4 ply](../native-depth4-elo-2026-10-11/RESULTS.md).

```sh
PYTHONPATH=build/test-python python3 tools/rate_difficulties.py \
  --native-engine tests/uci --depths 1 --games-per-opponent 600 \
  --workers 16 --date 2026-10-11 \
  --openings docs/engine/native-depth-elo-2026-10-11/openings.json \
  --out docs/engine/native-depth1-elo-2026-10-11

PYTHONPATH=build/test-python python3 tools/compare_depth_runs.py \
  docs/engine/native-depth1-elo-2026-10-11 \
  docs/engine/native-depth-elo-2026-10-11 \
  docs/engine/native-depth4-elo-2026-10-11 \
  --out docs/engine/native-depth1-elo-2026-10-11/comparisons.json
```
