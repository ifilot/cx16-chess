"""Compare native/X16 fixed-depth searches on recorded positions and warm games."""
import argparse
import hashlib
import json
import multiprocessing
import random
from multiprocessing.util import Finalize
from pathlib import Path
import time

from engine_evidence import open_text

import chess
import chess.pgn

from engine_bridge import ROOT
from rate_difficulties import NativeEngine
from x16uci import X16Engine

native = x16 = None


def initialize(depth):
    global native, x16
    native = NativeEngine(str(ROOT / 'tests/uci'))
    native.depth = depth
    x16 = X16Engine(depth=depth, time_per_move=0)
    Finalize(None, native.quit, exitpriority=10)
    Finalize(None, x16.quit, exitpriority=10)


def compare(board):
    native.play(board)
    x16.play(board)
    changes = {key: [native.last[key], x16.last[key]] for key in
               ('move', 'depth', 'score', 'nodes') if native.last[key] != x16.last[key]}
    return dict(fen=board.fen(), result=x16.last, changes=changes)


def cold(position):
    board = chess.Board(position['base_fen'])
    for frm, to, promo in position['history']:
        board.push(chess.Move((frm >> 4) * 8 + (frm & 7), (to >> 4) * 8 + (to & 7), promo or None))
    native.new_game()
    x16.new_game()
    return dict(name=position['name'], **compare(board))


def warm(task):
    path, limit = task
    with open_text(path) as stream:
        game = chess.pgn.read_game(stream)
    assert game is not None and not game.errors
    colour = chess.WHITE if game.headers['White'].startswith('CX16') else chess.BLACK
    board = game.board()
    native.new_game()
    x16.new_game()
    rows = []
    for move in game.mainline_moves():
        if board.turn == colour and board.ply() >= 12:
            rows.append(dict(game=path.name, ply=board.ply(), **compare(board)))
            print(f'warm {path.name} {len(rows)}/{limit}: '
                  f'{rows[-1]["result"]["seconds"]:.1f} X16 seconds; '
                  f'{len(rows[-1]["changes"])} differences', flush=True)
            if len(rows) == limit:
                break
        board.push(move)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depth', type=int, required=True, choices=range(1, 9))
    parser.add_argument('--cold-positions', type=int, help='Seeded subset of the recorded positions; default: all')
    parser.add_argument('--warm-searches', type=int, default=18, help='Searches per warm game sequence')
    parser.add_argument('--seed', type=int, default=16)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--positions', type=Path, default=ROOT / 'docs/engine/fixed-depth-2026-10-11/timing.json')
    parser.add_argument('--warm-run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.workers > 0
    positions = json.loads(args.positions.read_text())['positions']
    if args.warm_searches < 1 or (args.cold_positions is not None and
                                  not 1 <= args.cold_positions <= len(positions)):
        parser.error('invalid cold position count or warm search count')
    if args.cold_positions is not None:
        positions = random.Random(args.seed).sample(positions, args.cold_positions)
    config = json.loads((args.warm_run / 'configuration.json').read_text())
    level = next(iter(config['levels']))
    anchor = config['opponents'][0]
    games = [(args.warm_run / 'games' / f'{level}-{anchor}-{number:02d}.pgn', args.warm_searches) for number in (0, 1)]
    started = time.monotonic()
    with multiprocessing.Pool(args.workers, initialize, (args.depth,)) as pool:
        cold_rows = []
        for row in pool.imap_unordered(cold, positions):
            cold_rows.append(row)
            print(f'cold {len(cold_rows)}/{len(positions)}: {row["name"]}; '
                  f'{row["result"]["seconds"]:.1f} X16 seconds; '
                  f'{len(row["changes"])} differences', flush=True)
        warm_rows = [row for result in pool.map(warm, games) for row in result]
    differences = [row for row in cold_rows + warm_rows if row['changes']]
    report = dict(depth=args.depth, cold_searches=len(cold_rows), warm_searches=len(warm_rows),
                  differences=differences, elapsed_seconds=time.monotonic() - started,
                  native_engine_sha256=hashlib.sha256((ROOT / 'tests/uci').read_bytes()).hexdigest(),
                  engine_sha256=hashlib.sha256((ROOT / 'src/ENGINE.PRG').read_bytes()).hexdigest(),
                  emulator_sha256=hashlib.sha256((ROOT.parent / 'x16-emulator/build/x16emu').read_bytes()).hexdigest(),
                  seed=args.seed, warm_run=str(args.warm_run),
                  positions_sha256=hashlib.sha256(args.positions.read_bytes()).hexdigest(),
                  cold=cold_rows, warm=warm_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(cold_rows)} cold and {len(warm_rows)} warm searches; {len(differences)} differences; '
          f'{report["elapsed_seconds"]:.1f}s', flush=True)
    raise SystemExit(bool(differences))


if __name__ == '__main__':
    main()
