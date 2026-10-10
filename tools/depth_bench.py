"""How deep does the X16 engine search within a time limit?"""
import sys

from engine_bridge import EngineBridge

POSITIONS = {
    'opening':    'rnbqkb1r/pppp1ppp/5n2/4p3/4P3/2N5/PPPP1PPP/R1BQKBNR w KQkq - 2 3',
    'italian':    'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R b KQkq - 0 5',
    'sicilian':   'r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/R3KB1R w KQ - 2 9',
    'qgd':        'r1bq1rk1/pp1nbppp/2p1pn2/3p2B1/2PP4/2NBPN2/PP3PPP/R2QK2R w KQ - 0 8',
    'kiwipete':   'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',
    'middlegame': 'r2q1rk1/1b2bppp/p2ppn2/1p6/3NP3/1BN1B3/PPP2PPP/R2Q1RK1 w - - 0 12',
    'rook_end':   '8/5pk1/6p1/3R4/1r5P/6P1/5PK1/8 w - - 0 40',
    'pawn_end':   '8/2k5/3p4/p2P1p2/P2P1P2/8/3K4/8 w - - 0 50',
}


def main():
    limits = [float(x) for x in sys.argv[1:]] or [5, 10, 30]
    print(f"{'position':12s}" + ''.join(f'  {int(t):>3d}s: depth  nodes   nps' for t in limits))
    with EngineBridge() as eng:
        for name, fen in POSITIONS.items():
            row = f'{name:12s}'
            for t in limits:
                eng.search(fen, depth=1, fresh=True)          # clear tables first
                r = eng.search(fen, time_limit=t)
                row += f"  {r['move']:>6s}  {r['depth']:2d}  {r['nodes']:6d} {r['nps']:5.0f}"
            print(row, flush=True)


if __name__ == '__main__':
    main()
