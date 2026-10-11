"""Regression checks for inherited pointers, hardware mouse bounds and keyboard ownership."""
import os
from pathlib import Path
import shutil
import tempfile
from runtime_files import RUNTIME_FILES
from screenshot import ROOT, Session


def main():
    symbols = {p[2].lstrip('.'): int(p[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(p := line.split()) == 3}
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-input-') as temporary:
        folder = Path(temporary)
        for name in RUNTIME_FILES:
            shutil.copyfile(Path(os.environ.get('CHESS_FSROOT', ROOT / 'src')) / name, folder / name)
        session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=folder)
        try:
            def vram(address, size=1):
                return bytes(session.emu.read_memory(address, size, space='vram'))

            # Simulate a pointer inherited from BASIC/an earlier application.
            stop = symbols['boot_loading']
            session.emu.request('breakpoint', address=stop, bank=0)
            result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint', result
            saved = result['state']
            session.emu.request('breakpoint', action='remove', address=stop, bank=0)
            scratch = bytes(session.emu.read_memory(0x400, 6))
            session.emu.write_memory(0x400, b'\x20\x68\xff\x4c\x03\x04')
            session.emu.request('set_registers', pc=0x400, a=1, x=40, y=30, p=saved['p'] | 4)
            session.emu.request('breakpoint', address=0x403, bank=0)
            assert session.emu.advance(100000, unit='instructions')['reason'] == 'breakpoint'
            session.emu.request('breakpoint', action='remove', address=0x403, bank=0)
            assert vram(0x1FC06)[0] & 12, 'Inherited pointer should be visible before constructor'
            session.emu.write_memory(0x400, scratch)
            session.emu.request('set_registers', **{k: saved[k] for k in ('pc', 'a', 'x', 'y', 'p', 'sp')})
            # Every covered frame, including main's mouse configuration, must
            # keep sprite 0 hidden while retaining the Loading label.
            session.emu.request('breakpoint', address=symbols['boot_loading_ready'], bank=0)
            assert session.emu.advance(600)['reason'] == 'breakpoint'
            session.emu.request('breakpoint', action='remove', address=symbols['boot_loading_ready'], bank=0)
            assert vram(0x1FC06)[0] & 12 == 0
            for frame in range(1200):
                if frame % 3 == 0:
                    session.emu.request('mouse', dx=7, dy=5, buttons=0)
                result = session.emu.advance(1)
                if not session.emu.read_memory(symbols['_transition_covered'])[0]:
                    break
                assert vram(0x1FC06)[0] & 12 == 0, ('Pointer exposed under startup cover', frame, result, vram(0x1FC00, 8))
            else:
                raise AssertionError('Startup did not finish')
            session.emu.advance(120)
            assert vram(0x1FC06)[0] & 12 == 12
            attr = vram(0x1FC00, 2)
            assert (attr[0] | ((attr[1] & 15) << 8)) << 5 == 0x1D000, 'KERNAL replaced the native pointer image'
            print('PASS: inherited pointer is disabled; every startup frame hides the pointer; native image is preserved', flush=True)

            for point in ((0, 0), (639, 0), (639, 479), (0, 479), (639, 479)):
                session.move_mouse(*point)
                session.emu.advance(12)
                assert session.read_mouse() == point
            print('PASS: pointer reaches all four corners of the 640x480 screen', flush=True)

            def key(value):
                session.press(value)
                session.emu.advance(12)

            def cursor():
                attr = vram(0x1FC08, 8)
                assert attr[6] & 12 == 12, 'Keyboard cursor disappeared under stationary mouse'
                return (attr[2] | ((attr[3] & 3) << 8)), (attr[4] | ((attr[5] & 3) << 8))

            def at(col, row):
                assert cursor() == (20 + col * 56, 4 + row * 56), (col, row, cursor())

            def repeat(value, count):
                for _ in range(count):
                    key(value)

            def sweep():
                repeat('Left', 8)
                repeat('Up', 8)
                for row in range(8):
                    columns = range(8) if row % 2 == 0 else range(7, -1, -1)
                    for i, col in enumerate(columns):
                        if i:
                            key('Right' if row % 2 == 0 else 'Left')
                        at(col, row)
                        session.emu.advance(12)
                        at(col, row)
                    if row < 7:
                        key('Down')
                repeat('Down', 3)
                repeat('Left', 3)
                at(0, 7)

            key('n'); key('Left'); key('Return')  # local two-player game
            session.move_mouse(220, 260)  # stationary pointer stays over d4
            session.emu.advance(12)
            key('Up')
            at(3, 4)
            sweep()
            repeat('Right', 4); key('Up'); key('Return')  # e2
            repeat('Up', 2); key('Return')  # e4
            assert int.from_bytes(session.emu.read_memory(symbols['_ply'], 2), 'little') == 1
            repeat('Up', 3); key('Return')  # e7
            repeat('Down', 2); key('Return')  # e5
            assert int.from_bytes(session.emu.read_memory(symbols['_ply'], 2), 'little') == 2
            key('f')
            sweep()
            # Real mouse input can still take control, and keyboard can return.
            session.move_mouse(108, 372)
            session.emu.advance(12)
            assert vram(0x1FC0E)[0] & 12 == 0
            key('Up'); at(1, 6)
            session.click(108, 372)
            assert vram(0x1FC0E)[0] & 12 == 0
            key('Up'); at(1, 6)
            print('PASS: keyboard reaches all 64 squares in both orientations, clamps at edges, plays e2-e4/e7-e5, and shares control with mouse movement/clicks', flush=True)
        finally:
            session.close()


if __name__ == '__main__':
    main()
