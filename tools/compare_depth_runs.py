"""Compare complete depth runs with identical engines, opponents and openings."""
import argparse
import json
from pathlib import Path

from engine_evidence import records

from rate_difficulties import paired_comparisons
from validate_difficulty_run import validate


def compare(runs, already_validated=False, compatibility_reports=()):
    proofs = []
    for path in compatibility_reports:
        proof = json.loads(path.read_text())
        source = proof['source_configuration']
        assert not proof['differences'] and proof['searches'] > 0
        assert source['backend'] == 'native' and not source.get('noise_by_level')
        assert proof['games'] == len(source['levels']) * len(source['opponents']) * source['games_per_opponent']
        assert proof['x16_engine_sha256'] == source['engine_sha256']
        proofs.append(proof)
    baseline = None
    game_records, levels, summaries, noises = [], {}, {}, {}
    # Preserve pairing only when the actual opening list and test conditions
    # match. Different engine builds or opponent time controls are not pooled.
    keys = ('backend', 'native_engine_sha256', 'engine_sha256', 'stockfish_sha256',
            'stockfish_id', 'opponents', 'sf_time', 'clock_seconds', 'search_mode',
            'games_per_opponent', 'openings', 'opening_suite_sha256', 'seed', 'weakness_policy')
    for root in runs:
        if not already_validated:
            validate(root)
        else:
            # The calibration reporter runs immediately after the tournament's
            # own complete validation, while its finished data stay unchanged.
            audit = json.loads((root / 'validation.json').read_text())
            assert audit['configuration_and_summary_match']
        config = json.loads((root / 'configuration.json').read_text())
        assert config.get('search_mode') == 'depth'
        signature = {key: config.get(key) for key in keys}
        for proof in proofs:
            if config == proof['source_configuration']:
                # A complete replay establishes identical search behavior on
                # this reference run despite a changed executable hash.
                signature['native_engine_sha256'] = proof['native_engine_sha256']
                signature['engine_sha256'] = proof['current_x16_engine_sha256']
        if baseline is None:
            baseline = signature
        assert signature == baseline, f'Different test conditions: {root}'
        assert not set(levels).intersection(config['levels']), 'Duplicate depth level'
        levels.update(config['levels'])
        noises.update(config.get('noise_by_level', {}))
        summaries.update(json.loads((root / 'summary.json').read_text())['summaries'])
        game_records.extend(records(root / 'games.jsonl'))
    levels = dict(sorted(levels.items(), key=lambda pair: pair[1]))
    return dict(source_runs=[str(root) for root in runs], games=len(game_records),
                engine_compatibility_reports=[str(path) for path in compatibility_reports],
                levels=levels, noise_by_level=noises, summaries=summaries,
                paired_comparisons=paired_comparisons(game_records, baseline['opponents'], levels))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--compatibility-report', action='append', type=Path, default=[],
                        help='Complete historical replay proving unchanged searches across builds')
    args = parser.parse_args()
    report = compare(args.runs, compatibility_reports=args.compatibility_report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['paired_comparisons'], indent=2))


if __name__ == '__main__':
    main()
