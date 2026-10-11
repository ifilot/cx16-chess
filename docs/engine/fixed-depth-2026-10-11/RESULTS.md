# Fixed-depth waiting times, 2026-10-11

The unchanged X16 engine was measured at nominal depths 2 through 6, with no
thinking-time limit. The main sample contains 64 positions from 64 distinct
Normal-level games in the extended tournament. Seed 16 selects games uniformly,
then one engine turn uniformly in each selected game, excluding the first 12
plies. Eight established benchmark positions provide a separate reference set.
All 360 searches returned legal moves. Searches ending below the target depth
had found a mate or had only one legal move, matching the engine's early exits.

Times below are emulated CPU-cycle time at 8 MHz, corresponding to waiting time
on an X16 or an emulator at normal speed. Host execution time with eight parallel
emulators is not a measure of player waiting time.

| Target depth | Mean | Median | 90th percentile | Maximum observed |
|---|---:|---:|---:|---:|
| 2 plies | 0.71 s | 0.75 s | 1.00 s | 1.50 s |
| 3 plies | 1.53 s | 1.25 s | 2.25 s | 7.50 s |
| 4 plies | 3.94 s | 3.50 s | 8.00 s | 11.50 s |
| 5 plies | 10.13 s | 8.13 s | 20.75 s | 58.00 s |
| 6 plies | 26.22 s | 22.38 s | 55.00 s | 90.50 s |

The separate eight-position reference means were 0.69, 1.84, 5.03, 13.91 and
37.56 seconds respectively. Thus the mean depends appreciably on the position
mix. These are preliminary estimates, not a guarantee of a maximum waiting time.

Each search clears the transposition and other search tables, then replays the
position's reversible history. This includes mailbox and replay overhead and
0.25-second bridge polling granularity. Retaining tables between actual game
moves may reduce time; GUI thinking/clock callbacks are absent here and may add
time. Checks and quiescence can extend search beyond the nominal depth, while
pruning and reductions skip some branches. Iterative deepening still runs all
earlier depths before the target.

Depths 2–4 look suitable for quick play. Depth 5 averages about ten seconds, with
occasional minute-long searches. Depth 6 averages about half a minute, with
observed waits around a minute and a half. A time ceiling would limit long waits,
but then some moves would finish below the selected depth.

Raw positions, per-search results, engine/emulator hashes and summaries are in
[timing.json](timing.json). The incremental search log is in
[timing.jsonl](timing.jsonl). Reproduce with a new output path:

```sh
PYTHONPATH=build/test-python python3 tools/fixed_depth_bench.py \
  --pgn docs/engine/difficulty-2026-10-11/normal.pgn \
  --positions 64 --workers 8 --seed 16 \
  --out build/fixed-depth-timing.json
```

The game difficulty settings have not been changed by this measurement.
