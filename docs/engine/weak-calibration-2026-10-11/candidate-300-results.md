This records the earlier noise-300 candidate; see RESULTS.md for the final preset.

# Beginner and Easy calibration, 2026-10-11

The game now offers **Beginner**, **Easy**, and **1–6 ply**. The default remains
4 ply, and each CPU in a demo has its own setting. Beginner uses noise 300;
Easy uses noise 50. Both search one nominal ply. The regular depth modes retain
the original move selection. Analysis uses the regular engine regardless of difficulty.

## Final assessment on held-out openings

| Preset | Root noise (cp) | Games | Estimated Elo | 95% interval | Wins/draws/losses |
|---|---:|---:|---:|---:|---:|
| Beginner | 300 | 1,200 | 852 | 811–887 | 19/66/1115 |
| Easy | 50 | 1,200 | 1089 | 1063–1113 | 119/116/965 |

These estimates use **1,200 games per preset**, on the last 300 distinct balanced
opening positions, both colours, against Stockfish 16 UCI_Elo 1320 and 1500 at
100ms per move. No X16 clock is simulated in native matches. Whole opening
groups are resampled 20,000 times, preserving opponent and colour pairing.
The confidence intervals cover game/opening sampling, rather than uncertainty
in Stockfish's rating scale. They are local benchmark ratings, not certified
FIDE or online human ratings. Extrapolation below the opponent ratings also
assumes the usual Elo logistic score model.

Beginner was frozen when 1083 of its
bracketing games had completed, with maximum observed opening index
271; final assessment starts at
opening index 300. Easy was selected from the initial pilot. The unused final
opening groups provide a separate check after selecting the presets.
Easy minus Beginner is **+237 Elo**, with paired 95%
interval **+194 to +285**.

## Tuning and full samples

The pilots played 864 games across nine policies, including noise 0.
A new 600-position opening suite, generated with seed 17, was used for
2,400 games each at noise 50, 200 and 300: **7,200 games**, all validated.
Noise 200 was stronger than the desired Beginner setting, so 300 was chosen.
The full samples include tuning observations; the table above uses the
separate final opening groups.

| Noise (cp) | Games | Full-sample estimate | 95% interval |
|---:|---:|---:|---:|
| 50 | 2,400 | 1076 | 1057–1094 |
| 200 | 2,400 | 911 | 885–934 |
| 300 | 2,400 | 840 | 810–868 |

Confirmation used 16 workers and the bracketing run used 8. Their game phases
partly overlapped. Opponent search limits are host wall time, so scheduling
and hardware can influence opponent strength. Execution details, binary
hashes, seeds, opening suites, all PGNs and every engine search are retained.
The nominal ratings of another weak engine are not treated as independently
measured anchors; retaining the earlier Stockfish panel keeps this calibration
on the same benchmark scale.

## Weakening policy and X16 checks

Every legal root candidate gets a full-window search score. Add seeded uniform
integer noise from zero through the preset's noise limit, then play the highest
adjusted score. This bounds the selected move's loss against the best root
score by the noise limit. The reported score remains its unmodified search
score. The policy uses a 16-bit xorshift generator shared by native C and cc65;
recorded nonzero seeds reproduce the stream. Seed zero preserves the stream.
The game seeds new matches from its clock; saved games retain difficulty,
while the random stream starts afresh when reloaded.

All **353 seeded cold/warm searches** matched native/X16 moves,
scores, depths and nodes, including complete recorded games. With noise
turned off, all **8,339 historical searches** still matched.
Native tests, graphical menu/demo/scorecard tests, save compatibility,
real SD-card saving, weak search selection, full-strength analysis and a
Golden RAM stack guard passed. See `test-results.json`.

Beginner: 0.32s average, 0.50s maximum across 19 sampled X16 searches. Easy: 0.37s average, 0.75s maximum across 19 sampled X16 searches. These small samples are timing checks, rather than a new
representative waiting-time study.

The X16 game places two root arrays at $0400–$05BF and leaves $05C0–$07FF
for its C stack. The headless harness retains that area for its mailbox.
Version 3 saves/preferences accept existing versions 1 and 2; old difficulty
IDs retain their meanings. The save table abbreviates Beginner as `BEGIN.`
and CPU pairs as `B/E`.

## Reproduction

Build with `make -C src` and `make -C tests uci`. Use Python with python-chess
installed (this session used `PYTHONPATH=build/test-python`). For example:

```sh
python3 tools/rate_difficulties.py --native-engine tests/uci --depths 1 \
  --noises 50 300 --games-per-opponent 1200 --seed 19377 --workers 16 \
  --openings docs/engine/weak-calibration-2026-10-11/held-out-openings.json \
  --out build/weak-calibration-reproduction
python3 tools/weakness_parity_test.py \
  --run docs/engine/weak-calibration-2026-10-11/confirmation \
  --out build/weakness-parity.json
python3 tools/summarize_weak_calibration.py \
  --root docs/engine/weak-calibration-2026-10-11
```

Summary data are in `holdout-assessment.json` and `comparisons.json`.
Preset selection was recorded before the Beginner holdout in `profile-selection.json`.
