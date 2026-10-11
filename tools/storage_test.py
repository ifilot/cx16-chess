"""Exercise disk slots, transactional reads, pause UI and preferences on X16.

Uses a private filesystem so tests never read or overwrite a player's saves.
"""
from runtime_files import RUNTIME_FILES
from pathlib import Path
import os
import shutil
import tempfile

from screenshot import ROOT, Session


def digest(data):
    value = 0xA761
    for byte in data:
        value = ((value << 5) ^ (value >> 11) ^ byte) & 0xffff
    return value


def main():
    symbols = {}
    for line in (ROOT / 'src/CHESS.sym').read_text().splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2].lstrip('.')] = int(parts[1], 16)
    emu = ROOT.parent / 'x16-emulator/build/x16emu'
    rom = next(p for p in (ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin') if p.exists())
    output = ROOT / 'build/storage'
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix='chess-storage-') as temporary:
        fsroot = Path(temporary)
        for name in RUNTIME_FILES:
            shutil.copyfile(Path(os.environ.get('CHESS_FSROOT', ROOT / 'src')) / name, fsroot / name)
        session = None

        def boot():
            nonlocal session
            if session:
                session.close()
            session = Session(emu, rom, fsroot=fsroot)
            session.emu.advance(480)

        def read(name, size=1):
            return bytes(session.emu.read_memory(symbols['_' + name], size))

        def keys(*names):
            for name in names:
                session.press(name)
                session.emu.advance(120)

        def shot(name):
            session.move_mouse(639, 479)
            session.shot(output / (name + '.png'))

        def text_at(col, row, text):
            data = bytes(session.emu.read_memory(0x18000 + (row * 128 + col) * 2, len(text) * 2, space='vram'))
            tiles = [data[i] | ((data[i + 1] & 3) << 8) for i in range(0, len(data), 2)]
            assert tiles == [(ord(c) - 32) * 2 for c in text], (col, row, text, tiles)

        def navigate(key, col, row, text, clear_message=False):
            # Stop on any border redraw or panel clear, including transient
            # writes that a completed screenshot would miss.
            names = ['video_tile']
            if not clear_message:
                names.append('video_clear_block')
            for name in names:
                session.emu.request('breakpoint', address=symbols['_' + name], bank=0)
            try:
                session.emu.request('key', key=key, down=True)
                result = session.emu.advance(3)
                assert result['reason'] != 'breakpoint', (key, 'navigation redrew the panel', result)
                session.emu.request('key', key=key, down=False)
                result = session.emu.advance(120)
                assert result['reason'] != 'breakpoint', (key, 'navigation redrew the panel', result)
            finally:
                for name in names:
                    session.emu.request('breakpoint', action='remove', address=symbols['_' + name], bank=0)
            text_at(col, row, text)
            for half in range(2):
                data = bytes(session.emu.read_memory(
                    0x18000 + ((row + half) * 128 + col) * 2, len(text) * 2, space='vram'))
                assert all(byte >> 4 == 7 for byte in data[1::2]), (key, 'missing red selection')

        def paused():
            return {name: read(name, size) for name, size in (
                ('board', 128), ('side', 1), ('castling', 1), ('ep_square', 1),
                ('halfmove_clock', 1), ('ply', 2), ('match_clock', 4),
                ('match_result', 1), ('match_state', 1), ('match_computer', 1),
                ('match_difficulty', 1), ('playfield_theme', 1), ('start_piece_set', 1),
                ('playfield_flipped', 1), ('playfield_info', 1))}

        def save(slot, overwrite=False):
            keys(str(slot), 'Return')
            if overwrite:
                keys('Down', 'Return')

        def load(slot):
            keys('l', str(slot))
            address = symbols['_playfield_loaded']
            session.emu.request('breakpoint', address=address, bank=0)
            session.emu.request('key', key='Return', down=True)
            result = session.emu.advance(600)
            assert result['reason'] == 'breakpoint', result
            # Inspect the restored match before its clocks begin running again.
            assert paused() == snapshot
            session.emu.request('breakpoint', action='remove', address=address, bank=0)
            session.emu.request('key', key='Return', down=False)
            keys('Escape')

        def move(source, target):
            def coordinates(square):
                return 52 + (ord(square[0]) - ord('a')) * 56, 36 + (8 - int(square[1])) * 56
            session.click(*coordinates(source))
            session.emu.advance(30)
            session.click(*coordinates(target))
            session.emu.advance(60)

        try:
            boot()
            keys('n')
            keys('Left', 'Return')  # local two-player game
            for source, target in [('e2', 'e4'), ('e7', 'e5'), ('g1', 'f3'), ('b8', 'c6'),
                                   ('f1', 'b5'), ('a7', 'a6'), ('b5', 'a4'), ('g8', 'f6'), ('e1', 'g1')]:
                move(source, target)
            shot('before-pause')
            assert int.from_bytes(read('ply', 2), 'little') == 9, paused()
            keys('Escape')
            snapshot = paused()
            shot('pause')
            navigate('Up', 33, 42, 'SOUNDS: ON ')
            navigate('Up', 33, 37, 'MUSIC: ON ')
            navigate('Up', 34, 32, 'MAIN MENU')
            navigate('Up', 34, 27, 'SAVE GAME')
            navigate('Up', 33, 22, 'RESUME GAME')
            navigate('Down', 34, 27, 'SAVE GAME')
            navigate('Up', 33, 22, 'RESUME GAME')
            session.emu.advance(600)
            assert paused() == snapshot, 'Pause dialog must freeze both clocks and the position'
            keys('Down', 'Return')
            shot('slots')
            navigate('Up', 21, 41, '9')
            navigate('Down', 21, 17, '1')
            navigate('5', 21, 29, '5')
            navigate('5', 21, 29, '5')  # selecting the same slot does no drawing
            navigate('1', 21, 17, '1')
            for slot in range(1, 10):
                save(slot)
                data = (fsroot / f'CHESS{slot}A.SAV').read_bytes()
                assert len(data) == 28 + 9 * 3 and data[:8] == b'X16SAVE4'
                assert digest(data[:26] + data[28:]) == int.from_bytes(data[26:28], 'little')
                assert paused() == snapshot
            text_at(26, 17, 'LOCAL')
            text_at(35, 17, 'BOTH')
            text_at(45, 17, '9')
            shot('saved')
            navigate('1', 26, 17, 'LOCAL', clear_message=True)
            text_at(31, 44, 'W/B: PLY OR B/E')
            navigate('Down', 35, 20, 'BOTH')
            navigate('Up', 45, 17, '9')
            keys('Return')
            navigate('Down', 35, 28, 'REPLACE')
            navigate('Down', 35, 23, 'CANCEL')
            navigate('Up', 35, 28, 'REPLACE')
            navigate('Up', 35, 23, 'CANCEL')
            keys('Return')
            # Overwriting requires an explicit Replace, with Cancel selected first.
            first = (fsroot / 'CHESS1A.SAV').read_bytes()
            keys('1', 'Return', 'Return')
            assert not (fsroot / 'CHESS1B.SAV').exists()
            save(1, overwrite=True)
            assert (fsroot / 'CHESS1A.SAV').read_bytes() == first
            assert int.from_bytes((fsroot / 'CHESS1B.SAV').read_bytes()[8:10], 'little') == 2
            # Simulate a failed open for the next generation; the valid B survives.
            (fsroot / 'CHESS1A.SAV').unlink()
            (fsroot / 'CHESS1A.SAV').mkdir()
            save(1, overwrite=True)
            assert (fsroot / 'CHESS1B.SAV').exists()
            (fsroot / 'CHESS1A.SAV').rmdir()
            (fsroot / 'CHESS1A.SAV').write_bytes(first)
            # Main Menu retains the current game, and Continue restores its board.
            session.click(304, 384)  # Back from save slots, then Main Menu.
            session.emu.advance(120)
            session.click(304, 264)
            session.emu.advance(120)
            assert paused() == snapshot
            keys('c', 'Escape')
            assert paused()['board'] == snapshot['board']
            keys('Down', 'Down', 'Return')
            # Change and explicitly persist board/pieces.
            keys('o', 'Right', 'Down', 'Right', 'Down', 'Down', 'Down', 'Return')
            assert (fsroot / 'CHESSOPT.DAT').exists()
            session.click(560, 344)  # Save Preferences also supports the mouse.
            session.emu.advance(120)
            assert read('playfield_theme') == b'\x01' and read('start_piece_set') == b'\x01'
            shot('preferences')
            keys('Escape')
            boot()
            assert read('playfield_theme') == b'\x01' and read('start_piece_set') == b'\x01'
            assert read('start_computer') == b'\x00'
            # Disk load is available immediately after boot, independently of Continue.
            load(9)
            shot('restored')
            # A damaged newest generation falls back to the previous checked copy.
            keys('Down', 'Down', 'Return')
            (fsroot / 'CHESS1B.SAV').write_bytes(b'truncated')
            load(1)
            # Corrupt both copies: loading cannot change the live game.
            keys('Down', 'Down', 'Return')
            (fsroot / 'CHESS2A.SAV').write_bytes(b'truncated')
            current = paused()
            keys('l', '2', 'Return')
            assert paused() == current
            keys('Escape', 'c', 'Escape')
            current = paused()
            assert current['board'] == snapshot['board']
            # A structurally correct/checksummed file with an illegal move is rejected
            # after validation, with all live rule state and clocks restored.
            bad = bytearray(first)
            bad[28] = 0x88
            bad[26:28] = digest(bad[:26] + bad[28:]).to_bytes(2, 'little')
            (fsroot / 'CHESS3A.SAV').write_bytes(bad)
            keys('Down', 'Down', 'Return', 'l', '3', 'Return')
            assert paused() == current
            keys('Escape', 'c', 'Escape')
            current = paused()
            assert current['board'] == snapshot['board']
            # Independent coordinate fixtures also cover en passant, promotion,
            # and an engine repetition draw after rebuilding history from disk.
            def fixture(sequence):
                payload = bytearray()
                for source, target, promotion in sequence:
                    def square(value):
                        return (int(value[1]) - 1) * 16 + ord(value[0]) - ord('a')
                    payload.extend((square(source), square(target), promotion))
                record = bytearray(first[:28]) + payload
                record[10:12] = len(sequence).to_bytes(2, 'little')
                record[18:20] = b'\0\0'
                record[26:28] = digest(record[:26] + record[28:]).to_bytes(2, 'little')
                (fsroot / 'CHESS4A.SAV').write_bytes(record)

            keys('Down', 'Down', 'Return')
            fixture([(a, b, 0) for a, b in [('e2', 'e4'), ('a7', 'a6'), ('e4', 'e5'), ('d7', 'd5')]])
            keys('l', '4', 'Return', 'Escape')
            assert read('ep_square') == b'\x53' and int.from_bytes(read('ply', 2), 'little') == 4
            keys('Escape')
            move('e5', 'd6')
            assert read('board', 128)[0x43] == 0 and read('board', 128)[0x53] == 1
            keys('Escape', 'Down', 'Down', 'Return')
            fixture([(a, b, 0) for a, b in [('a2', 'a4'), ('h7', 'h5'), ('a4', 'a5'), ('h5', 'h4'),
                                          ('a5', 'a6'), ('h4', 'h3'), ('a6', 'b7'), ('h3', 'g2')]] +
                    [('b7', 'a8', 5), ('g2', 'h1', 2)])
            keys('l', '4', 'Return', 'Escape')
            assert read('board', 128)[0x70] == 5 and read('board', 128)[7] == 10
            assert int.from_bytes(read('ply', 2), 'little') == 10
            keys('Down', 'Down', 'Return')
            fixture([(a, b, 0) for a, b in [('g1', 'f3'), ('g8', 'f6'), ('f3', 'g1'), ('f6', 'g8'),
                                          ('g1', 'f3'), ('g8', 'f6'), ('f3', 'g1')]])
            keys('l', '4', 'Return', 'Escape', 'Escape')
            move('f6', 'g8')
            assert read('match_state') == b'\x01' and read('match_result') == b'\x06'
            # Existing-format saves expose metadata without a format migration.
            for slot in range(1, 10):
                record = bytearray(first[:28]) + first[28:28 + (slot - 1) * 3]
                record[10:12] = (slot - 1).to_bytes(2, 'little')
                record[16] = (slot - 1) // 3
                record[7] = ord('1')  # Legacy levels must migrate without changing checksums.
                record[17] = (slot - 1) % 3
                record[26:28] = digest(record[:26] + record[28:]).to_bytes(2, 'little')
                (fsroot / f'CHESS{slot}A.SAV').write_bytes(record)
                (fsroot / f'CHESS{slot}B.SAV').unlink(missing_ok=True)
            boot()
            keys('l')
            text_at(26, 14, 'LEVEL')
            text_at(35, 14, 'PLAYER')
            text_at(45, 14, 'MOVES')
            for index in range(9):
                row = 17 + index * 3
                text_at(26, row, 'LOCAL' if index < 3 else ('2', '4', '6')[index % 3])
                text_at(35, row, ('BOTH', 'BLACK', 'WHITE')[index // 3])
                text_at(45, row, str(index))
            shot('metadata')
            # Hover may select a slot underneath the initial pointer.
            keys('1')
            navigate('Down', 26, 20, 'LOCAL')
            navigate('9', 26, 41, '6')
            navigate('Down', 35, 17, 'BOTH')
            keys('9', 'Return')
            assert read('match_difficulty') == b'\x04', 'Legacy Hard save must load as 6 ply'
            # Preference formats use different packing bases. Exercise legacy
            # independent levels and the highest new level for both computers.
            for magic, packed, white, black in ((b'X16P1', 7, 2, 4), (b'X16P2', 24, 4, 4), (b'X16P3', 62, 6, 7), (b'X16P4', 98, 8, 9)):
                preferences = bytearray(magic + bytes((0, 0, 3, packed, 0)))
                preferences[9] = digest(preferences[:9]) & 255
                (fsroot / 'CHESSOPT.DAT').write_bytes(preferences)
                boot()
                assert read('start_difficulty') == bytes((white,))
                assert read('start_black_difficulty') == bytes((black,))
            print('PASS: nine restart-persistent slots, castling/en passant/promotions/repetition/history/clocks, incremental dialog navigation, pause and Continue, overwrite confirmation, failed write, damaged-copy fallback, transactional malformed replay, persisted options')
        finally:
            if session:
                session.close()


if __name__ == '__main__':
    main()
