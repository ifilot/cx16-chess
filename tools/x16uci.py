"""The emulated X16 engine as a python-chess player (and a tiny UCI wrapper).

    from x16uci import X16Engine
    eng = X16Engine(time_per_move=10)       # emulated seconds on the X16
    move = eng.play(board)

Run as a script it speaks UCI on stdin/stdout, so GUIs and match tools can
use the real X16 binary as an engine:  python3 tools/x16uci.py
"""
import sys
from pathlib import Path

import chess

from engine_bridge import EngineBridge

PROMO = {chess.KNIGHT: 2, chess.BISHOP: 3, chess.ROOK: 4, chess.QUEEN: 5}


def sq88(square):
    return (chess.square_rank(square) << 4) | chess.square_file(square)


class X16Engine:
    def __init__(self, time_per_move=10.0, depth=0):
        self.bridge = EngineBridge()
        self.time_per_move = time_per_move
        self.depth = depth
        self.last = None
        self.fresh = True

    def new_game(self):
        self.fresh = True

    def play(self, board):
        """Best move for board; the game since the last capture or pawn move
        is passed along so the engine sees repetitions."""
        base = board.copy()
        moves = []
        for _ in range(min(board.halfmove_clock, len(board.move_stack), 85)):
            m = base.pop()
            moves.append((sq88(m.from_square), sq88(m.to_square), PROMO.get(m.promotion, 0)))
        moves.reverse()
        self.last = self.bridge.search(base.fen(), depth=self.depth, time_limit=self.time_per_move,
                                       fresh=self.fresh, moves=moves)
        self.fresh = False
        if self.last['replayed'] != len(moves):
            raise RuntimeError(f'X16 replayed {self.last["replayed"]} of {len(moves)} moves '
                               f'from {base.fen()}: {moves}')
        move = chess.Move.from_uci(self.last['move'])
        if move not in board.legal_moves or self.last['illegal']:
            dump = self.bridge.emu.read_memory(0x0700, 256)
            names = '.PNBRQK..pnbrqk.'
            def show(b):
                return '/'.join(''.join(names[b[r * 16 + f]] for f in range(8)) for r in range(7, -1, -1))
            dump_file = Path(__file__).resolve().parents[1] / 'build/illegal_dump.txt'
            dump_file.parent.mkdir(exist_ok=True)
            with open(dump_file, 'a') as f:
                f.write(f'final {board.fen()}\nbase {base.fen()}\nmoves {moves}\n'
                        f'result {self.last}\nengine {show(dump[:128])}\nrules  {show(dump[128:])}\n'
                        f'game {[m.uci() for m in board.move_stack]}\n\n')
            raise RuntimeError(f'X16 engine returned illegal move {move} in {board.fen()}')
        return move

    def quit(self):
        self.bridge.close()


def uci_loop():
    board = chess.Board()
    engine = None
    movetime = 10.0
    for line in sys.stdin:
        cmd = line.split()
        if not cmd:
            continue
        if cmd[0] == 'uci':
            print('id name CX16-CHESS (X16 emulated)\nid author Ivo Filot\n'
                  'option name MoveTime type spin default 10 min 1 max 600\nuciok', flush=True)
        elif cmd[0] == 'isready':
            engine = engine or X16Engine(movetime)
            print('readyok', flush=True)
        elif cmd[:4] == ['setoption', 'name', 'MoveTime', 'value']:
            movetime = float(cmd[4])
            if engine:
                engine.time_per_move = movetime
        elif cmd[0] == 'ucinewgame':
            engine and engine.new_game()
        elif cmd[0] == 'position':
            if cmd[1] == 'startpos':
                board = chess.Board()
                rest = cmd[2:]
            else:
                board = chess.Board(' '.join(cmd[2:8]))
                rest = cmd[8:]
            if rest and rest[0] == 'moves':
                for m in rest[1:]:
                    board.push_uci(m)
        elif cmd[0] == 'go':
            engine = engine or X16Engine(movetime)
            move = engine.play(board)
            r = engine.last
            print(f"info depth {r['depth']} score cp {r['score']} nodes {r['nodes']} "
                  f"pv {' '.join(r['pv'])}\nbestmove {move.uci()}", flush=True)
        elif cmd[0] == 'quit':
            break
    if engine:
        engine.quit()


if __name__ == '__main__':
    uci_loop()
