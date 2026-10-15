"""Verify independent demo levels, automatic turns, pause and persistence."""
from runtime_files import RUNTIME_FILES
import shutil
import tempfile
from pathlib import Path
from screenshot import ROOT, Session


def main():
    symbols = {}
    for line in (ROOT / 'src/CHESS.sym').read_text().splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2].lstrip('.')] = int(fields[1], 16)
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-demo-') as folder:
        for filename in RUNTIME_FILES:
            shutil.copyfile(ROOT / 'src' / filename, Path(folder) / filename)
        session = None
        def boot():
            nonlocal session
            if session:
                session.close()
            session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=folder)
            session.emu.advance(480)
        def read(name, size=1):
            return int.from_bytes(session.emu.read_memory(symbols['_' + name], size), 'little')
        def keys(*names):
            for name in names:
                session.press(name)
                session.emu.advance(120)
        def shot(name):
            session.move_mouse(639, 479)
            session.shot(ROOT / 'build/demo' / (name + '.png'))
        try:
            boot()
            keys('n', 'Right', 'Right', 'Down', 'Left', 'Left', 'Left', 'Right', 'Down', 'Right')
            assert read('start_difficulty') == 0 and read('start_black_difficulty') == 4
            # Both difficulty rows support mouse input independently.
            session.click(356, 296)  # black Deep -> Strong
            session.click(604, 296)  # black Strong -> Deep
            session.click(604, 240)  # white 2 -> 3 ply
            session.click(356, 240)  # white 3 -> 2 ply
            shot('setup')
            # Stop at each search entry to inspect the actual allocated budget.
            address = symbols['_engine_search']
            session.emu.request('breakpoint', address=address, bank=0)
            session.emu.request('key', key='Return', down=True)
            result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint', result
            assert read('match_computer') == 3 and read('side') == 0
            assert read('match_difficulty') == 0 and read('match_black_difficulty') == 4
            assert read('match_think_budget', 2) == 0 and read('match_think_depth') == 2
            session.emu.request('key', key='Return', down=False)
            session.emu.request('breakpoint', action='remove', address=address, bank=0)
            session.emu.advance(1)
            session.emu.request('breakpoint', address=address, bank=0)
            result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint', result
            assert read('side') == 8 and read('ply', 2) == 1, (read('side'), read('ply', 2))
            assert read('match_think_budget', 2) == 0 and read('match_think_depth') == 6
            session.emu.request('breakpoint', action='remove', address=address, bank=0)
            session.emu.advance(5)
            # Escape interrupts a hard search promptly, then freezes the demo.
            keys('Escape')
            frozen = (read('ply', 2), read('match_clock', 4))
            assert frozen[0] >= 2
            session.emu.advance(600)
            assert (read('ply', 2), read('match_clock', 4)) == frozen
            shot('paused')
            keys('Down', 'Return', '1', 'Return')
            data = (Path(folder) / 'CHESS1A.SAV').read_bytes()
            assert data[16] == 3 and data[17] == 0 and data[25] == 4
            shot('saved')
            keys('Escape', 'Down', 'Down', 'Return', 'o', 'Down', 'Down', 'Down', 'Down', 'Return')
            assert (Path(folder) / 'CHESSOPT.DAT').read_bytes()[7:9] == bytes((3, 40))
            boot()
            assert read('start_computer') == 3
            assert read('start_difficulty') == 0 and read('start_black_difficulty') == 4
            keys('n')
            shot('restored-setup')
            keys('Escape', 'l')
            address = symbols['_playfield_loaded']
            session.emu.request('breakpoint', address=address, bank=0)
            session.emu.request('key', key='Return', down=True)
            result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint', result
            assert read('match_computer') == 3
            assert read('match_difficulty') == 0 and read('match_black_difficulty') == 4
            assert read('ply', 2) == frozen[0]
            session.emu.request('breakpoint', action='remove', address=address, bank=0)
            session.emu.request('key', key='Return', down=False)
            session.emu.advance(900)
            assert read('ply', 2) > frozen[0], 'Loaded demo must continue automatically'
            keys('Escape')
            print('PASS: demo keyboard/mouse levels, independent 2/6-ply searches and no move time caps, automatic turns, responsive Escape, pause, saved levels and preferences, restart and automatic resume')
        finally:
            if session:
                session.close()


if __name__ == '__main__':
    main()
