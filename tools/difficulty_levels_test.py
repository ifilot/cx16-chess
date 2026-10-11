"""Verify deep GUI searches, stack margin and new saved depth IDs on X16."""
from runtime_files import RUNTIME_FILES
import shutil
import tempfile
from pathlib import Path
from screenshot import ROOT, Session


def main():
    symbols = {p[2].lstrip('.'): int(p[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(p := line.split()) == 3}
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    for depth, level in ((7, 8), (8, 9)):
        with tempfile.TemporaryDirectory(prefix='chess-deep-ui-') as folder:
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
            try:
                session.emu.advance(480)
                keys('n', 'Right', 'Down', *(['Right'] * (depth - 5)))
                assert read('start_difficulty') == level
                session.emu.write_memory(0x05C0, bytes([0xA5]) * 32)
                breakpoint('engine_search')
                session.emu.request('key', key='Return', down=True)
                assert session.emu.advance(600)['reason'] == 'breakpoint'
                assert read('match_think_depth') == depth and read('match_think_budget', 2) == 0
                assert read('match_difficulty') == level
                session.emu.request('key', key='Return', down=False)
                breakpoint('engine_search', True)
                breakpoint('match_play')
                # Complete a real search using the GUI's smaller C stack and polling.
                for _ in range(240):
                    result = session.emu.advance(80_000_000, unit='cycles')
                    if result['reason'] == 'breakpoint':
                        break
                else:
                    raise AssertionError(f'{depth}-ply opening search did not finish within 40 emulated minutes')
                assert session.emu.read_memory(0x05C0, 32) == bytes([0xA5]) * 32
                breakpoint('match_play', True)
                session.emu.advance(120)
                assert read('ply', 2) == 1
                keys('Escape', 'Down', 'Return', '1', 'Return')
                data = (Path(folder) / 'CHESS1A.SAV').read_bytes()
                assert data[:8] == b'X16SAVE4' and data[17] == level
                keys('Escape', 'Down', 'Down', 'Return')
                for name, value in (('start_computer', 3), ('start_difficulty', 8), ('start_black_difficulty', 9)):
                    session.emu.write_memory(symbols['_' + name], bytes([value]))
                keys('o', 'Down', 'Down', 'Return')
                prefs = (Path(folder) / 'CHESSOPT.DAT').read_bytes()
                assert prefs[:5] == b'X16P4' and prefs[7:9] == bytes([3, 98])
                session.close()
                session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=folder)
                session.emu.advance(480)
                assert read('start_difficulty') == 8 and read('start_black_difficulty') == 9
                keys('l', '1')
                breakpoint('playfield_loaded')
                session.emu.request('key', key='Return', down=True)
                assert session.emu.advance(600)['reason'] == 'breakpoint'
                assert read('match_difficulty') == level and read('ply', 2) == 1
                # Black's setting must independently select the deeper search.
                session.emu.write_memory(symbols['_match_computer'], bytes([3]))
                session.emu.write_memory(symbols['_match_black_difficulty'], bytes([9]))
                breakpoint('playfield_loaded', True)
                breakpoint('engine_search')
                session.emu.request('key', key='Return', down=False)
                assert session.emu.advance(600)['reason'] == 'breakpoint'
                assert read('side') == 8 and read('match_think_depth') == 8, {n: read(n) for n in ('side', 'match_think_depth', 'match_computer', 'match_black_difficulty', 'match_difficulty')}
                print(f'PASS: {depth}-ply GUI search, stack guard, version-4 save/reload, independent black 8-ply dispatch', flush=True)
            finally:
                session.close()


if __name__ == '__main__':
    main()
