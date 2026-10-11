"""Exercise sprite dragging and legal moves in an isolated X16 game."""
from runtime_files import RUNTIME_FILES
from pathlib import Path
import os
import shutil
import sys
import tempfile
import numpy as np
from screenshot import ROOT, Session
from storage_test import digest
sys.path.insert(0, str(ROOT / 'assets/scripts'))
from build_graphics import load_indexed
import layout as L


def main():
    symbols = {p[2].lstrip('.'): int(p[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(p := line.split()) == 3}
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    runtime = Path(os.environ.get('CHESS_FSROOT', ROOT / 'src'))
    for style, name in enumerate(('victorian', 'continental', 'letterpress')):
        with tempfile.TemporaryDirectory(prefix='chess-drag-') as folder:
            for file in RUNTIME_FILES:
                shutil.copyfile(runtime / file, Path(folder) / file)
            session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=folder)
            def read(key, length=1):
                return bytes(session.emu.read_memory(symbols['_' + key], length))
            def keys(*values):
                for value in values:
                    session.press(value)
                    session.emu.advance(120)
            def sq(value):
                return (int(value[1]) - 1) * 16 + ord(value[0]) - ord('a')
            def point(value):
                f, r = ord(value[0]) - ord('a'), int(value[1]) - 1
                col, row = (7 - f, r) if read('playfield_flipped')[0] else (f, 7 - r)
                return L.BOARD_X + col * 56 + 28, L.BOARD_Y + row * 56 + 28
            def attrs():
                return bytes(session.emu.read_memory(0x1FC78, 8, space='vram'))
            def grab(value, piece=None, offset=(0, 0)):
                cx, cy = point(value)
                x, y = cx + offset[0], cy + offset[1]
                session.move_mouse(x, y)
                before = read('board', 128)
                font = bytes(session.emu.read_memory(L.VRAM_L1_TILES, L.L1_PIECES * 32, space='vram'))
                session.emu.request('mouse', buttons=1)
                session.emu.advance(8)
                a = attrs()
                assert a[6:] == b'\x0c\xf0', a
                assert (int.from_bytes(a[:2], 'little') & 0xfff) * 32 == L.VRAM_DRAG
                assert int.from_bytes(a[2:4], 'little') == cx - 32
                assert int.from_bytes(a[4:6], 'little') == cy - 32
                assert read('board', 128) == before, 'Dragging modified the logical board'
                assert bytes(session.emu.read_memory(L.VRAM_L1_TILES, len(font), space='vram')) == font, 'Dragging overwrote the resident font'
                col, row = (cx - 28) // 8, (cy - 28) // 8
                for dy in range(7):
                    data = bytes(session.emu.read_memory(L.VRAM_L1_MAP + ((row + dy) * 128 + col) * 2, 14, space='vram'))
                    assert data == bytes(14), 'Source piece remains in the tile layer'
                if piece is not None:
                    packed = np.frombuffer(bytes(session.emu.read_memory(L.VRAM_DRAG, 2048, space='vram')), dtype=np.uint8)
                    pixels = np.empty(4096, np.uint8)
                    pixels[::2], pixels[1::2] = packed >> 4, packed & 15
                    expected = np.zeros((64, 64), np.uint8)
                    sheet = load_indexed(ROOT / 'assets/pieces' / (name + '.png'))
                    expected[4:60, 4:60] = sheet[:, piece * 56:(piece + 1) * 56]
                    np.testing.assert_array_equal(pixels.reshape(64, 64), expected)
            def drop(value=None):
                session.move_mouse(*(point(value) if value else (620, 464)), buttons=1)
                session.emu.request('mouse', buttons=0)
                session.emu.advance(120)
                assert attrs()[6] == 0, 'Drag sprite remained visible after release'
            def drag(source, target):
                grab(source)
                session.move_mouse(*point(target), buttons=1)
                session.emu.advance(8)
                x, y = point(target)
                a = attrs()
                assert int.from_bytes(a[2:4], 'little') == x - 32, (source, target, x, y, a)
                assert int.from_bytes(a[4:6], 'little') == y - 32, (source, target, x, y, a)
                drop(target)
            def fixture(moves):
                keys('m')
                payload = b''.join(bytes((sq(a), sq(b), 0)) for a, b in moves)
                header = bytearray(28)
                header[:8] = b'X16SAVE4'
                header[8:10] = (1).to_bytes(2, 'little')
                header[10:12] = len(moves).to_bytes(2, 'little')
                header[12:16] = (1800).to_bytes(2, 'little') * 2
                header[17] = 2
                header[21] = style
                header[23] = 1
                header[26:28] = digest(header[:26] + payload).to_bytes(2, 'little')
                (Path(folder) / 'CHESS1A.SAV').write_bytes(header + payload)
                keys('l', '1', 'Return')
                assert read('ply', 2) == len(moves).to_bytes(2, 'little')
            try:
                session.emu.advance(480)
                if style:
                    keys('o', 'Down', *(['Right'] * style), 'Escape')
                keys('n', 'Left', 'Return')  # local two-player game
                assert read('match_computer') == b'\0'
                # An opponent's piece cannot be dragged.
                session.move_mouse(*point('a7'))
                session.emu.request('mouse', buttons=1)
                session.emu.advance(8)
                assert attrs()[6] == 0
                session.emu.request('mouse', buttons=0)
                session.emu.advance(8)
                # All six piece types match the imported sheet, with zero padding.
                for source, piece in (('e2', 0), ('g1', 1), ('c1', 2), ('a1', 3), ('d1', 4), ('e1', 5)):
                    grab(source, piece)
                    drop()
                    assert read('ply', 2) == b'\0\0'
                grab('e2', 0, (10, -8))
                session.move_mouse(*point('e4'), buttons=1)
                x, y = point('e4')
                assert int.from_bytes(attrs()[2:4], 'little') == x - 42
                assert int.from_bytes(attrs()[4:6], 'little') == y - 24
                # Clock strings must remain in resident RAM while input runs banked.
                session.emu.advance(120)
                for label, row in (('BLACK', 9), ('WHITE', 11)):
                    text = bytes(session.emu.read_memory(L.VRAM_L1_MAP + (row * 128 + 64) * 2, 10, space='vram'))
                    assert list(text[::2]) == [(ord(c) - 32) * 2 for c in label], (label, text)
                session.shot(ROOT / 'build/drag' / (name + '.png'))
                drop('e4')
                assert read('board', 128)[sq('e4')] == 1 and read('ply', 2) == b'\x01\0'
                grab('d7', 6); drop('d6')
                # Invalid drops, click-to-move and keyboard flipping still work.
                grab('g1', 1); drop('g3')
                assert read('ply', 2) == b'\x02\0'
                session.click(*point('g1')); session.emu.advance(8)
                session.click(*point('f3')); session.emu.advance(120)
                assert read('ply', 2) == b'\x03\0'
                keys('f')
                drag('g8', 'f6')
                assert read('board', 128)[sq('f6')] == 10
                grab('b1', 1)
                keys('Escape')
                assert attrs()[6] == 0
                session.emu.request('mouse', buttons=0)
                keys('Return')
                assert read('board', 128)[sq('b1')] == 2
                # Same rules path handles captures, en passant, castling and promotion.
                fixture([('e2', 'e4'), ('d7', 'd5')])
                drag('e4', 'd5')
                assert read('board', 128)[sq('d5')] == 1
                fixture([('e2', 'e4'), ('a7', 'a6'), ('e4', 'e5'), ('d7', 'd5')])
                drag('e5', 'd6')
                assert read('board', 128)[sq('d6')] == 1 and read('board', 128)[sq('d5')] == 0
                fixture([('e2', 'e4'), ('e7', 'e5'), ('g1', 'f3'), ('b8', 'c6'), ('f1', 'c4'), ('g8', 'f6')])
                drag('e1', 'g1')
                assert read('board', 128)[sq('g1')] == 6 and read('board', 128)[sq('f1')] == 4
                fixture([('a2', 'a4'), ('h7', 'h5'), ('a4', 'a5'), ('h5', 'h4'), ('a5', 'a6'), ('h4', 'h3'), ('a6', 'b7'), ('h3', 'g2')])
                drag('b7', 'a8')
                assert read('ply', 2) == b'\x08\0'
                session.click(*point('a7')); session.emu.advance(120)
                assert read('board', 128)[sq('a8')] == 2 and read('ply', 2) == b'\x09\0'
                assert attrs()[6] == 0
                print(f'PASS: {name} sprite pixels/padding, moving pointer, hidden source, valid/invalid drops, click moves, flipped board, pause cancellation, capture, en passant, castling and promotion', flush=True)
            finally:
                session.close()


if __name__ == '__main__':
    main()
