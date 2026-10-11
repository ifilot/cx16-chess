"""Judge every move the X16 engine played in a PGN file.

For each move of CX16-CHESS the position before and after it is evaluated
by a strong engine; the difference is the centipawn loss (how much worse
the move is than the best one). The engine is the local Stockfish
(/usr/games/stockfish) by default, or with --online:

  1. Lichess cloud evaluation (https://lichess.org/api/cloud-eval), very
     deep, but only for positions in its cache (mostly openings);
  2. chess-api.com (Stockfish 17 NNUE), any position.

Online answers are cached in build/online_cache.json. The online services
take a few seconds per position.

  python3 tools/review_games.py docs/engine/x16_vs_stockfish1320.pgn
  python3 tools/review_games.py games.pgn --online --games 4
"""
import argparse
import concurrent.futures
import json
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import chess
import chess.pgn
from engine_evidence import open_text

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'build/online_cache.json'
MATE = 10000
LOCAL_MODE = False


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {}


def request_json(url, data=None):
    req = urllib.request.Request(url, data=data, headers={
        'User-Agent': 'cx16-chess engine review',
        'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def lichess(fen):
    url = 'https://lichess.org/api/cloud-eval?fen=' + urllib.parse.quote(fen)
    try:
        d = request_json(url)
    except Exception:
        return None
    pv = d['pvs'][0]
    cp = MATE if pv.get('mate', 0) > 0 else -MATE if 'mate' in pv else pv['cp']
    return {'cp': cp, 'best': pv['moves'].split()[0], 'depth': d['depth'], 'src': 'lichess'}


def chess_api(fen, depth):
    body = json.dumps({'fen': fen, 'depth': depth}).encode()
    for attempt in range(4):
        try:
            d = request_json('https://chess-api.com/v1', body)
            break
        except Exception:
            time.sleep(2 + 3 * attempt)
    else:
        return None
    if d.get('mate') is not None:
        cp = MATE if int(d['mate']) > 0 else -MATE
    else:
        cp = d['centipawns']
    return {'cp': int(cp), 'best': d.get('move'), 'depth': d.get('depth'), 'src': 'chess-api'}


cache_lock = threading.Lock()


LOCAL = None             # the local Stockfish (default reference engine)


def local_eval(fen, depth):
    import chess.engine
    global LOCAL
    if LOCAL is None:
        LOCAL = chess.engine.SimpleEngine.popen_uci('/usr/games/stockfish')
    info = LOCAL.analyse(chess.Board(fen), chess.engine.Limit(depth=depth))
    pv = info.get('pv') or [None]
    return {'cp': info['score'].white().score(mate_score=MATE),
            'best': pv[0].uci() if pv[0] else None, 'src': 'local'}


def evaluate(fen, cache, depth):
    """White's view centipawns of a position (mates clipped to +-10000)."""
    board = chess.Board(fen)
    if board.is_checkmate():
        return {'cp': -MATE if board.turn == chess.WHITE else MATE, 'best': None, 'src': 'rules'}
    if board.is_game_over(claim_draw=True):
        return {'cp': 0, 'best': None, 'src': 'rules'}
    key = ' '.join(fen.split()[:4])
    if LOCAL_MODE:
        return local_eval(fen, depth)
    if key not in cache:
        r = lichess(fen)
        if r is None:
            r = chess_api(fen, depth)
            time.sleep(0.5)
        if r is None:
            return None
        with cache_lock:
            cache[key] = r
            CACHE.write_text(json.dumps(cache))
    return cache[key]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('pgn')
    p.add_argument('--games', type=int, default=1000)
    p.add_argument('--depth', type=int, default=12)
    p.add_argument('--online', action='store_true', help='use the online engines')
    args = p.parse_args()
    global LOCAL_MODE
    LOCAL_MODE = not args.online
    cache = load_cache()
    # fetch all needed evaluations first, a few requests at a time
    fens = set()
    with open_text(args.pgn) as f:
        for gi in range(args.games):
            game = chess.pgn.read_game(f)
            if game is None:
                break
            ours_white = game.headers['White'].startswith('CX16')
            board = game.board()
            for ply, move in enumerate(game.mainline_moves()):
                if (board.turn == chess.WHITE) == ours_white and ply >= 4:
                    fens.add(board.fen())
                    board.push(move)
                    fens.add(board.fen())
                else:
                    board.push(move)
    print(f'{len(fens)} positions to evaluate', flush=True)
    if not LOCAL_MODE:
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda fen: evaluate(fen, cache, args.depth), sorted(fens)))
    losses, sources = [], {}
    blunders = mistakes = inaccuracies = best = 0
    with open_text(args.pgn) as f:
        for gi in range(args.games):
            game = chess.pgn.read_game(f)
            if game is None:
                break
            ours_white = game.headers['White'].startswith('CX16')
            board = game.board()
            game_losses = []
            for ply, move in enumerate(game.mainline_moves()):
                ours = (board.turn == chess.WHITE) == ours_white
                if ours and ply >= 4:                     # skip the fixed opening
                    before = evaluate(board.fen(), cache, args.depth)
                    san = board.san(move)
                    board.push(move)
                    after = evaluate(board.fen(), cache, args.depth)
                    if before and after:
                        sign = 1 if ours_white else -1
                        # clip so that already decided positions do not dominate
                        b = max(-1000, min(1000, sign * before['cp']))
                        a = max(-1000, min(1000, sign * after['cp']))
                        loss = max(0, b - a)
                        game_losses.append(loss)
                        sources[before['src']] = sources.get(before['src'], 0) + 1
                        best += before.get('best') == move.uci()
                        blunders += loss >= 300
                        mistakes += 100 <= loss < 300
                        inaccuracies += 50 <= loss < 100
                        if loss >= 300:
                            print(f"  game {gi + 1} move {ply // 2 + 1}: {san} loses {loss} cp "
                                  f"(best {before.get('best')})")
                else:
                    board.push(move)
            if game_losses:
                print(f"game {gi + 1}: {game.headers['White']} - {game.headers['Black']} "
                      f"{game.headers['Result']}: ACPL {sum(game_losses) / len(game_losses):.0f} "
                      f"over {len(game_losses)} moves", flush=True)
            losses += game_losses
    n = len(losses)
    if n:
        print(f'\n{n} moves reviewed (sources: {sources})')
        print(f'average centipawn loss: {sum(losses) / n:.0f}')
        print(f'same move as the reference engine: {100 * best / n:.0f}%')
        print(f'blunders (>=300 cp): {blunders}, mistakes (100-299): {mistakes}, '
              f'inaccuracies (50-99): {inaccuracies}')


if __name__ == '__main__':
    main()
