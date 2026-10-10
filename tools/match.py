"""Play the engine against Stockfish and estimate its rating.

  python3 tools/match.py --x16 --time 10 --sf-elo 1320 --games 20 --workers 10
  python3 tools/match.py --nodes 8000 ...          (native build, node limit)

--x16 plays the real X16 binary in the AgentBridge emulator (emulated
seconds per move). Stockfish plays with UCI_LimitStrength at --sf-elo.
Openings come from a fixed list of balanced lines, each played with both
colours. Games are written to a PGN file.
"""
import argparse
import datetime
import math
import multiprocessing
import sys
from pathlib import Path

import chess
import chess.engine
import chess.pgn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

OPENINGS = [
    'e2e4 e7e5 g1f3 b8c6', 'd2d4 d7d5 c2c4 e7e6', 'e2e4 c7c5 g1f3 d7d6',
    'd2d4 g8f6 c2c4 g7g6', 'e2e4 e7e6 d2d4 d7d5', 'c2c4 e7e5 b1c3 g8f6',
    'e2e4 c7c6 d2d4 d7d5', 'g1f3 d7d5 g2g3 g8f6', 'd2d4 d7d5 g1f3 g8f6',
    'e2e4 e7e5 f1c4 g8f6', 'd2d4 g8f6 c2c4 e7e6', 'e2e4 d7d5 e4d5 d8d5',
    'e2e4 c7c5 b1c3 b8c6', 'd2d4 f7f5 g2g3 g8f6', 'e2e4 g7g6 d2d4 f8g7',
    'c2c4 c7c5 g1f3 g8f6',
]

ours = None
sf = None
config = None


def init_worker(args):
    global ours, sf, config
    config = args
    if args.x16:
        from x16uci import X16Engine
        ours = X16Engine(time_per_move=args.time)
    else:
        ours = chess.engine.SimpleEngine.popen_uci(args.engine)
    sf = chess.engine.SimpleEngine.popen_uci('/usr/games/stockfish')
    sf.configure({'UCI_LimitStrength': True, 'UCI_Elo': args.sf_elo, 'Threads': 1})


def play_game(g):
    opening = OPENINGS[(g // 2) % len(OPENINGS)].split()
    we_are_white = g % 2 == 0
    board = chess.Board()
    for m in opening:
        board.push_uci(m)
    if config.x16:
        ours.new_game()
    while not board.is_game_over(claim_draw=True) and board.ply() < 300:
        if (board.turn == chess.WHITE) == we_are_white:
            if config.x16:
                move = ours.play(board)
            else:
                move = ours.play(board, chess.engine.Limit(nodes=config.nodes),
                                 game=g).move
        else:
            move = sf.play(board, chess.engine.Limit(time=config.sf_time), game=g).move
        board.push(move)
    result = board.result(claim_draw=True)
    if result == '*':
        result = '1/2-1/2'
    game = chess.pgn.Game.from_board(board)
    name = f'CX16-CHESS ({"X16 %gs" % config.time if config.x16 else "%d nodes" % config.nodes})'
    game.headers['Event'] = f'CX16-CHESS vs Stockfish {config.sf_elo}'
    game.headers['White'] = name if we_are_white else f'Stockfish {config.sf_elo}'
    game.headers['Black'] = f'Stockfish {config.sf_elo}' if we_are_white else name
    game.headers['Result'] = result
    game.headers['Date'] = datetime.date.today().isoformat()
    score = {'1-0': 1.0, '0-1': 0.0}.get(result, 0.5)
    return g, we_are_white, result, (score if we_are_white else 1 - score), board.ply(), str(game)


def elo_diff(score):
    score = min(max(score, 0.01), 0.99)
    return -400 * math.log10(1 / score - 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--games', type=int, default=20)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--nodes', type=int, default=8000, help='node limit per move (native)')
    p.add_argument('--x16', action='store_true', help='use the emulated X16 engine')
    p.add_argument('--engine', default=str(ROOT / 'tests/uci'), help='native UCI engine binary')
    p.add_argument('--time', type=float, default=10.0, help='seconds per move on the X16')
    p.add_argument('--sf-elo', type=int, default=1320)
    p.add_argument('--sf-time', type=float, default=0.1)
    p.add_argument('--pgn', default=str(ROOT / 'build/match.pgn'))
    args = p.parse_args()

    points = 0.0
    done = 0
    Path(args.pgn).parent.mkdir(parents=True, exist_ok=True)
    with open(args.pgn, 'w') as out, \
            multiprocessing.Pool(args.workers, initializer=init_worker, initargs=(args,)) as pool:
        for g, white, result, mine, plies, pgn in pool.imap_unordered(play_game, range(args.games)):
            done += 1
            points += mine
            print(pgn, file=out, end='\n\n')
            out.flush()
            print(f'game {g + 1:2d}: {"W" if white else "B"} {result:8s} ({plies:3d} plies)  '
                  f'total {points}/{done}', flush=True)
    s = points / args.games
    print(f'score {points}/{args.games} = {100 * s:.0f}%  -> about {args.sf_elo + elo_diff(s):.0f} '
          f'Elo (Stockfish UCI_Elo {args.sf_elo} scale)')


if __name__ == '__main__':
    main()
