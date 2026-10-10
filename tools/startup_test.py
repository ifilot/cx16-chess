"""Check the first visible startup view and measure emulated startup cycles.

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
    flashes = 0
    try:
        def stop_at(name, bank=0):
            session.emu.request('breakpoint', address=symbols[name], bank=bank)
            result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint', result
            session.emu.request('breakpoint', action='remove', address=symbols[name], bank=bank)
            return result['state']['cycles']

        begin = stop_at('_main')
        opening = stop_at('_start_open', 21)
        enabled_before_open = bool(session.emu.read_memory(0x9F29)[0] & 0x30)
        if not args.record:
            assert not enabled_before_open, 'Startup exposes a tile layer before loading the opening screen'
        session.emu.request('breakpoint', address=symbols['_cbm_k_getin'], bank=0)
        for _ in range(600):
            result = session.emu.advance(1)
            if session.emu.read_memory(0x9F29)[0] & 0x30:
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
        report = {'main_to_menu_cycles': ready - begin,
                  'main_to_menu_seconds_8mhz': (ready - begin) / 8_000_000,
                  'init_cycles': opening - begin,
                  'layers_enabled_before_open': enabled_before_open,
                  'incorrect_visible_frames_during_open': flashes,
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
