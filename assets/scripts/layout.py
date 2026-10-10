"""Screen geometry of the playing field (640x480), shared with the C code.

Layer 0 is scrolled by (8, 8): its 16x16 tile (c, r) covers screen pixels
x = 16c-8 .. 16c+7 and y = 16r-8 .. 16r+7. This lets the 48x48 board squares
start at the 8-pixel aligned position (104, 72) while staying tile aligned.
Layer 1 uses 8x8 tiles without scrolling.
"""

SCROLL = 8

BOARD_X, BOARD_Y, SQUARE = 104, 72, 48

# Left panel: player plates and clocks for the top and bottom player.
LEFT_X0, LEFT_X1 = 4, 83                       # inclusive
PLATE_Y = {'top': 72, 'bottom': 408}          # 48 pixels high
CLOCK_Y = {'top': 128, 'bottom': 352}         # 48 pixels high
PHOTO_Y = 184                                  # framed halftone, 92 high
STATUS_Y = 296                                 # 48 pixels high
CLOCK_REGION = {'top': (0, 8), 'bottom': (0, 22)}   # layer-0 tile (col, row)
CLOCK_REGION_SIZE = (6, 4)

# Right column: move list.
RIGHT_X0, RIGHT_X1 = 498, 635
COLUMN_RULES = (86, 494)                       # vertical hairlines
MOVES_Y, MOVE_ROWS, MOVE_ROW_H = 104, 21, 16
MOVE_REGION_COL, MOVE_REGION_W = 31, 10          # layer-0 tile columns
MOVE_REGION_ROW = 7                              # tile row of move row 0
MOVE_TEXT_X = 504                                # 16 characters wide

RANK_LABEL_X = 88
FILE_LABEL_Y = 456

# Layer-1 tile numbering.
L1_FONT = 0          # 2 tiles per glyph, Windows-1251 codes 32..255
L1_PIECES = 448      # 12 pieces x 36 tiles
L1_DIGITS = 880      # 10 digits x 8 tiles
L1_COLON = 960       # 4 tiles
L1_COUNT = 964

# VRAM map.
VRAM_L0_TILES = 0x00000
VRAM_L1_TILES = 0x10000
VRAM_L1_MAP = 0x18000      # 128 x 64 entries
VRAM_L0_MAP = 0x1C000      # 64 x 32 entries
VRAM_SPRITES = 0x1D000
VRAM_POINTER = VRAM_SPRITES
VRAM_CURSOR = VRAM_SPRITES + 0x100

# Square highlight states (layer-0 variants), for each board style.
SQUARE_STATES = ['NORMAL', 'LASTMOVE', 'SELECTED', 'TARGET', 'CAPTURE', 'CHECK']
BOARD_THEMES = ['NEWSPRINT', 'WOOD']

# Figurine glyphs in the 8x16 font: FIGURINE_CODE + piece type.
FIGURINE_CODE = 0x80
