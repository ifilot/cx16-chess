"""Screen geometry of the playing field (640x480), shared with the C code.

Both tile layers use 8x8 tiles. Layer 0 (background) has two complete
maps in VRAM: PLAIN shows only the masthead, board and status bar; INFO
adds the side columns (players, clocks, photo, move list). Switching the
layer's map base toggles between them.
"""

BOARD_X, BOARD_Y, SQUARE = 96, 16, 56        # 448 x 448 board
STATUS_Y = 464                                # 16 px status bar
RANK_LABEL_COLS = (10, 69)                    # layer-1 columns left/right of the board

# side columns of the INFO view
LEFT_X0, LEFT_X1 = 4, 75
RIGHT_X0, RIGHT_X1 = 564, 635
PLATE_Y = {'top': 24, 'bottom': 408}          # 48 pixels high
CLOCK_Y = {'top': 80, 'bottom': 352}          # 48 pixels high
PHOTO_Y = 168                                 # framed halftone, 92 high
MOVES_Y, MOVE_ROWS, MOVE_ROW_H = 56, 25, 16   # move list: one half move per row

# status bar: text columns (8 px) of the values, separators (pixels)
STATUS_TURN_COL = 13                          # 10 characters
STATUS_BEST_COL = 36                          # 7 characters
STATUS_EVAL_COL = 52                          # 7 characters
STATUS_CLOCK_COL = 61                         # 11 characters
STATUS_SEPARATORS = (188, 348, 476, 598)
ANALYSE_BUTTON = (4, 63)                      # x range of the АНАЛИЗ box
INFO_BUTTON = (604, 635)                      # x range of the "—" box

# Layer-1 tile numbering. Glyphs use two tiles each (8x16), in this order
# of Windows-1251 codes; other codes show as blanks.
FONT_RANGES = [(32, 127), (0x80, 0x87), (0xA8, 0xA8), (0xB8, 0xB9), (0xC0, 0xFF)]
L1_FONT = 0
L1_PIECES = 2 * sum(b - a + 1 for a, b in FONT_RANGES)    # 12 pieces x 49 tiles
L1_DIGITS = L1_PIECES + 12 * 49                          # 10 digits x 8 tiles
L1_COLON = L1_DIGITS + 80                                # 4 tiles
L1_FILES = L1_COLON + 4                                  # 8 small letters a-h
L1_COUNT = L1_FILES + 8

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
BOARD_THEMES = ['NEWSPRINT', 'WOOD']

# Figurine glyphs in the 8x16 font: FIGURINE_CODE + piece type.
FIGURINE_CODE = 0x80

# Palette row used to tint layer-0 regions: paper becomes red (active
# clock, current move). Text never uses this colour row.
TINT_ROW = 14
