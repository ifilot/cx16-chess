"""Test persistent writes and restart/load using the real ROM SD-card path.

Creates an isolated FAT32 image, never accesses a physical disk.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from make_sdcard import create_sdcard
from screenshot import ROOT, Session
from storage_test import digest


def main():
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(line.split()) == 3}
    emu = ROOT.parent / 'x16-emulator/build/x16emu'
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    output = ROOT / 'build/storage'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chess-sd-') as temporary:
        folder = Path(temporary)
        runtime = folder / 'runtime'
        runtime.mkdir()
        for name in ('CHESS.PRG', 'MENU.BIN', 'UI.BIN', 'CHESS.DAT'):
            shutil.copyfile(ROOT / 'src' / name, runtime / name)
        image = folder / 'card.img'
        create_sdcard(runtime, image)
        os.environ['CHESS_SDCARD'] = str(image)

        def copy(name):
            path = folder / name
            subprocess.run(['mcopy', '-o', '-i', str(image) + '@@1048576',
                            '::' + name, str(path)], check=True)
            return path.read_bytes()

        def read(name, length=1):
            return bytes(session.emu.read_memory(symbols['_' + name], length))

        def keys(*names):
            for name in names:
                session.press(name)
                session.emu.advance(480)

        session = Session(emu, rom, fsroot=runtime)
        try:
            session.emu.advance(1200)
            keys('n', 'Left', 'Return', 'Escape', 'Down', 'Return', '9', 'Return')
            keys('Return', 'Down', 'Return')  # confirm an overwrite to generation B
            session.shot(output / 'sd-saved.png')
        finally:
            session.close()
        for name, generation in [('CHESS9A.SAV', 1), ('CHESS9B.SAV', 2)]:
            data = copy(name)
            assert data[:8] == b'X16SAVE1'
            assert digest(data[:26] + data[28:]) == int.from_bytes(data[26:28], 'little')
            assert int.from_bytes(data[8:10], 'little') == generation
        session = Session(emu, rom, fsroot=runtime)
        try:
            session.emu.advance(1200)
            keys('l', '9', 'Return', 'Escape')
            assert read('board', 128)[4] == 6 and read('match_clock', 4) != b'\0' * 4
            session.shot(output / 'sd-loaded.png')
            keys('Down', 'Down', 'Return', 'o', 'Right', 'Down', 'Right', 'Down', 'Return')
        finally:
            session.close()
        assert copy('CHESSOPT.DAT')[5:7] == b'\x01\x01'
        session = Session(emu, rom, fsroot=runtime)
        try:
            session.emu.advance(1200)
            assert read('playfield_theme') == b'\x01' and read('start_piece_set') == b'\x01'
        finally:
            session.close()
        print('PASS: real ROM CMDR-DOS SD save, overwrite generations, restart/load and persistent preferences')


if __name__ == '__main__':
    main()
