"""Exercise native 16x16 figurines with SAN rendering fixtures in the emulator.

The fixtures cover every piece, captures, disambiguation, castling, promotions
and check/mate marks. They replace only the score sheet in an isolated process.
"""
import sys

import numpy as np
from PIL import Image

from screenshot import ROOT, Session

sys.path.insert(0, str(ROOT / 'assets/scripts'))
from bitmap_font import BitmapFont
from build_graphics import FIGURINES16, font_codes
from palette import INK, rgb, splash_colors
from layout import MOVES_Y, MOVE_ROWS

MOVES = ['e4', 'e5', 'Nf3', 'Nc6', 'Bb5', 'Nf6', 'Bxc6+', 'dxc6',
         'Qe2', 'Qe7', 'Re1', 'Re8', 'Kh1', 'Kh8', 'O-O', 'O-O-O',
         'exd8=Q+', 'gxh1=N#', 'Nb1d2+', 'Raxd8+', 'Qa1xc3+', 'Qh8xb2#'] * 2


def main():
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(line.split()) == 3}
    roms = [ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin']
    session = Session(ROOT.parent / 'x16-emulator/build/x16emu', next(p for p in roms if p.exists()))
    try:
        session.emu.advance(480)
        session.press('Return')
        session.emu.advance(300)
        for key in ['Right', 'Right', 'Right', 'Down', 'Down', 'Return']:
            session.press(key)
        session.emu.advance(300)
        for _ in range(120):
            if session.emu.read_memory(0x9F29)[0] & 0x30 == 0x30:
                break
            session.emu.advance(10)
        else:
            raise AssertionError('Game never became visible')
        assert session.emu.read_memory(symbols['_match_computer'])[0] == 0
        data = b''.join(move.encode('ascii').ljust(8, b'\0') for move in MOVES)
        session.emu.write_memory(0, data, space='banked_ram', bank=19)
        session.emu.write_memory(symbols['_ply'], len(MOVES).to_bytes(2, 'little'))
        session.press('i')
        session.press('i')
        session.move_mouse(639, 479)
        dest = ROOT / 'build/scorecard-icons.png'
        session.shot(dest)
        actual = np.asarray(Image.open(dest).convert('RGB'))
        expected = np.asarray(Image.open(ROOT / 'build/graphics/playfield-info.png')).copy()
        font = BitmapFont()
        first = max(0, len(MOVES) // 2 - MOVE_ROWS + 1)
        for row in range(MOVE_ROWS):
            y = MOVES_Y + row * 16
            if (first + row) * 2 <= len(MOVES):
                font.draw(expected, 488, y + 12, str(first + row + 1).rjust(3), INK)
            for side, x in [(0, 512), (1, 576)]:
                n = (first + row) * 2 + side
                if n >= len(MOVES):
                    continue
                for char in MOVES[n]:
                    if char == '=':
                        continue
                    if char in 'PNBRQK':
                        piece = 'PNBRQK'.index(char)
                        icon = FIGURINES16[:, piece * 16:(piece + 1) * 16]
                        dest_region = expected[y:y + 16, x:x + 16]
                        dest_region[icon != 0] = icon[icon != 0]
                        x += 16
                    else:
                        font.draw(expected, x, y + 12, char, INK)
                        x += 8
        colors = splash_colors()
        palette = np.array([rgb(i, colors) for i in range(len(colors))], np.uint8)
        np.testing.assert_array_equal(actual[MOVES_Y:MOVES_Y + MOVE_ROWS * 16, 488:], palette[expected][MOVES_Y:MOVES_Y + MOVE_ROWS * 16, 488:])
        assert Image.open(dest).size == (640, 480)
        assert set(Image.open(dest).getdata()) <= {rgb(i, colors) for i in range(len(colors))}
        Image.open(dest).crop((488, 112, 640, 432)).resize((456, 960), Image.Resampling.NEAREST).save(ROOT / 'build/scorecard-icons-detail.png')
        print('PASS: all scorecard fixture pixels match, including 16x16 icons, notation spacing, promotions and check/mate marks')
        # Evaluation is signed from White's view; verify both directions,
        # saturation (including mate), and an empty bar without an evaluation.
        for score, valid in [(350, 1), (-350, 1), (30000, 1), (-30000, 1), (0, 1), (350, 0)]:
            session.emu.write_memory(symbols['_match_eval'], score.to_bytes(2, 'little', signed=True))
            session.emu.write_memory(symbols['_match_eval_valid'], bytes([valid]))
            session.press('m')
            session.emu.advance(300)
            session.press('c')
            session.emu.advance(300)
            session.shot(ROOT / 'build/scorecard-bar.png')
            pixels = np.asarray(Image.open(ROOT / 'build/scorecard-bar.png').convert('RGB'))
            expected_bar = np.tile(rgb(2), (4, 112, 1)).astype(np.uint8)
            width = min(abs(score), 700) * 56 // 700 if valid else 0
            if score < 0 and width:
                expected_bar[:, 56-width:56] = rgb(1)
            elif width:
                expected_bar[:, 56:56+width] = rgb(7)
            # The printed centre tick remains visible when the bar is empty.
            if score <= 0 or not width:
                expected_bar[:, 56] = rgb(1)
            np.testing.assert_array_equal(pixels[58:62, 504:616], expected_bar)
        print('PASS: evaluation bar direction, proportional width, mate saturation and unavailable evaluation')
        # A genuine normal-difficulty CPU search: status animates and its
        # percentage increases against the actual 600-jiffy search budget.
        session.emu.write_memory(symbols['_ply'], b'\0\0')
        session.press('m')
        session.emu.advance(300)
        session.press('c')
        session.emu.advance(300)
        session.emu.write_memory(symbols['_match_difficulty'], b'\1')
        session.emu.write_memory(symbols['_match_computer'], b'\1')
        session.emu.advance(45)
        assert int.from_bytes(session.emu.read_memory(symbols['_match_think_budget'], 2), 'little') == 600
        glyphs = {index * 2: chr(code) for index, code in enumerate(font_codes())}
        snapshots, percentages = [], []
        clear = symbols['_video_clear_block']
        session.emu.request('breakpoint', address=clear, bank=0)
        try:
            for index in range(3):
                result = session.emu.advance(40)
                assert result['reason'] != 'breakpoint', 'Thinking animation blanked its status row'
                path = ROOT / f'build/scorecard-thinking-{index}.png'
                session.shot(path)
                pixels = np.asarray(Image.open(path).convert('RGB'))
                snapshots.append(pixels[440:456, 488:544].copy())
                cells = session.emu.read_memory(0x18000 + (55 * 128 + 69) * 2, 16, space='vram')
                tiles = np.frombuffer(cells, dtype='<u2') & 1023
                label = ''.join(glyphs[int(tile)] for tile in tiles)
                assert label.startswith('TIME ') and label.endswith('%'), label
                percentages.append(int(label[5:7]))
                assert set(Image.open(path).getdata()) <= {rgb(i, colors) for i in range(len(colors))}
        finally:
            session.emu.request('breakpoint', action='remove', address=clear, bank=0)
        assert percentages[0] < percentages[-1] < 100, percentages
        assert any(not np.array_equal(snapshots[0], frame) for frame in snapshots[1:]), 'Figurines did not animate'
        session.emu.advance(650)
        assert int.from_bytes(session.emu.read_memory(symbols['_ply'], 2), 'little') == 1
        session.shot(ROOT / 'build/scorecard-after-thinking.png')
        pixels = np.asarray(Image.open(ROOT / 'build/scorecard-after-thinking.png').convert('RGB'))
        assert np.all(pixels[440:456, 488:632] == rgb(2)), 'Thinking indicator did not clear'
        print(f'PASS: real CPU search, animated figurines, increasing budget percentages {percentages}, indicator clears after move')
    finally:
        session.close()


if __name__ == '__main__':
    main()
