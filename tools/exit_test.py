"""Exercise real main returns and BASIC after exit; audit restored system RAM."""
import os
import shutil
import tempfile
from pathlib import Path
from screenshot import ROOT, Session
from runtime_files import RUNTIME_FILES


def main():
    symbols = {p[2].lstrip('.'): int(p[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(p := line.split()) == 3}
    emulator = ROOT.parent / 'x16-emulator/build/x16emu'
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin',
                           ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-exit-') as temporary:
        runtime = Path(temporary)
        for name in RUNTIME_FILES:
            if name != 'AUTOBOOT.X16':
                shutil.copyfile(Path(os.environ.get('CHESS_FSROOT', ROOT / 'src')) / name, runtime / name)
        for case in ('shortcut', 'keyboard', 'mouse', 'played', 'load-error', 'graphics-error'):
            session = Session(emulator, rom, fsroot=runtime)
            emu = session.emu
            def stop(name):
                address = symbols[name]
                emu.request('breakpoint', address=address, bank=0)
                result = emu.advance(1200)
                assert result['reason'] == 'breakpoint', (case, name, result)
                emu.request('breakpoint', action='remove', address=address, bank=0)
                return result['state']
            try:
                before = stop('runtime_start')
                zp = emu.read_memory(0x22, 0x5E)
                vectors = emu.read_memory(0x314, 32)
                bank = emu.read_memory(0)[0]
                basic_pointers = emu.read_memory(0x3E1, 10)  # VARTAB through MEMSIZ
                basic_bank = emu.read_memory(0, 8192, space='banked_ram', bank=0)
                sentinel = bytes((i * 17 + 3) & 255 for i in range(8192))
                emu.write_memory(0, sentinel, space='banked_ram', bank=46)
                if case == 'load-error':
                    (runtime / 'CHESS.BIN').rename(runtime / 'HIDDEN.BIN')
                elif case == 'graphics-error':
                    (runtime / 'CHESS.DAT').rename(runtime / 'HIDDEN.DAT')
                else:
                    emu.advance(1200)
                emu.request('breakpoint', address=symbols['runtime_restored'], bank=0)
                if case == 'keyboard':
                    session.press('Up')
                    session.press('Return')
                elif case == 'mouse':
                    session.click(310, 452)
                elif case == 'played':
                    session.press('n')
                    session.press('Left')   # two local players
                    session.press('Return')
                    emu.advance(120)
                    session.click(228, 396)  # e2-e4, exercising engine/game RAM
                    session.click(228, 284)
                    assert emu.read_memory(symbols['_ply'], 2) == b'\x01\x00'
                    session.press('m')
                    emu.advance(120)
                    session.press('x')
                elif case not in ('load-error', 'graphics-error'):
                    session.press('x')
                state = stop('runtime_restored')
                assert emu.read_memory(0x22, 0x5E) == zp, (case, 'BASIC zero page changed')
                assert emu.read_memory(0x314, 32) == vectors, (case, 'KERNAL vectors changed')
                assert emu.read_memory(0x3E1, 10) == basic_pointers, (case, 'BASIC memory bounds changed')
                bank0_after = emu.read_memory(0, 8192, space='banked_ram', bank=0)
                changed = [(0xA000 + i, a, b)
                           for i, (a, b) in enumerate(zip(basic_bank, bank0_after)) if a != b]
                # ROM mouse/timer state and audio register shadows legitimately
                # change through KERNAL calls; the rest of bank 0 must survive.
                assert all(0xA886 <= address < 0xA8B7 or
                           0xADC0 <= address < 0xAF00
                           for address, _, _ in changed), (case, changed)
                assert emu.read_memory(0)[0] == bank
                assert emu.read_memory(1)[0] == 4
                assert state['sp'] == before['sp'], (case, 'hardware stack leaked')
                assert emu.read_memory(0, 8192, space='banked_ram', bank=46) == sentinel
                assert all(emu.read_memory(0x1F9C2 + 4 * i, space='vram')[0] & 63 == 0 for i in range(16))
                emu.advance(120)
                emu.request('paste', text='PRINT 120+4\r')
                emu.advance(120)
                screen = emu.read_memory(0x1B000, 80 * 60 * 2, space='vram')[::2]
                assert b'124' in screen, (case, 'BASIC direct mode failed')
                # BASIC must accept and run a fresh program, with working variables.
                for line in ('new', '10 a=456:print a+123', 'run'):
                    emu.request('paste', text=line.upper() + '\r')
                    emu.advance(120)
                emu.advance(120)
                screen = emu.read_memory(0x1B000, 80 * 60 * 2, space='vram')[::2]
                assert b'579' in screen, (case, 'BASIC did not execute new program')
                session.shot(ROOT / 'build/exit' / (case + '.png'))
                if case == 'shortcut':
                    emu.request('paste', text='LOAD"CHESS.PRG",8,1\r')
                    emu.advance(120)
                    emu.request('paste', text='RUN\r')
                    stop('runtime_start')
                    emu.advance(1200)
                    emu.request('breakpoint', address=symbols['runtime_restored'], bank=0)
                    session.press('x')
                    stop('runtime_restored')
                    emu.advance(120)
                print(f'PASS: {case}: main returned, ZP/vectors/banks/stack restored, BASIC runs', flush=True)
            finally:
                if (runtime / 'HIDDEN.BIN').exists():
                    (runtime / 'HIDDEN.BIN').rename(runtime / 'CHESS.BIN')
                if (runtime / 'HIDDEN.DAT').exists():
                    (runtime / 'HIDDEN.DAT').rename(runtime / 'CHESS.DAT')
                session.close()


if __name__ == '__main__':
    main()
