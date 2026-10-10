"""Check that the X16 engine (assembly) matches the native reference (C).

Compares perft counts, static evaluations and complete fixed-depth searches
(nodes, best move, score) between ENGINE.PRG in the emulator and the native
tests/uci build. Any difference means engine_asm.s and engine_hot.c disagree.
"""
import subprocess
import sys

from engine_bridge import ROOT, EngineBridge

POSITIONS = [
    'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',
    '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',
    'r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1',
    'rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8',
    'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R b KQkq - 0 5',
    '8/5pk1/6p1/3R4/1r5P/6P1/5PK1/8 w - - 0 40',
    '8/8/8/4k3/8/8/2Q5/4K3 w - - 0 1',            # mop-up
    '8/8/3k4/8/8/2K5/8/7r b - - 0 1',              # mop-up for black
    '4k3/pp3ppp/8/2P5/1P6/8/P4PPP/4K3 w - - 0 1',  # passed/isolated pawns
    'r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/R3KB1R w KQ - 2 9',
]


def native(commands):
    out = subprocess.run([str(ROOT / 'tests/uci')], input='\n'.join(commands) + '\nquit\n',
                         capture_output=True, text=True).stdout
    return out


def main():
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    failures = 0
    with EngineBridge() as eng:
        for fen in POSITIONS:
            ref = native([f'position fen {fen}', 'eval', 'perft 2', 'ucinewgame',
                          f'position fen {fen}', f'go depth {depth}'])
            ref_eval = int(ref.split('eval ')[1].split()[0])
            ref_perft = int(ref.split('nodes ')[1].split()[0])
            info = [l for l in ref.splitlines() if l.startswith('info')][0].split()
            ref_nodes = int(info[info.index('nodes') + 1])
            ref_score = int(info[info.index('cp') + 1])
            ref_move = ref.split('bestmove ')[1].split()[0]

            x_eval = eng.evaluate(fen)
            x_perft = eng.perft(fen, 2)['nodes']
            r = eng.search(fen, depth=depth, fresh=True)
            same = (x_eval, x_perft, r['nodes'], r['score'], r['move']) == \
                   (ref_eval, ref_perft, ref_nodes, ref_score, ref_move)
            failures += not same
            print(f"{'ok  ' if same else 'FAIL'} eval {x_eval:5d}/{ref_eval:5d} perft {x_perft}/{ref_perft} "
                  f"d{depth} {r['move']}/{ref_move} {r['score']}/{ref_score} nodes {r['nodes']}/{ref_nodes} "
                  f"{r['seconds']:6.1f}s {r['nps']:5.0f} nps")
    print('all identical' if not failures else f'{failures} DIFFERENCES')
    return failures


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
