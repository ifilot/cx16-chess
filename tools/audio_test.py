"""Check banked assets and actual ZSMKit PSG output, including loops and release."""
import os
from pathlib import Path
import re
import shutil
import tempfile

from runtime_files import RUNTIME_FILES, SOUND_FILES
from screenshot import ROOT, Session

PSG = 0x1F9C0


def decode(data):
    assert data[:3] == b'zm\x01'
    assert not any(data[6:10]), 'Only PSG music is expected'
    assert int.from_bytes(data[12:14], 'little') == 60
    loop = int.from_bytes(data[3:6], 'little')
    mask = int.from_bytes(data[10:12], 'little')
    frames, loop_tick, pos = [[]], None, 16
    while pos < len(data):
        if loop and pos == loop:
            loop_tick = len(frames) - 1
        cmd = data[pos]
        pos += 1
        if cmd < 64:
            frames[-1].append((cmd, data[pos]))
            pos += 1
        elif cmd == 128:
            break
        elif cmd > 128:
            frames.extend([] for _ in range(cmd & 127))
        else:
            raise AssertionError(('Unexpected non-PSG command', cmd))
    if not frames[-1]:
        frames.pop()
    return frames, loop_tick, mask


def main():
    symbols = {p[2].lstrip('.'): int(p[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(p := line.split()) == 3}
    runtime = Path(os.environ.get('CHESS_FSROOT', ROOT / 'src'))
    music = (ROOT / 'assets/sound/music.h').read_text()
    banks = {name: int(bank) for name, bank in re.findall(r'#define MUSIC_(\w+)_BANK (\d+)', music)}
    offsets = {name: int(offset, 16) for name, offset in re.findall(
        r'#define (SFX_\w+)\s+(0x[0-9A-Fa-f]+)', (ROOT / 'assets/sound/sfx.h').read_text()) if name != 'SFX_BANK_ADDR'}
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-audio-') as temporary:
        folder = Path(temporary)
        for name in RUNTIME_FILES:
            shutil.copyfile(runtime / name, folder / name)
        session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=folder)
        try:
            session.emu.advance(480)
            assert session.emu.read_memory(symbols['_sound_ready'])[0] == 1
            for name in SOUND_FILES:
                data = (ROOT / 'assets/sound' / name).read_bytes()
                bank = 25 if name == 'SFX.BIN' else banks[name.split('.')[0]]
                actual = b''.join(bytes(session.emu.read_memory(0, min(8192, len(data) - pos),
                    space='banked_ram', bank=bank + pos // 8192)) for pos in range(0, len(data), 8192))
                assert actual == data, ('Loaded audio differs from asset', name)
            print('PASS: all audio files loaded exactly across RAM banks 25–43', flush=True)
            # Park the main loop. A private machine-code caller drives real player
            # ticks with IRQ masked, making every sampled register deterministic.
            stop = symbols['_cbm_k_getin']
            session.emu.request('breakpoint', address=stop, bank=0)
            saved = session.emu.advance(120)['state']
            assert saved['pc'] == stop
            session.emu.request('breakpoint', action='remove', address=stop, bank=0)
            scratch = bytes(session.emu.read_memory(0x0400, 64))

            def invoke(name, arg=0):
                address = symbols[name]
                session.emu.write_memory(0x0400, bytes((0x20, address & 255, address >> 8, 0x4C, 3, 4)))
                session.emu.request('set_registers', pc=0x0400, a=arg & 255, x=arg >> 8,
                                    p=saved['p'] | 4, sp=saved['sp'])
                session.emu.request('breakpoint', address=0x0403, bank=0)
                result = session.emu.advance(100_000, unit='instructions')
                session.emu.request('breakpoint', action='remove', address=0x0403, bank=0)
                assert result['reason'] == 'breakpoint', (name, result)

            def ticks(count):
                address = symbols['zsm_tick']
                session.emu.write_memory(0x0400, bytes((0xA9, 0, 0x20, address & 255, address >> 8,
                    0xCE, 0x30, 4, 0xD0, 0xF6, 0x4C, 0x0A, 4)))
                session.emu.write_memory(0x0430, bytes((count,)))
                session.emu.request('set_registers', pc=0x0400, p=saved['p'] | 4, sp=saved['sp'])
                session.emu.request('breakpoint', address=0x040A, bank=0)
                result = session.emu.advance(1_000_000, unit='instructions')
                session.emu.request('breakpoint', action='remove', address=0x040A, bank=0)
                assert result['reason'] == 'breakpoint', result

            def verify(label, data, function, arg):
                frames, loop, mask = decode(data)
                invoke(function, arg)
                state = list(session.emu.read_memory(PSG, 64, space='vram'))
                registers = [r for r in range(64) if mask >> (r // 4) & 1]
                idx = 0
                remaining = len(frames) + 120
                while remaining:
                    count = min(13, remaining)
                    for _ in range(count):
                        if idx >= len(frames):
                            if loop is not None:
                                idx = loop
                            else:
                                for reg in registers:
                                    if reg & 3 == 2:
                                        state[reg] = 0
                        if idx < len(frames):
                            for reg, value in frames[idx]:
                                state[reg] = value
                            idx += 1
                    ticks(count)
                    actual = session.emu.read_memory(PSG, 64, space='vram')
                    assert all(actual[r] == state[r] for r in registers), (label, len(frames) + 120 - remaining,
                        [(r, actual[r], state[r]) for r in registers if actual[r] != state[r]][:8])
                    remaining -= count
                print(f'PASS: {label} matches every sampled PSG register through its end/loop', flush=True)

            for name in SOUND_FILES:
                if name.endswith('.ZSM'):
                    verify(name, (ROOT / 'assets/sound' / name).read_bytes(), '_sound_music', banks[name.split('.')[0]])
            effects = (ROOT / 'assets/sound/SFX.BIN').read_bytes()
            for name, offset in offsets.items():
                verify(name, effects[offset:], '_sound_sfx', offset)
            # Restore the game and check that its live IRQ advances while a
            # genuine engine search runs, without disk reads or damaged graphics.
            invoke('_sound_music', banks['TITLE'])
            session.emu.write_memory(0x0400, scratch)
            session.emu.request('set_registers', **{k: saved[k] for k in ('pc', 'a', 'x', 'y', 'p', 'sp')})
            session.press('n')
            session.emu.advance(120)
            session.press('Right')  # computer plays white
            session.emu.advance(120)
            session.emu.request('breakpoint', address=symbols['_engine_search'], bank=0)
            session.press('Return')
            result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint'
            assert session.emu.read_memory(symbols['_match_think_depth'])[0] == 4
            session.emu.request('breakpoint', action='remove', address=symbols['_engine_search'], bank=0)
            previous = session.emu.read_memory(PSG, 48, space='vram')
            session.emu.request('breakpoint', address=symbols['_bank_load_raw'], bank=0)
            result = session.emu.advance(60)
            assert result['reason'] != 'breakpoint', 'Engine search streamed audio from disk'
            session.emu.request('breakpoint', action='remove', address=symbols['_bank_load_raw'], bank=0)
            assert session.emu.read_memory(PSG, 48, space='vram') != previous
            session.emu.advance(600)
            assert int.from_bytes(session.emu.read_memory(symbols['_ply'], 2), 'little') == 1
            session.press('v')
            session.emu.advance(5)
            assert all(session.emu.read_memory(PSG + 4 * voice + 2, 1, space='vram')[0] & 63 == 0 for voice in range(12))
            session.press('v')
            session.press('s')
            assert session.emu.read_memory(symbols['_sound_effects_enabled'])[0] == 0
            print('PASS: music advances through a real engine search with no disk reads; music/effect toggles work', flush=True)
            session.emu.request('breakpoint', address=stop, bank=0)
            saved = session.emu.advance(120)['state']
            session.emu.request('breakpoint', action='remove', address=stop, bank=0)
            assert saved['pc'] == stop
            invoke('_sound_event', 9)  # re-enable effects

            def write(name, value):
                session.emu.write_memory(symbols['_' + name], bytes((value,)))

            def player_value(name, priority=0):
                return session.emu.read_memory(symbols[name] - 0xA000 + priority, 1,
                    space='banked_ram', bank=44)[0]

            write('side', 0)
            write('match_state', 0)
            # Exactly one effect, including competing capture/promotion flags.
            for event, flags, expected in ((6, 0, 'SFX_MOVE'), (7, 0, 'SFX_MOVE_CPU'),
                    (6, 1, 'SFX_CAPTURE'), (6, 3, 'SFX_CAPTURE'),
                    (6, 5, 'SFX_CASTLE'), (6, 17, 'SFX_PROMOTE')):
                write('match_last_flags', flags)
                invoke('_sound_event', event)
                pointer = player_value('zsm_ptr_l', 1) | player_value('zsm_ptr_h', 1) << 8
                assert pointer == 0xA000 + offsets[expected] + 16, (expected, pointer)
            board = bytearray(128)
            board[4], board[116], board[20] = 6, 14, 12  # e1/e8 kings, black rook e2
            session.emu.write_memory(symbols['_board'], board)
            invoke('_sound_event', 6)
            pointer = player_value('zsm_ptr_l', 1) | player_value('zsm_ptr_h', 1) << 8
            assert pointer == 0xA000 + offsets['SFX_CHECK'] + 16
            print('PASS: check > promotion > castle > capture > move, en passant, distinct CPU knock', flush=True)
            for computer, result, expected in (
                    (2, 1, 'WIN'), (2, 2, 'LOSE'), (2, 3, 'WIN'), (2, 4, 'LOSE'),
                    (1, 1, 'LOSE'), (1, 2, 'WIN'), (0, 2, 'WIN'), (3, 2, 'WIN'),
                    *((2, result, 'DRAW') for result in range(5, 11))):
                write('match_state', 0)
                write('match_computer', computer)
                invoke('_sound_event', 2)
                write('match_state', 1)
                write('match_result', result)
                invoke('_sound_event', 4)
                assert player_value('zsm_ptr_bank') == banks[expected], (computer, result, expected)
                assert player_value('loop_enable') == 0
                ticks(13)
                position = (player_value('zsm_ptr_l'), player_value('zsm_ptr_h'))
                invoke('_sound_event', 4)
                assert (player_value('zsm_ptr_l'), player_value('zsm_ptr_h')) == position, 'Result jingle restarted'
            print('PASS: human win/loss, decisive local/demo results, every draw cause, result jingles play once', flush=True)
        finally:
            session.close()


if __name__ == '__main__':
    main()
