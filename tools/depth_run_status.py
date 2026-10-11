"""Report provisional ratings and comparisons on complete shared openings."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from engine_evidence import records as evidence_records

from rate_difficulties import rating


def records(root):
    # A tournament can still be writing the final line of the checkpoint.
    return list(evidence_records(root / 'games.jsonl', complete_lines=True))


def stats(rows):
    count = len(rows)
    points = sum(row['points'] for row in rows)
    return dict(games=count, points=points,
                wins=sum(row['points'] == 1 for row in rows),
                draws=sum(row['points'] == .5 for row in rows),
                losses=sum(row['points'] == 0 for row in rows),
                score_percent=round(100 * points / count, 1) if count else None,
                provisional_elo=rating(points / count, [r['opponent_elo'] for r in rows]) if count else None)


def status(root, references):
    config = json.loads((root / 'configuration.json').read_text())
    rows = records(root)
    current = {level: stats([r for r in rows if r['level'] == level]) for level in config['levels']}
    levels = dict(config['levels'])
    for reference in references:
        source = json.loads((reference / 'configuration.json').read_text())
        for key in ('openings', 'opponents', 'games_per_opponent', 'backend', 'search_mode',
                    'native_engine_sha256', 'engine_sha256', 'stockfish_sha256',
                    'sf_time', 'clock_seconds', 'seed', 'weakness_policy'):
            assert config.get(key) == source.get(key), f'Different test conditions: {key}'
        assert not set(levels).intersection(source['levels']), 'Duplicate level'
        levels.update(source['levels'])
        rows.extend(records(reference))
    counts = {level: Counter(r['opening_pair'] for r in rows if r['level'] == level) for level in levels}
    complete = set.intersection(*(set(k for k, n in groups.items() if n == 2 * len(config['opponents']))
                                  for groups in counts.values()))
    return dict(recorded_at=datetime.now(ZoneInfo('Europe/Amsterdam')).isoformat(),
                provisional=True, completed=sum(s['games'] for s in current.values()),
                planned=len(config['levels']) * len(config['opponents']) * config['games_per_opponent'],
                current=current, matched_complete_openings=len(complete),
                matched_openings={level: stats([r for r in rows if r['level'] == level and r['opening_pair'] in complete])
                                  for level in sorted(levels, key=levels.get)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--reference', type=Path, action='append', default=[])
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = status(args.run, args.reference)
    output = json.dumps(report, indent=2) + '\n'
    if args.out:
        args.out.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
