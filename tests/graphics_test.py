"""Regression tests for opaque dithered portraits on transparent VERA layers."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets/scripts'))
from build_graphics import ASSETS, build_splash, load_indexed, menu_artwork, pack4
from bitmap_font import glyph8
from build_graphics import FONT, FIGURINES16, build_layer1
import layout as L
import indicators
from build_graphics import square_image, build_sprites
from build_graphics import build_layer0, render_options
from palette import RGB12, SPLASH_RGB12, SETUP_RGB12, INK, PAPER, pil_palette, vera_palette, splash_colors
from verify_graphics import composite, decode_layer, decode_tiles, verify_artwork
from PIL import Image


def map_bytes(index):
    return np.full(128 * 64, index, dtype='<u2').tobytes()


class ArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.dest = Path(cls.temp.name)
        build_splash(cls.dest)
        build_splash(cls.dest, 'setup', 'SET')
        build_splash(cls.dest, 'about', 'ABT')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_portrait_export_is_lossless(self):
        expected = menu_artwork('splash')
        decoded = verify_artwork(self.dest, 'SPL', expected,
                                 (self.dest / 'SPLPAL.DAT').read_bytes(), splash_colors())
        np.testing.assert_array_equal(decoded, expected)
        # The entire queen portrait must also survive the layer split.
        actual = composite((self.dest / 'SETTILE.DAT').read_bytes(),
                           (self.dest / 'SETMAP.DAT').read_bytes(),
                           (self.dest / 'FONT.DAT').read_bytes() + (self.dest / 'SET1ART.DAT').read_bytes(),
                           (self.dest / 'SET1MAP.DAT').read_bytes(),
                           palette_data=(self.dest / 'SETPAL.DAT').read_bytes())
        expected = load_indexed(ASSETS / 'art/setup.png', SETUP_RGB12)
        np.testing.assert_array_equal(actual[:, :320], np.array(SETUP_RGB12)[expected[:, :320]])
        self.assertEqual(set(np.unique(expected[:, :320])) - {PAPER}, {0, 3, 4, 12})
        self.assertTrue(np.any(expected[-1, :320] != PAPER))

    def test_about_portrait_export_is_lossless(self):
        expected = menu_artwork('about')
        decoded = verify_artwork(self.dest, 'ABT', expected,
                                 (self.dest / 'ABTPAL.DAT').read_bytes(), splash_colors(SETUP_RGB12))
        np.testing.assert_array_equal(decoded, expected)
        original = load_indexed(ASSETS / 'art/about.png', SETUP_RGB12)
        np.testing.assert_array_equal(expected[:, :320], original[:, :320])
        self.assertEqual(set(np.unique(expected[:, :320])) - {PAPER}, {0, 3, 4, 12})
        self.assertTrue(np.any(expected[-1, :320] != PAPER))

    def test_new_game_serif_heading_survives_tile_packing(self):
        expected = menu_artwork('setup')
        decoded = verify_artwork(self.dest, 'SET', expected,
                                 (self.dest / 'SETPAL.DAT').read_bytes(),
                                 splash_colors(SETUP_RGB12))
        np.testing.assert_array_equal(decoded, expected)
        heading = expected[48:96, 344:616]
        self.assertEqual(set(np.unique(heading)), {PAPER, 7, 243, 244, 245, 246})
        rows, columns = np.nonzero(heading != PAPER)
        self.assertLessEqual(abs(int(columns.min() + columns.max()) - 271), 1)
        self.assertLessEqual(abs(int(rows.min() + rows.max()) - 43), 1)

    def test_game_serif_heading_survives_both_tile_maps(self):
        tiles, maps, _, plain, info = build_layer0()
        colors = np.array(splash_colors(), dtype=np.uint16)
        for tilemap, expected in zip(maps, (plain, info)):
            decoded = decode_layer(tiles.data(), tilemap)
            np.testing.assert_array_equal(colors[decoded], colors[expected])
            heading = expected[:36, 488:632]
            self.assertEqual(set(np.unique(heading)), {PAPER, 7, 243, 244, 245, 246})
            rows, columns = np.nonzero(heading != PAPER)
            self.assertLessEqual(abs(int(columns.min() + columns.max()) - 143), 1)
            self.assertLessEqual(abs(int(rows.min() + rows.max()) - 44), 1)

    def test_about_and_options_serif_headings_are_centered_and_pack_exactly(self):
        tiles, maps, _, _, _ = build_layer0()
        options = render_options()
        colors = np.array(splash_colors(), dtype=np.uint16)
        decoded = decode_layer(tiles.data(), maps[2])
        np.testing.assert_array_equal(colors[decoded], colors[options])
        for image, x0, x1, cy in ((menu_artwork('about'), 344, 616, 72), (options, 488, 632, 70)):
            heading = image[48:96, x0:x1]
            self.assertEqual(set(np.unique(heading)), {PAPER, 7, 243, 244, 245, 246})
            rows, columns = np.nonzero(heading != PAPER)
            self.assertLessEqual(abs(int(columns.min() + columns.max()) - (x1 - x0 - 1)), 1)
            self.assertLessEqual(abs(int(rows.min() + rows.max()) - (2 * (cy - 48) - 1)), 1)

    def test_masthead_keeps_portrait_and_solid_ink(self):
        original = load_indexed(ASSETS / 'art/splash.png')
        refined = menu_artwork('splash')
        np.testing.assert_array_equal(refined[96:], original[96:])
        np.testing.assert_array_equal(refined[80:96, 272:304], original[80:96, 272:304])
        np.testing.assert_array_equal(refined[original == 0], original[original == 0])
        np.testing.assert_array_equal(refined[original == 7], original[original == 7])
        self.assertEqual(set(np.unique(refined[refined >= 16])), {243, 244, 245, 246})
        # Extra colors belong only to the selected tile palette. Base artwork
        # colors and every text palette's ink entry retain their exact values.
        palette = np.frombuffer(vera_palette(), dtype='<u2').reshape(16, 16)
        np.testing.assert_array_equal(palette[0], RGB12)
        np.testing.assert_array_equal(palette[:, 1], RGB12[1:2] + RGB12[1:])

    def test_native_bitmap_pixels(self):
        for code in range(32, 128):
            slot = code - 32
            actual = FONT[slot // 16 * 16:slot // 16 * 16 + 16,
                          slot % 16 * 8:slot % 16 * 8 + 8]
            expected = np.zeros((16, 8), np.uint8)
            expected[4:12] = glyph8(code)
            np.testing.assert_array_equal(actual, expected)
    def test_packed_16px_figurines_preserve_pixels(self):
        tiles = decode_tiles(build_layer1())
        for piece in range(6):
            offset = L.L1_FIGURINES + piece * 4
            actual = np.block([[tiles[offset], tiles[offset + 1]],
                               [tiles[offset + 2], tiles[offset + 3]]])
            np.testing.assert_array_equal(actual, FIGURINES16[:, piece * 16:(piece + 1) * 16])
    def test_all_newspaper_sets_pack_without_changing_pixels(self):
        for name in ('victorian', 'continental', 'letterpress'):
            sheet = load_indexed(ASSETS / f'pieces/{name}.png')
            self.assertEqual(sheet.shape, (56, 672))
            self.assertTrue(set(np.unique(sheet)) <= {0, 1, 2})
            tiles = decode_tiles(build_layer1(sheet))
            for piece in range(12):
                offset = L.L1_PIECES + piece * 49
                actual = np.block([[tiles[offset + row * 7 + col]
                                    for col in range(7)] for row in range(7)])
                np.testing.assert_array_equal(actual, sheet[:, piece * 56:(piece + 1) * 56])

    def test_approved_indicators_match_review_and_remove_selection_tint(self):
        import json
        path = ASSETS.parent / 'tests/fixtures/graphics/indicators-approved.json'
        reference = json.loads(path.read_text())
        np.testing.assert_array_equal(indicators.cursor(), reference['cursor'])
        np.testing.assert_array_equal(indicators.movement(), reference['movement'])
        np.testing.assert_array_equal(indicators.capture(), reference['capture'])
        self.assertEqual(set(np.unique(indicators.cursor())), {0, PAPER, 7})
        for theme in L.BOARD_THEMES:
            for light in (False, True):
                normal = square_image(theme, light, 'NORMAL')
                for state, overlay in [('SELECTED', indicators.selection()),
                                       ('TARGET', indicators.movement()),
                                       ('CAPTURE', indicators.capture())]:
                    actual = square_image(theme, light, state)
                    np.testing.assert_array_equal(actual[overlay == 0], normal[overlay == 0])
                    np.testing.assert_array_equal(actual[overlay != 0], overlay[overlay != 0])
                    self.assertFalse(np.any(np.isin(actual, [13, 14])))
        sprite = build_sprites()[L.VRAM_CURSOR - L.VRAM_POINTER:]
        packed = np.frombuffer(sprite, np.uint8)
        decoded = np.empty(4096, np.uint8)
        decoded[::2], decoded[1::2] = packed >> 4, packed & 15
        np.testing.assert_array_equal(decoded.reshape(64, 64), reference['cursor'])

    def test_compact_font_and_runtime_files_have_no_legacy_slots(self):
        self.assertEqual(L.L1_FIGURINES, 196)  # 96 ASCII + two arrows, two tiles each
        self.assertEqual(L.L1_PIECES, 220)     # six 16x16 icons add 24 tiles
        self.assertEqual(L.L1_COUNT, 833)
        self.assertEqual(len(build_layer1()), 833 * 32)
        self.assertEqual((self.dest / 'FONT.DAT').stat().st_size, 7040)
        self.assertFalse((self.dest / 'SPL1TIL.DAT').exists())
        self.assertFalse((self.dest / 'SET1TIL.DAT').exists())

    def test_all_sixteen_colors_are_opaque_with_black_underlay(self):
        tile = np.arange(64, dtype=np.uint8).reshape(8, 8) % 16
        black = np.zeros((8, 8), np.uint8)
        actual = composite(pack4(black), map_bytes(0), pack4(tile), map_bytes(0))
        expected = np.array(RGB12)[np.tile(tile, (60, 80))]
        np.testing.assert_array_equal(actual, expected)
        # Reproduce the former bug: transparent black becomes paper.
        paper = np.full((8, 8), PAPER, np.uint8)
        broken = composite(pack4(paper), map_bytes(0), pack4(tile), map_bytes(0))
        self.assertEqual(int((broken != expected).sum()), 640 * 480 // 16)

    def test_old_paper_underlay_fails_pixel_verification(self):
        expected = menu_artwork('setup')
        path = self.dest / 'SETMAP.DAT'
        original = path.read_bytes()
        entries = np.frombuffer(original, dtype='<u2').copy()
        overlay = np.frombuffer((self.dest / 'SET1MAP.DAT').read_bytes(), dtype='<u2')
        entries[overlay != 0] = 0  # tile zero is paper
        path.write_bytes(entries.tobytes())
        try:
            with self.assertRaisesRegex(ValueError, 'artwork pixels changed'):
                verify_artwork(self.dest, 'SET', expected,
                               (self.dest / 'SETPAL.DAT').read_bytes(), splash_colors(SETUP_RGB12))
        finally:
            path.write_bytes(original)

    def test_palette_cannot_silently_recolor_ink(self):
        data = bytearray(vera_palette(SETUP_RGB12))
        self.assertEqual(int.from_bytes(data[2:4], 'little'), RGB12[INK])
        data[2:4] = b'\0\0'  # previous palette row zero mapped ink to black
        with self.assertRaisesRegex(ValueError, 'artwork pixels changed'):
            verify_artwork(self.dest, 'SET', menu_artwork('setup'), data, splash_colors(SETUP_RGB12))

    def test_bad_tile_data_and_indices_fail(self):
        with self.assertRaises(ValueError):
            decode_tiles(bytes(31))
        with self.assertRaisesRegex(ValueError, 'missing tile'):
            decode_layer(bytes(32), map_bytes(1023))
        with self.assertRaises(ValueError):
            decode_layer(bytes(32), bytes(16382))

    def test_source_palette_order_must_match_hardware(self):
        im = Image.new('P', (8, 8), PAPER)
        colors = pil_palette()
        colors[PAPER * 3:PAPER * 3 + 3] = [0, 0, 0]
        im.putpalette(colors)
        path = self.dest / 'wrong-palette.png'
        im.save(path)
        with self.assertRaisesRegex(ValueError, 'does not match the project palette'):
            load_indexed(path)


if __name__ == '__main__':
    unittest.main()
