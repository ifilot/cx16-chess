# Final weak-engine calibration, 2026-10-11

**Beginner** uses root noise 350 and **Easy** uses noise 50, both at one nominal
ply. The game also offers regular **1–6 ply**, with **4 ply** still the default.
Both computers in a demo can choose independent settings. Analysis always
uses the regular engine.

| Preset | Final assessment games | Estimated Elo | 95% interval | Wins/draws/losses |
|---|---:|---:|---:|---:|
| Beginner | 1,200 | **804** | 755–845 | 14/52/1134 |
| Easy | 1,200 | **1089** | 1063–1113 | 119/116/965 |

These are estimates on the existing local Stockfish benchmark scale, rather
than certified human FIDE or online ratings. Confidence intervals resample
whole opening groups 20,000 times; they cover game/opening sampling, not
uncertainty in the reference ratings or host timing. The score model
extrapolates below Stockfish's nominal 1320 and 1500 anchors.

## Calibration and final checks

There were **864 pilot games**, then **7,200 games** across noise 50, 200 and
300 on a fresh 600-position suite. Noise 300 was frozen before its last
300 opening groups were played. Those separate final groups showed it was
stronger than the 800 target, so noise 400 was selected for another check.

Noise 400 then measured 730 Elo (675–775) over 1,200 games. The midpoint,
noise 350, was selected for a fresh assessment.

The final Beginner assessment played **1,200 games** on **300 fresh distinct
balanced openings**, generated with seed 19 and explicitly excluding all
positions from the earlier suites. The noise-350 setting was selected before
this suite or its games were observed. Easy's assessment uses the last 300
opening groups of the seed-17 suite, also 1,200 games. Both assessments pair
colours and opponents. These different suites are not given a paired
between-preset confidence interval.

In total, **10,464 games** completed. All full runs and both pilots passed
PGN/search validation. The final Beginner run used 16 workers after the earlier
game phases finished. Opponents were Stockfish 16 UCI_Elo 1320/1500, one thread,
16 MB hash, 100ms per move. Native games have no move cap or simulated X16
clock. Earlier noise-50/200 and noise-300 game phases partly overlapped;
execution details are recorded in their folders. Opponent time limits are host
wall time, so scheduling and hardware may affect reference strength.

See [candidate-300-results.md](candidate-300-results.md) for the earlier
candidate, [final-assessment.json](final-assessment.json) for the final
numbers, and [comparisons.json](comparisons.json) for the matched-opening
tuning comparisons. Source configurations, seeds, binary hashes, opening
suites, PGNs and every search are retained. Nominal ratings of an additional
weak engine were not assumed to be independently measured reference ratings.

## Implementation and verification

Each legal root move receives a full-window search score. Seeded uniform
integer noise in 0..N is added for selection; the reported score remains the
unmodified evaluation. The selected move's root-score loss is bounded by N.
Native C and cc65 use the same 16-bit xorshift generator. New games in the UI
seed it from the clock; nonzero test seeds reproduce the stream. Seed zero
preserves the stream. Reloading retains difficulty and starts a fresh stream.

**353 seeded native/X16 searches** matched moves, scores,
depths and nodes, including complete game replays. With noise off, all
**8,339 historical searches** still matched. Native tests,
menu/demo/scorecard tests, versioned save/preferences compatibility, real
SD-card saving, selected weak noise/depth, regular analysis and a Golden RAM
stack guard passed. Details are in [test-results.json](test-results.json).

The game keeps root arrays at $0400–$05BF and leaves $05C0–$07FF for its C
stack. The headless harness retains the mailbox there. Version 3 saves and
preferences accept versions 1 and 2 without changing old difficulty IDs.
The menu cycles Beginner → Easy → 1 ply → 2–6 ply. The save table abbreviates
Beginner as BEGIN. and paired CPU presets as B/E.

## Reproduction

Build with `make -C src` and `make -C tests uci`; install python-chess for the
Python tools. This session used `PYTHONPATH=build/test-python`.

```sh
python3 tools/rate_difficulties.py --native-engine tests/uci --depths 1 \
  --noises 350 --games-per-opponent 600 --seed 31415 --workers 16 \
  --openings docs/engine/weak-calibration-2026-10-11/final350-openings.json \
  --out build/weak-beginner-reproduction
python3 tools/summarize_weak_calibration.py \
  --root docs/engine/weak-calibration-2026-10-11 --final
```
