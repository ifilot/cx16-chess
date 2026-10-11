# Extended native fixed-depth Elo test, 2026-10-11

Raw PGNs, search records and logs are in [evidence.zip](evidence.zip).
Aggregate PGNs are reconstructed without duplicate storage; see the
[archive guide](../ARCHIVES.md).

The 2,400-game run completed successfully, with 1,200 games at each depth.
The game phase took about 11 minutes with 16 workers; summary calculation and
automatic validation finished afterward. The process exited with status 0.

| Depth | Games | Wins / draws / losses | Points | Estimated Elo | 95% interval |
|---|---:|---:|---:|---:|---:|
| 2 ply | 1,200 | 415 / 192 / 593 | 511 | 1355 | 1335–1374 |
| 3 ply | 1,200 | 512 / 160 / 528 | 592 | 1405 | 1386–1424 |

The paired estimate for **3 ply minus 2 ply is +50 Elo**, with a 95% confidence
interval of **+24 to +77**. This supports stronger play at 3 ply under these
benchmark conditions. Individual rating intervals are approximately ±20 Elo,
matching the intended statistical precision. These are estimates on the local
limited-strength Stockfish scale, not independently calibrated human ratings.

Both depths used the same 300 distinct, balanced opening positions. Each opening
was played with both colours against Stockfish 16 UCI_Elo 1320 and 1500, for
eight games per opening across the two depths. Every depth/opponent/colour
combination contains exactly 300 games. Stockfish used one thread, 16 MiB hash
and 100 milliseconds per move. Opening-group bootstrap intervals use 20,000
samples and seed 16; the paired comparison resamples the same groups for both
depths. Engine and opponent settings were frozen throughout the run.

Native C was used to accelerate fixed-depth searches. Before launch it
reproduced all 8,339 searches from the earlier 192 X16 games, including warm
tables and repetition histories: moves, depths, scores and node counts matched
exactly. The native executable, X16 engine, Stockfish and opening-suite hashes
were checked again after completion and matched the recorded configuration.
Parity evidence is in [parity.json](parity.json).

Native execution measures host time and does not simulate the X16 clock.
Searches have no per-move time cap and stop at the selected nominal depth, with
the existing mate and forced-move early exits. Extensions, quiescence and
pruning remain enabled. Mean completed depths were 2.00 and 2.97. Host search
times must not be interpreted as waiting times on hardware; see the separate
[X16 timing measurements](../fixed-depth-2026-10-11/RESULTS.md).

An independent post-run audit confirmed all 2,400 legal PGNs, all 102,807 search
records, results and summary totals, complete game identities without missing
or duplicate jobs, paired colours/opponents and the reasons for early search
termination. All games ended naturally: 2,048 checkmates, 315 threefold draws,
23 fifty-move draws, 13 insufficient-material draws and one stalemate. There
were no time forfeits or move-limit draws.

The earlier 96-game-per-depth probe estimated 1406 and 1410, with broad
intervals. The extended run adds opening diversity and greatly reduces
sampling uncertainty; its narrower result replaces that preliminary estimate
for this benchmark. The earlier probe was run through the X16 emulator and
used an ordinary game clock, so the two datasets were kept separate.

Raw evidence: [configuration.json](configuration.json), [summary.json](summary.json),
[validation.json](validation.json), [audit.json](audit.json),
[games.jsonl (archive)](evidence.zip), [2-ply PGNs (archive)](evidence.zip), [3-ply PGNs (archive)](evidence.zip),
[run.log (archive)](evidence.zip). The recorded opening suite is [openings.json](openings.json).

```sh
PYTHONPATH=build/test-python python3 tools/rate_difficulties.py \
  --native-engine tests/uci --depths 2 3 --games-per-opponent 600 \
  --workers 16 --date 2026-10-11 \
  --openings docs/engine/native-depth-elo-2026-10-11/openings.json \
  --out docs/engine/native-depth-elo-2026-10-11
```

The runner checkpoints every game and only resumes with the same configuration.
