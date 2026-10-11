"""Exercise CHESS.DAT rejection, short reads and byte-at-a-time fallback in ROM."""
from pathlib import Path
import json
import os
import shutil
import tempfile

from screenshot import ROOT, Session


def main():
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(line.split()) == 3}
    roms = [ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin']
    emulator, rom = ROOT.parent / 'x16-emulator/build/x16emu', next(p for p in roms if p.exists())
    runtime = Path(os.environ.get('CHESS_FSROOT', ROOT / 'src'))
    original = (runtime / 'CHESS.DAT').read_bytes()
    resources = json.loads((ROOT / 'build/graphics/runtime-manifest.json').read_text())
    with tempfile.TemporaryDirectory(prefix='chess-assets-') as temporary:
        folder = Path(temporary)
        for name in ('CHESS.PRG', 'MENU.BIN', 'UI.BIN'):
            shutil.copyfile(runtime / name, folder / name)
        for case in ('missing', 'wrong-build', 'truncated-font', 'truncated-setup'):
            data = original
            if case == 'wrong-build':
                data = b'BADPACK!' + original[8:]
            elif case == 'truncated-font':
                data = original[:resources['FONT']['offset'] + 100]
            elif case == 'truncated-setup':
                data = original[:resources['SETTILE']['offset'] + 100]
            file = folder / 'CHESS.DAT'
            if case == 'missing':
                if file.exists():
                    file.unlink()
            else:
                file.write_bytes(data)
            session = Session(emulator, rom, fsroot=folder)
            try:
                session.emu.request('breakpoint', address=symbols['asset_abort'], bank=0)
                if case == 'truncated-setup':
                    # Initial assets precede the truncated portion and still load.
                    session.emu.advance(480)
                    assert session.emu.read_memory(0x9F29)[0] & 0x70 == 0x70
                    session.press('Return')
                result = session.emu.advance(600)
                assert result['reason'] == 'breakpoint', (case, result)
                assert session.emu.read_memory(0x9F29)[0] & 0x70 == 0, case
                session.emu.request('breakpoint', action='remove', address=symbols['asset_abort'], bank=0)
                session.emu.advance(120)
                assert session.emu.read_memory(symbols['asset_opened'])[0] == 0
                assert session.emu.read_memory(0x9F29)[0] & 0x70 == 0
                print(f'PASS: {case} rejected; display stays hidden and file channels close')
            finally:
                session.emu.close()
        file.write_bytes(original)
        # Drive startup while making MACPTR return smaller successful reads.
        # Also force one unsupported bulk call, exercising the ACPTR path.
        session = Session(emulator, rom, fsroot=folder)
        try:
            reader = symbols['_asset_read']
            session.emu.request('breakpoint', address=reader, bank=0)
            result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint'
            session.emu.request('breakpoint', action='remove', address=reader, bank=0)
            for kind in ('short-header', 'short-vram', 'fallback-vram'):
                session.emu.request('breakpoint', address=0xFF44, bank=0)
                result = session.emu.advance(600)
                assert result['reason'] == 'breakpoint'
                state = result['state']
                if kind == 'short-vram':
                    # Finish any remaining header read before testing the VRAM stream.
                    while state['x'] != 0x23 or state['y'] != 0x9f:
                        session.emu.request('breakpoint', action='remove', address=0xFF44, bank=0)
                        session.emu.advance(1, unit='instructions')
                        session.emu.request('breakpoint', address=0xFF44, bank=0)
                        state = session.emu.advance(600)['state']
                session.emu.request('breakpoint', action='remove', address=0xFF44, bank=0)
                if kind.startswith('short'):
                    session.emu.request('set_registers', a=3 if kind == 'short-header' else 37)
                    session.emu.advance(1, unit='instructions')
                else:
                    # Emulate an unsupported MACPTR: return to the caller with C set,
                    # consuming no file data, so ACPTR reads the correct next byte.
                    stack = state['sp']
                    return_bytes = session.emu.read_memory(0x100 | ((stack + 1) & 255), 2)
                    return_address = int.from_bytes(return_bytes, 'little') + 1
                    session.emu.request('set_registers', pc=return_address,
                                        sp=0x100 | ((stack + 2) & 255), p=state['p'] | 1)
                session.emu.advance(10, unit='instructions')
            session.emu.advance(480)
            assert session.emu.read_memory(0x9F29)[0] & 0x70 == 0x70
            expected = (ROOT / 'build/graphics/SPRITES.DAT').read_bytes()
            assert session.emu.read_memory(0x1D000, len(expected), space='vram') == expected
            expected = (ROOT / 'build/graphics/FONT.DAT').read_bytes()
            assert session.emu.read_memory(0x10000, len(expected), space='vram') == expected
            print('PASS: short header/VRAM reads and ACPTR fallback preserve every font/sprite byte')
        finally:
            session.emu.close()


if __name__ == '__main__':
    main()
