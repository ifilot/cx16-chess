"""Verify Options through real input, comparing every preview board pixel.

Also checks that appearance changes preserve a paused match and its clocks.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from screenshot import ROOT, Session

sys.path.insert(0, str(ROOT / 'assets/scripts'))
from build_graphics import load_indexed, square_image, blit, ASSETS
from palette import rgb
import layout as L

SETS = ['victorian', 'continental', 'letterpress']
BACK = [3, 1, 2, 4, 5, 2, 1, 3]


def expected_board(piece_set, theme):
    image = np.zeros((448, 448), np.uint8)
    sheet = load_indexed(ASSETS / f'pieces/{piece_set}.png')
    for row in range(8):
        for col in range(8):
            y, x = row * 56, col * 56
            image[y:y+56, x:x+56] = square_image(theme, (row + col) % 2 == 0, 'NORMAL')
            piece = BACK[col] + 6 if row == 0 else 6 if row == 1 else 0 if row == 6 else BACK[col] if row == 7 else None
            if piece is not None:
                blit(image, x, y, sheet[:, piece * 56:(piece + 1) * 56])
    return np.array([rgb(i) for i in range(16)], np.uint8)[image]


def main():
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(line.split()) == 3}
    rom = next(p for p in [ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin'] if p.exists())
    session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom)
    dest = ROOT / 'build/options'
    dest.mkdir(parents=True, exist_ok=True)

    def read(name, size=1):
        return bytes(session.emu.read_memory(symbols['_' + name], size))

    def visible():
        session.emu.advance(120)
        for _ in range(120):
            if session.emu.read_memory(0x9F29)[0] & 0x30 == 0x30:
                return
            session.emu.advance(10)
        raise AssertionError('View never became visible')

    try:
        session.emu.advance(480)
        clocks = read('match_clock', 4)
        session.click(320, 432)  # Opening screen OPTIONS, not New Game.
        visible()
        session.move_mouse(639, 479)
        for index, piece_set in enumerate(SETS):
            for board, theme in enumerate(L.BOARD_THEMES):
                assert read('start_piece_set') == bytes([index])
                assert read('playfield_theme') == bytes([board])
                path = dest / f'{piece_set}-{theme.lower()}.png'
                session.shot(path)
                image = Image.open(path).convert('RGB')
                assert image.size == (640, 480)
                assert set(image.getdata()) <= {rgb(i) for i in range(16)}
                np.testing.assert_array_equal(np.asarray(image)[8:456, 24:472], expected_board(piece_set, theme))
                session.press('Right')
                visible()
            session.press('Down')
            session.press('Right')
            visible()
            session.press('Up')
        assert read('match_clock', 4) == clocks, 'Preview must not run or start a match'
        assert read('ply', 2) == b'\0\0'
        # Left arrows wrap both selectors; mouse chooses Continental / crosshatch.
        session.press('Left')
        visible()
        assert read('playfield_theme') == b'\3'
        session.click(492, 168)
        visible()
        assert read('playfield_theme') == b'\2'
        session.press('Down')
        session.press('Left')
        visible()
        assert read('start_piece_set') == b'\2'
        session.click(492, 240)
        visible()
        assert read('start_piece_set') == b'\1'
        session.click(560, 320)  # DONE returns to the opening screen.
        visible()
        session.press('n')
        visible()
        session.press('Left')  # two-player game
        session.press('Return')
        visible()
        assert read('match_computer') == b'\0'
        session.shot(dest / 'continental-game.png')
        actual = np.asarray(Image.open(dest / 'continental-game.png').convert('RGB'))
        np.testing.assert_array_equal(actual[8:456, 24:472], expected_board('continental', 'CROSSHATCH'))
        session.click(276, 372)
        session.click(276, 260)  # e2-e4
        assert read('ply', 2) == b'\1\0'
        position = read('board', 128)
        session.press('m')
        visible()
        paused_clock = read('match_clock', 4)
        session.press('o')
        visible()
        session.click(628, 240)  # Continental -> Letterpress
        visible()
        session.click(628, 168)  # Crosshatch -> coarse hatch
        visible()
        session.emu.advance(300)
        assert read('board', 128) == position
        assert read('ply', 2) == b'\1\0'
        assert read('match_clock', 4) == paused_clock
        session.press('Escape')
        visible()
        session.press('c')
        visible()
        assert read('board', 128) == position
        assert read('start_piece_set') == b'\2'
        assert read('playfield_theme') == b'\3'
        session.shot(dest / 'letterpress-resumed.png')
        actual = np.asarray(Image.open(dest / 'letterpress-resumed.png').convert('RGB'))
        expected = expected_board('letterpress', 'COARSE')
        # Compare all unchanged squares; the moved pawn and highlighted cells
        # are covered by the normal game UI tests.
        mask = np.ones((448, 448), bool)
        mask[4*56:5*56, 4*56:5*56] = False  # e4
        mask[6*56:7*56, 4*56:5*56] = False  # e2
        np.testing.assert_array_equal(actual[8:456, 24:472][mask], expected[mask])
        print('PASS: 12 hardware previews, exact imported pixels, keyboard/mouse selectors and wraparound, new-game appearance, paused clocks/position, resume with changed appearance')
    finally:
        session.close()


if __name__ == '__main__':
    main()
