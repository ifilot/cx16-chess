"""Build all VERA graphics for the playing field.

Outputs (in the given directory, normally src/):
  L0TILES.DAT   layer-0 4bpp 16x16 tiles (deduplicated background)
  L0MAP.DAT     layer-0 64x32 tilemap
  L1TILES.DAT   layer-1 4bpp 8x8 tiles: font, pieces, clock digits
  SPRITES.DAT   mouse pointer (16x16) and keyboard cursor (64x64), 4bpp
  PALETTE.DAT   512-byte VERA palette
  gfx.h         layout constants and layer-0 variant tile tables
  playfield.png preview of the composed background (not loaded by the game)
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import layout as L
from palette import (ALERT, CREAM, DARK, DARK_GRAIN, DARK_GREY, DEEP_RED, GREY, HL_DARK,
                     HL_LIGHT, INK, PAPER, RED, SHADE, TEXTURE, WHITE, pil_palette,
                     vera_palette)

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
KNIGHT = load_indexed(ASSETS / 'art/knight.png')
PHOTO = load_indexed(ASSETS / 'art/photo.png')


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
    """48x48 board square of a style in a highlight state.

    NEWSPRINT is a printed chess diagram: plain paper for light squares and
    diagonal hatching for dark ones. WOOD is the brown board of the mockups.
    """
    s = L.SQUARE
    y, x = np.mgrid[0:s, 0:s]
    highlighted = state in ('LASTMOVE', 'SELECTED')
    if theme == 'NEWSPRINT':
        hatch = (x + y) % 3 == 0
        base = HL_LIGHT if highlighted else PAPER
        a = np.full((s, s), base, np.uint8)
        if not light:
            a[hatch] = HL_DARK if highlighted else DARK_GREY
    else:
        base, speck = (SHADE, TEXTURE) if light else (DARK, DARK_GRAIN)
        a = np.where(grain(x, y), speck, base).astype(np.uint8)
        if highlighted:
            a[:] = HL_LIGHT if light else HL_DARK
    r2 = (x - 23.5) ** 2 + (y - 23.5) ** 2
    if state == 'SELECTED':
        frame(a, 2, 2, s - 3, s - 3, RED, 2)
    elif state == 'TARGET':
        a[r2 <= 6.5 ** 2] = DEEP_RED
    elif state == 'CAPTURE':
        corner = (x + y < 12) | ((s - 1 - x) + y < 12) | (x + (s - 1 - y) < 12) | \
                 ((s - 1 - x) + (s - 1 - y) < 12)
        a[corner] = DEEP_RED
    elif state == 'CHECK':
        a[(r2 <= 21.5 ** 2) & ((x + y) % 2 == 0)] = ALERT
        a[r2 <= 15.5 ** 2] = ALERT
    return a


def kremlin(img, cx, y1):
    """Small skyline: crenellated wall with a spired tower at cx."""
    x0, x1 = cx - 20, cx + 20
    fill(img, x0, y1 - 7, x1, y1, INK)
    for x in range(x0, x1 + 1, 5):
        fill(img, x, y1 - 10, min(x + 2, x1), y1 - 8, INK)
        if x + 1 <= x1:
            img[y1 - 10, x + 1] = PAPER
    fill(img, cx - 6, y1 - 22, cx + 6, y1, INK)
    fill(img, cx - 8, y1 - 24, cx + 8, y1 - 23, INK)
    fill(img, cx - 4, y1 - 30, cx + 4, y1 - 25, INK)
    fill(img, cx - 5, y1 - 31, cx + 5, y1 - 31, INK)
    fill(img, cx - 2, y1 - 34, cx + 2, y1 - 32, INK)
    for i in range(6):                       # spire
        half = max(0, 2 - (i + 1) // 3)
        fill(img, cx - half, y1 - 35 - i, cx + half, y1 - 35 - i, INK)
    fill(img, cx - 2, y1 - 20, cx + 2, y1 - 16, PAPER)   # clock face
    img[y1 - 18, cx] = INK
    img[y1 - 19, cx] = INK
    img[y1 - 18, cx + 1] = INK
    fill(img, cx - 2, y1 - 5, cx + 2, y1, PAPER)         # gate
    img[y1 - 5, cx - 2] = INK
    img[y1 - 5, cx + 2] = INK
    img[y1 - 42, cx] = RED                                # finial
    fill(img, cx - 1, y1 - 41, cx + 1, y1 - 41, RED)


# A few fixed specks per 16x16 tile: newsprint fibres that leave blank
# paper tiles identical, so they cost no extra tiles.
SPECKS = [(1, 3), (6, 12), (11, 7), (14, 14), (9, 1)]


def newsprint(img, keep_out):
    """Sprinkle specks over plain paper, outside the given rectangles."""
    mask = np.zeros(img.shape, bool)
    for sx, sy in SPECKS:
        # specks are placed in layer-0 canvas coordinates (screen + scroll)
        mask[(sy - L.SCROLL) % 16::16, (sx - L.SCROLL) % 16::16] = True
    for x0, y0, x1, y1 in keep_out:
        mask[y0:y1 + 1, x0:x1 + 1] = False
    img[mask & (img == PAPER)] = SHADE


def render(clock_active=(), move_highlight=None):
    img = np.full((H, W), PAPER, np.uint8)

    # ---- masthead -------------------------------------------------------
    fill(img, 4, 1, 635, 2, INK)
    fill(img, 4, 4, 635, 4, INK)

    fill(img, 4, 7, 119, 44, RED)                         # left ear
    frame(img, 6, 9, 117, 42, CREAM)
    blit(img, 9, 8, KNIGHT, {INK: DEEP_RED, WHITE: CREAM})
    for i, word in enumerate(['ИГРА', 'АНАЛИЗ', 'ИСТОРИЯ']):
        SMALL.draw(img, 50, 19 + 11 * i, word, CREAM, tracking=1)

    mh, mw = MASTHEAD.shape
    blit(img, 320 - mw // 2, 8, MASTHEAD)

    for i, word in enumerate(['ЕЖЕНЕДЕЛЬНАЯ', 'ШАХМАТНАЯ', 'ГАЗЕТА']):   # right ear
        SMALL.centered(img, 526, 20 + 10 * i, word, INK)
    kremlin(img, 608, 44)

    fill(img, 4, 47, 635, 47, INK)                        # dateline
    SMALL.draw(img, 6, 56, '№ 1 (1)', INK, tracking=1)
    SMALL.centered(img, 320, 56, 'СУББОТА, 12 ЯНВАРЯ 1985 ГОДА', INK, tracking=1)
    SMALL.right(img, 634, 56, 'ЦЕНА 5 КОП.', INK, tracking=1)
    fill(img, 4, 59, 635, 59, INK)
    fill(img, 4, 61, 635, 62, INK)

    # ---- board frame, column rules and footer ---------------------------
    bx, by, bs = L.BOARD_X, L.BOARD_Y, 8 * L.SQUARE
    frame(img, bx - 2, by - 2, bx + bs + 1, by + bs + 1, INK, 2)
    for rank in range(8):
        for file in range(8):
            img[by + rank * 48:by + rank * 48 + 48, bx + file * 48:bx + file * 48 + 48] = \
                square_image('NEWSPRINT', (rank + file) % 2 == 0, 'NORMAL')
    for x in L.COLUMN_RULES:
        fill(img, x, 68, x, 471, INK)
    fill(img, 4, 474, 635, 475, INK)
    fill(img, 4, 477, 635, 477, INK)

    # ---- left column ----------------------------------------------------
    x0, x1 = L.LEFT_X0, L.LEFT_X1
    for side in ('top', 'bottom'):
        py = L.PLATE_Y[side]
        fill(img, x0, py, x1, py + 47, RED)
        frame(img, x0 + 2, py + 2, x1 - 2, py + 45, CREAM)
        cy = L.CLOCK_Y[side]
        double_frame(img, x0, cy, x1, cy + 47)
        if side in clock_active:
            fill(img, x0 + 4, cy + 4, x1 - 4, cy + 43, RED)
    py = L.PHOTO_Y
    frame(img, x0, py, x1, py + 91, INK)
    ph, pw = PHOTO.shape
    img[py + 2:py + 2 + ph, (x0 + x1 + 1 - pw) // 2:(x0 + x1 + 1 + pw) // 2] = PHOTO
    ITALIC.centered(img, (x0 + x1 + 1) // 2, py + 103, 'Из архива', INK)
    sy = L.STATUS_Y
    double_frame(img, x0, sy, x1, sy + 47)

    # ---- right column ---------------------------------------------------
    rx0, rx1 = L.RIGHT_X0, L.RIGHT_X1
    HEADLINE.centered(img, (rx0 + rx1 + 1) // 2, 88, 'ХОД ПАРТИИ', INK)
    fill(img, rx0, 93, rx1, 94, INK)
    fill(img, rx0, 96, rx1, 96, INK)
    if move_highlight is not None:
        y = L.MOVES_Y + move_highlight * L.MOVE_ROW_H
        fill(img, rx0, y, rx1, y + L.MOVE_ROW_H - 1, RED)
    fill(img, rx0, 444, rx1, 444, INK)
    ITALIC.centered(img, (rx0 + rx1 + 1) // 2, 459, '(Продолжение следует)', INK)

    newsprint(img, [(bx - 2, by - 2, bx + bs + 1, by + bs + 1),
                    (x0, py, x1, py + 91)])
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


def layer0_canvas(img):
    canvas = np.full((32 * 16, 64 * 16), PAPER, np.uint8)
    canvas[L.SCROLL:L.SCROLL + H, L.SCROLL:L.SCROLL + W] = img
    return canvas


def region_entries(tiles, img, col, row, w, h):
    canvas = layer0_canvas(img)
    return [tiles.add(canvas[16 * r:16 * r + 16, 16 * c:16 * c + 16])
            for r in range(row, row + h) for c in range(col, col + w)]


def build_layer0():
    tiles = TileSet(16)
    tiles.add(np.full((16, 16), PAPER, np.uint8))       # tile 0 = blank paper
    base = render()
    canvas = layer0_canvas(base)
    tilemap = [tiles.add(canvas[16 * r:16 * r + 16, 16 * c:16 * c + 16])
               for r in range(32) for c in range(64)]

    squares = [[[[tiles.add(square_image(theme, light, state)[16 * (k // 3):16 * (k // 3) + 16,
                                                              16 * (k % 3):16 * (k % 3) + 16])
                  for k in range(9)] for state in L.SQUARE_STATES] for light in (True, False)]
               for theme in L.BOARD_THEMES]

    cw, ch = L.CLOCK_REGION_SIZE
    clocks = {}
    for side in ('top', 'bottom'):
        col, row = L.CLOCK_REGION[side]
        clocks[side] = (region_entries(tiles, base, col, row, cw, ch),
                        region_entries(tiles, render(clock_active=(side,)), col, row, cw, ch))

    rows = []
    for k in range(L.MOVE_ROWS):
        args = (L.MOVE_REGION_COL, L.MOVE_REGION_ROW + k, L.MOVE_REGION_W, 1)
        rows.append((region_entries(tiles, base, *args),
                     region_entries(tiles, render(move_highlight=k), *args)))
    # Rows only differ by their stripe, which keeps the tables small.
    assert all(r == rows[k % 2] for k, r in enumerate(rows))
    assert len(tiles.tiles) <= 512, f'{len(tiles.tiles)} layer-0 tiles exceed 64 KiB'
    return tiles, tilemap, squares, clocks, rows[:2], base


def build_layer1():
    tiles = []

    def cut(image, x, y):
        tiles.append(pack4(image[y:y + 8, x:x + 8]))

    for code in range(32, 256):
        g = glyph(code)
        cut(g, 0, 0)
        cut(g, 0, 8)
    assert len(tiles) == L.L1_PIECES
    for p in range(12):
        piece = piece_image(p)
        for ty in range(6):
            for tx in range(6):
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
    assert len(tiles) == L.L1_COUNT
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
    lo, hi, t, n = 8, 55, 3, 14
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


def c_array(name, values, per_line=12):
    lines = []
    for i in range(0, len(values), per_line):
        lines.append('    ' + ', '.join(f'0x{v:03X}' for v in values[i:i + per_line]) + ',')
    return f'static const uint16_t {name}[{len(values)}] = {{\n' + '\n'.join(lines) + '\n};\n'


def write_header(path, tiles, squares, clocks, rows):
    out = ['/* Generated by assets/scripts/build_graphics.py - do not edit. */',
           '#ifndef _GFX_H', '#define _GFX_H', '', '#include <stdint.h>', '']
    for name in ('BOARD_X', 'BOARD_Y', 'SQUARE', 'SCROLL', 'LEFT_X0', 'LEFT_X1', 'STATUS_Y',
                 'MOVES_Y', 'MOVE_ROWS', 'MOVE_ROW_H', 'MOVE_REGION_COL', 'MOVE_REGION_W',
                 'MOVE_REGION_ROW', 'MOVE_TEXT_X', 'RANK_LABEL_X', 'FILE_LABEL_Y',
                 'L1_FONT', 'L1_PIECES', 'L1_DIGITS', 'L1_COLON', 'L1_COUNT'):
        out.append(f'#define {name:<18} {getattr(L, name)}')
    for side in ('top', 'bottom'):
        out.append(f'#define PLATE_Y_{side.upper():<10} {L.PLATE_Y[side]}')
        out.append(f'#define CLOCK_Y_{side.upper():<10} {L.CLOCK_Y[side]}')
        out.append(f'#define CLOCK_REG_COL_{side.upper():<4} {L.CLOCK_REGION[side][0]}')
        out.append(f'#define CLOCK_REG_ROW_{side.upper():<4} {L.CLOCK_REGION[side][1]}')
    out.append(f'#define CLOCK_REG_W        {L.CLOCK_REGION_SIZE[0]}')
    out.append(f'#define CLOCK_REG_H        {L.CLOCK_REGION_SIZE[1]}')
    for name in ('VRAM_L0_TILES', 'VRAM_L1_TILES', 'VRAM_L1_MAP', 'VRAM_L0_MAP',
                 'VRAM_SPRITES', 'VRAM_POINTER', 'VRAM_CURSOR'):
        out.append(f'#define {name:<18} 0x{getattr(L, name):05X}UL')
    out.append(f'#define L0_TILE_COUNT      {len(tiles.tiles)}')
    out.append('')
    for i, state in enumerate(L.SQUARE_STATES):
        out.append(f'#define SQ_{state:<15} {i}')
    out.append(f'#define SQ_STATES          {len(L.SQUARE_STATES)}')
    for i, theme in enumerate(L.BOARD_THEMES):
        out.append(f'#define THEME_{theme:<12} {i}')
    out.append(f'#define THEMES             {len(L.BOARD_THEMES)}')
    out.append(f'#define FIGURINE_CODE      0x{L.FIGURINE_CODE:02X}')
    out.append('')
    out.append('#ifdef GFX_TABLES')
    out.append('/* [theme][dark][state][3x3 tiles] layer-0 entries of a board square */')
    flat = [v for theme in squares for light in theme for state in light for v in state]
    out.append(c_array('square_tiles', flat))
    for side in ('top', 'bottom'):
        out.append(c_array(f'clock_{side}_idle', clocks[side][0]))
        out.append(c_array(f'clock_{side}_active', clocks[side][1]))
    out.append('/* [stripe][normal, highlighted][columns] */')
    out.append(c_array('move_row_tiles', rows[0][0] + rows[0][1] + rows[1][0] + rows[1][1]))
    out.append('#endif')
    out.append('')
    out.append('#endif')
    path.write_text('\n'.join(out) + '\n')


def main(dest):
    dest = Path(dest)
    tiles, tilemap, squares, clocks, rows, base = build_layer0()
    (dest / 'L0TILES.DAT').write_bytes(tiles.data())
    (dest / 'L0MAP.DAT').write_bytes(b''.join(v.to_bytes(2, 'little') for v in tilemap))
    (dest / 'L1TILES.DAT').write_bytes(build_layer1())
    (dest / 'SPRITES.DAT').write_bytes(build_sprites())
    (dest / 'PALETTE.DAT').write_bytes(vera_palette())
    write_header(dest / 'gfx.h', tiles, squares, clocks, rows)
    preview = Image.fromarray(base, 'P')
    preview.putpalette(pil_palette())
    preview.save(dest / 'playfield.png')
    print(f'layer 0: {len(tiles.tiles)} tiles ({len(tiles.tiles) * 128} bytes)')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
