"""Boot CHESS.PRG in the X16 AgentBridge emulator and capture screenshots.

Usage:
  python3 tools/screenshot.py [--out build/screenshot.png] [--keys "Right Return ..."]

Keys are SDL key names separated by spaces. Special tokens:
  wait:N            advance N frames
  sec:S             advance S emulated seconds
  shot:PATH         capture a screenshot
  click:X,Y         move the mouse to screen pixel (X, Y) and left-click
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'x16-emulator/api/python'))
from x16agent import X16Agent  # noqa: E402


class Session:
    def __init__(self, emu, rom, fsroot=None):
        fsroot = Path(fsroot or os.environ.get('CHESS_FSROOT', ROOT / 'src'))
        options = ['-prg', str(fsroot / 'CHESS.PRG'), '-run']
        if os.environ.get('CHESS_SDCARD'):
            options += ['-sdcard', os.environ['CHESS_SDCARD']]
        self.emu = X16Agent(emu, rom, fsroot=fsroot, options=options)
        self.mouse = None

    def press(self, key):
        self.emu.request('key', key=key, down=True)
        self.emu.advance(3)
        self.emu.request('key', key=key, down=False)
        self.emu.advance(3)

    def read_mouse(self):
        # the KERNAL keeps sprite 0 (the pointer) at the mouse position
        data = self.emu.read_memory(0x1FC02, 4, space='vram')
        return data[0] | data[1] << 8, data[2] | data[3] << 8

    def move_mouse(self, x, y):
        """Steer the relative mouse until the KERNAL pointer reaches (x, y)."""
        for _ in range(40):
            cx, cy = self.read_mouse()
            dx, dy = x - cx, y - cy
            if dx == 0 and dy == 0:
                return
            self.emu.request('mouse', dx=max(-255, min(255, dx)), dy=max(-255, min(255, dy)))
            self.emu.advance(2)
        raise RuntimeError(f'mouse did not reach {(x, y)}')

    def click(self, x, y):
        self.move_mouse(x, y)
        self.emu.request('mouse', buttons=1)
        self.emu.advance(3)
        self.emu.request('mouse', buttons=0)
        self.emu.advance(3)

    def shot(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        result = self.emu.screenshot(path.resolve())
        assert result['captured'], result
        print(f'saved {path}')

    def run(self, tokens):
        for token in tokens:
            if token.startswith('wait:'):
                self.emu.advance(int(token[5:]))
            elif token.startswith('sec:'):           # emulated seconds (8 MHz)
                cycles = int(float(token[4:]) * 8_000_000)
                while cycles > 0:                     # at most 1e8 cycles per request
                    self.emu.advance(min(cycles, 80_000_000), unit='cycles')
                    cycles -= 80_000_000
            elif token.startswith('shot:'):
                self.shot(token[5:])
            elif token.startswith('click:'):
                x, y = (int(v) for v in token[6:].split(','))
                self.click(x, y)
            else:
                self.press(token)

    def close(self):
        self.emu.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--emu', default=str(ROOT.parent / 'x16-emulator/build/x16emu'))
    roms = [ROOT.parent / 'emulator/rom.bin', ROOT.parent / 'emulator-win/rom.bin']
    parser.add_argument('--rom', default=str(next((r for r in roms if r.exists()), roms[0])))
    parser.add_argument('--out', default=str(ROOT / 'build/screenshot.png'))
    parser.add_argument('--keys', default='')
    parser.add_argument('--boot', type=int, default=240, help='frames to boot and load')
    args = parser.parse_args()

    session = Session(args.emu, args.rom)
    try:
        session.emu.advance(args.boot)
        session.run(args.keys.split())
        session.shot(args.out)
    finally:
        session.close()


if __name__ == '__main__':
    main()
