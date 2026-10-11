"""Validate a complete difficulty tournament against its PGNs and configuration."""
import argparse
from collections import Counter
import io
import json
import math
from pathlib import Path

import chess
import chess.pgn


def validate(root):
    config = json.loads((root / 'configuration.json').read_text())
    rows = [json.loads(line) for line in (root / 'games.jsonl').read_text().splitlines()]
    expected = {(level, anchor, number) for level in config['levels']
                for anchor in config['opponents'] for number in range(config['games_per_opponent'])}
    actual = {(row['level'], row['opponent_elo'], row['number']) for row in rows}
    assert actual == expected and len(rows) == len(expected), 'Missing or duplicate games'
    early_stops = Counter()
    for row in rows:
        level, anchor, number = row['level'], row['opponent_elo'], row['number']
        assert row['white'] == (number % 2 == 0)
        assert row['opening_pair'] == number // 2
        game = chess.pgn.read_game(io.StringIO((root / 'games' / f'{level}-{anchor}-{number:02d}.pgn').read_text()))
        assert game is not None and not game.errors, (level, anchor, number, 'PGN parse')
        assert game.headers['Result'] == row['result']
        ours = 'White' if row['white'] else 'Black'
        theirs = 'Black' if row['white'] else 'White'
        assert game.headers[ours].startswith(f'CX16-CHESS {level} ')
        assert game.headers[theirs].endswith(f'UCI_Elo {anchor}')
        assert game.headers['OpeningPair'] == str(number // 2)
        if config.get('noise_by_level'):
            assert row['noise'] == config['noise_by_level'][level]
            expected_seed = 1 + ((config['seed'] + (number // 2) * 131 + anchor * 17 + int(row['white'])) % 65535)
            assert row['seed'] == expected_seed
            assert game.headers['RootNoise'] == str(row['noise'])
            assert game.headers['RandomSeed'] == str(row['seed'])
        white_points = {'1-0': 1, '0-1': 0, '1/2-1/2': .5}[row['result']]
        assert row['points'] == (white_points if row['white'] else 1 - white_points)
        board = game.board()
        moves = list(game.mainline_moves())
        early = {entry['ply']: entry for entry in row.get('engine_moves', [])
                 if config.get('search_mode') == 'depth' and entry['depth'] < config['levels'][level]}
        if 'openings' in config:
            opening = config['openings'][number // 2].split()
            assert [move.uci() for move in moves[:len(opening)]] == opening
        for move in moves:
            if board.ply() in early:
                entry = early[board.ply()]
                reason = 'mate' if abs(entry['score']) > 29488 else 'forced move'
                assert reason == 'mate' or board.legal_moves.count() == 1, 'Unexpected incomplete depth'
                early_stops[reason] += 1
            assert move in board.legal_moves
            board.push(move)
        assert board.ply() == row['plies']
        if row['termination'] not in ('time forfeit', 'game move limit'):
            assert board.result(claim_draw=True) == row['result']
            assert board.outcome(claim_draw=True).termination.name.lower() == row['termination']
        if 'engine_moves' in row:
            trace = row['engine_moves']
            assert len(trace) == row['searches']
            assert sum(move['nodes'] for move in trace) == row['nodes']
            assert sum(move['depth'] for move in trace) == row['depth_total']
            assert math.isclose(sum(move['seconds'] for move in trace),
                                row.get('host_search_seconds', row.get('emulated_seconds', 0)))
            for entry in trace:
                if config.get('search_mode') == 'depth':
                    assert entry['budget'] == 0
                    assert 1 <= entry['depth'] <= config['levels'][level]
                else:
                    assert 2 <= entry['budget'] <= config['levels'][level]
                assert entry['ply'] % 2 == (0 if row['white'] else 1)
                if entry['ply'] < len(moves):
                    assert entry['move'] == moves[entry['ply']].uci()
                else:
                    assert row['termination'] == 'time forfeit' and entry is trace[-1]
    summary = json.loads((root / 'summary.json').read_text())
    assert summary['configuration'] == config
    for level in config['levels']:
        selected = [row for row in rows if row['level'] == level]
        stats = summary['summaries'][level]
        assert stats['games'] == len(selected)
        assert stats['points'] == sum(row['points'] for row in selected)
        for key, value in (('wins', 1), ('draws', .5), ('losses', 0)):
            assert stats[key] == sum(row['points'] == value for row in selected)
    return dict(games=len(rows), legal_pgns=len(rows),
                searches=sum(row['searches'] for row in rows),
                early_stops_verified=dict(early_stops),
                levels=dict(Counter(row['level'] for row in rows)),
                terminations=dict(Counter(row['termination'] for row in rows)),
                unique_opening_groups=config['games_per_opponent'] // 2,
                configuration_and_summary_match=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    result = validate(args.run)
    (args.run / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
