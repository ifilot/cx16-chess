"""Screen geometry of the playing field (640x480), shared with the C code.

Both tile layers use 8x8 tiles. Layer 0 has two complete playing-field maps:
PLAIN hides the move sheet; INFO shows it. The board, clocks and sidebar
remain in place. Menu artwork temporarily replaces both tile layers.
"""

BOARD_X, BOARD_Y, SQUARE = 24, 8, 56         # 448 x 448 board, scorecard on right
RANK_LABEL_COLS = (1, 59)

# right sidebar (clock labels/boxes, paired move sheet)
LEFT_X0, LEFT_X1 = 488, 631
RIGHT_X0, RIGHT_X1 = 488, 631
PLATE_Y = {'top': 72, 'bottom': 88}
MOVES_Y, MOVE_ROWS, MOVE_ROW_H = 128, 19, 16  # paired white/black moves

# Layer-1 tile numbering. Glyphs use two tiles each (8x16), in this order
# of character codes; unsupported codes show as blanks.
FONT_RANGES = [(32, 127), (0x80, 0x80), (0x87, 0x87)]
MENU_ARROW_LEFT, MENU_ARROW_RIGHT = 0x80, 0x87
L1_FONT = 0
L1_FIGURINES = 2 * sum(b - a + 1 for a, b in FONT_RANGES)
L1_PIECES = L1_FIGURINES + 6 * 4    # 12 pieces x 49 tiles
L1_FILES = L1_PIECES + 12 * 49                           # 8 small letters a-h
L1_BAR = L1_FILES + 8
L1_COUNT = L1_BAR + 17

# VRAM map
# No file may end exactly on a 64 KB boundary: cbm_k_load then returns end
# address $0000, which video.c cannot tell from a failed load.
VRAM_L0_TILES = 0x00000        # up to 768 tiles
VRAM_L0_MAP_PLAIN = 0x06000    # 128 x 64 entries
VRAM_L0_MAP_INFO = 0x0A000
VRAM_L1_TILES = 0x10000
VRAM_L1_MAP = 0x18000          # 128 x 64 entries
VRAM_SPRITES = 0x1D000
VRAM_POINTER = VRAM_SPRITES
VRAM_CURSOR = VRAM_SPRITES + 0x100

# board square tiles (SQTILES.DAT) are loaded into this RAM bank
GUI_BANK = 20

# Square highlight states (layer-0 variants), for each board style.
SQUARE_STATES = ['NORMAL', 'LASTMOVE', 'SELECTED', 'TARGET', 'CAPTURE', 'CHECK']
BOARD_THEMES = ['NEWSPRINT', 'WOOD', 'CROSSHATCH', 'COARSE']

# Figurine glyphs in the 8x16 font: FIGURINE_CODE + piece type.
FIGURINE_CODE = 0x80
