"""Check the visible loading cover on every frame of scene and piece changes."""
from pathlib import Path
import shutil
import tempfile
from screenshot import ROOT, Session


def main():
    symbols = {}
    for line in (ROOT / 'src/CHESS.sym').read_text().splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2].lstrip('.')] = int(parts[1], 16)
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-transitions-') as folder:
        for name in ('CHESS.PRG', 'MENU.BIN', 'UI.BIN', 'CHESS.DAT'):
            shutil.copyfile(ROOT / 'src' / name, Path(folder) / name)
        session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=folder)
        def memory(address, size=1, space='cpu'):
            return bytes(session.emu.read_memory(address, size, space=space))
        def transition(key, name):
            seen = False
            seen_figures = False
            frames = 0
            session.emu.request('key', key=key, down=True)
            try:
                for frames in range(300):
                    session.emu.advance(1)
                    if frames == 3:
                        session.emu.request('key', key=key, down=False)
                    video = memory(0x9F29)[0]
                    assert video & 0x10, (name, 'Black frame', frames)
                    if memory(symbols['_transition_covered'])[0]:
                        seen = True
                        assert video & 0x70 == 0x50, (name, 'Scene layers exposed')
                        assert memory(0x9F2D, 3) == bytes((2, 0xF0, 0xF4)), (name, 'Cover map changed')
                        assert memory(0x1E000, 2048, 'vram') == bytes(2048)
                        assert memory(0x1E800, 32, 'vram') == b'\x22' * 32
                        assert memory(0x1FC16, 2, 'vram') == b'\x0c\x77'
                        depths = []
                        for index in range(12):
                            attributes = memory(0x1FC1E + index * 8, 2, 'vram')
                            assert attributes[1] == 0xA5
                            assert attributes[0] in (0, 12 | (index & 1))
                            depths.append(attributes[0])
                        seen_figures |= all(depths)
                        assert memory(0x1FA04, 2, 'vram') == b'\xdb\x0e', (name, 'Paper color changed')
                        assert memory(0x1FAE2, 2, 'vram') == b'\x11\x09', (name, 'Label color changed')
                    elif seen:
                        assert video & 0x70 == 0x70
                        assert memory(0x1FC16, 1, 'vram') == b'\0', (name, 'Loading label left visible')
                        for index in range(12):
                            assert memory(0x1FC1E + index * 8, 1, 'vram') == b'\0'
                        assert seen_figures, (name, 'Figurines never shown')
                        break
                else:
                    raise AssertionError((name, 'No completed transition'))
            finally:
                session.emu.request('key', key=key, down=False)
            print(f'{name}: visible cover, {frames + 1} frames', flush=True)
            session.emu.advance(12)
        try:
            session.emu.advance(480)
            transition('n', 'Menu to setup')
            transition('Escape', 'Setup to menu')
            transition('a', 'Menu to About')
            transition('Escape', 'About to menu')
            transition('o', 'Menu to options')
            session.press('Down')
            transition('Right', 'Piece set change')
            transition('Escape', 'Options to menu')
            transition('n', 'Menu to setup again')
            session.press('Left')  # local two-player
            transition('Return', 'Setup to board')
            transition('m', 'Board to menu')
            transition('c', 'Menu to board')
            print('PASS: every transition keeps paper and native Loading sprite visible, with no black frame or scene layers exposed')
        finally:
            session.close()


if __name__ == '__main__':
    main()
