"""Verify passive mouse focus and keyboard coexistence in every menu layout."""
from runtime_files import RUNTIME_FILES
from pathlib import Path
import os
import shutil
import tempfile

from screenshot import ROOT, Session


def main():
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(line.split()) == 3}
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin',
                          ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-hover-') as folder:
        root = Path(folder)
        runtime = Path(os.environ.get('CHESS_FSROOT', ROOT / 'src'))
        for name in RUNTIME_FILES:
            shutil.copyfile(runtime / name, root / name)
        session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=root)

        def key(name):
            session.press(name)
            session.emu.advance(60)

        def hover(x, y):
            # A hover must never clear a panel or rebuild the board preview.
            forbidden = ('video_clear_block', 'video_clear_layer1', 'video_square', 'video_piece')
            for name in forbidden:
                session.emu.request('breakpoint', address=symbols['_' + name], bank=0)
            try:
                session.move_mouse(x, y)
                result = session.emu.advance(12)
                assert result['reason'] != 'breakpoint', ('hover redrew a panel', result)
            finally:
                for name in forbidden:
                    session.emu.request('breakpoint', action='remove', address=symbols['_' + name], bank=0)

        def text(col, row, expected, color):
            for half in range(2):
                data = bytes(session.emu.read_memory(
                    0x18000 + ((row + half) * 128 + col) * 2, len(expected) * 2, space='vram'))
                tiles = [data[i] | ((data[i + 1] & 3) << 8) for i in range(0, len(data), 2)]
                assert tiles == [(ord(c) - 32) * 2 + half for c in expected], (row, expected, tiles)
                assert all(v >> 4 == color for v in data[1::2]), (row, expected, 'focus color', data)

        def centered(cx, row, expected, color):
            text((cx - len(expected) * 4 + 4) // 8, row, expected, color)

        def read(name):
            return session.emu.read_memory(symbols['_' + name], 1)[0]

        try:
            session.emu.advance(480)
            hover(320, 408)
            text(36, 50, 'LOAD GAME', 7)
            text(36, 46, 'NEW GAME', 1)
            hover(320, 392)
            text(36, 48, 'CONTINUE', 10)
            text(36, 50, 'LOAD GAME', 7)
            key('Down')
            text(36, 52, 'OPTIONS', 7)
            session.emu.advance(120)
            text(36, 52, 'OPTIONS', 7)
            hover(320, 440)
            text(36, 54, 'ABOUT', 7)
            key('Return')
            hover(480, 408)
            centered(480, 51, 'BACK', 7)
            hover(639, 479)
            centered(480, 51, 'BACK', 1)
            key('Escape')
            key('n')
            difficulty = read('start_difficulty')
            hover(480, 232)
            centered(480, 29, 'STRONG (~1450 ELO)', 7)
            assert read('start_difficulty') == difficulty
            centered(480, 20, 'WHITE', 1)
            hover(400, 312)
            text(44, 39, 'START GAME', 7)
            key('Up')
            centered(480, 29, 'STRONG (~1450 ELO)', 7)
            hover(480, 160)
            key('Right')
            key('Right')
            hover(480, 296)
            centered(480, 37, 'STRONG (~1450 ELO)', 7)
            centered(480, 29, 'STRONG (~1450 ELO)', 1)
            assert read('start_black_difficulty') == difficulty
            hover(480, 160)
            key('Right')
            hover(480, 232)
            centered(480, 29, 'NOT USED', 10)
            key('Escape')
            key('o')
            theme, pieces = read('playfield_theme'), read('start_piece_set')
            hover(560, 232)
            text(61, 29, '\x80', 7)
            text(61, 20, '\x80', 1)
            assert (read('playfield_theme'), read('start_piece_set')) == (theme, pieces)
            hover(560, 344)
            centered(560, 42, 'SAVE PREFERENCES', 7)
            assert not (root / 'CHESSOPT.DAT').exists()
            hover(560, 376)
            centered(560, 46, 'DONE', 7)
            key('Escape')
            key('n')
            # The retained TWO PLAYERS selection starts a local match.
            key('Return')
            key('Escape')
            hover(304, 264)
            centered(304, 32, 'MAIN MENU', 7)
            centered(304, 22, 'RESUME GAME', 1)
            hover(304, 224)
            centered(304, 27, 'SAVE GAME', 7)
            key('Return')
            hover(304, 164)
            text(21, 20, '2', 7)
            text(21, 17, '1', 1)
            assert not list(root.glob('CHESS*.SAV'))
            hover(304, 392)
            centered(304, 48, 'BACK', 7)
            hover(639, 479)
            centered(304, 48, 'BACK', 1)
            key('1')
            key('Return')
            saves = {p.name: p.read_bytes() for p in root.iterdir()}
            key('Return')
            hover(304, 232)
            centered(304, 28, 'REPLACE', 7)
            centered(304, 23, 'CANCEL', 1)
            hover(304, 192)
            centered(304, 23, 'CANCEL', 7)
            assert {p.name: p.read_bytes() for p in root.iterdir()} == saves
            key('Escape')
            key('Escape')
            hover(304, 264)
            key('Return')
            key('l')
            hover(304, 188)
            text(21, 23, '3', 7)
            text(21, 17, '1', 1)
            session.shot(ROOT / 'build/hover/load-slots.png')
            print('PASS: every menu layout highlights on hover; values and saves stay unchanged; keyboard focus persists')
        finally:
            session.close()


if __name__ == '__main__':
    main()
