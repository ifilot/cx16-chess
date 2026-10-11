"""Drive ENGINE.PRG inside the X16 AgentBridge emulator.

The engine runs on the emulated 65C02 exactly as it would on hardware; the
host only writes positions into the $0400 mailbox (see src/bridge/bridge.h)
and reads back results. Timing is measured in emulated CPU cycles (8 MHz).

    with EngineBridge() as eng:
        print(eng.perft('startpos', 3))
        print(eng.search(fen, time_limit=10.0))
"""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'x16-emulator/api/python'))
from x16agent import X16Agent  # noqa: E402

MAILBOX = 0x0400
CMD_PERFT, CMD_SEARCH, CMD_EVAL, CMD_LIST, CMD_VALIDATE = 1, 2, 3, 4, 5
READY, BUSY, DONE, ERROR = 1, 2, 3, 4
STARTPOS = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
CPU_HZ = 8_000_000
FILES = 'abcdefgh'
PROMO = {0: '', 2: 'n', 3: 'b', 4: 'r', 5: 'q'}


def square_name(sq):
    return FILES[sq & 7] + str((sq >> 4) + 1)


def default_rom():
    roms = [ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin']
    return next((r for r in roms if r.exists()), roms[0])


class EngineBridge:
    def __init__(self, emu=None, rom=None, prg=ROOT / 'src/ENGINE.PRG'):
        emu = emu or ROOT.parent / 'x16-emulator/build/x16emu'
        # A runtime AUTOBOOT.X16 would launch the GUI before the headless PRG.
        # The harness needs no disk assets, so give it an empty boot directory.
        self._boot_directory = tempfile.TemporaryDirectory(prefix='chess-engine-')
        self.emu = X16Agent(emu, rom or default_rom(), fsroot=self._boot_directory.name,
                            options=['-prg', str(prg), '-run'], timeout=600)
        for _ in range(100):
            self.emu.advance(10)
            if self.emu.read_memory(MAILBOX + 1)[0] == READY:
                break
        else:
            self.close()
            raise RuntimeError('ENGINE.PRG did not start')

    def close(self):
        self.emu.close()
        self._boot_directory.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _run(self, cmd, fen, depth=0, time_limit=0.0, fresh=False, moves=(), max_seconds=3600, noise=0, seed=1):
        fen = STARTPOS if fen == 'startpos' else fen
        data = fen.encode('ascii')[:127] + b'\0'
        self.emu.write_memory(MAILBOX + 0x80, data)
        hist = bytes([len(moves)]) + b''.join(bytes(m) for m in moves)
        self.emu.write_memory(0x0600, hist)
        self.emu.write_memory(MAILBOX + 2, bytes([depth, 1 if fresh else 0]) +
                              struct.pack('<H', min(65535, round(time_limit * 60))))
        self.emu.write_memory(MAILBOX + 1, bytes([BUSY]))
        self.emu.write_memory(MAILBOX + 0x14, struct.pack('<HH', noise, seed))
        start = self.emu.request('status')['cycles']
        self.emu.write_memory(MAILBOX, bytes([cmd]))
        step = 2_000_000                                   # 1/4 emulated second
        while True:
            result = self.emu.advance(step, unit='cycles')
            status = self.emu.read_memory(MAILBOX + 1)[0]
            if status in (DONE, ERROR):
                break
            if result['state']['cycles'] - start > max_seconds * CPU_HZ:
                raise TimeoutError('engine did not finish')
        cycles = result['state']['cycles'] - start
        if status == ERROR:
            raise ValueError(f'engine rejected command {cmd} for {fen}')
        raw = self.emu.read_memory(MAILBOX, 0x40)
        nodes, = struct.unpack_from('<I', raw, 8)
        frm, to, promo, depth_done = raw[12:16]
        score, jiffies = struct.unpack_from('<hH', raw, 16)
        pv_raw = self.emu.read_memory(MAILBOX + 0x20, 32)
        pv = []
        for i in range(0, 32, 2):
            if pv_raw[i] & 0x88 or pv_raw[i] == pv_raw[i + 1]:
                break
            pv.append(square_name(pv_raw[i]) + square_name(pv_raw[i + 1]))
        return {
            'replayed': raw[6],
            'illegal': raw[7],
            'nodes': nodes,
            'move': square_name(frm) + square_name(to) + PROMO.get(promo, '') if frm != to else None,
            'depth': depth_done,
            'score': score,
            'jiffies': jiffies,
            'pv': pv,
            'seconds': cycles / CPU_HZ,
            'nps': nodes / max(1e-9, cycles / CPU_HZ),
        }

    def perft(self, fen, depth):
        return self._run(CMD_PERFT, fen, depth=depth)

    def search(self, fen, depth=0, time_limit=0.0, fresh=False, moves=(), noise=0, seed=1):
        """Search fen (after playing moves: (from, to, promo) 0x88 triples)."""
        return self._run(CMD_SEARCH, fen, depth=depth, time_limit=time_limit, fresh=fresh,
                         moves=moves, noise=noise, seed=seed)

    def legal_moves(self, fen):
        self._run(CMD_LIST, fen)
        n = self.emu.read_memory(0x0500)[0]
        raw = self.emu.read_memory(0x0501, 2 * n) if n else b''
        return [square_name(raw[i]) + square_name(raw[i + 1]) for i in range(0, 2 * n, 2)]

    def evaluate(self, fen):
        return self._run(CMD_EVAL, fen)['score']


if __name__ == '__main__':
    with EngineBridge() as eng:
        for d in (1, 2, 3):
            r = eng.perft('startpos', d)
            print(f"perft({d}) = {r['nodes']:7d}  {r['seconds']:8.2f} s  {r['nps']:7.0f} nodes/s")
