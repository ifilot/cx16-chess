"""Statistical profiler for ENGINE.PRG running in the AgentBridge emulator.

Starts a search, then repeatedly advances the emulated CPU by a prime number
of cycles and records the program counter. Samples are attributed to the
nearest preceding symbol of src/ENGINE.sym (C functions appear as _name,
cc65 runtime helpers by their own names).

  python3 tools/profile_engine.py [FEN] [--depth 4]
"""
import argparse
import bisect
import collections
import struct

from engine_bridge import CMD_SEARCH, DONE, ERROR, MAILBOX, ROOT, EngineBridge, BUSY

KIWIPETE = 'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R b KQkq - 0 5'


def load_symbols(path):
    symbols = []
    for line in open(path):
        parts = line.split()
        if len(parts) == 3 and parts[0] == 'al':
            name = parts[2].lstrip('.')
            if name.startswith('__') or name.startswith('L'):
                continue
            symbols.append((int(parts[1], 16), name))
    symbols.sort()
    return [a for a, _ in symbols], [n for _, n in symbols]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('fen', nargs='?', default=KIWIPETE)
    parser.add_argument('--depth', type=int, default=3)
    parser.add_argument('--step', type=int, default=997)
    args = parser.parse_args()
    addresses, names = load_symbols(ROOT / 'src/ENGINE.sym')

    counts = collections.Counter()
    with EngineBridge() as eng:
        emu = eng.emu
        emu.write_memory(MAILBOX + 0x80, args.fen.encode() + b'\0')
        emu.write_memory(MAILBOX + 2, bytes([args.depth, 0]) + struct.pack('<H', 0))
        emu.write_memory(MAILBOX + 1, bytes([BUSY]))
        emu.write_memory(MAILBOX, bytes([CMD_SEARCH]))
        samples = 0
        while True:
            for _ in range(200):
                emu.advance(args.step, unit='cycles')
                pc = emu.request('status')['pc']
                i = bisect.bisect_right(addresses, pc) - 1
                counts[names[i] if i >= 0 and pc < 0x9F00 else f'${pc:04X}'] += 1
                samples += 1
            if emu.read_memory(MAILBOX + 1)[0] in (DONE, ERROR):
                break
    total = sum(counts.values())
    print(f'{total} samples')
    for name, n in counts.most_common(30):
        print(f'{100.0 * n / total:6.2f}%  {name}')


if __name__ == '__main__':
    main()
