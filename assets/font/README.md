# Bitmap font

`kakuro-ui.png` is the native 8×8 ASCII font copied from Ivo Filot’s
`cx16-kakuro/assets/tiles/ui-charmap.png` (GPL-3.0-or-later). The alpha mask
uses the same >150 cutoff as Kakuro’s exporter.

`python3 assets/scripts/bitmap_font.py` regenerates `font8x16.png`: 96 ASCII
cells, with each original 8×8 glyph centered vertically in an 8×16 cell.
Titles repeat pixels at integer scales; game clocks use the native glyphs.
The serif masthead uses `headline.png` and `headline.json`, retained PT Serif
artwork (ParaType, SIL Open Font License 1.1).

The packed font keeps ASCII 0x20–0x7F plus two generated menu arrows at 0x80
and 0x87: 98 glyphs, two tiles each, or 196 tiles. Unsupported codes display
a space. The six 16×16 figurines at 0x81–0x86 use the separate scorecard atlas
and four tiles each; they are not narrow font glyphs.

| Removed code range | Old meaning | Glyph slots | 8×8 tiles |
| --- | --- | ---: | ---: |
| 0xA8 | Cyrillic uppercase Ё | 1 | 2 |
| 0xB8–0xB9 | Cyrillic lowercase ё and № | 2 | 4 |
| 0xC0–0xFF | Cyrillic alphabet | 64 | 128 |
| 0x81–0x86 | Legacy narrow chess icons | 6 | 12 |
| Total | | 73 | 146 |

These code ranges came from the previous Windows-1251 font layout. The
current UI uses English ASCII; unused Russian string definitions have been
removed. The Kakuro source has no Cyrillic glyphs, so those legacy slots
contained repeated question-mark fallback pixels rather than usable Cyrillic
lettering. The six narrow chess icons were bypassed by `video_text`, which
already renders the stronger 16×16 icons from `scorecard.png`.

The resident font and figurines now occupy 220 tiles / 7,040 bytes, down from
366 tiles / 11,712 bytes: 4,672 fewer bytes loaded at startup. Removing the
unused large clock digits and colon saves 42 additional tiles / 1,344 bytes.
The complete game foreground now uses 833 of VERA’s 1,024 tiles (191 free),
down from 1,021 (three free). ASCII, arrows, mini icons, and masthead pixels
are preserved. Tests compare native glyphs and approved graphics fixtures.
