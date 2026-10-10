"""Regenerate the committed source artwork from third-party originals.

This is *not* part of the normal build. It needs rsvg-convert and the
PT Serif and Roboto Slab fonts, and writes editable PNGs:

  assets/pieces/pieces.png      12 Cburnett pieces in 56x56 cells, 2-tone pixel art
  assets/font/font8x16.png      condensed PT Serif Bold, Windows-1251 32..255,
                                with figurines at codes 0x81-0x86
  assets/font/digits16x32.png   PT Serif Bold clock digits 0-9 and ':'
  assets/font/headline.png/.json  proportional PT Serif Bold (headings)
  assets/font/small.png/.json     proportional PT Serif (small print)
  assets/font/italic.png/.json    proportional PT Serif Italic (captions)
  assets/art/masthead.png       the 'ШАХМАТЫ' newspaper title (14 px high)
  assets/art/photo.png          halftone 'photograph' of a king

Hand edits to these PNGs are preserved by the build; rerunning this script
overwrites them.
"""
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from palette import INK, PAPER, WHITE, pil_palette

ASSETS = Path(__file__).resolve().parents[1]
SLAB = '/usr/share/fonts/opentype/roboto/slab/RobotoSlab-Bold.otf'
PT_SERIF = '/usr/share/fonts/truetype/paratype/PTF55F.ttf'
PT_SERIF_ITALIC = '/usr/share/fonts/truetype/paratype/PTF56F.ttf'
PT_SERIF_BOLD = '/usr/share/fonts/truetype/paratype/PTF75F.ttf'

# Sheet order equals the engine's piece types: pawn, knight, bishop, rook,
# queen, king; white first, then black.
PIECE_NAMES = 'pnbrqk'
CELL = 56
PIECE_SIZE = 52
FIGURINE_CODE = 0x80        # + piece type (1..6)

# Solid figurines for the move list, 7x11, standing on the font's baseline.
FIGURINES = {
    1: ['.......', '.......', '..###..', '..###..', '...#...', '..###..',
        '..###..', '..###..', '.#####.', '#######', '#######'],
    2: ['..#.#..', '..####.', '.######', '##.####', '#######', '###.###',
        '#..####', '...####', '..####.', '.######', '#######'],
    3: ['...#...', '..###..', '..#.#..', '.##.##.', '.###.#.', '.#####.',
        '..###..', '...#...', '..###..', '.#####.', '#######'],
    4: ['.......', '#.#.#.#', '#######', '.#####.', '..###..', '..###..',
        '..###..', '..###..', '.#####.', '#######', '#######'],
    5: ['...#...', '#..#..#', '.#.#.#.', '.#.#.#.', '.#####.', '.#####.',
        '..###..', '..###..', '.#####.', '#######', '#######'],
    6: ['...#...', '..###..', '...#...', '.##.##.', '#######', '#######',
        '#######', '.#####.', '..###..', '.#####.', '#######'],
}


def indexed(array):
    image = Image.fromarray(array.astype(np.uint8), 'P')
    image.putpalette(pil_palette())
    return image


def cp1251(code):
    try:
        return bytes([code]).decode('cp1251')
    except UnicodeDecodeError:
        return None


# --------------------------------------------------------------------------
# pieces
# --------------------------------------------------------------------------
def render_svg(name, size, stroke=None, over=16):
    source = (ASSETS / 'pieces/svg' / f'Chess_{name}45.svg').read_text()
    if stroke:
        source = source.replace('stroke-width="1.5"', f'stroke-width="{stroke}"')
    hi = size * over
    png = subprocess.run(['rsvg-convert', '-w', str(hi), '-h', str(hi), '-b', '#00000000'],
                         input=source.encode(), capture_output=True, check=True).stdout
    return np.asarray(Image.open(io.BytesIO(png)).convert('RGBA')).astype(float) / 255


def render_piece(name, size=45, stroke=None, over=16):
    """Rasterise a Cburnett SVG to 0=transparent, INK, WHITE pixels.

    Supersampled coverage decides each pixel: a pixel is opaque when at least
    half of it is covered, and inked when 40% of that coverage is black. Thin
    black strokes that fall between pixels survive through the second rule.
    """
    rgba = render_svg(name, size, stroke, over)
    alpha = rgba[..., 3]
    dark = alpha * (rgba[..., :3].mean(-1) < 0.5)

    def pool(x):
        return x.reshape(size, over, size, over).mean((1, 3))

    a, d = pool(alpha), pool(dark)
    out = np.zeros((size, size), np.uint8)
    opaque = a >= 0.5
    out[opaque] = WHITE
    out[opaque & (d / np.maximum(a, 1e-6) >= 0.40)] = INK
    out[~opaque & (d >= 0.30)] = INK
    return out


def make_pieces():
    sheet = np.zeros((CELL, CELL * 12), np.uint8)
    o = (CELL - PIECE_SIZE) // 2
    for colour, suffix, stroke in ((0, 'lt', 2.0), (1, 'dt', None)):
        for i, letter in enumerate(PIECE_NAMES):
            piece = render_piece(letter + suffix, size=PIECE_SIZE, stroke=stroke)
            x = (colour * 6 + i) * CELL + o
            sheet[o:o + PIECE_SIZE, x:x + PIECE_SIZE] = piece
    indexed(sheet).save(ASSETS / 'pieces/pieces.png')


# --------------------------------------------------------------------------
# fonts
# --------------------------------------------------------------------------
def font_for_cap(path, cap):
    """Font whose capital H is cap pixels high."""
    probe = ImageFont.truetype(path, 200)
    height = -probe.getbbox('H', anchor='ls')[1]
    return ImageFont.truetype(path, 200 * cap / height)


def fitted_glyph(font, char, rows, baseline, max_width, over=8):
    """Supersample a glyph and squeeze it horizontally to max_width.

    font must be scaled by the supersampling factor over.

    Glyphs that need squeezing get a lower threshold so their thinner
    strokes survive. Returns a (rows x width) boolean array.
    """
    canvas = Image.new('L', (48 * over, 48 * over), 0)
    ImageDraw.Draw(canvas).text((8 * over, 36 * over), char, font=font, fill=255, anchor='ls')
    a = np.asarray(canvas).astype(float) / 255
    cols = np.nonzero(a.any(0))[0]
    if not len(cols):
        return np.zeros((rows, 0), bool)
    a = a[:, cols[0]:cols[-1] + 1]
    width = a.shape[1] / over
    scale = min(1.0, max_width / width)
    w = max(1, round(width * scale))
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8))
                   .resize((w * over, a.shape[0]), Image.BOX)).astype(float) / 255
    top = (36 - baseline) * over
    a = a[top:top + rows * over]
    cell = a.reshape(rows, over, w, over).mean((1, 3))
    return cell >= (0.5 if scale == 1.0 else 0.4)


def make_font():
    font = font_for_cap(PT_SERIF_BOLD, 10 * 8)
    sheet = np.zeros((14 * 16, 16 * 8), np.uint8)
    for code in range(33, 256):
        char = cp1251(code)
        slot = code - 32
        ox, oy = (slot % 16) * 8, (slot // 16) * 16
        if code - FIGURINE_CODE in FIGURINES:
            rows = FIGURINES[code - FIGURINE_CODE]
            glyph = np.array([[c == '#' for c in row] for row in rows])
            sheet[oy + 2:oy + 13, ox:ox + 7][glyph] = INK
            continue
        if char is None:
            continue
        glyph = fitted_glyph(font, char, 16, 12, 7)
        w = glyph.shape[1]
        if w:
            x = ox + (8 - w) // 2 if w < 7 else ox
            sheet[oy:oy + 16, x:x + w][glyph] = INK
    indexed(sheet).save(ASSETS / 'font/font8x16.png')

    font = font_for_cap(PT_SERIF_BOLD, 24 * 8)
    digits = np.zeros((32, 11 * 16), np.uint8)
    for i, char in enumerate('0123456789:'):
        glyph = fitted_glyph(font, char, 32, 28, 15)
        w = glyph.shape[1]
        x = i * 16 + (16 - w) // 2
        digits[:, x:x + w][glyph] = INK
    indexed(digits).save(ASSETS / 'font/digits16x32.png')


def make_proportional(name, path, size, cell=(16, 20), baseline=15, threshold=110):
    """Proportional font sheet plus advance widths, rendered with hinting."""
    font = ImageFont.truetype(path, size)
    cw, ch = cell
    sheet = np.zeros((14 * ch, 16 * cw), np.uint8)
    advances = []
    for code in range(32, 256):
        char = cp1251(code) or ' '
        slot = code - 32
        canvas = Image.new('L', (cw * 2, ch), 0)
        ImageDraw.Draw(canvas).text((2, baseline), char, font=font, fill=255, anchor='ls')
        glyph = np.asarray(canvas) >= threshold
        glyph = glyph[:, 2:2 + cw]
        ox, oy = (slot % 16) * cw, (slot // 16) * ch
        sheet[oy:oy + ch, ox:ox + cw][glyph] = INK
        advances.append(round(font.getlength(char)))
    indexed(sheet).save(ASSETS / f'font/{name}.png')
    (ASSETS / f'font/{name}.json').write_text(json.dumps(
        {'cell': list(cell), 'baseline': baseline, 'advance': advances}))


def make_fonts():
    make_font()
    make_proportional('headline', PT_SERIF_BOLD, 16)
    make_proportional('small', PT_SERIF, 11, cell=(12, 14), baseline=10)
    make_proportional('italic', PT_SERIF_ITALIC, 11, cell=(12, 14), baseline=10)


# --------------------------------------------------------------------------
# artwork
# --------------------------------------------------------------------------
def make_masthead(height=14, embolden=3):
    font = ImageFont.truetype(SLAB, 200)
    big = Image.new('L', (1900, 300), 0)
    ImageDraw.Draw(big).text((20, 10), 'ШАХМАТЫ', font=font, fill=255,
                             stroke_width=embolden, stroke_fill=255)
    big = big.crop(big.getbbox())
    width = round(big.width * height / big.height)
    small = np.asarray(big.resize((width, height), Image.BOX)) >= 128
    out = np.zeros(small.shape, np.uint8)
    out[small] = INK
    indexed(out).save(ASSETS / 'art/masthead.png')


def halftone(gray, period=4.0, angle=45):
    """Clustered-dot halftone: ink dots grow with darkness (0=black, 1=white)."""
    h, w = gray.shape
    y, x = np.mgrid[0:h, 0:w] + 0.5
    t = np.radians(angle)
    u = (x * np.cos(t) + y * np.sin(t)) / period
    v = (-x * np.sin(t) + y * np.cos(t)) / period
    du, dv = u - np.floor(u) - 0.5, v - np.floor(v) - 0.5
    # inked area of a dot of radius r is pi r^2 of the cell; make it linear
    threshold = np.minimum(1.0, np.pi * (du * du + dv * dv))
    return (1 - gray) > threshold


def make_photo(w=74, h=88, over=4):
    """A studio 'photograph' of the black king, printed as a halftone."""
    W, H = w * over, h * over
    y, x = np.mgrid[0:H, 0:W] / over
    # light backdrop, brightest behind the piece, on a slightly darker table
    gray = 1.02 - 0.40 * np.hypot((x - w * 0.45) / w, (y - h * 0.40) / h)
    floor = y > h * 0.82
    gray[floor] = 0.62 + 0.12 * (y[floor] / h - 0.82) / 0.18
    shadow = ((x - w * 0.60) / (w * 0.40)) ** 2 + ((y - h * 0.86) / (h * 0.045)) ** 2 < 1
    gray[shadow] = 0.35

    size = 60
    rgba = render_svg('kdt', size, over=over)
    alpha = rgba[..., 3] > 0.5
    light = alpha & (rgba[..., :3].mean(-1) >= 0.5)
    px, py = (W - size * over) // 2, H - size * over - int(h * 0.11 * over)
    for r in range(size * over):
        cols = np.nonzero(alpha[r])[0]
        if not len(cols):
            continue
        u = (np.arange(size * over) - cols[0]) / max(1, cols[-1] - cols[0])
        shade = 0.60 * np.clip(0.45 - u, 0, 1) ** 1.2            # highlight on the left
        row = np.where(light[r], 1.0, shade)
        target = gray[py + r, px:px + size * over]
        gray[py + r, px:px + size * over] = np.where(alpha[r], row, target)

    small = np.asarray(Image.fromarray((np.clip(gray, 0, 1) * 255).astype(np.uint8))
                       .resize((w, h), Image.BOX)).astype(float) / 255
    out = np.full((h, w), PAPER, np.uint8)
    out[halftone(small)] = INK
    indexed(out).save(ASSETS / 'art/photo.png')


if __name__ == '__main__':
    targets = sys.argv[1:] or ['pieces', 'font', 'masthead', 'photo']
    if 'pieces' in targets:
        make_pieces()
    if 'font' in targets:
        make_fonts()
    if 'masthead' in targets:
        make_masthead()
    if 'photo' in targets:
        make_photo()
