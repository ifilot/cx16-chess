# Fonts

All sheets are rendered from PT Serif by ParaType (SIL Open Font License 1.1)
by `assets/scripts/make_sources.py`; the PNGs are what the build uses.

* `font8x16.png`: PT Serif Bold condensed into 8x16 cells for the dynamic
  text on layer 1, Windows-1251 codes 32..255 (16 per row). Codes 0x81-0x86
  hold hand-drawn figurines (pawn .. king) for the move list.
* `digits16x32.png`: PT Serif Bold digits `0`-`9` and `:` for the clocks.
* `headline.png`, `small.png`, `italic.png`: proportional PT Serif Bold,
  Regular and Italic for static artwork (headings, dateline, captions); the
  `.json` files hold cell size, baseline and advance widths.
