"""Exercise real menu, setup, clocks and board input in AgentBridge.

Run after make: python3 tools/ui_test.py
Screenshots are saved under build/ui/.
"""
from pathlib import Path
import sys

from PIL import Image
import numpy as np

from screenshot import ROOT, Session

sys.path.insert(0, str(ROOT / 'assets/scripts'))
from palette import rgb, RGB12, SPLASH_RGB12, SETUP_RGB12


def main():
    symbols = {}
    for line in (ROOT / 'src/CHESS.sym').read_text().splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2].lstrip('.')] = int(parts[1], 16)
    roms = [ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin']
    session = Session(ROOT.parent / 'x16-emulator/build/x16emu', next(r for r in roms if r.exists()))

    def read(name, size=1):
        return bytes(session.emu.read_memory(symbols['_' + name], size))

    def number(name):
        return int.from_bytes(read(name, 2), 'little')

    def shot(name):
        path = ROOT / 'build/ui' / (name + '.png')
        # Views remain hidden throughout loading and drawing. Wait for the
        # completed view rather than treating a fixed delay as a load budget.
        for _ in range(120):
            if session.emu.read_memory(0x9F29)[0] & 0x30 == 0x30:
                break
            session.emu.advance(10)
        else:
            raise AssertionError(f'{name}: view never became visible')
        # Keep the pointer outside artwork being compared, rather than
        # tolerating a generic pixel-error threshold that can hide defects.
        session.move_mouse(639, 479)
        session.shot(path)
        with Image.open(path) as im:
            assert im.size == (640, 480)
            colors = SPLASH_RGB12 if name in ('start', 'paused-start') else SETUP_RGB12 if name in ('setup', 'white-hard-setup', 'about', 'paused-about') else RGB12
            assert set(im.convert('RGB').getdata()) <= {rgb(i, colors) for i in range(16)}
            palette_data = bytes(session.emu.read_memory(0x1FA00, 32, space='vram'))
            assert list(np.frombuffer(palette_data, dtype='<u2')) == colors, f'{name}: wrong view palette'
            actual = np.asarray(im.convert('RGB'))
        if name in ('scorecard', 'selected', 'moves', 'flipped-newsprint', 'flipped-wood', 'black-easy', 'white-hard'):
            # Only eight file labels may occupy the strip below the board.
            mask = np.zeros((480, 640), dtype=bool)
            mask[458:, :480] = True
            mask[459, 20:476] = False  # outer newspaper frame
            mask[458, 20] = mask[458, 475] = False
            for file in range(8):
                mask[464:472, 48 + file * 56:56 + file * 56] = False
            assert np.all(actual[mask] == rgb(2)), f'{name}: unexpected board footer pixels'
            # The left margin contains only one rank label per square.
            mask[:] = False
            mask[:, :22] = True
            mask[4:460, 20] = False  # outer newspaper frame
            mask[4, 20:22] = False
            mask[459, 20:22] = False
            for rank in range(8):
                mask[32 + rank * 56:48 + rank * 56, 8:16] = False
            assert np.all(actual[mask] == rgb(2)), f'{name}: unexpected left margin pixels'
        if name in ('setup', 'white-hard-setup'):
            queen = actual[:, :320]
            neutral = {(0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255)}
            queen_colors = {tuple(c) for c in np.unique(queen.reshape(-1, 3), axis=0)}
            assert queen_colors - {rgb(2)} == neutral
            assert np.any(actual[-1, 100:220] != rgb(2)), 'Queen floats above bottom'
            for row, width in [(17, 7), (26, 14)]:
                header = actual[row * 8:(row + 2) * 8, 352:352 + width * 8]
                pixels = header[np.any(header != rgb(2), axis=2)]
                assert len(pixels) and np.all(pixels == rgb(7)), 'Setup header is not red'
        if name == 'scorecard':
            # Compare every board pixel against the approved Victorian study.
            with Image.open(ROOT / 'tests/fixtures/graphics/victorian-board-approved.png') as im:
                expected = np.asarray(im.convert('RGB'))
            np.testing.assert_array_equal(actual[8:456, 24:472], expected[8:456, 24:472])
            print('verified Victorian board and all starting pieces: zero pixel differences')
        artwork = 'splash' if name in ('start', 'paused-start') else 'setup' if name in ('setup', 'white-hard-setup') else 'about' if name in ('about', 'paused-about') else None
        if artwork:
            with Image.open(ROOT / 'build/graphics' / (artwork + '.png')) as im:
                expected = np.asarray(im.convert('RGB'))
            mask = np.zeros((480, 640), dtype=bool)
            if artwork == 'splash':
                mask[:368] = True
                with Image.open(ROOT / 'tests/fixtures/graphics/splash-approved.png') as im:
                    approved = np.asarray(im.convert('RGB'))
                np.testing.assert_array_equal(actual[:368], approved[:368])
            else:
                mask[:, :320] = True
                mask[:136] = True
            changed = mask & np.any(actual != expected, axis=2)
            assert not changed.any(), f'{name}: {int(changed.sum())} artwork pixels differ from exported preview'
            print(f'verified {name}: {int(mask.sum())} artwork pixels, zero differences')

    def keys(*names):
        for name in names:
            session.press(name)

    try:
        session.emu.advance(480)
        shot('start')
        initial = read('match_clock', 4)
        # Main-menu wrap includes About, skipping disabled Continue.
        keys('Up', 'Return')
        session.emu.advance(300)
        shot('about')
        assert read('match_clock', 4) == initial
        # Direction keys have no settings to change on this informational view.
        keys('Left', 'Right', 'Up', 'Down', 'Escape')
        session.emu.advance(300)
        session.click(320, 440)
        session.emu.advance(300)
        shot('about')
        session.click(480, 416)
        session.emu.advance(300)
        keys('a')
        session.emu.advance(300)
        shot('about')
        keys('Return')
        session.emu.advance(300)
        session.click(320, 392)  # Continue is disabled before the first game.
        session.emu.advance(120)
        assert read('match_clock', 4) == initial
        keys('Return')
        session.emu.advance(300)
        shot('setup')
        session.click(356, 168)  # left triangle: white -> two players
        # Disabled difficulty triangles must not alter the stored normal level.
        session.click(604, 240)
        keys('Down', 'Return')
        session.emu.advance(300)
        assert read('match_computer') == b'\x00'
        assert number('ply') == 0
        shot('scorecard')
        # e2-e4 via the new board geometry, followed by e7-e5.
        session.click(276, 372)
        shot('selected')
        assert number('ply') == 0
        session.click(276, 260)
        assert number('ply') == 1
        session.click(276, 92)
        session.click(276, 204)
        assert number('ply') == 2
        position = read('board', 128)
        shot('moves')
        keys('m')
        session.emu.advance(300)
        paused = read('match_clock', 4)
        shot('paused-start')
        paused_clock = read('match_clock', 4)
        paused_ply = number('ply')
        keys('a')
        session.emu.advance(300)
        shot('paused-about')
        assert read('match_clock', 4) == paused_clock
        assert number('ply') == paused_ply
        keys('space')
        session.emu.advance(300)
        session.emu.advance(600)
        assert read('match_clock', 4) == paused, 'Menu must pause both clocks'
        keys('c')
        session.emu.advance(300)
        assert read('board', 128) == position
        assert number('ply') == 2
        resumed = read('match_clock', 4)
        assert int.from_bytes(resumed[:2], 'little') >= int.from_bytes(paused[:2], 'little') - 6
        keys('f', 't', 'i', 'i')
        shot('flipped-wood')
        keys('t', 't', 't')
        shot('flipped-newsprint')
        # In-game New Game opens setup rather than clearing the match.
        keys('n')
        session.emu.advance(300)
        assert read('board', 128) == position
        keys('Escape')
        session.emu.advance(300)
        keys('c')
        session.emu.advance(300)
        assert read('board', 128) == position
        # Choose black and easy: the CPU must play the first white move.
        keys('n')
        session.emu.advance(300)
        keys('Left', 'Left', 'Down', 'Left', 'Down', 'Return')
        session.emu.advance(480)
        assert read('match_computer') == b'\x01'
        assert read('match_difficulty') == b'\x00'
        assert number('ply') >= 1
        assert int.from_bytes(read('match_clock', 4)[:2], 'little') >= 1797, 'Easy must limit CPU thinking to about two seconds'
        shot('black-easy')
        # Configure hard and white using mouse input; setup changes only
        # the next match, so cancelling must preserve the live difficulty.
        keys('n')
        session.emu.advance(300)
        session.click(604, 168)  # black -> computer versus computer
        session.click(604, 168)  # computer versus computer -> two players
        session.click(604, 168)  # two players -> white
        session.click(604, 240)  # easy -> normal
        session.click(604, 240)  # normal -> hard
        session.click(356, 240)  # left triangle: hard -> normal
        session.click(604, 240)  # restore hard with right triangle
        assert read('match_difficulty') == b'\x00'
        shot('white-hard-setup')
        session.click(460, 320)
        session.emu.advance(300)
        assert read('match_computer') == b'\x02'
        assert read('match_difficulty') == b'\x02'
        assert number('ply') == 0
        shot('white-hard')
        print('PASS: menu/setup/about, disabled Continue, all sides and difficulties, keyboard/mouse, moves, pause/resume, flip/theme, 640x480 and palette')
    finally:
        session.close()


if __name__ == '__main__':
    main()
