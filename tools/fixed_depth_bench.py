"""Measure fixed-depth X16 waiting times on sampled tournament positions."""
import argparse
import hashlib
import json
import multiprocessing
from multiprocessing.util import Finalize
from pathlib import Path
import random
import statistics
import time

import chess.pgn

from depth_bench import POSITIONS
from engine_bridge import CPU_HZ, EngineBridge, ROOT
from x16uci import PROMO, sq88

engine = None


def initialize():
    global engine
    engine = EngineBridge()
    Finalize(None, engine.close, exitpriority=10)


def measure(task):
    position, depth = task
    started = time.monotonic()
    result = engine.search(position['base_fen'], depth=depth, fresh=True,
                           moves=position['history'])
    if result['replayed'] != len(position['history']):
        raise RuntimeError('Incomplete history replay')
    return dict(position=position['name'], group=position['group'], target_depth=depth,
                wall_seconds=time.monotonic() - started, result=result)


def sample_positions(pgn, count, seed):
    rng = random.Random(seed)
    games = []
    with pgn.open() as stream:
        while (game := chess.pgn.read_game(stream)) is not None:
            if game.errors:
                raise ValueError(game.errors)
            games.append(game)
    positions = []
    for game in rng.sample(games, count):
        colour = chess.WHITE if game.headers['White'].startswith('CX16') else chess.BLACK
        boards = []
        for node in game.mainline():
            board = node.parent.board()
            if board.ply() >= 12 and board.turn == colour and not board.is_game_over():
                boards.append(board)
        board = rng.choice(boards)
        base = board.copy()
        moves = []
        for _ in range(min(board.halfmove_clock, len(board.move_stack), 85)):
            move = base.pop()
            moves.append((sq88(move.from_square), sq88(move.to_square), PROMO.get(move.promotion, 0)))
        positions.append(dict(name=f"round-{game.headers['Round']}-ply-{board.ply()}",
                              group='sample', fen=board.fen(), base_fen=base.fen(),
                              history=list(reversed(moves))))
    for name, fen in POSITIONS.items():
        positions.append(dict(name=name, group='reference', fen=fen, base_fen=fen, history=[]))
    return positions


def summarize(rows):
    summaries = {}
    for group in ('sample', 'reference'):
        summaries[group] = {}
        for depth in range(2, 7):
            selected = [r for r in rows if r['group'] == group and r['target_depth'] == depth]
            seconds = sorted(r['result']['seconds'] for r in selected)
            summaries[group][depth] = dict(count=len(seconds), mean=statistics.mean(seconds),
                median=statistics.median(seconds), p90=seconds[min(len(seconds)-1, int(.9*len(seconds)))],
                maximum=max(seconds), stopped_early=sum(r['result']['depth'] < depth for r in selected))
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pgn', type=Path, required=True)
    parser.add_argument('--positions', type=int, default=64)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--seed', type=int, default=16)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.positions < 1 or args.workers < 1:
        parser.error('positions and workers must be positive')
    if args.out.exists() or args.out.with_suffix('.jsonl').exists():
        parser.error('output already exists; choose a new path')
    positions = sample_positions(args.pgn, args.positions, args.seed)
    tasks = [(position, depth) for depth in range(2, 7) for position in positions]
    rows = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.with_suffix('.jsonl').open('w') as progress, \
            multiprocessing.Pool(args.workers, initialize) as pool:
        for row in pool.imap_unordered(measure, tasks):
            rows.append(row)
            print(f"{len(rows)}/{len(tasks)}: {row['position']} depth {row['target_depth']} "
                  f"{row['result']['seconds']:.2f} X16 seconds", flush=True)
            # Keep completed searches available even during a long depth-six run.
            progress.write(json.dumps(row) + '\n')
            progress.flush()
    report = dict(pgn=str(args.pgn), pgn_sha256=hashlib.sha256(args.pgn.read_bytes()).hexdigest(),
        engine_sha256=hashlib.sha256((ROOT / 'src/ENGINE.PRG').read_bytes()).hexdigest(),
        emulator_sha256=hashlib.sha256((ROOT.parent / 'x16-emulator/build/x16emu').read_bytes()).hexdigest(),
        cpu_hz=CPU_HZ,
        seed=args.seed, workers=args.workers, fresh_tables=True, time_limit=0,
        positions=positions, summary=summarize(rows), searches=rows)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary'], indent=2), flush=True)


if __name__ == '__main__':
    main()
