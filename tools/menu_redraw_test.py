"""Catch transient menu clears and unnecessary preview redraws in AgentBridge."""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import tempfile

from screenshot import ROOT, Session


def main():
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(line.split()) == 3}
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    runtime = Path(os.environ.get('CHESS_FSROOT', ROOT / 'src'))
    with tempfile.TemporaryDirectory(prefix='chess-menu-redraw-') as folder:
        for name in ('CHESS.PRG', 'MENU.BIN', 'UI.BIN', 'CHESS.DAT'):
            shutil.copyfile(runtime / name, Path(folder) / name)
        session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=folder)

        @contextmanager
        def guard(background=False, pieces=False, assets=False):
            forbidden = [('video_clear_block', 0), ('video_clear_layer1', 0)]
            if not background:
                forbidden.append(('video_square', 0))
            if not pieces:
                forbidden.append(('video_piece', 0))
            if not assets:
                forbidden.append(('asset_prepare', 21))
            for name, bank in forbidden:
                session.emu.request('breakpoint', address=symbols['_' + name], bank=bank)
            try:
                yield
            finally:
                for name, bank in forbidden:
                    session.emu.request('breakpoint', action='remove', address=symbols['_' + name], bank=bank)

        def advance(frames=3):
            result = session.emu.advance(frames)
            assert result['reason'] != 'breakpoint', ('unnecessary clear/redraw during input', result)

        def key(name):
            session.emu.request('key', key=name, down=True)
            advance()
            session.emu.request('key', key=name, down=False)
            advance(30)

        def click(x, y):
            session.move_mouse(x, y)
            session.emu.request('mouse', buttons=1)
            advance()
            session.emu.request('mouse', buttons=0)
            advance(30)

        def text(col, row, expected, color=None):
            data = bytes(session.emu.read_memory(0x18000 + (row * 128 + col) * 2,
                                                 len(expected) * 2, space='vram'))
            assert [data[i] | ((data[i + 1] & 3) << 8) for i in range(0, len(data), 2)] == [(ord(c) - 32) * 2 for c in expected], (col, row, expected, data)
            if color is not None:
                assert all(v >> 4 == color for v in data[1::2]), (row, expected, 'wrong focus color')

        def centered(row, expected, color=None, cx=480):
            text((cx - len(expected) * 4 + 4) // 8, row, expected, color)

        try:
            session.emu.advance(480)
            with guard():
                key('Down'); text(36, 50, 'LOAD GAME', 7)
                key('Up'); text(36, 46, 'NEW GAME', 7)
                key('Up'); text(36, 54, 'ABOUT', 7)
                key('Down'); text(36, 46, 'NEW GAME', 7)
            key('n'); session.emu.advance(120)
            with guard():
                key('Up'); text(44, 39, 'START GAME', 7)
                key('Down'); text(44, 39, 'START GAME', 1)
                key('Right'); centered(20, 'BLACK')
                key('Down'); key('Right'); centered(29, 'HARD')
                key('Left'); key('Left'); centered(29, 'EASY')
                text(44, 32, '2 SEC / MOVE' + ' ' * 2)
                key('Up'); key('Right'); centered(20, 'CPU VS CPU')
                text(44, 26, 'WHITE CPU' + ' ' * 5)
                text(44, 34, 'BLACK CPU')
                key('Down'); key('Down'); key('Right'); centered(37, 'HARD')
                key('Down'); text(44, 41, 'START GAME', 7)
                click(604, 168); centered(20, 'TWO PLAYERS')
                centered(29, 'NOT USED', 10)
                for row in (34, 37, 41):
                    text(42, row, ' ' * 34)
                text(44, 32, 'LOCAL TWO PLAYER')
                click(604, 240); centered(29, 'NOT USED', 10)
                key('Left'); centered(29, 'NOT USED', 10)
                key('Up'); key('Left'); centered(20, 'CPU VS CPU')
                key('Left'); centered(20, 'BLACK')
                text(44, 26, 'CPU DIFFICULTY')
            key('Escape'); session.emu.advance(120)
            key('o'); session.emu.advance(120)
            with guard():
                key('Down'); key('Up')
            with guard(background=True):
                key('Right'); centered(20, 'WOOD', cx=560)
            with guard():
                key('Down')
            with guard(pieces=True, assets=True):
                key('Right'); centered(29, 'CONTINENTAL', cx=560)
            with guard():
                key('Down'); key('Return')
                centered(42, 'PREFERENCES SAVED', 7, cx=560)
                key('Up'); key('Down')
            key('Escape'); session.emu.advance(120)
            key('n'); session.emu.advance(120)
            key('Right'); key('Right')  # Black -> CPU/CPU -> local
            key('Return'); session.emu.advance(120)
            before = bytes(session.emu.read_memory(symbols['_match_clock'], 4))
            with guard():
                advance(180)
            after = bytes(session.emu.read_memory(symbols['_match_clock'], 4))
            assert before != after, 'Clock did not tick during redraw guard'
            print('PASS: main menu, all New Game layouts, shorter values, keyboard/mouse focus, disabled CPU, Options selectors/preferences, preview layers, and live clocks avoid transient clears')
        finally:
            session.close()


if __name__ == '__main__':
    main()
