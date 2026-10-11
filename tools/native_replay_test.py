"""Replay recorded X16 games through native C, checking every search result."""
import argparse
import hashlib
import json
from pathlib import Path

import chess.pgn

from rate_difficulties import NativeEngine, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--native-engine', type=Path, default=ROOT / 'tests/uci')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--allow-new-engine', action='store_true', help='Compare a changed engine against historical traces')
    args = parser.parse_args()
    config = json.loads((args.run / 'configuration.json').read_text())
    assert config['search_mode'] == 'depth'
    current_hash = hashlib.sha256((ROOT / 'src/ENGINE.PRG').read_bytes()).hexdigest()
    assert args.allow_new_engine or config['engine_sha256'] == current_hash
    rows = [json.loads(line) for line in (args.run / 'games.jsonl').read_text().splitlines()]
    engine = NativeEngine(str(args.native_engine.resolve()))
    searches, differences = 0, []
    try:
        for index, row in enumerate(rows):
            path = args.run / 'games' / f'{row["level"]}-{row["opponent_elo"]}-{row["number"]:02d}.pgn'
            with path.open() as stream:
                game = chess.pgn.read_game(stream)
            assert game is not None and not game.errors
            board = game.board()
            trace = {entry['ply']: entry for entry in row['engine_moves']}
            engine.new_game()
            engine.depth = config['levels'][row['level']]
            for move in game.mainline_moves():
                if board.ply() in trace:
                    expected = trace.pop(board.ply())
                    engine.play(board)
                    changed = {key: [expected[key], engine.last[key]] for key in
                               ('move', 'depth', 'score', 'nodes') if expected[key] != engine.last[key]}
                    searches += 1
                    if changed:
                        differences.append(dict(game=path.name, ply=board.ply(), changes=changed))
                board.push(move)
            assert not trace, 'Unplayed search in reference game'
            if (index + 1) % 24 == 0:
                print(f'{index + 1}/{len(rows)} games; {searches} searches; {len(differences)} differences', flush=True)
    finally:
        engine.quit()
    report = dict(games=len(rows), searches=searches, differences=differences,
                  x16_engine_sha256=config['engine_sha256'],
                  current_x16_engine_sha256=current_hash,
                  native_engine_sha256=hashlib.sha256(args.native_engine.read_bytes()).hexdigest(),
                  source_configuration=config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{searches} searches; {len(differences)} differences', flush=True)
    raise SystemExit(bool(differences))


if __name__ == '__main__':
    main()
