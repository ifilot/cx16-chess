"""Generate a recorded, diverse opening suite using full-strength local Stockfish.

Each line starts with a familiar four-ply opening, then samples near-best moves.
The resulting positions must be distinct, unfinished, and within 100 centipawns
of equality. The saved suite, rather than regeneration, reproduces a tournament.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random

import chess

from match import OPENINGS
from rate_difficulties import LocalStockfish


def generate(engine, count, seed, depth, excluded=()):
    rng = random.Random(seed)
    lines, evaluations, positions = [], [], set(excluded)
    attempts = 0
    while len(lines) < count:
        attempts += 1
        if attempts > count * 50:
            raise RuntimeError('Could not generate enough distinct balanced openings')
        board = chess.Board()
        for move in OPENINGS[(attempts - 1) % len(OPENINGS)].split():
            board.push_uci(move)
        target = rng.choice((8, 10, 12))
        while board.ply() < target and not board.is_game_over(claim_draw=True):
            infos = engine.analyse(board, depth=depth, multipv=3)
            scored = [(info['score'], info['pv'][0]) for info in infos if info['score'] is not None]
            if not scored:
                break
            best = max(score for score, _ in scored)
            candidates = [move for score, move in scored if score >= best - 50]
            board.push(rng.choice(candidates))
        if board.ply() < target or board.is_game_over(claim_draw=True):
            continue
        key = tuple(board.fen().split()[:4])
        if key in positions:
            continue
        score = engine.analyse(board, depth=depth + 2)[0]['score']
        if score is not None and board.turn == chess.BLACK:
            score = -score
        if score is None or abs(score) > 100:
            continue
        positions.add(key)
        lines.append(' '.join(move.uci() for move in board.move_stack))
        evaluations.append(score)
        if len(lines) % 10 == 0:
            print(f'{len(lines)}/{count} balanced distinct openings', flush=True)
    return lines, evaluations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--seed', type=int, default=16)
    parser.add_argument('--depth', type=int, default=8)
    parser.add_argument('--stockfish', type=Path, default=Path('/usr/games/stockfish'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--exclude-openings', nargs='+', type=Path, default=[], help='Exclude positions from earlier suites')
    args = parser.parse_args()
    if args.count < 1 or args.depth < 1:
        parser.error('count and depth must be positive')
    if args.out.exists():
        parser.error('Opening suite already exists; choose a new output path')
    engine = LocalStockfish(str(args.stockfish))
    try:
        engine.configure({'Threads': 1, 'Hash': 16, 'UCI_LimitStrength': False})
        excluded = set()
        for path in args.exclude_openings:
            for line in json.loads(path.read_text())['openings']:
                board = chess.Board()
                for move in line.split():
                    board.push_uci(move)
                excluded.add(tuple(board.fen().split()[:4]))
        lines, evaluations = generate(engine, args.count, args.seed, args.depth, excluded)
        suite = dict(seed=args.seed, depth=args.depth, stockfish_id=engine.id,
                     stockfish_sha256=hashlib.sha256(args.stockfish.read_bytes()).hexdigest(),
                     max_final_white_cp=100, max_move_loss_cp=50,
                     openings=lines, final_white_cp=evaluations)
        if args.exclude_openings:
            suite['excluded_suite_sha256'] = [hashlib.sha256(path.read_bytes()).hexdigest() for path in args.exclude_openings]
    finally:
        engine.quit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(suite, indent=2) + '\n')
    print(f'Saved {args.out}', flush=True)


if __name__ == '__main__':
    main()
