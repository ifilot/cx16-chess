"""Build all VERA graphics for the playing field.

Intermediate outputs (normally build/graphics/; package_graphics.py packs
them into the single runtime CHESS.DAT container):
  L0TILES.DAT   layer-0 4bpp 8x8 tiles (deduplicated background)
  L0PLAIN.DAT   layer-0 128x64 map: masthead, board, status bar
  L0INFO.DAT    layer-0 128x64 map: the same plus the side columns
  SQTILES.DAT   layer-0 entries of every board square variant (banked RAM)
  SPRITES.DAT   mouse pointer (16x16) and keyboard cursor (64x64), 4bpp
  FONT.DAT      resident bitmap font shared by every view
  L1ART.DAT     game foreground tiles after the resident font
  SPL1ART.DAT, SET1ART.DAT  menu artwork after the resident font
  PALETTE.DAT   512-byte VERA palette
  gfx.h         layout constants
  playfield.png, playfield-info.png  previews (not loaded by the game)
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from bitmap_font import BitmapFont, glyph8

import layout as L
import indicators
from palette import (ALERT, DARK, DARK_GREY, HL_DARK, HL_LIGHT,
                     INK, PAPER, RED, RGB12, SPLASH_RGB12, SETUP_RGB12, SHADE, TEXTURE, WHITE, pil_palette, rgb, vera_palette, MASTHEAD_BANK, splash_colors)

ASSETS = Path(__file__).resolve().parents[1]
W, H = 640, 480


def load_indexed(path, colors=RGB12):
    with Image.open(path) as image:
        if image.mode != 'P':
            raise ValueError(f'{path} must be an indexed PNG')
        pixels = np.asarray(image).copy()
        palette = image.getpalette()
        for index in np.unique(pixels):
            if index >= 16 or tuple(palette[index * 3:index * 3 + 3]) != rgb(int(index), colors):
                raise ValueError(f'{path}: palette index {index} does not match the project palette')
        if 'transparency' in image.info:
            raise ValueError(f'{path}: PNG transparency must be explicit in the layer compositor')
    return pixels


FONT = load_indexed(ASSETS / 'font/font8x16.png')
PIECES = load_indexed(ASSETS / 'pieces/victorian.png')
FIGURINES16 = load_indexed(ASSETS / 'pieces/scorecard.png')

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


SMALL = BitmapFont()


def masthead(img, cx, baseline):
    """Preserve the original serif CX16 CHESS logo; UI text stays bitmap."""
    sheet = load_indexed(ASSETS / 'font/headline.png')
    meta = json.loads((ASSETS / 'font/headline.json').read_text())
    cw, ch = meta['cell']
    codes = b'CX16 CHESS'
    x = cx - sum(meta['advance'][code - 32] for code in codes) // 2
    for code in codes:
        slot = code - 32
        cell = sheet[slot // 16 * ch:(slot // 16 + 1) * ch,
                     slot % 16 * cw:(slot % 16 + 1) * cw]
        blit(img, x, baseline - meta['baseline'], cell)
        x += meta['advance'][slot]


def serif_title(image, mask_name, cx, cy):
    """Draw retained PT Serif coverage with the masthead's red/paper shades."""
    with Image.open(ASSETS / 'font' / mask_name) as mask:
        coverage = np.asarray(mask.convert('L'))
    shades = np.array([PAPER, MASTHEAD_BANK * 16 + 3,
                       MASTHEAD_BANK * 16 + 4, MASTHEAD_BANK * 16 + 5,
                       MASTHEAD_BANK * 16 + 6, RED], np.uint8)
    height, width = coverage.shape
    x, y = cx - width // 2, cy - height // 2
    image[y:y + height, x:x + width] = shades[np.rint(coverage / 255 * 5).astype(int)]


def piece_image(index):
    return PIECES[:, index * L.SQUARE:(index + 1) * L.SQUARE]


# --------------------------------------------------------------------------
# artwork
# --------------------------------------------------------------------------
def square_image(theme, light, state):
    """Board square of a style in a highlight state.

    NEWSPRINT is a printed chess diagram: plain paper for light squares and
    diagonal hatching for dark ones. CROSSHATCH and COARSE use the reviewed
    newspaper patterns. WOOD is the brown board of the mockups.
    """
    s = L.SQUARE
    c = (s - 1) / 2
    y, x = np.mgrid[0:s, 0:s]
    highlighted = state == 'LASTMOVE'
    if theme != 'WOOD':
        # Four-pixel repeat aligns exactly at every 8x8 tile and 56px square.
        if theme == 'CROSSHATCH':
            hatch = ((x + y) % 8 == 0) | ((x - y) % 8 == 0)
        elif theme == 'COARSE':
            hatch = (x + y) % 8 < 2
        else:
            hatch = (x + y) % 4 == 0
        a = np.full((s, s), HL_LIGHT if highlighted else PAPER, np.uint8)
        if not light:
            a[hatch] = HL_DARK if highlighted else INK
    else:
        base = SHADE if light else DARK
        a = np.full((s, s), base, np.uint8)
        if highlighted:
            a[:] = HL_LIGHT if light else HL_DARK
    r2 = (x - c) ** 2 + (y - c) ** 2
    if state == 'SELECTED':
        blit(a, 0, 0, indicators.selection())
    elif state == 'TARGET':
        blit(a, 0, 0, indicators.movement())
    elif state == 'CAPTURE':
        blit(a, 0, 0, indicators.capture())
    elif state == 'CHECK':
        a[(r2 <= 25.5 ** 2) & ((x + y) % 2 == 0)] = ALERT
        a[r2 <= 18.5 ** 2] = ALERT
    return a


def render(info):
    img = np.full((H, W), PAPER, np.uint8)
    bx, by, bs = L.BOARD_X, L.BOARD_Y, 8 * L.SQUARE

    # Scorecard 02: board first, one quiet sidebar, flat warm paper.
    frame(img, bx - 4, by - 4, bx + bs + 3, by + bs + 3, INK)
    frame(img, bx - 2, by - 2, bx + bs + 1, by + bs + 1, INK)
    for rank in range(8):
        for file in range(8):
            y, x = by + rank * L.SQUARE, bx + file * L.SQUARE
            img[y:y + L.SQUARE, x:x + L.SQUARE] = square_image('NEWSPRINT', (rank + file) % 2 == 0, 'NORMAL')
    cx = (L.RIGHT_X0 + L.RIGHT_X1 + 1) // 2
    serif_title(img, 'game-title-mask.png', cx, 22)
    # Red masthead; compact clocks and a centred, signed evaluation bar.
    for y in (36, 39):
        fill(img, L.RIGHT_X0, y, L.RIGHT_X1, y, INK)
    frame(img, 496, 56, 623, 63, INK)
    fill(img, 560, 55, 560, 64, INK)
    SMALL.draw(img, 488, 52, 'B', INK)
    SMALL.draw(img, 624, 52, 'W', INK)
    if info:
        SMALL.draw(img, 488, 118, 'No.', INK)
        SMALL.centered(img, 536, 118, 'WHITE', INK)
        SMALL.centered(img, 600, 118, 'BLACK', INK)
        fill(img, 488, 122, 631, 122, INK)
        bottom = L.MOVES_Y + L.MOVE_ROWS * 16 - 1
        for row in range(L.MOVE_ROWS):
            if row % 2:
                fill(img, 488, L.MOVES_Y + row * 16, 631, L.MOVES_Y + row * 16 + 15, SHADE)
        fill(img, 511, 123, 511, bottom, TEXTURE)
        fill(img, 575, 123, 575, bottom, TEXTURE)

    return img


def render_options():
    image = render(False)
    fill(image, 480, 0, 639, 479, PAPER)
    serif_title(image, 'options-mask.png', 560, 70)
    for y in (104, 107, 352, 355):
        fill(image, 488, y, 631, y, INK)
    return image


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

    def add_flipped(self, pixels):
        """Reuse mirrored tiles with VERA's flips, preserving every pixel."""
        for candidate, flags in ((pixels, 0), (pixels[:, ::-1], 1024),
                                 (pixels[::-1], 2048), (pixels[::-1, ::-1], 3072)):
            data = pack4(candidate)
            if data in self.index:
                return self.index[data], flags
        return self.add(pixels), 0


def tile_map(tiles, img):
    """128 x 64 layer-0 map of a 640 x 480 image."""
    entries = [0] * (128 * 64)
    for r in range(60):
        for c in range(80):
            block = img[8 * r:8 * r + 8, 8 * c:8 * c + 8]
            bank = MASTHEAD_BANK << 12 if np.any(block >= 16) else 0
            entries[r * 128 + c] = tiles.add(block & 15) | bank
    return b''.join(v.to_bytes(2, 'little') for v in entries)


def refine_masthead(image):
    """Keep the printed letter shapes; replace quantized edge colors by coverage.

    The original red ink and every portrait pixel remain intact. Only nonblack
    edge pixels in the masthead region use palette row 15.
    """
    result = image.copy()
    header = image[:96]
    # Tile-aligned masthead regions leave the bishop's finial untouched.
    logo = np.ones_like(header, dtype=bool)
    logo[80:96, 272:304] = False
    eligible = logo & (header != 0) & (header != INK) & (header != PAPER) & (header != RED)
    colors = np.array([rgb(i) for i in range(16)], dtype=float)
    paper, ink = colors[PAPER], colors[RED]
    direction = ink - paper
    coverage = np.clip((colors - paper) @ direction / (direction @ direction), 0, 1)
    steps = np.rint(coverage * 5).astype(int)
    lookup = np.array([PAPER, MASTHEAD_BANK * 16 + 3, MASTHEAD_BANK * 16 + 4,
                       MASTHEAD_BANK * 16 + 5, MASTHEAD_BANK * 16 + 6, RED], np.uint8)
    # Keep a single edge band; discarded distant quantization specks would
    # otherwise turn into red halos when assigned the corrected colors.
    core = header == RED
    padded = np.pad(core, 1)
    near = np.zeros_like(core)
    for dy in range(3):
        for dx in range(3):
            near |= padded[dy:dy + 96, dx:dx + W]
    result[:96][eligible] = PAPER
    edges = eligible & near
    result[:96][edges] = lookup[steps[header[edges]]]
    return result


def menu_artwork(artwork):
    image = load_indexed(ASSETS / f'art/{artwork}.png',
                         SPLASH_RGB12 if artwork == 'splash' else SETUP_RGB12)
    assert image.shape == (H, W) and image.max() < 16
    if artwork == 'splash':
        image = refine_masthead(image)
    if artwork in ('setup', 'about'):
        if artwork == 'setup':
            # Retained PT Serif coverage mask: build without a system font
            # dependency and use the same red/paper shades as the masthead.
            serif_title(image, 'new-game-mask.png', 480, 70)
        else:
            serif_title(image, 'about-mask.png', 480, 72)
        for y in ((104, 107, 392, 395) if artwork == 'about' else (104, 107, 352, 355)):
            fill(image, 344, y, 615, y, INK)
    return image


def build_splash(dest, artwork="splash", prefix="SPL"):
    """Split the native-resolution artwork across two 4bpp tile layers.

    Layer 1 retains the runtime font, so menu labels can change without
    baking dead controls into the picture. Its unused piece slots hold the
    artwork overflow while the start screen is visible.
    """
    image = menu_artwork(artwork)
    colors = SPLASH_RGB12 if artwork == 'splash' else SETUP_RGB12
    palette = vera_palette(colors)
    preview_colors = splash_colors(colors)
    (dest / f'{prefix}PAL.DAT').write_bytes(palette)
    tiles = TileSet(8)
    tiles.add(np.full((8, 8), PAPER, np.uint8))
    # Index zero is opaque in the artwork but transparent on VERA layer 1.
    # Overflow tiles need that exact palette color underneath (black in both
    # portraits), preserving every source pixel.
    underlay_tile = tiles.add(np.zeros((8, 8), np.uint8))
    capacity0 = (L.VRAM_L0_MAP_PLAIN - L.VRAM_L0_TILES) // 32
    capacity1 = (L.VRAM_L1_MAP - L.VRAM_L1_TILES) // 32
    layer0, layer1 = [0] * 8192, [0] * 8192
    for r in range(60):
        for c in range(80):
            block = image[r * 8:r * 8 + 8, c * 8:c * 8 + 8]
            bank = MASTHEAD_BANK << 12 if np.any(block >= 16) else 0
            # About's detailed portrait leaves little room for its title.
            # Hardware flips share exact mirrored tiles without reducing art.
            t, flips = tiles.add_flipped(block & 15) if artwork == 'about' else (tiles.add(block & 15), 0)
            if t < capacity0:
                layer0[r * 128 + c] = t | flips | bank
            else:
                layer0[r * 128 + c] = underlay_tile
                layer1[r * 128 + c] = (L.L1_PIECES + t - capacity0) | flips | bank
    count1 = L.L1_PIECES + max(0, len(tiles.tiles) - capacity0)
    if count1 > capacity1:
        raise ValueError(f'{artwork}: needs {count1} layer-1 tiles, budget is {capacity1}; '
                         'reduce artwork complexity explicitly, never drop or truncate tiles')
    (dest / f'{prefix}TILE.DAT').write_bytes(b''.join(tiles.tiles[:capacity0]))
    font = build_layer1()[:L.L1_PIECES * 32]
    art = b''.join(tiles.tiles[capacity0:])
    (dest / f'{prefix}1ART.DAT').write_bytes(art)
    (dest / 'FONT.DAT').write_bytes(font)
    for name, entries in [(f'{prefix}MAP.DAT', layer0), (f'{prefix}1MAP.DAT', layer1)]:
        (dest / name).write_bytes(b''.join(t.to_bytes(2, 'little') for t in entries))
    # Check actual packed files and palette, rather than trusting the source
    # preview. Any missing/recoloured pixel or invalid tile reference fails
    # the build before it can reach the emulator.
    from verify_graphics import verify_artwork
    reconstructed = verify_artwork(dest, prefix, image, palette_data=palette, expected_palette=preview_colors)
    preview = reconstructed.copy()
    if artwork == 'splash':
        for y, label, color in [(368, 'NEW GAME', RED), (384, 'CONTINUE', DARK_GREY), (400, 'LOAD GAME', INK), (416, 'OPTIONS', INK), (432, 'ABOUT', INK)]:
            text(preview, 288, y, label, color)
        text_centered(preview, 0, 639, 464, 'UP/DOWN  ENTER TO SELECT', INK)
    save_preview(preview, dest / f'{artwork}.png', preview_colors)
    print(f'{artwork}: {len(tiles.tiles)} tiles across two layers')


def build_layer0():
    tiles = TileSet(8)
    tiles.add(np.full((8, 8), PAPER, np.uint8))           # tile 0 = blank paper
    plain, info = render(False), render(True)
    maps = (tile_map(tiles, plain), tile_map(tiles, info), tile_map(tiles, render_options()))
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


def build_layer1(pieces=PIECES):
    tiles = []

    def cut(image, x, y):
        tiles.append(pack4(image[y:y + 8, x:x + 8]))

    for code in font_codes():
        g = glyph(code)
        if code in (L.MENU_ARROW_LEFT, L.MENU_ARROW_RIGHT):
            g = np.zeros((16, 8), np.uint8)
            for y, width in enumerate((1, 2, 3, 4, 3, 2, 1)):
                g[4 + y, 2:2 + width] = INK
            if code == L.MENU_ARROW_LEFT:
                g = g[:, ::-1]
        if code == L.MENU_WARNING:
            # Outlined warning triangle with an exclamation mark, in an 8x16 cell.
            g = np.zeros((16, 8), np.uint8)
            g[3, 3] = INK
            for y in range(4, 11):
                radius = (y - 2) // 2
                radius = min(radius, 3)
                g[y, 3 - radius] = g[y, 3 + radius] = INK
            g[11, :7] = INK
            g[6:9, 3] = INK
            g[10, 3] = INK
        cut(g, 0, 0)
        cut(g, 0, 8)
    assert len(tiles) == L.L1_FIGURINES
    for p in range(6):
        for ty in range(2):
            for tx in range(2):
                cut(FIGURINES16, p * 16 + tx * 8, ty * 8)
    assert len(tiles) == L.L1_PIECES
    for p in range(12):
        piece = pieces[:, p * L.SQUARE:(p + 1) * L.SQUARE]
        for ty in range(7):
            for tx in range(7):
                cut(piece, tx * 8, ty * 8)
    assert len(tiles) == L.L1_FILES
    for letter in 'abcdefgh':
        tiles.append(pack4(glyph8(ord(letter))))
    assert len(tiles) == L.L1_BAR
    for width in range(9):
        bar = np.zeros((8, 8), np.uint8)
        bar[2:6, :width] = INK
        tiles.append(pack4(bar))
    for width in range(1, 9):
        bar = np.zeros((8, 8), np.uint8)
        bar[2:6, 8-width:] = INK
        tiles.append(pack4(bar))
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
    cursor = indicators.cursor()
    data = pack4(pointer)
    data += bytes(L.VRAM_CURSOR - L.VRAM_POINTER - len(data))
    return data + pack4(cursor)


def write_header(path, tiles):
    out = ['/* Generated by assets/scripts/build_graphics.py - do not edit. */',
           '#ifndef _GFX_H', '#define _GFX_H', '']
    for name in ('BOARD_X', 'BOARD_Y', 'SQUARE', 'LEFT_X0', 'LEFT_X1',
                 'RIGHT_X0', 'RIGHT_X1', 'MOVES_Y', 'MOVE_ROWS', 'MOVE_ROW_H',
                 'L1_FONT', 'L1_FIGURINES', 'L1_PIECES', 'L1_FILES', 'L1_BAR', 'L1_COUNT',
                 'GUI_BANK', 'FIGURINE_CODE'):
        out.append(f'#define {name:<20} {getattr(L, name)}')
    out.append(f'#define RANK_LABEL_COL_LEFT  {L.RANK_LABEL_COLS[0]}')
    out.append(f'#define RANK_LABEL_COL_RIGHT {L.RANK_LABEL_COLS[1]}')
    for side in ('top', 'bottom'):
        out.append(f'#define PLATE_Y_{side.upper():<12} {L.PLATE_Y[side]}')
    for name in ('VRAM_L0_TILES', 'VRAM_L0_MAP_PLAIN', 'VRAM_L0_MAP_INFO', 'VRAM_L1_TILES',
                 'VRAM_L1_MAP', 'VRAM_DRAG', 'VRAM_SPRITES', 'VRAM_POINTER', 'VRAM_CURSOR'):
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
    out.append(f'#define MENU_ARROW_LEFT      {L.MENU_ARROW_LEFT}')
    out.append(f'#define MENU_ARROW_RIGHT     {L.MENU_ARROW_RIGHT}')
    out.append(f'#define MENU_WARNING         {L.MENU_WARNING}')
    out.append('')
    out.append('#endif')
    path.write_text('\n'.join(out) + '\n')


def save_preview(img, path, colors=RGB12):
    preview = Image.fromarray(img, 'P')
    preview.putpalette(pil_palette(colors))
    preview.save(path)


def main(dest):
    dest = Path(dest)
    build_splash(dest)
    build_splash(dest, "setup", "SET")
    build_splash(dest, "about", "ABT")
    tiles, maps, squares, plain, info = build_layer0()
    (dest / 'L0TILES.DAT').write_bytes(tiles.data())
    (dest / 'L0PLAIN.DAT').write_bytes(maps[0])
    (dest / 'L0INFO.DAT').write_bytes(maps[1])
    (dest / 'OPTMAP.DAT').write_bytes(maps[2])
    (dest / 'SQTILES.DAT').write_bytes(squares)
    foreground = build_layer1()
    (dest / 'L1ART.DAT').write_bytes(foreground[L.L1_PIECES * 32:])
    for name, filename in [('continental', 'ENGART.DAT'), ('letterpress', 'LETART.DAT')]:
        sheet = load_indexed(ASSETS / f'pieces/{name}.png')
        assert sheet.shape == (L.SQUARE, L.SQUARE * 12)
        (dest / filename).write_bytes(build_layer1(sheet)[L.L1_PIECES * 32:])
    (dest / 'SPRITES.DAT').write_bytes(build_sprites())
    (dest / 'PALETTE.DAT').write_bytes(vera_palette())
    write_header(dest / 'gfx.h', tiles)
    save_preview(plain, dest / 'playfield.png', splash_colors())
    save_preview(info, dest / 'playfield-info.png', splash_colors())
    save_preview(render_options(), dest / 'options.png', splash_colors())
    print(f'layer 0: {len(tiles.tiles)} tiles ({len(tiles.tiles) * 32} bytes)')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
