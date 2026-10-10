"""Run an EPD test suite (e.g. Win At Chess) on the emulated X16 engine.

  python3 tools/epd_test.py tests/epd/wac.epd --time 10 --workers 8

A position counts as solved when the engine plays a 'bm' (best move) or
avoids every 'am' (avoid move). Times are emulated X16 seconds.
"""
import argparse
import multiprocessing
import sys
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

bridge = None


def init_worker():
    global bridge
    from engine_bridge import EngineBridge
    bridge = EngineBridge()


def run(job):
    epd, limit, depth = job
    board, ops = chess.Board.from_epd(epd)
    r = bridge.search(board.fen(), time_limit=limit, depth=depth, fresh=True)
    move = chess.Move.from_uci(r['move'])
    solved = True
    if 'bm' in ops:
        solved = move in ops['bm']
    if 'am' in ops:
        solved = solved and move not in ops['am']
    want = ' '.join(board.san(m) for m in ops.get('bm', [])) or \
        'not ' + ' '.join(board.san(m) for m in ops.get('am', []))
    return ops.get('id', '?'), solved, board.san(move), want, r['depth'], r['nodes']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('epd')
    p.add_argument('--time', type=float, default=10.0)
    p.add_argument('--depth', type=int, default=0)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--limit', type=int, default=0, help='only the first N positions')
    args = p.parse_args()
    lines = [l.strip() for l in open(args.epd) if l.strip()]
    if args.limit:
        lines = lines[:args.limit]
    solved = 0
    with multiprocessing.Pool(args.workers, initializer=init_worker) as pool:
        for i, (pid, ok, played, want, depth, nodes) in enumerate(
                pool.imap(run, [(l, args.time, args.depth) for l in lines])):
            solved += ok
            print(f'{pid:10s} {"ok  " if ok else "FAIL"} played {played:7s} want {want:14s} '
                  f'depth {depth:2d} nodes {nodes:6d}', flush=True)
    print(f'solved {solved}/{len(lines)} at {args.time:g} s per position')


if __name__ == '__main__':
    main()
