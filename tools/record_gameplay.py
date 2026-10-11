"""Record a one-minute, 640x480 walkthrough using real emulator input/video."""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'assets/scripts'))
from palette import RGB12, SETUP_RGB12, rgb

SAMPLES = 600
DELAY = 100


def square_name(square):
    return chr(97 + (square & 7)) + str((square >> 4) + 1)


def fen(board, side, castling, ep, halfmove, ply):
    ranks = []
    for rank in reversed(range(8)):
        row, empty = '', 0
        for file in range(8):
            piece = board[rank * 16 + file]
            if not piece:
                empty += 1
                continue
            if empty:
                row += str(empty)
                empty = 0
            letter = ' PNBRQK'[piece & 7]
            row += letter.lower() if piece & 8 else letter
        ranks.append(row + (str(empty) if empty else ''))
    rights = ''.join(c for bit, c in enumerate('KQkq') if castling & (1 << bit)) or '-'
    return f'{"/".join(ranks)} {"b" if side else "w"} {rights} {square_name(ep) if ep != 128 else "-"} {halfmove} {ply // 2 + 1}'


class HumanPlayer:
    """Choose legal moves on the host; enter them only through mouse clicks."""
    def __init__(self, executable):
        self.process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, text=True, bufsize=1)

    def choose(self, position):
        self.process.stdin.write(f'position fen {position}\ngo depth 3\n')
        self.process.stdin.flush()
        for line in self.process.stdout:
            if line.startswith('bestmove '):
                return line.split()[1]
        raise RuntimeError('Native engine ended without choosing a move')

    def close(self):
        self.process.stdin.write('quit\n')
        self.process.stdin.flush()
        self.process.communicate(timeout=10)
        if self.process.returncode:
            raise RuntimeError('Native engine failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--api-dir', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/cx16-chess-gameplay.gif')
    args = parser.parse_args()
    sys.path.insert(0, str(args.api_dir or args.emulator.resolve().parent.parent / 'api/python'))
    try:
        from x16agent import X16Agent
    except ImportError:
        parser.error('AgentBridge Python client not found; supply --api-dir')
    symbols = {name: int(address, 16) for address, name in re.findall(
        r'al ([0-9A-Fa-f]+) \.(\S+)', (ROOT / 'src/CHESS.sym').read_text())}
    colors = list(dict.fromkeys(rgb(i, values) for values in (RGB12, SETUP_RGB12) for i in range(16)))
    palette = Image.new('P', (1, 1))
    palette.putpalette([channel for color in colors for channel in color] + [0] * (768 - len(colors) * 3))
    frames, events = [], []
    speed = 1
    human = HumanPlayer((ROOT / 'tests/uci').resolve())
    try:
        with tempfile.TemporaryDirectory(prefix='chess-recording-') as directory:
            runtime = Path(directory)
            for name in ('CHESS.PRG', 'MENU.BIN', 'UI.BIN', 'CHESS.DAT'):
                shutil.copy2(ROOT / 'src' / name, runtime / name)
            with X16Agent(args.emulator.resolve(), args.rom.resolve(), fsroot=runtime,
                          options=['-prg', str(runtime / 'CHESS.PRG'), '-run']) as emu:
                def read(name, size=1):
                    return int.from_bytes(emu.read_memory(symbols['_' + name], size), 'little')

                def record(count):
                    for _ in range(min(count, SAMPLES - len(frames))):
                        # AgentBridge screenshot advances two display frames.
                        emu.advance(6 * speed - 2)
                        result = emu.screenshot(runtime / 'frame.png')
                        assert result['captured'], result
                        with Image.open(runtime / 'frame.png') as frame:
                            assert frame.size == (640, 480)
                            frames.append(frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE))

                def mark(label, **details):
                    events.append(dict(event=label, seconds=len(frames) / 10, speed=speed, **details))

                def pointer():
                    data = emu.read_memory(0x1FC02, 4, space='vram')
                    return int.from_bytes(data[:2], 'little'), int.from_bytes(data[2:], 'little')

                def move(x, y, samples=4):
                    start_x, start_y = pointer()
                    for step in range(1, samples + 1):
                        t = step / samples
                        eased = t * t * (3 - 2 * t)
                        target_x = round(start_x + (x - start_x) * eased)
                        target_y = round(start_y + (y - start_y) * eased)
                        actual_x, actual_y = pointer()
                        emu.request('mouse', dx=max(-255, min(255, target_x - actual_x)),
                                    dy=max(-255, min(255, target_y - actual_y)))
                        record(1)
                    # Accommodate KERNAL mouse sensitivity and packet delivery.
                    for _ in range(20):
                        actual_x, actual_y = pointer()
                        if (actual_x, actual_y) == (x, y):
                            return
                        emu.request('mouse', dx=max(-255, min(255, x - actual_x)),
                                    dy=max(-255, min(255, y - actual_y)))
                        record(1)
                    raise RuntimeError(f'Pointer did not reach {(x, y)}')

                def click(x, y, samples=4):
                    move(x, y, samples)
                    emu.request('mouse', buttons=1)
                    record(1)
                    emu.request('mouse', buttons=0)
                    record(1)

                def coordinates(square):
                    return 52 + (square & 7) * 56, 36 + (7 - (square >> 4)) * 56

                print('[demo] Recording menus, About, options and game setup...', flush=True)
                emu.advance(480)
                mark('opening')
                record(18)
                click(320, 440)  # About
                record(14)
                click(480, 408)  # Back
                record(5)
                click(320, 424)  # Options
                record(10)
                click(620, 168)  # Wood board preview
                record(7)
                click(496, 168)  # Restore newsprint
                record(5)
                click(620, 240)  # Continental chess set
                record(10)
                click(560, 288)  # Save preferences in disposable filesystem
                record(7)
                click(560, 320)  # Done
                record(5)
                click(320, 376)  # New Game
                record(12)
                click(356, 240)  # Normal -> Easy, human plays White
                record(8)
                click(460, 320)  # Start Game
                for _ in range(30):
                    if read('match_clock', 2) and emu.read_memory(0x9F29)[0] & 0x70 == 0x70:
                        break
                    record(1)
                assert read('match_computer') == 2 and read('match_difficulty') == 0
                assert read('playfield_flipped') == 0 and read('ply', 2) == 0
                mark('human versus computer', difficulty='easy', human='white')
                record(10)
                turns = 0
                while len(frames) < SAMPLES - 25 and read('match_state') == 0:
                    assert read('side') == 0, 'Expected the human turn'
                    if turns == 3:
                        speed = 4
                        mark('accelerated battle')
                        print('[demo] First three turns recorded; speeding up the battle to 4x...', flush=True)
                    old_ply = read('ply', 2)
                    position = fen(emu.read_memory(symbols['_board'], 128), read('side'), read('castling'),
                                   read('ep_square'), read('halfmove_clock'), old_ply)
                    chosen = human.choose(position)
                    assert chosen != '0000', position
                    source = (int(chosen[1]) - 1) * 16 + ord(chosen[0]) - 97
                    target = (int(chosen[3]) - 1) * 16 + ord(chosen[2]) - 97
                    promotion = {'n': 2, 'b': 3, 'r': 4, 'q': 5}.get(chosen[4:], 0)
                    legal = emu.read_memory(symbols['_legal_moves'], read('legal_count') * 4)
                    assert any(legal[i:i + 3] == bytes((source, target, promotion)) for i in range(0, len(legal), 4)), chosen
                    mark('human move', uci=chosen, ply=old_ply + 1)
                    click(*coordinates(source), samples=4 if speed == 1 else 2)
                    record(5 if speed == 1 else 1)  # Show selected piece and legal targets.
                    click(*coordinates(target), samples=4 if speed == 1 else 2)
                    if promotion:
                        emu.request('key', key=chosen[4], down=True)
                        record(1)
                        emu.request('key', key=chosen[4], down=False)
                    for _ in range(120):
                        if read('ply', 2) > old_ply and (read('side') == 0 or read('match_state')):
                            break
                        record(1)  # Keep the CPU thinking indicator and move animation.
                    else:
                        raise RuntimeError(f'Computer did not reply after {chosen}')
                    assert read('ply', 2) > old_ply, 'Mouse move was not entered'
                    if read('ply', 2) == old_ply + 2:
                        reply = square_name(read('match_last_from')) + square_name(read('match_last_to'))
                        mark('computer reply', uci=reply, ply=old_ply + 2)
                    turns += 1
                    record(5 if speed == 1 else 1)
                    if len(frames) >= SAMPLES - 25:
                        break
                assert turns > 3, 'Expected both normal and accelerated gameplay'
                mark('last position', human_turns=turns, ply=read('ply', 2), result=read('match_result'))
                print(f'[demo] Played {turns} human turns ({read("ply", 2)} half moves); encoding GIF...', flush=True)
                # Hold the final genuine board without advancing its clocks.
                frames.extend([frames[-1].copy() for _ in range(SAMPLES - len(frames))])
    finally:
        human.close()
    assert len(frames) == SAMPLES
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(args.output, save_all=True, append_images=frames[1:], duration=DELAY,
                   loop=0, optimize=True, disposal=1)
    with Image.open(args.output) as gif:
        assert gif.size == (640, 480) and gif.info['loop'] == 0
        duration = 0
        for index in range(gif.n_frames):
            gif.seek(index)
            duration += gif.info['duration']
        assert duration == 60_000, duration
        encoded_frames = gif.n_frames
    report = dict(duration_ms=duration, size=[640, 480], fps=10, accelerated_speed=4,
                  first_normal_human_turns=3, encoded_frames=encoded_frames, events=events)
    report_path = ROOT / 'build/demo-recording.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'[demo] Saved {args.output} (60.0s, 640x480, 10 fps, {args.output.stat().st_size:,} bytes)', flush=True)


if __name__ == '__main__':
    main()
