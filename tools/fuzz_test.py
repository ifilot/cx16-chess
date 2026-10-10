"""Fuzz tests: the X16 engine (assembly) on positions from random games.

  python3 tools/fuzz_test.py [positions]

1. Static evaluation and the set of legal moves must equal those of the
   native C reference build (tests/uci) and of python-chess.
2. The move validator (used for moves from the transposition table) must
   accept every pseudo-legal move with the generator's flags and reject
   random other moves.

Needs python-chess.
"""
import random
import subprocess
import sys

import chess

from engine_bridge import CMD_VALIDATE, ROOT, EngineBridge

def random_positions(n, seed):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        board = chess.Board()
        for _ in range(rng.randint(4, 120)):
            moves = list(board.legal_moves)
            if not moves:
                break
            # prefer captures now and then to reach endgames
            caps = [m for m in moves if board.is_capture(m)]
            board.push(rng.choice(caps if caps and rng.random() < 0.4 else moves))
        if not board.is_game_over():
            out.append(board.fen())
    return out

F_CAPTURE, F_EP, F_CASTLE, F_DOUBLE = 0x08, 0x10, 0x20, 0x40

def sq88(s):
    return (chess.square_rank(s) << 4) | chess.square_file(s)

def expected(board, move):
    fl = move.promotion or 0
    if board.is_castling(move):
        return F_CASTLE
    if board.is_en_passant(move):
        return F_CAPTURE | F_EP
    if board.is_capture(move):
        fl |= F_CAPTURE
    if board.piece_type_at(move.from_square) == chess.PAWN and \
            abs(move.to_square - move.from_square) == 16:
        fl |= F_DOUBLE
    return fl

def check_evaluation(eng, fens):
    cmds = ''.join(f'position fen {f}\neval\n' for f in fens) + 'quit\n'
    ref = [int(l.split()[1]) for l in subprocess.run([str(ROOT / 'tests/uci')], input=cmds,
           capture_output=True, text=True).stdout.splitlines() if l.startswith('eval')]
    bad = 0
    for fen, r in zip(fens, ref):
        e = eng.evaluate(fen)
        moves = sorted(set(eng.legal_moves(fen)))
        want = sorted(set(m.uci()[:4] for m in chess.Board(fen).legal_moves))
        if e != r or moves != want:
            bad += 1
            print('DIFF', fen, 'eval', e, r, 'moves', set(moves) ^ set(want))
    print(f'evaluation and move generation: {len(fens) - bad}/{len(fens)} positions identical')
    return bad

def check_validator(eng, fens):
    rng = random.Random(3)
    bad = checked = 0

    def validate(fen, f, t, p):
        eng.emu.write_memory(0x0500, bytes([f, t, p]))
        eng._run(CMD_VALIDATE, fen)
        return eng.emu.read_memory(0x0503)[0]

    for fen in fens:
        board = chess.Board(fen)
        pseudo = {}
        for m in board.pseudo_legal_moves:
            pseudo[(sq88(m.from_square), sq88(m.to_square), m.promotion or 0)] = expected(board, m)
        tests = list(pseudo.items())
        for _ in range(25):                   # random non-moves (and a few real ones)
            f, t = rng.randrange(128), rng.randrange(128)
            p = rng.choice([0, 0, 0, 2, 5])
            tests.append(((f, t, p), pseudo.get((f, t, p), 0xFF) if not ((f | t) & 0x88) else 0xFF))
        for (f, t, p), want in tests:
            got = validate(fen, f, t, p)
            checked += 1
            if got != want:
                bad += 1
                print(f'DIFF {fen} move {f:02x}-{t:02x} promo {p}: got {got:02x} want {want:02x}')
    print(f'move validator: {checked - bad}/{checked} correct')
    return bad

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    fens = random_positions(n, 1)
    with EngineBridge() as eng:
        bad = check_evaluation(eng, fens) + check_validator(eng, fens[:max(1, n // 3)])
    return bad

if __name__ == '__main__':
    sys.exit(1 if main() else 0)
