# Initial fixed-depth Elo probe, 2026-10-11

Raw PGNs, search records and logs are in [evidence.zip](evidence.zip).
Aggregate PGNs are reconstructed without duplicate storage; see the
[archive guide](../ARCHIVES.md).

The first probe of the new 2–6-ply difficulty settings completed 192 games:
96 each at 2 and 3 ply. Both depths used the same 24 opening positions from the
extended tournament, each with both colours against Stockfish 16 UCI_Elo 1320
and 1500. This is a preliminary Stockfish-scale estimate, not a calibrated
human rating or evidence that the two depths have equal strength.

| Depth | Games | Wins / draws / losses | Points | Estimated Elo | 95% interval | Mean X16 time / move |
|---|---:|---:|---:|---:|---:|---:|
| 2 ply | 96 | 43 / 9 / 44 | 47.5 | 1406 | 1344–1472 | 0.62 s |
| 3 ply | 96 | 41 / 14 / 41 | 48 | 1410 | 1340–1480 | 1.41 s |

The paired difference, 3 ply minus 2 ply, is **+4 Elo**, with a 95% interval of
**−94 to +103**. This probe does not establish a strength difference. More
games and additional depths are needed to assess the difficulty progression.
The previous Easy/Normal/Hard ratings used different search limits and a larger
opening suite, so their point estimates are not a controlled depth comparison.

Searches have a fixed nominal target and no move time cap. The ordinary
30-minute X16 clock still applies. Iterative deepening, check extensions,
quiescence and pruning remain active. A mate or a forced move can finish below
the target. Mean completed depths were 2.00 and 2.97; all early stops were
verified as mates or forced moves.

Stockfish used one thread, 16 MiB hash, limited strength and 0.1 host seconds per
move. Opening-group bootstrap uncertainty uses 20,000 samples with seed 16;
the paired comparison resamples the same groups for both depths. It does not
cover Stockfish calibration error. Warm search tables are retained within a
game and cleared at the start of each game. Timing includes bridge/history
overhead; graphical thinking callbacks are absent.

All 192 PGNs, recorded search limits, results and summary totals passed the
validator. Terminations: 169 checkmates, 20 threefold repetitions, two fifty-move
draws and one stalemate. There were no time forfeits or move-limit draws.
Engine algorithms and ENGINE.PRG are unchanged from the earlier tournament;
binary, emulator and opening-suite hashes are recorded in configuration.json.

The game now defaults to 4 ply and offers 2, 3, 4, 5 and 6 ply for either CPU.
Saves and preferences use version 2 records; version 1 Easy/Normal/Hard levels
load as 2/4/6 ply. CPU thinking shows the selected PLY depth, while the existing
10-second analysis mode retains its time-budget percentage.

Validation included building the X16 binaries and running the menu, graphical
UI, scorecard animation, CPU demo and disk-storage tests. These exercised depth
selection and wraparound, independent CPU levels, uncapped searches, pause,
save/reload, legacy save/preference migration and the highest new preferences.
The legacy rating summaries and confidence intervals were reproduced exactly
after extending the runner.

Raw data: [summary.json](summary.json), [configuration.json](configuration.json),
[validation.json](validation.json), [games.jsonl (archive)](evidence.zip),
[2-ply PGNs (archive)](evidence.zip), [3-ply PGNs (archive)](evidence.zip), [run.log (archive)](evidence.zip).

```sh
PYTHONPATH=build/test-python python3 tools/rate_difficulties.py \
  --depths 2 3 --games-per-opponent 48 --workers 16 --date 2026-10-11 \
  --emulator ../x16-emulator/build/x16emu \
  --openings docs/engine/difficulty-2026-10-11/openings.json \
  --out docs/engine/fixed-depth-elo-2026-10-11
```

The runner supports checkpoint/resume and rejects a changed configuration or
binary in an existing output folder.
