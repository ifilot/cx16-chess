"""Kakuro's native 8x8 pixel font; scaling repeats pixels without filtering."""
from pathlib import Path

import numpy as np
from PIL import Image

from palette import INK, pil_palette

ASSETS = Path(__file__).resolve().parents[1]
with Image.open(ASSETS / 'font/kakuro-ui.png') as source:
    if source.size != (128, 48):
        raise ValueError('Bitmap font must contain ASCII 32..127 in 8x8 cells')
    MASK = np.asarray(source.convert('RGBA'))[:, :, 3] > 150


def glyph8(code):
    code = code if 32 <= code <= 127 else ord('?')
    slot = code - 32
    return MASK[slot // 16 * 8:slot // 16 * 8 + 8,
                slot % 16 * 8:slot % 16 * 8 + 8].astype(np.uint8) * INK


class BitmapFont:
    def __init__(self, scale=1):
        self.scale = scale

    def width(self, string, tracking=0):
        return len(string) * (8 * self.scale + tracking) - tracking

    def draw(self, image, x, baseline, string, colour, tracking=0):
        for char in string:
            g = glyph8(ord(char)).repeat(self.scale, 0).repeat(self.scale, 1)
            y = baseline - 8 * self.scale
            region = image[y:y + g.shape[0], x:x + g.shape[1]]
            region[g != 0] = colour
            x += 8 * self.scale + tracking

    def centered(self, image, cx, baseline, string, colour, tracking=0):
        self.draw(image, cx - self.width(string, tracking) // 2,
                  baseline, string, colour, tracking)


def export_sheets():
    # Standard ASCII only; menu arrows are generated while packing VERA tiles.
    sheet = np.zeros((96, 128), np.uint8)
    for code in range(32, 128):
        slot = code - 32
        x, y = slot % 16 * 8, slot // 16 * 16
        sheet[y + 4:y + 12, x:x + 8] = glyph8(code)
    image = Image.fromarray(sheet, 'P')
    image.putpalette(pil_palette())
    image.save(ASSETS / 'font/font8x16.png')


if __name__ == '__main__':
    export_sheets()
