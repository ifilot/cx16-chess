"""The 16-colour 'Soviet chess gazette' palette shared by all assets.

VERA stores 12-bit colours, so every channel is a single hex digit. Index 0 is
transparent on layer 1 and for sprites, which is why ink lives at index 1.
"""

INK = 1
PAPER = 2
SHADE = 3          # light squares, alternate move-list rows
TEXTURE = 4        # fine grain on light squares
DARK = 5           # dark squares
DARK_GRAIN = 6     # fine grain on dark squares
RED = 7
DEEP_RED = 8
CREAM = 9          # text on red
GREY = 10
DARK_GREY = 11
WHITE = 12         # fill of the white pieces
HL_LIGHT = 13      # highlighted light square
HL_DARK = 14       # highlighted dark square
ALERT = 15         # check, keyboard cursor

RGB12 = [
    0x000,  # 0 backdrop / transparent
    0x111,  # 1 ink
    0xEDB,  # 2 paper
    0xDCA,  # 3 shade / light square
    0xCB9,  # 4 light-square grain
    0x975,  # 5 dark square
    0x864,  # 6 dark-square grain
    0x911,  # 7 red
    0x600,  # 8 deep red
    0xFEC,  # 9 cream
    0x887,  # 10 grey
    0x554,  # 11 dark grey
    0xFFE,  # 12 white piece fill
    0xDC6,  # 13 highlighted light square
    0xB94,  # 14 highlighted dark square
    0xD33,  # 15 alert red
]


# Row 15 retains its text ink at index 1, but reserves four otherwise unused
# artwork entries for masthead edge coverage between red ink and paper.
MASTHEAD_BANK = 15
MASTHEAD_EDGES = (0xDB9, 0xC87, 0xB65, 0xA33)

# The black-and-paper opening portrait uses the standard palette.
# Keep its palette separate so switching views always restores their colors.
SPLASH_RGB12 = RGB12.copy()

# Four achromatic tones for the setup queen, plus paper and the UI colors.
SETUP_RGB12 = RGB12.copy()
SETUP_RGB12[3] = 0x555
SETUP_RGB12[4] = 0xAAA
SETUP_RGB12[12] = 0xFFF


def rgb(index, colors=RGB12):
    """Return the 24-bit colour of a palette index."""
    value = colors[index]
    return (((value >> 8) & 15) * 17, ((value >> 4) & 15) * 17, (value & 15) * 17)


def pil_palette(colors=RGB12):
    """Palette list for PIL 'P' images (unused entries are black)."""
    flat = []
    for i in range(len(colors)):
        flat.extend(rgb(i, colors))
    return flat + [0] * (768 - len(flat))



def vera_palette(colors=RGB12):
    """256 VERA palette entries (512 bytes).

    Row 0 preserves the complete base palette for artwork. Other rows repeat
    the base palette but replace index 1 by colour k. Text and
    digit glyphs are drawn with index 1, so the tilemap palette offset selects
    their colour. Row 15 also reserves four entries for masthead edge shades;
    ordinary artwork and all text ink colors retain their original values.

    """
    out = bytearray()
    for row in range(16):
        for i in range(16):
            value = colors[row] if i == INK and row != 0 else colors[i]
            if row == MASTHEAD_BANK and 3 <= i <= 6:
                value = MASTHEAD_EDGES[i - 3]
            out += bytes([value & 0xFF, value >> 8])
    return bytes(out)


def splash_colors(colors=SPLASH_RGB12):
    """All hardware colors, including the masthead's separate tile palette."""
    data = vera_palette(colors)
    return [int.from_bytes(data[i:i + 2], 'little') for i in range(0, len(data), 2)]
