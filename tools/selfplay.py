"""Self-play between two native engine builds, for testing changes.

  python3 tools/selfplay.py tests/uci_NAME tests/uci --games 400 --nodes 8000

Each balanced opening (tests/openings.txt, generated with --make-openings)
is played twice with colours swapped, so the result measures A against B.
"""
import argparse
import math
import multiprocessing
import random
from pathlib import Path

import chess
import chess.engine

ROOT = Path(__file__).resolve().parents[1]
OPENINGS = ROOT / 'tests/openings.txt'
engines = None
cfg = None


def make_openings(n):
    sf = chess.engine.SimpleEngine.popen_uci('/usr/games/stockfish')
    rng = random.Random(42)
    lines = []
    while len(lines) < n:
        board = chess.Board()
        for _ in range(8):
            board.push(rng.choice(list(board.legal_moves)))
            if board.is_game_over():
                break
        if board.is_game_over():
            continue
        score = sf.analyse(board, chess.engine.Limit(depth=12))['score'].white().score(mate_score=9999)
        if abs(score) <= 60:
            lines.append(' '.join(m.uci() for m in board.move_stack))
    sf.quit()
    OPENINGS.write_text('\n'.join(lines) + '\n')


def init(args):
    global engines, cfg
    cfg = args
    engines = [chess.engine.SimpleEngine.popen_uci(args.a), chess.engine.SimpleEngine.popen_uci(args.b)]


def play(job):
    g, opening = job
    a_white = g % 2 == 0
    board = chess.Board()
    for m in opening.split():
        board.push_uci(m)
    while not board.is_game_over(claim_draw=True) and board.ply() < 300:
        a_turn = (board.turn == chess.WHITE) == a_white
        eng = engines[0 if a_turn else 1]
        board.push(eng.play(board, chess.engine.Limit(nodes=cfg.nodes), game=g).move)
    r = board.result(claim_draw=True)
    s = {'1-0': 1.0, '0-1': 0.0}.get(r, 0.5)
    return s if a_white else 1 - s


def main():
    p = argparse.ArgumentParser()
    p.add_argument('a', nargs='?')
    p.add_argument('b', nargs='?')
    p.add_argument('--games', type=int, default=400)
    p.add_argument('--nodes', type=int, default=8000)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--make-openings', type=int, default=0)
    args = p.parse_args()
    if args.make_openings:
        make_openings(args.make_openings)
        return
    openings = OPENINGS.read_text().split('\n')
    jobs = [(g, openings[(g // 2) % len(openings)]) for g in range(args.games)]
    with multiprocessing.Pool(args.workers, initializer=init, initargs=(args,)) as pool:
        scores = pool.map(play, jobs)
    n = len(scores)
    s = sum(scores) / n
    sd = math.sqrt(sum((x - s) ** 2 for x in scores) / n / n)
    elo = -400 * math.log10(1 / min(max(s, 0.001), 0.999) - 1)
    print(f'{Path(args.a).name} vs {Path(args.b).name}: {sum(scores)}/{n} = {100 * s:.1f}% '
          f'+- {100 * sd:.1f}%  ({elo:+.0f} Elo)')


if __name__ == '__main__':
    main()
