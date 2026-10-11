"""Validate weak calibration runs and assess frozen presets on unused opening groups."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from validate_difficulty_run import validate

from compare_depth_runs import compare
from rate_difficulties import ROOT, paired_comparisons, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--final', action='store_true', help='Include fresh final confirmation and write final results')
    args = parser.parse_args()
    root = args.root
    runs = [root / 'confirmation', root / 'beginner-bracket']
    report = compare(runs, already_validated=True)
    (root / 'comparisons.json').write_text(json.dumps(report, indent=2) + '\n')
    selection = json.loads((root / 'profile-selection.json').read_text())
    assert selection['max_beginner_opening_pair_observed'] < min(selection['final_holdout_opening_pairs'])
    records = [json.loads(line) for run in runs for line in (run / 'games.jsonl').read_text().splitlines()]
    levels = {f'noise{p["noise"]}': p['depth'] for p in selection['profiles'].values()}
    holdout = [r for r in records if r['level'] in levels and r['opening_pair'] in selection['final_holdout_opening_pairs']]
    assert len(holdout) == 2400
    config = json.loads((runs[0] / 'configuration.json').read_text())
    for key, path in (('engine_sha256', ROOT / 'src/ENGINE.PRG'), ('native_engine_sha256', ROOT / 'tests/uci')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == config[key]
    stats = summarize(holdout, config['opponents'], levels, 'depth')
    assessment = dict(games=len(holdout), opening_groups=300, summaries=stats,
                      paired_comparisons=paired_comparisons(holdout, config['opponents'], levels),
                      frozen_profiles=selection, configuration=config,
                      source_runs=[str(p) for p in runs])
    (root / 'holdout-assessment.json').write_text(json.dumps(assessment, indent=2) + '\n')
    parity = json.loads((root / 'weakness-parity.json').read_text())
    regression = json.loads((root / 'unchanged-search-parity.json').read_text())
    assert parity['differences'] == 0 and not regression['differences']
    assert parity['x16_sha256'] == config['engine_sha256']
    assert parity['native_sha256'] == config['native_engine_sha256']
    table = []
    for name, policy in selection['profiles'].items():
        s = stats[f'noise{policy["noise"]}']
        lo, hi = s['confidence_95']
        table.append(f'| {name} | {policy["noise"]} | {s["games"]:,} | {s["estimated_elo"]} | {lo}–{hi} | {s["wins"]}/{s["draws"]}/{s["losses"]} |')
    full_table = []
    for level, s in report['summaries'].items():
        lo, hi = s['confidence_95']
        full_table.append(f'| {report["noise_by_level"][level]} | {s["games"]:,} | {s["estimated_elo"]} | {lo}–{hi} |')
    timing = []
    for name, policy in selection['profiles'].items():
        samples = [c['result']['seconds'] for c in parity['cases'] if c['noise'] == policy['noise']]
        timing.append(f'{name}: {mean(samples):.2f}s average, {max(samples):.2f}s maximum across {len(samples)} sampled X16 searches.')
    diff = next(iter(assessment['paired_comparisons'].values()))
    text = f'''# Beginner and Easy calibration, 2026-10-11

The game now offers **Beginner**, **Easy**, and **1–6 ply**. The default remains
4 ply, and each CPU in a demo has its own setting. Beginner uses noise 300;
Easy uses noise 50. Both search one nominal ply. The regular depth modes retain
the original move selection. Analysis uses the regular engine regardless of difficulty.

## Final assessment on held-out openings

| Preset | Root noise (cp) | Games | Estimated Elo | 95% interval | Wins/draws/losses |
|---|---:|---:|---:|---:|---:|
{chr(10).join(table)}

These estimates use **1,200 games per preset**, on the last 300 distinct balanced
opening positions, both colours, against Stockfish 16 UCI_Elo 1320 and 1500 at
100ms per move. No X16 clock is simulated in native matches. Whole opening
groups are resampled 20,000 times, preserving opponent and colour pairing.
The confidence intervals cover game/opening sampling, rather than uncertainty
in Stockfish's rating scale. They are local benchmark ratings, not certified
FIDE or online human ratings. Extrapolation below the opponent ratings also
assumes the usual Elo logistic score model.

Beginner was frozen when {selection['beginner_bracket_games_observed']} of its
bracketing games had completed, with maximum observed opening index
{selection['max_beginner_opening_pair_observed']}; final assessment starts at
opening index 300. Easy was selected from the initial pilot. The unused final
opening groups provide a separate check after selecting the presets.
Easy minus Beginner is **{diff['estimated_difference']:+d} Elo**, with paired 95%
interval **{diff['confidence_95'][0]:+d} to {diff['confidence_95'][1]:+d}**.

## Tuning and full samples

The pilots played 864 games across nine policies, including noise 0.
A new 600-position opening suite, generated with seed 17, was used for
2,400 games each at noise 50, 200 and 300: **7,200 games**, all validated.
Noise 200 was stronger than the desired Beginner setting, so 300 was chosen.
The full samples include tuning observations; the table above uses the
separate final opening groups.

| Noise (cp) | Games | Full-sample estimate | 95% interval |
|---:|---:|---:|---:|
{chr(10).join(full_table)}

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

All **{parity['searches']} seeded cold/warm searches** matched native/X16 moves,
scores, depths and nodes, including complete recorded games. With noise
turned off, all **{regression['searches']:,} historical searches** still matched.
Native tests, graphical menu/demo/scorecard tests, save compatibility,
real SD-card saving, weak search selection, full-strength analysis and a
Golden RAM stack guard passed. See `test-results.json`.

{' '.join(timing)} These small samples are timing checks, rather than a new
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
python3 tools/rate_difficulties.py --native-engine tests/uci --depths 1 \\
  --noises 50 300 --games-per-opponent 1200 --seed 19377 --workers 16 \\
  --openings docs/engine/weak-calibration-2026-10-11/held-out-openings.json \\
  --out build/weak-calibration-reproduction
python3 tools/weakness_parity_test.py \\
  --run docs/engine/weak-calibration-2026-10-11/confirmation \\
  --out build/weakness-parity.json
python3 tools/summarize_weak_calibration.py \\
  --root docs/engine/weak-calibration-2026-10-11
```

Summary data are in `holdout-assessment.json` and `comparisons.json`.
Preset selection was recorded before the Beginner holdout in `profile-selection.json`.
'''
    (root / 'candidate-300-results.md').write_text('This records the earlier noise-300 candidate; see RESULTS.md for the final preset.\n\n' + text)
    if args.final:
        selected_noise = 350
        final_run = root / 'final-beginner-350'
        final_validation = json.loads((final_run / 'validation.json').read_text())
        assert final_validation['games'] == 1200 and final_validation['configuration_and_summary_match']
        final_summary = json.loads((final_run / 'summary.json').read_text())
        final_choice = json.loads((root / 'final350-profile-selection.json').read_text())
        assert final_choice['noise'] == selected_noise
        assert final_summary['configuration']['noise_by_level'] == {f'noise{selected_noise}': selected_noise}
        assert final_summary['configuration']['engine_sha256'] == config['engine_sha256']
        assert final_summary['configuration']['native_engine_sha256'] == config['native_engine_sha256']
        final_stats = {'Beginner': final_summary['summaries'][f'noise{selected_noise}'], 'Easy': stats['noise50']}
        (root / 'final-assessment.json').write_text(json.dumps(dict(
            profiles=final_stats, beginner_noise=selected_noise, easy_noise=50,
            beginner_configuration=final_summary['configuration'],
            easy_configuration=config, beginner_validation=final_validation,
            note='Beginner uses a fresh disjoint opening suite; Easy uses the seed-17 holdout. No paired CI between these different suites.'), indent=2) + '\n')
        final_table = []
        for name, s in final_stats.items():
            lo, hi = s['confidence_95']
            final_table.append(f'| {name} | {s["games"]:,} | **{s["estimated_elo"]}** | {lo}–{hi} | {s["wins"]}/{s["draws"]}/{s["losses"]} |')
        final_text = f"""# Final weak-engine calibration, 2026-10-11

**Beginner** uses root noise {selected_noise} and **Easy** uses noise 50, both at one nominal
ply. The game also offers regular **1–6 ply**, with **4 ply** still the default.
Both computers in a demo can choose independent settings. Analysis always
uses the regular engine.

| Preset | Final assessment games | Estimated Elo | 95% interval | Wins/draws/losses |
|---|---:|---:|---:|---:|
{chr(10).join(final_table)}

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
positions from the earlier suites. The noise-{selected_noise} setting was selected before
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

**{parity['searches']} seeded native/X16 searches** matched moves, scores,
depths and nodes, including complete game replays. With noise off, all
**{regression['searches']:,} historical searches** still matched. Native tests,
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
python3 tools/rate_difficulties.py --native-engine tests/uci --depths 1 {chr(92)}
  --noises {selected_noise} --games-per-opponent 600 --seed 31415 --workers 16 {chr(92)}
  --openings docs/engine/weak-calibration-2026-10-11/final350-openings.json {chr(92)}
  --out build/weak-beginner-reproduction
python3 tools/summarize_weak_calibration.py {chr(92)}
  --root docs/engine/weak-calibration-2026-10-11 --final
```
"""
        (root / 'RESULTS.md').write_text(final_text)
        print(json.dumps(final_stats, indent=2))
    else:
        print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
