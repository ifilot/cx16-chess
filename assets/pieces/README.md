# Chess pieces

Options offers three newspaper sets: `victorian.png` (Victorian Diagram),
`continental.png` (Continental Engraving), and `letterpress.png` (Daily
Letterpress). Victorian is the default. Each sheet contains twelve 56×56 pieces in engine order:
white pawn, knight, bishop, rook, queen, king, then the black pieces.

The artwork was generated with imagegen from the user's historical newspaper
reference. It uses ink (index 1), paper (index 2), and transparent index 0.
A one-pixel paper halo keeps black silhouettes readable on hatched squares.
The PNG intentionally has no transparency metadata; the renderer treats
index 0 as transparent. Each piece uses 49 8×8 4bpp tiles.

`assets/scripts/build_graphics.py` packs all three sheets for VERA. Only the
selected set occupies VRAM, using 588 piece tiles. The sheets preserve the
approved mockup pixels without resizing or color changes. Prompts and source
information are retained in `newspaper-source.json`; historical references
are in `references.md`.

Original design studies and the unused Cburnett set by Colin M.L. Burnett
(GFDL/BSD/GPL, formerly `pieces.png` and `svg/`) were archived outside the
repository during cleanup. See `docs/cleanup-manifest.json` for the verified
archive and original member paths. Attribution is retained here.

## Scorecard figurines

`scorecard-source.png` is copied from the user-provided
`/mnt/c/tmp/chesspieces/set_regular/pieces_black_1.png`. Its six 15×15 pixel
cells are preserved without resampling, padded to 16×16, and reordered into
pawn, knight, bishop, rook, queen, king in `scorecard.png`. The source's three
opaque colors map to the game's ink, dark gray and gray; alpha becomes index 0.

The move list and thinking animation use these icons with a 16-pixel horizontal
advance and 8-pixel text. The atlas occupies 24 resident 8×8 tiles. The complete
foreground uses 833 of VERA’s 1,024 tiles, including the evaluation bar;
large clock glyphs and obsolete font slots have been removed.

`tools/scorecard_test.py` compares an actual emulator capture against native
source pixels for piece moves, captures, disambiguation, castling, promotions
and check/mate notation. Its preview uses notation fixtures in an isolated
emulator process.
