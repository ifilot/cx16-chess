"""Build all VERA graphics for the playing field.

Outputs (in the given directory, normally src/):
  L0TILES.DAT   layer-0 4bpp 8x8 tiles (deduplicated background)
  L0PLAIN.DAT   layer-0 128x64 map: masthead, board, status bar
  L0INFO.DAT    layer-0 128x64 map: the same plus the side columns
  SQTILES.DAT   layer-0 entries of every board square variant (banked RAM)
  L1TILES.DAT   layer-1 4bpp 8x8 tiles: font, pieces, clock digits, letters
  SPRITES.DAT   mouse pointer (16x16) and keyboard cursor (64x64), 4bpp
  PALETTE.DAT   512-byte VERA palette
  gfx.h         layout constants
  playfield.png, playfield-info.png  previews (not loaded by the game)
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import layout as L
from palette import (ALERT, CREAM, DARK, DARK_GRAIN, DARK_GREY, DEEP_RED, HL_DARK, HL_LIGHT,
                     INK, PAPER, RED, SHADE, TEXTURE, WHITE, pil_palette, vera_palette)

ASSETS = Path(__file__).resolve().parents[1]
W, H = 640, 480


def load_indexed(path):
    image = Image.open(path)
    assert image.mode == 'P', f'{path} must be an indexed PNG'
    return np.asarray(image).copy()


FONT = load_indexed(ASSETS / 'font/font8x16.png')
DIGITS = load_indexed(ASSETS / 'font/digits16x32.png')
PIECES = load_indexed(ASSETS / 'pieces/pieces.png')
MASTHEAD = load_indexed(ASSETS / 'art/masthead.png')
PHOTO = load_indexed(ASSETS / 'art/photo.png')

ROOK = ['#.#.#.#.#', '#########', '.#######.', '..#####..', '..#####..', '..#####..',
        '..#####..', '..#####..', '.#######.', '#########', '#########']

# small letters a-h for the corners of the bottom row of squares (4x5)
FILE_LETTERS = {
    'a': ['.##.', '...#', '.###', '#..#', '.###'],
    'b': ['#...', '###.', '#..#', '#..#', '###.'],
    'c': ['.##.', '#..#', '#...', '#..#', '.##.'],
    'd': ['...#', '.###', '#..#', '#..#', '.###'],
    'e': ['.##.', '#..#', '####', '#...', '.##.'],
    'f': ['..##', '.#..', '###.', '.#..', '.#..'],
    'g': ['.###', '#..#', '.###', '...#', '.##.'],
    'h': ['#...', '###.', '#..#', '#..#', '#..#'],
}


# --------------------------------------------------------------------------
# drawing primitives (inclusive coordinates)
# --------------------------------------------------------------------------
def fill(img, x0, y0, x1, y1, colour):
    img[y0:y1 + 1, x0:x1 + 1] = colour


def frame(img, x0, y0, x1, y1, colour, t=1):
    fill(img, x0, y0, x1, y0 + t - 1, colour)
    fill(img, x0, y1 - t + 1, x1, y1, colour)
    fill(img, x0, y0, x0 + t - 1, y1, colour)
    fill(img, x1 - t + 1, y0, x1, y1, colour)


def double_frame(img, x0, y0, x1, y1, colour=INK):
    """Newspaper box: heavy outer rule, hairline inside."""
    frame(img, x0, y0, x1, y1, colour, 2)
    frame(img, x0 + 3, y0 + 3, x1 - 3, y1 - 3, colour, 1)


def blit(img, x, y, sprite, remap=None):
    h, w = sprite.shape
    h, w = min(h, img.shape[0] - y), min(w, img.shape[1] - x)      # clip
    sprite = sprite[:h, :w]
    region = img[y:y + h, x:x + w]
    for src in np.unique(sprite):
        if src == 0:
            continue
        region[sprite == src] = remap.get(int(src), src) if remap else src


def glyph(code):
    slot = code - 32
    return FONT[(slot // 16) * 16:(slot // 16) * 16 + 16, (slot % 16) * 8:(slot % 16) * 8 + 8]


def text(img, x, y, string, colour):
    """Fixed 8x16 font (the one layer 1 uses for dynamic text)."""
    for i, char in enumerate(string.encode('cp1251')):
        blit(img, x + 8 * i, y, glyph(char), {INK: colour})


def text_centered(img, x0, x1, y, string, colour):
    text(img, (x0 + x1 + 1 - 8 * len(string)) // 2, y, string, colour)


class PropFont:
    """Proportional font sheet written by make_sources.py."""

    def __init__(self, name):
        self.sheet = load_indexed(ASSETS / f'font/{name}.png')
        meta = json.loads((ASSETS / f'font/{name}.json').read_text())
        self.cw, self.ch = meta['cell']
        self.baseline = meta['baseline']
        self.advance = meta['advance']

    def width(self, string, tracking=0):
        codes = string.encode('cp1251')
        return sum(self.advance[c - 32] + tracking for c in codes) - tracking

    def draw(self, img, x, baseline, string, colour, tracking=0):
        for c in string.encode('cp1251'):
            slot = c - 32
            cell = self.sheet[(slot // 16) * self.ch:(slot // 16 + 1) * self.ch,
                              (slot % 16) * self.cw:(slot % 16 + 1) * self.cw]
            blit(img, x, baseline - self.baseline, cell, {INK: colour})
            x += self.advance[slot] + tracking

    def centered(self, img, cx, baseline, string, colour, tracking=0):
        self.draw(img, cx - self.width(string, tracking) // 2, baseline, string, colour, tracking)

    def right(self, img, x1, baseline, string, colour, tracking=0):
        self.draw(img, x1 + 1 - self.width(string, tracking), baseline, string, colour, tracking)


HEADLINE = PropFont('headline')
SMALL = PropFont('small')
ITALIC = PropFont('italic')


def piece_image(index):
    return PIECES[:, index * L.SQUARE:(index + 1) * L.SQUARE]


# --------------------------------------------------------------------------
# artwork
# --------------------------------------------------------------------------
def grain(x, y):
    return ((y % 4 == 0) & (x % 4 == 0)) | ((y % 4 == 2) & (x % 4 == 2))


def square_image(theme, light, state):
    """Board square of a style in a highlight state.

    NEWSPRINT is a printed chess diagram: plain paper for light squares and
    diagonal hatching for dark ones. WOOD is the brown board of the mockups.
    """
    s = L.SQUARE
    c = (s - 1) / 2
    y, x = np.mgrid[0:s, 0:s]
    highlighted = state in ('LASTMOVE', 'SELECTED')
    if theme == 'NEWSPRINT':
        hatch = (x + y) % 3 == 0
        a = np.full((s, s), HL_LIGHT if highlighted else PAPER, np.uint8)
        if not light:
            a[hatch] = HL_DARK if highlighted else DARK_GREY
    else:
        base, speck = (SHADE, TEXTURE) if light else (DARK, DARK_GRAIN)
        a = np.where(grain(x, y), speck, base).astype(np.uint8)
        if highlighted:
            a[:] = HL_LIGHT if light else HL_DARK
    r2 = (x - c) ** 2 + (y - c) ** 2
    if state == 'SELECTED':
        frame(a, 2, 2, s - 3, s - 3, RED, 2)
    elif state == 'TARGET':
        a[r2 <= 7.5 ** 2] = DEEP_RED
    elif state == 'CAPTURE':
        corner = (x + y < 14) | ((s - 1 - x) + y < 14) | (x + (s - 1 - y) < 14) | \
                 ((s - 1 - x) + (s - 1 - y) < 14)
        a[corner] = DEEP_RED
    elif state == 'CHECK':
        a[(r2 <= 25.5 ** 2) & ((x + y) % 2 == 0)] = ALERT
        a[r2 <= 18.5 ** 2] = ALERT
    return a


def newsprint(img, keep_out):
    """Sprinkle specks over plain paper, outside the given rectangles.

    The pattern repeats every 16 pixels, so blank paper stays a handful of
    tiles.
    """
    mask = np.zeros(img.shape, bool)
    mask[3::16, 1::16] = True
    mask[11::16, 9::16] = True
    mask[6::16, 13::16] = True
    for x0, y0, x1, y1 in keep_out:
        mask[y0:y1 + 1, x0:x1 + 1] = False
    img[mask & (img == PAPER)] = SHADE


def render(info):
    img = np.full((H, W), PAPER, np.uint8)
    bx, by, bs = L.BOARD_X, L.BOARD_Y, 8 * L.SQUARE

    # ---- masthead strip ------------------------------------------------
    left = '№ 1  ·  ЯНВАРЬ 1985  ·  МОСКВА'
    right = 'СОВЕТСКАЯ ШАХМАТНАЯ ГАЗЕТА'
    SMALL.draw(img, 4, 11, left, INK, tracking=1)
    lw = SMALL.width(left, 1)
    rx = 615 - SMALL.width(right, 1)
    SMALL.right(img, 614, 11, right, INK, tracking=1)
    mh, mw = MASTHEAD.shape
    tx = 320 - mw // 2
    blit(img, tx, 0, MASTHEAD)
    for y in (5, 8):                                  # double rules to the title
        fill(img, 4 + lw + 8, y, tx - 8, y, INK)
        fill(img, tx + mw + 8, y, rx - 8, y, INK)
    fill(img, 620, 1, 635, 13, RED)                   # rook emblem
    rook = np.array([[c == '#' for c in row] for row in ROOK])
    img[2:13, 624:633][rook] = CREAM

    # ---- board ---------------------------------------------------------
    frame(img, bx - 2, by - 2, bx + bs + 1, by + bs + 1, INK, 2)
    for rank in range(8):
        for file in range(8):
            img[by + rank * 56:by + rank * 56 + 56, bx + file * 56:bx + file * 56 + 56] = \
                square_image('NEWSPRINT', (rank + file) % 2 == 0, 'NORMAL')

    # ---- status bar ----------------------------------------------------
    fill(img, 0, 464, 639, 465, INK)
    ax0, ax1 = L.ANALYSE_BUTTON
    fill(img, ax0, 467, ax1, 479, RED)
    text_centered(img, ax0, ax1, 464, 'АНАЛИЗ', CREAM)
    ix0, ix1 = L.INFO_BUTTON
    fill(img, ix0, 467, ix1, 479, RED)
    fill(img, (ix0 + ix1) // 2 - 6, 472, (ix0 + ix1) // 2 + 5, 473, CREAM)   # "—"
    for x in L.STATUS_SEPARATORS:
        fill(img, x, 468, x, 478, INK)
    for col, label in ((L.STATUS_TURN_COL, 'ХОД:'), (L.STATUS_BEST_COL, 'ЛУЧШИЙ ХОД:'),
                       (L.STATUS_EVAL_COL, 'ОЦЕНКА:')):
        SMALL.right(img, col * 8 - 5, 476, label, INK, tracking=1)

    keep_out = [(bx - 2, by - 2, bx + bs + 1, by + bs + 1)]

    # ---- side columns (INFO view) --------------------------------------
    if info:
        x0, x1 = L.LEFT_X0, L.LEFT_X1
        for side in ('top', 'bottom'):
            py = L.PLATE_Y[side]
            fill(img, x0, py, x1, py + 47, RED)
            frame(img, x0 + 2, py + 2, x1 - 2, py + 45, CREAM)
            cy = L.CLOCK_Y[side]
            double_frame(img, x0, cy, x1, cy + 47)
        py = L.PHOTO_Y
        frame(img, x0, py, x1, py + 91, INK)
        ph, pw = PHOTO.shape
        img[py + 2:py + 2 + ph, (x0 + x1 + 1 - pw) // 2:(x0 + x1 + 1 + pw) // 2] = PHOTO
        ITALIC.centered(img, (x0 + x1 + 1) // 2, py + 103, 'Из архива', INK)
        keep_out.append((x0, py, x1, py + 91))

        rx0, rx1 = L.RIGHT_X0, L.RIGHT_X1
        HEADLINE.centered(img, (rx0 + rx1 + 1) // 2, 39, 'ХОДЫ', INK)
        fill(img, rx0, 44, rx1, 45, INK)
        fill(img, rx0, 47, rx1, 47, INK)
        fill(img, rx0, 456, rx1, 456, INK)
    newsprint(img, keep_out)
    return img


# --------------------------------------------------------------------------
# tile encoding
# --------------------------------------------------------------------------
def pack4(pixels):
    flat = pixels.reshape(-1)
    return bytes(int(flat[i]) << 4 | int(flat[i + 1]) for i in range(0, len(flat), 2))


class TileSet:
    def __init__(self, size):
        self.size = size
        self.tiles = []
        self.index = {}

    def add(self, pixels):
        assert pixels.shape == (self.size, self.size) and pixels.max() < 16
        data = pack4(pixels)
        if data not in self.index:
            self.index[data] = len(self.tiles)
            self.tiles.append(data)
        return self.index[data]

    def data(self):
        return b''.join(self.tiles)


def tile_map(tiles, img):
    """128 x 64 layer-0 map of a 640 x 480 image."""
    entries = [0] * (128 * 64)
    for r in range(60):
        for c in range(80):
            entries[r * 128 + c] = tiles.add(img[8 * r:8 * r + 8, 8 * c:8 * c + 8])
    return b''.join(v.to_bytes(2, 'little') for v in entries)


def build_layer0():
    tiles = TileSet(8)
    tiles.add(np.full((8, 8), PAPER, np.uint8))           # tile 0 = blank paper
    plain, info = render(False), render(True)
    maps = (tile_map(tiles, plain), tile_map(tiles, info))
    squares = bytearray()
    for theme in L.BOARD_THEMES:
        for light in (True, False):
            for state in L.SQUARE_STATES:
                sq = square_image(theme, light, state)
                for k in range(49):
                    t = tiles.add(sq[8 * (k // 7):8 * (k // 7) + 8, 8 * (k % 7):8 * (k % 7) + 8])
                    squares += t.to_bytes(2, 'little')
    assert len(tiles.tiles) <= 768, f'{len(tiles.tiles)} layer-0 tiles'
    return tiles, maps, bytes(squares), plain, info


def font_codes():
    for a, b in L.FONT_RANGES:
        yield from range(a, b + 1)


def build_layer1():
    tiles = []

    def cut(image, x, y):
        tiles.append(pack4(image[y:y + 8, x:x + 8]))

    for code in font_codes():
        g = glyph(code)
        cut(g, 0, 0)
        cut(g, 0, 8)
    assert len(tiles) == L.L1_PIECES
    for p in range(12):
        piece = piece_image(p)
        for ty in range(7):
            for tx in range(7):
                cut(piece, tx * 8, ty * 8)
    assert len(tiles) == L.L1_DIGITS
    for d in range(10):
        for ty in range(4):
            for tx in range(2):
                cut(DIGITS, d * 16 + tx * 8, ty * 8)
    colon = DIGITS[:, 160:176]
    used = np.nonzero(colon.any(axis=0))[0]
    left = 160 + max(0, min(8, (used[0] + used[-1] + 1) // 2 - 4))
    for ty in range(4):
        cut(DIGITS, left, ty * 8)
    for letter in 'abcdefgh':
        t = np.zeros((8, 8), np.uint8)
        g = np.array([[c == '#' for c in row] for row in FILE_LETTERS[letter]])
        t[2:7, 1:5][g] = INK
        tiles.append(pack4(t))
    assert len(tiles) == L.L1_COUNT <= 1024
    return b''.join(tiles)


POINTER = """
1...............
11..............
1c1.............
1cc1............
1ccc1...........
1cccc1..........
1ccccc1.........
1cccccc1........
1ccccccc1.......
1cccccccc1......
1cccc11111......
1cc1cc1.........
1c1.1cc1........
11..1cc1........
1....1cc1.......
.....1111.......
"""


def build_sprites():
    rows = POINTER.strip().splitlines()
    pointer = np.array([[{'.': 0, '1': INK, 'c': WHITE}[ch] for ch in row] for row in rows],
                       np.uint8)
    cursor = np.zeros((64, 64), np.uint8)
    lo, hi, t, n = 4, 59, 3, 16                       # corner brackets of a 56 px square
    for (x, y, dx, dy) in ((lo, lo, 1, 1), (hi, lo, -1, 1), (lo, hi, 1, -1), (hi, hi, -1, -1)):
        xs = sorted((x, x + dx * (n - 1)))
        ys = sorted((y, y + dy * (t - 1)))
        fill(cursor, xs[0], ys[0], xs[1], ys[1], ALERT)
        xs = sorted((x, x + dx * (t - 1)))
        ys = sorted((y, y + dy * (n - 1)))
        fill(cursor, xs[0], ys[0], xs[1], ys[1], ALERT)
    data = pack4(pointer)
    data += bytes(L.VRAM_CURSOR - L.VRAM_POINTER - len(data))
    return data + pack4(cursor)


def write_header(path, tiles):
    out = ['/* Generated by assets/scripts/build_graphics.py - do not edit. */',
           '#ifndef _GFX_H', '#define _GFX_H', '']
    for name in ('BOARD_X', 'BOARD_Y', 'SQUARE', 'STATUS_Y', 'LEFT_X0', 'LEFT_X1',
                 'RIGHT_X0', 'RIGHT_X1', 'PHOTO_Y', 'MOVES_Y', 'MOVE_ROWS', 'MOVE_ROW_H',
                 'STATUS_TURN_COL', 'STATUS_BEST_COL', 'STATUS_EVAL_COL', 'STATUS_CLOCK_COL',
                 'L1_FONT', 'L1_PIECES', 'L1_DIGITS', 'L1_COLON', 'L1_FILES', 'L1_COUNT',
                 'GUI_BANK', 'TINT_ROW', 'FIGURINE_CODE'):
        out.append(f'#define {name:<20} {getattr(L, name)}')
    out.append(f'#define RANK_LABEL_COL_LEFT  {L.RANK_LABEL_COLS[0]}')
    out.append(f'#define RANK_LABEL_COL_RIGHT {L.RANK_LABEL_COLS[1]}')
    out.append(f'#define ANALYSE_X0           {L.ANALYSE_BUTTON[0]}')
    out.append(f'#define ANALYSE_X1           {L.ANALYSE_BUTTON[1]}')
    out.append(f'#define INFO_X0              {L.INFO_BUTTON[0]}')
    out.append(f'#define INFO_X1              {L.INFO_BUTTON[1]}')
    for side in ('top', 'bottom'):
        out.append(f'#define PLATE_Y_{side.upper():<12} {L.PLATE_Y[side]}')
        out.append(f'#define CLOCK_Y_{side.upper():<12} {L.CLOCK_Y[side]}')
    for name in ('VRAM_L0_TILES', 'VRAM_L0_MAP_PLAIN', 'VRAM_L0_MAP_INFO', 'VRAM_L1_TILES',
                 'VRAM_L1_MAP', 'VRAM_SPRITES', 'VRAM_POINTER', 'VRAM_CURSOR'):
        out.append(f'#define {name:<20} 0x{getattr(L, name):05X}UL')
    out.append(f'#define L0_TILE_COUNT        {len(tiles.tiles)}')
    out.append('')
    for i, state in enumerate(L.SQUARE_STATES):
        out.append(f'#define SQ_{state:<17} {i}')
    out.append(f'#define SQ_STATES            {len(L.SQUARE_STATES)}')
    for i, theme in enumerate(L.BOARD_THEMES):
        out.append(f'#define THEME_{theme:<14} {i}')
    out.append(f'#define THEMES               {len(L.BOARD_THEMES)}')
    out.append('')
    out.append('// layer-1 font: glyph code ranges and their first slot (2 tiles per slot)')
    slot = 0
    for i, (a, b) in enumerate(L.FONT_RANGES):
        out.append(f'#define FONT_RANGE{i}_FIRST    0x{a:02X}')
        out.append(f'#define FONT_RANGE{i}_LAST     0x{b:02X}')
        out.append(f'#define FONT_RANGE{i}_SLOT     {slot}')
        slot += b - a + 1
    out.append('')
    out.append('#endif')
    path.write_text('\n'.join(out) + '\n')


def save_preview(img, path):
    preview = Image.fromarray(img, 'P')
    preview.putpalette(pil_palette())
    preview.save(path)


def main(dest):
    dest = Path(dest)
    tiles, maps, squares, plain, info = build_layer0()
    (dest / 'L0TILES.DAT').write_bytes(tiles.data())
    (dest / 'L0PLAIN.DAT').write_bytes(maps[0])
    (dest / 'L0INFO.DAT').write_bytes(maps[1])
    (dest / 'SQTILES.DAT').write_bytes(squares)
    (dest / 'L1TILES.DAT').write_bytes(build_layer1())
    (dest / 'SPRITES.DAT').write_bytes(build_sprites())
    (dest / 'PALETTE.DAT').write_bytes(vera_palette())
    write_header(dest / 'gfx.h', tiles)
    save_preview(plain, dest / 'playfield.png')
    save_preview(info, dest / 'playfield-info.png')
    print(f'layer 0: {len(tiles.tiles)} tiles ({len(tiles.tiles) * 32} bytes)')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
