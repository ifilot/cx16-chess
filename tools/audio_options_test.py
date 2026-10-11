"""Exercise audio controls, actual mute, pause state and preference compatibility."""
import os
from pathlib import Path
import shutil
import tempfile
from runtime_files import RUNTIME_FILES
from screenshot import ROOT, Session
from storage_test import digest


def main():
    symbols = {p[2].lstrip('.'): int(p[1], 16)
               for line in (ROOT / 'src/CHESS.sym').read_text().splitlines()
               if len(p := line.split()) == 3}
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    with tempfile.TemporaryDirectory(prefix='chess-audio-options-') as temporary:
        root = Path(temporary)
        for name in RUNTIME_FILES:
            shutil.copyfile(Path(os.environ.get('CHESS_FSROOT', ROOT / 'src')) / name, root / name)
        session = None

        def boot():
            nonlocal session
            if session:
                session.close()
            session = Session(ROOT.parent / 'x16-emulator/build/x16emu', rom, fsroot=root)
            session.emu.advance(480)
            assert read('sound_ready') == 1

        def read(name):
            return session.emu.read_memory(symbols['_' + name], 1)[0]

        def keys(*names):
            for name in names:
                session.press(name)
                session.emu.advance(120)

        def flags():
            return read('sound_music_enabled'), read('sound_effects_enabled')

        def text(cx, row, label, color):
            col = (cx - len(label) * 4 + 4) // 8
            for half in range(2):
                data = bytes(session.emu.read_memory(0x18000 + ((row + half) * 128 + col) * 2,
                                                    len(label) * 2, space='vram'))
                assert [data[i] | ((data[i + 1] & 3) << 8) for i in range(0, len(data), 2)] == [
                    (ord(c) - 32) * 2 + half for c in label], (row, label, data)
                assert all(v >> 4 == color for v in data[1::2]), (row, label, color, data)

        def muted():
            music, effects = flags()
            for voice in range(16):
                if (voice < 12 and not music) or (voice >= 12 and not effects):
                    assert session.emu.read_memory(0x1F9C2 + voice * 4, 1, space='vram')[0] & 63 == 0

        try:
            boot()
            assert flags() == (1, 1)
            # All four combinations survive saving, a restart, and starting a game.
            for music, effects in ((0, 1), (0, 0), (1, 0), (1, 1)):
                keys('o')
                session.move_mouse(560, 272)
                session.emu.advance(12)
                before = flags()
                text(560, 33, 'MUSIC: ON ' if before[0] else 'MUSIC: OFF', 7)
                assert flags() == before, 'Hover must not toggle audio'
                if before[0] != music:
                    session.click(560, 272)
                if before[1] != effects:
                    session.click(560, 304)
                assert flags() == (music, effects)
                session.click(560, 344)
                session.emu.advance(120)
                data = (root / 'CHESSOPT.DAT').read_bytes()
                assert len(data) == 10 and data[:5] == b'X16P5'
                assert data[7] == read('start_computer') | (0 if music else 4) | (0 if effects else 8)
                assert data[9] == digest(data[:9]) & 255
                boot()
                assert flags() == (music, effects)
                muted()
            keys('o', 'Down', 'Down', 'Right')
            assert flags() == (0, 1)
            text(560, 33, 'MUSIC: OFF', 7)
            keys('v')
            text(560, 33, 'MUSIC: ON ', 7)
            keys('Down', 'Left')
            assert flags() == (1, 0)
            text(560, 37, 'SOUNDS: OFF', 7)
            keys('s')
            text(560, 37, 'SOUNDS: ON ', 7)
            keys('Escape', 'n', 'Left', 'Return', 'Escape')
            position = bytes(session.emu.read_memory(symbols['_board'], 128))
            clocks = bytes(session.emu.read_memory(symbols['_match_clock'], 4))
            session.move_mouse(304, 304)
            session.emu.advance(12)
            text(304, 37, 'MUSIC: ON ', 7)
            assert flags() == (1, 1)
            session.click(304, 304)
            assert flags() == (0, 1)
            text(304, 37, 'MUSIC: OFF', 7)
            keys('Down', 'Return')
            assert flags() == (0, 0)
            text(304, 42, 'SOUNDS: OFF', 7)
            muted()
            keys('Left', 'Up', 'Right')
            assert flags() == (1, 1)
            keys('v', 's')
            assert flags() == (0, 0)
            text(304, 37, 'MUSIC: OFF', 7)
            text(304, 42, 'SOUNDS: OFF', 1)
            assert bytes(session.emu.read_memory(symbols['_board'], 128)) == position
            assert bytes(session.emu.read_memory(symbols['_match_clock'], 4)) == clocks
            keys('Escape')
            assert bytes(session.emu.read_memory(symbols['_board'], 128)) == position
            assert flags() == (0, 0)
            muted()
            # Prior formats retain their original interpretation and audio defaults.
            for version in b'1234':
                data = bytearray(b'X16P' + bytes((version, 0, 0, 1, 0, 0)))
                data[9] = digest(data[:9]) & 255
                (root / 'CHESSOPT.DAT').write_bytes(data)
                boot()
                assert flags() == (1, 1)
            # Reject reserved flag bits, or a damaged checksum, without applying fields.
            for control, damage in ((17, False), (13, True)):
                data = bytearray(b'X16P5' + bytes((1, 1, control, 0, 0)))
                data[9] = (digest(data[:9]) & 255) ^ damage
                (root / 'CHESSOPT.DAT').write_bytes(data)
                boot()
                assert flags() == (1, 1)
                assert read('playfield_theme') == 0 and read('start_piece_set') == 0
            print('PASS: separate audio controls, hover, keyboard/shortcuts, immediate PSG mute, frozen pause state, all saved combinations, legacy and malformed preferences')
        finally:
            if session:
                session.close()


if __name__ == '__main__':
    main()
