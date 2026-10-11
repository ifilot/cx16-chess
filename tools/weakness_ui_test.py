"""Verify weak menu order, actual root noise, analysis reset and golden RAM stack margin."""
from runtime_files import RUNTIME_FILES
import shutil
import tempfile
from pathlib import Path
from screenshot import ROOT, Session


def main():
    symbols = {p[2].lstrip('.'): int(p[1], 16) for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(p := line.split()) == 3}
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-weak-ui-') as folder:
        for name in RUNTIME_FILES:
            shutil.copyfile(ROOT / 'src' / name, Path(folder) / name)
        session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=folder)
        def read(name, size=1):
            return int.from_bytes(session.emu.read_memory(symbols['_' + name], size), 'little')
        def keys(*names):
            for name in names:
                session.press(name)
                session.emu.advance(120)
        def breakpoint(name, remove=False):
            session.emu.request('breakpoint', address=symbols['_' + name], bank=0,
                                **({'action': 'remove'} if remove else {}))
        def noise():
            sp = int.from_bytes(session.emu.read_memory(symbols['sp'], 2), 'little')
            return int.from_bytes(session.emu.read_memory(sp, 2), 'little')
        try:
            session.emu.advance(480)
            # 4 -> 3 -> 2 -> 1 -> Easy -> Beginner; wrap to 8 and back.
            keys('n', 'Right', 'Down', 'Left', 'Left', 'Left', 'Left', 'Left')
            assert read('start_difficulty') == 7
            keys('Left'); assert read('start_difficulty') == 9
            keys('Right'); assert read('start_difficulty') == 7
            session.move_mouse(639, 479)
            session.shot(ROOT / 'build/weakness/beginner-setup.png')
            session.emu.write_memory(0x05C0, bytes([0xA5]) * 32)
            breakpoint('engine_set_weakness')
            session.emu.request('key', key='Return', down=True)
            stopped = session.emu.advance(600)
            assert stopped['reason'] == 'breakpoint'
            assert noise() == 0  # initial game seed
            breakpoint('engine_set_weakness', True)
            session.emu.advance(1, unit='instructions')
            breakpoint('engine_set_weakness')
            stopped = session.emu.advance(600)
            assert stopped['reason'] == 'breakpoint'
            assert noise() == 350
            breakpoint('engine_set_weakness', True)
            breakpoint('engine_search')
            assert session.emu.advance(600)['reason'] == 'breakpoint'
            assert read('match_think_depth') == 1 and read('match_think_budget', 2) == 0
            breakpoint('engine_search', True)
            session.emu.request('key', key='Return', down=False)
            session.emu.advance(180)
            assert read('match_difficulty') == 7 and read('ply', 2) == 1
            assert session.emu.read_memory(0x05C0, 32) == bytes([0xA5]) * 32
            # Analysis must remove weakening before searching.
            breakpoint('engine_set_weakness')
            session.emu.request('key', key='a', down=True)
            assert session.emu.advance(600)['reason'] == 'breakpoint'
            assert noise() == 0
            session.emu.request('key', key='a', down=False)
            breakpoint('engine_set_weakness', True)
            session.emu.advance(900)
            keys('Escape', 'Down', 'Return', '1', 'Return')
            data = (Path(folder) / 'CHESS1A.SAV').read_bytes()
            assert data[:8] == b'X16SAVE4' and data[17] == 7
            tiles = session.emu.read_memory(0x18000 + (17 * 128 + 26) * 2, 12, space='vram')
            assert list(tiles[::2]) == [(ord(c) - 32) * 2 for c in 'BEGIN.']
            session.move_mouse(639, 479)
            session.shot(ROOT / 'build/weakness/beginner-save.png')
            assert session.emu.read_memory(0x05C0, 32) == bytes([0xA5]) * 32
            print('PASS: weak menu order, 350cp noise at search, 1-ply uncapped search, strong analysis, weak save and golden RAM stack guard')
        finally:
            session.close()


if __name__ == '__main__':
    main()
