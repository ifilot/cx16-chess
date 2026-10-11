"""Check the startup loading cover and completed menu; measure startup cycles.

Run after make. HostFS timing excludes physical disk transfer time.
--record permits the old board flash when collecting a before measurement.
"""
import argparse
import json
import os

from screenshot import ROOT, Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--out', default='build/startup.json')
    args = parser.parse_args()
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(line.split()) == 3}
    roms = [ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin']
    session = Session(ROOT.parent / 'x16-emulator/build/x16emu', next(p for p in roms if p.exists()))
    expected_map = (ROOT / 'build/graphics/SPLMAP.DAT').read_bytes()[:46 * 256]
    flashes = loading_frames = 0
    try:
        def stop_at(name, bank=0, check_loading=False):
            session.emu.request('breakpoint', address=symbols[name], bank=bank)
            if check_loading:
                for _ in range(600):
                    result = session.emu.advance(1)
                    check_cover()
                    if result['reason'] == 'breakpoint':
                        break
            else:
                result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint', result
            session.emu.request('breakpoint', action='remove', address=symbols[name], bank=bank)
            return result['state']['cycles']

        def check_cover():
            video = session.emu.read_memory(0x9F29)[0]
            assert video & 0x70 == 0x50, 'Startup cover exposes scene layers'
            assert session.emu.read_memory(0x9F2D, 3) == bytes((2, 0xF0, 0xF4))
            assert session.emu.read_memory(0x1E000, 2048, space='vram') == bytes(2048)
            assert session.emu.read_memory(0x1E800, 32, space='vram') == b'\x22' * 32
            assert session.emu.read_memory(0x1FC16, 2, space='vram') == b'\x0c\x77'
            assert session.emu.read_memory(0x1FA04, 2, space='vram') == b'\xdb\x0e'
            assert session.emu.read_memory(0x1FAE2, 2, space='vram') == b'\x11\x09'
            assert session.emu.read_memory(0x1FC06, 1, space='vram') == b'\0', 'Pointer exposed during startup'

        boot = stop_at('boot_loading')
        cover_ready = stop_at('boot_loading_ready')
        check_cover()
        assert cover_ready - boot < 80_000, 'Initial loading cover takes more than 10ms at 8MHz'
        begin = stop_at('_main')
        stop_at('_bank_load_raw')  # First disk read: bundled code and audio.
        check_cover()
        opening = stop_at('_start_open', 21, check_loading=True)
        enabled_before_open = bool(session.emu.read_memory(0x9F29)[0] & 0x30)
        check_cover()
        session.emu.request('breakpoint', address=symbols['_cbm_k_getin'], bank=0)
        for _ in range(600):
            result = session.emu.advance(1)
            video = session.emu.read_memory(0x9F29)[0]
            covered = session.emu.read_memory(symbols['_transition_covered'])[0]
            if covered:
                loading_frames += 1
                check_cover()
            elif video & 0x30:
                actual = session.emu.read_memory(0x06000, len(expected_map), space='vram')
                if actual != expected_map:
                    flashes += 1
                    if not args.record:
                        raise AssertionError('A visible startup frame has unfinished or non-splash artwork')
            if result['reason'] == 'breakpoint':
                break
        else:
            raise AssertionError('Opening menu never became ready')
        ready = result['state']['cycles']
        if not args.record:
            assert loading_frames, 'Startup never showed the Loading cover'
            assert not session.emu.read_memory(symbols['_transition_covered'])[0]
            assert session.emu.read_memory(0x1FC16, 1, space='vram') == b'\0'
        report = {'main_to_menu_cycles': ready - begin,
                  'main_to_menu_seconds_8mhz': (ready - begin) / 8_000_000,
                  'init_cycles': opening - begin,
                  'layers_enabled_before_open': enabled_before_open,
                  'incorrect_visible_frames_during_open': flashes,
                  'loading_cover_frames': loading_frames,
                  'loading_cover_ready_cycles': cover_ready - boot,
                  'loading_cover_ready_seconds_8mhz': (cover_ready - boot) / 8_000_000,
                  'loading_cover_before_first_disk_read': True,
                  'timing': 'ROM CMDR-DOS with emulated SD card; physical hardware not measured' if os.environ.get('CHESS_SDCARD') else 'AgentBridge HostFS; physical disk transfer time excluded'}
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        session.emu.request('breakpoint', action='clear')
        session.move_mouse(639, 479)
        session.shot(ROOT / 'build/startup.png')
    finally:
        session.close()


if __name__ == '__main__':
    main()
