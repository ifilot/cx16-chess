"""Reject inherited startup input for explicit, automatic and SD-card boots."""
from runtime_files import RUNTIME_FILES
from pathlib import Path
import shutil
import os
import tempfile
from screenshot import ROOT, Session, X16Agent
from make_sdcard import create_sdcard


def main():
    symbols = {p[2].lstrip('.'): int(p[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(p := line.split()) == 3}
    emulator = ROOT.parent / 'x16-emulator/build/x16emu'
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-startup-input-') as temporary:
        folder = Path(temporary)
        runtime = folder / 'game'
        runtime.mkdir()
        for name in RUNTIME_FILES:
            shutil.copyfile(Path(os.environ.get('CHESS_FSROOT', ROOT / 'src')) / name, runtime / name)
        for case in ('explicit', 'explicit-with-autoboot', 'autoboot-only', 'sd-autoboot', 'held-mouse'):
            if case == 'sd-autoboot' and not all(shutil.which(tool) for tool in ('mkfs.fat', 'mcopy')):
                print('SKIP: SD autoboot check requires mkfs.fat and mcopy', flush=True)
                continue
            autoboot = runtime / 'AUTOBOOT.X16'
            if case == 'explicit':
                autoboot.unlink(missing_ok=True)
            else:
                shutil.copyfile(runtime / 'CHESS.PRG', autoboot)
            options = []
            if case.startswith('explicit') or case == 'held-mouse':
                options = ['-prg', str(runtime / 'CHESS.PRG'), '-run']
            if case == 'sd-autoboot':
                image = folder / 'card.img'
                create_sdcard(runtime, image)
                options = ['-sdcard', str(image)]
            session = Session.__new__(Session)
            session.emu = X16Agent(emulator, rom, fsroot=runtime, options=options)
            session.mouse = None
            def menu():
                data = bytes(session.emu.read_memory(0x18000 + (46 * 128 + 36) * 2, 16, space='vram'))
                assert list(data[::2]) == [(ord(c) - 32) * 2 for c in 'NEW GAME'], (case, data)
                assert session.emu.read_memory(symbols['_ply'], 2) == b'\0\0'
            try:
                if case == 'held-mouse':
                    session.emu.request('breakpoint', address=symbols['_start_open'], bank=21)
                    assert session.emu.advance(1200)['reason'] == 'breakpoint'
                    session.emu.request('breakpoint', action='remove', address=symbols['_start_open'], bank=21)
                    session.emu.request('mouse', dy=136, buttons=1)
                session.emu.request('breakpoint', address=symbols['_start_key'], bank=21)
                session.emu.request('breakpoint', address=symbols['_playfield_new'], bank=0)
                result = session.emu.advance(1200)
                assert result['reason'] != 'breakpoint', (case, 'startup triggered menu/game input', result)
                menu()
                session.emu.request('breakpoint', action='remove', address=symbols['_start_key'], bank=21)
                session.emu.request('breakpoint', action='remove', address=symbols['_playfield_new'], bank=0)
                if case == 'held-mouse':
                    session.emu.request('mouse', buttons=0)
                    session.emu.advance(120)
                    menu()
                session.shot(ROOT / 'build/startup-input' / (case + '.png'))
                # A real key after startup must still work immediately.
                session.press('n')
                session.emu.advance(120)
                data = bytes(session.emu.read_memory(0x18000 + (17 * 128 + 44) * 2, 14, space='vram'))
                assert list(data[::2]) == [(ord(c) - 32) * 2 for c in 'PLAY AS'], (case, data)
                print(f'PASS: {case} stays on main menu; fresh input opens New Game', flush=True)
            finally:
                session.close()


if __name__ == '__main__':
    main()
