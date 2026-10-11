# Experimental 7/8-ply exploration, 2026-10-11

Raw PGNs, search records and logs are in [evidence.zip](evidence.zip).
Aggregate PGNs are reconstructed without duplicate storage; see the
[archive guide](../ARCHIVES.md).

All **2,400 games** completed: 1,200 per depth, with 16 native workers. The
game phase took **26.3 minutes**; summary generation and validation brought
the total to 27.0 minutes. These depths are available in the test harness;
the game's selectable levels remain 1–6 ply plus Beginner/Easy.

| Depth | Games | Estimated Elo | 95% interval | Nearest 50 |
|---|---:|---:|---:|---:|
| 6 ply, previous run | 1,200 | 1464 | 1446–1482 | ~1450 |
| 7 ply | 1,200 | **1617** | **1595–1640** | ~1600 |
| 8 ply | 1,200 | **1729** | **1703–1758** | ~1750 |

| Paired comparison | Elo difference | 95% interval |
|---|---:|---:|
| 7 minus 6 ply | **+153** | **+126 to +181** |
| 8 minus 6 ply | **+265** | **+234 to +297** |
| 8 minus 7 ply | **+112** | **+77 to +147** |

All three intervals exclude zero, supporting stronger play at 7 than 6 ply,
and at 8 than 7 ply in this benchmark. Seven ply's improvement shows that
the earlier 5-ply dip does not support a general rule that odd depths are
weaker. These results do not diagnose why 5 ply scored below 4 ply; that
earlier difference's interval included zero.

| Depth | Wins | Draws | Losses | Points / games | vs 1320 | vs 1500 |
|---|---:|---:|---:|---:|---:|---:|
| 7 ply | 843 | 126 | 231 | 906 / 1200 | 496.5 / 600 | 409.5 / 600 |
| 8 ply | 975 | 93 | 132 | 1021.5 / 1200 | 544.5 / 600 | 477 / 600 |

## X16 waiting times and use in the game

The same seeded subset of **24 recorded positions** was measured at each
depth. These include assorted game positions and reference positions; the
figures are sample measurements, not averages over the full tournament.

| Depth | Mean X16 seconds | Median | 90th percentile | Maximum |
|---|---:|---:|---:|---:|
| 6 ply | 25.1 | 20.1 | 55.3 | 77.0 |
| 7 ply | 60.2 | 55.0 | 107.0 | 264.8 |
| 8 ply | 203.7 | 115.0 | 458.0 | 1148.0 |

Two separate early middlegame sequences supplied another 12 searches per new
depth, retaining warm transposition tables. These positions were much more
expensive: mean waits were **326.6 seconds at 7 ply** and **998.0 seconds at
8 ply**, with maxima of **1089.0 seconds (18.2 minutes)** and **2047.3 seconds
(34.1 minutes)**. The sequences followed recorded 6-ply games, not games
played out at the new depths. Cold and warm samples contain different positions;
their timing difference does not establish an effect of table warming.

The 8-ply maximum exceeds the game's default 30-minute clock in a single move.
The Elo tournament deliberately has no X16 clock or per-move cap, so these
ratings cannot be advertised as strength under that clock. Seven and eight
ply are promising for untimed analysis or a separate long-thinking mode, but
their waits need consideration before adding them to ordinary game settings.
Four ply remains a useful fast option despite 6 ply's measured advantage.
See [timing.json](timing.json) and the detailed parity reports.

## Verification and benchmark definition

The engine already supports these search depths internally. Only the rating
and parity tools' accepted ranges were extended to 1–8; the engine binaries
are unchanged from the completed 6-ply experiment. Both new depths matched
native C against the optimized X16 emulator on **24 cold and 12 warm searches
each**, comparing legal moves, scores, completed depths and node counts.
All **72 searches** matched. The 7-ply check took 485.9 host seconds; the
8-ply check took 1851.5 seconds. Warm searches ran in two sequential game
histories, limiting that phase to two active emulator workers.

The native games used the same 300 openings, both colours, Stockfish 16 binary,
anchors 1320/1500, 100 ms opponent move time, one opponent thread and 16 MB
opponent hash. Regular selection uses zero weakness noise and completes the
nominal depth, except for verified mate/forced-move early stops. Initial games
run alongside eight emulator workers were excluded and preserved as a pilot
under build/. The final tournament began after one warm sequence finished;
one emulator worker completed the last two checks alongside the native games
on the 20-logical-CPU host. This overlap is recorded in [job.json](job.json).

The paired comparison verifies matching binaries, opponents, limits and actual
opening lists against the completed 6-ply run. Intervals use **20,000 bootstrap
samples of whole opening groups**, seed 16, preserving opponent/colour pairing
and sampling the same groups at every depth. The three pairwise intervals
are not adjusted for multiple comparisons. They describe game/opening sampling
under the benchmark, not opponent calibration or host-load uncertainty.
These remain local Stockfish-scale estimates rather than certified human Elo.

Validation checked **2,400 legal PGNs and 105,323 search traces**, complete
unique game identities, results and summary totals. Early stops were 7,257
mate searches and 523 forced-move searches. Mean completed depths were 6.72
and 7.62. Terminations: 2,181 checkmates, 171 threefold draws, 36 fifty-move
draws, ten insufficient-material draws and two stalemates. There were no
time forfeits or move-limit draws. Engine hashes were checked after completion.

## What the internet research establishes

Aske Plaat explicitly describes **odd/even score oscillation** in his
[original MTD(f) explanation](https://people.csail.mit.edu/plaat/mtdf.html).
This is an evaluation/search phenomenon; it does not establish that odd-depth
engines necessarily have lower Elo.

Wilson, Parker and Nau's [2009 paper on search pathology](https://www.cs.umd.edu/~nau/papers/wilson2009error.pdf)
describes cases where deeper minimax search produces worse decisions and
discusses possible local pathological subtrees. It also recognizes that chess
generally benefits from deeper search. This makes a local regression plausible
without proving that our engine suffers from this mechanism.

Bettadapur and Marsland's [1988 capture-search study](https://www.sciencedirect.com/science/article/abs/pii/S0020737388800087)
even preferred odd depths when that capture search was depth-limited. Its scope
is capture search, not our full search. Together, these sources support testing
each setting rather than choosing even depths solely on parity.

## Data and reproduction

[Configuration](configuration.json), [summary](summary.json),
[paired comparisons](comparisons.json), [validation](validation.json),
[7-ply parity](parity7.json), [8-ply parity](parity8.json),
[7-ply PGNs (archive)](evidence.zip), [8-ply PGNs (archive)](evidence.zip),
[game records (archive)](evidence.zip), [run log (archive)](evidence.zip).

```sh
PYTHONPATH=build/test-python python3 tools/depth_parity_test.py \
  --depth 7 --workers 8 --cold-positions 24 --warm-searches 6 \
  --warm-run docs/engine/native-depth6-elo-2026-10-11 \
  --out docs/engine/native-depth78-elo-2026-10-11/parity7.json
# Repeat with --depth 8 and --out .../parity8.json.

PYTHONPATH=build/test-python python3 tools/rate_difficulties.py \
  --native-engine tests/uci --depths 7 8 --games-per-opponent 600 --workers 16 \
  --openings docs/engine/native-depth-elo-2026-10-11/openings.json \
  --out docs/engine/native-depth78-elo-2026-10-11

PYTHONPATH=build/test-python python3 tools/compare_depth_runs.py \
  docs/engine/native-depth6-elo-2026-10-11 \
  docs/engine/native-depth78-elo-2026-10-11 \
  --out docs/engine/native-depth78-elo-2026-10-11/comparisons.json

PYTHONPATH=build/test-python python3 tools/depth_run_status.py \
  --run docs/engine/native-depth78-elo-2026-10-11 \
  --reference docs/engine/native-depth6-elo-2026-10-11
```
