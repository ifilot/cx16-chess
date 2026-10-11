"""Check seeded weak searches on native C and real X16, cold and with warm history."""
import argparse
import hashlib
import json
from pathlib import Path
import chess
import chess.pgn
from engine_bridge import EngineBridge
from rate_difficulties import NativeEngine, ROOT
from x16uci import X16Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run', type=Path, help='Also replay complete recorded games through both builds')
    args = parser.parse_args()
    native = NativeEngine(str(ROOT / 'tests/uci'))
    cases = []
    suite = json.loads((ROOT / 'docs/engine/native-depth-elo-2026-10-11/openings.json').read_text())['openings']
    try:
        with EngineBridge() as bridge:
            for noise in (1, 10, 25, 50, 100, 200, 300, 350, 400, 600, 1000, 2000):
                for seed in (1, 32768, 65535):
                    board = chess.Board()
                    for move in suite[len(cases) % len(suite)].split():
                        board.push_uci(move)
                    native.noise, native.seed, native.depth = noise, seed, 1
                    native.new_game()
                    native.play(board)
                    actual = bridge.search(board.fen(), depth=1, fresh=True, noise=noise, seed=seed)
                    expected = native.last
                    for key in ('move', 'depth', 'score', 'nodes'):
                        assert actual[key] == expected[key], (noise, seed, key, actual, expected)
                    native.new_game()
                    native.play(board)
                    assert all(native.last[k] == expected[k] for k in ('move', 'score', 'nodes'))
                    cases.append(dict(noise=noise, seed=seed, fen=board.fen(), result=actual))
        x16 = X16Engine(depth=1, time_per_move=0)
        try:
            for noise in (25, 50, 100, 200, 300, 350, 400, 1000):
                board = chess.Board()
                native.noise = x16.noise = noise
                native.seed = x16.seed = 19377
                native.new_game()
                x16.new_game()
                for ply in range(16):
                    move = native.play(board)
                    assert x16.play(board) == move
                    assert all(x16.last[k] == native.last[k] for k in ('depth', 'score', 'nodes'))
                    cases.append(dict(noise=noise, seed=19377, fen=board.fen(), warm_ply=ply, result=x16.last))
                    board.push(move)
            if args.run:
                rows = [json.loads(line) for line in (args.run / 'games.jsonl').read_text().splitlines()]
                for row in sorted((r for r in rows if r['number'] < 2), key=lambda r: (r['level'], r['opponent_elo'], r['number'])):
                    native.noise = x16.noise = row['noise']
                    native.seed = x16.seed = row['seed']
                    native.new_game()
                    x16.new_game()
                    path = args.run / 'games' / f'{row["level"]}-{row["opponent_elo"]}-{row["number"]:02d}.pgn'
                    with path.open() as stream:
                        game = chess.pgn.read_game(stream)
                    board = game.board()
                    trace = {entry['ply']: entry for entry in row['engine_moves']}
                    for move in game.mainline_moves():
                        if board.ply() in trace:
                            expected = trace.pop(board.ply())
                            assert native.play(board) == x16.play(board) == move
                            assert all(native.last[k] == x16.last[k] == expected[k] for k in ('move', 'score', 'depth', 'nodes'))
                            cases.append(dict(noise=row['noise'], seed=row['seed'], game=path.name,
                                              warm_ply=board.ply(), result=x16.last))
                        board.push(move)
                    assert not trace
        finally:
            x16.quit()
    finally:
        native.quit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(searches=len(cases), differences=0, cases=cases,
        native_sha256=hashlib.sha256((ROOT / 'tests/uci').read_bytes()).hexdigest(),
        x16_sha256=hashlib.sha256((ROOT / 'src/ENGINE.PRG').read_bytes()).hexdigest()), indent=2) + '\n')
    print(f'{len(cases)} seeded cold/warm searches match; repeated seeds reproduce moves')


if __name__ == '__main__':
    main()
