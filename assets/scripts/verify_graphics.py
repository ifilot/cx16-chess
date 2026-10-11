"""Decode exported VERA assets and verify opaque artwork pixel for pixel.

This module consumes packed bytes, map entries and the hardware palette.
It models palette offsets, flips, index-zero transparency and the backdrop.
It never quantizes, resizes, or repairs the artwork being verified.
"""
from pathlib import Path

import numpy as np

from palette import RGB12, vera_palette

WIDTH, HEIGHT = 640, 480


def decode_tiles(data):
    if not data or len(data) % 32:
        raise ValueError('4bpp 8x8 tile data must contain complete 32-byte tiles')
    packed = np.frombuffer(data, dtype=np.uint8).reshape(-1, 32)
    pixels = np.empty((len(packed), 64), np.uint8)
    pixels[:, 0::2] = packed >> 4
    pixels[:, 1::2] = packed & 15
    return pixels.reshape(-1, 8, 8)


def decode_layer(tile_data, map_data):
    tiles = decode_tiles(tile_data)
    if len(map_data) != 128 * 64 * 2:
        raise ValueError('VERA map must contain exactly 128x64 entries')
    entries = np.frombuffer(map_data, dtype='<u2').reshape(64, 128)
    pixels = np.empty((HEIGHT, WIDTH), np.uint8)
    for row in range(HEIGHT // 8):
        for col in range(WIDTH // 8):
            entry = int(entries[row, col])
            index = entry & 1023
            if index >= len(tiles):
                raise ValueError(f'Map references missing tile {index} at ({col}, {row})')
            tile = tiles[index]
            if entry & 1024:
                tile = tile[:, ::-1]
            if entry & 2048:
                tile = tile[::-1]
            # Zero stays transparent, even if a palette offset is specified.
            pixels[row * 8:row * 8 + 8, col * 8:col * 8 + 8] = np.where(
                tile != 0, tile + ((entry >> 12) * 16), 0)
    return pixels


def composite(layer0_tiles, layer0_map, layer1_tiles, layer1_map, palette_data=None):
    base = decode_layer(layer0_tiles, layer0_map)
    overlay = decode_layer(layer1_tiles, layer1_map)
    pixels = np.where(overlay != 0, overlay, base)
    palette = np.frombuffer(vera_palette() if palette_data is None else palette_data,
                            dtype='<u2')
    if len(palette) != 256:
        raise ValueError('VERA palette must contain 256 12-bit entries')
    return palette[pixels]


def verify_artwork(dest, prefix, expected, palette_data=None, expected_palette=RGB12):
    dest = Path(dest)
    # Verify the exact files loaded at runtime, including resident font tiles.
    foreground = (dest / 'FONT.DAT').read_bytes() + (dest / f'{prefix}1ART.DAT').read_bytes()
    actual = composite((dest / f'{prefix}TILE.DAT').read_bytes(),
                       (dest / f'{prefix}MAP.DAT').read_bytes(), foreground,
                       (dest / f'{prefix}1MAP.DAT').read_bytes(),
                       palette_data=palette_data)
    expected_colors = np.array(expected_palette, dtype=np.uint16)[expected]
    differences = actual != expected_colors
    if differences.any():
        y, x = np.argwhere(differences)[0]
        raise ValueError(f'{prefix}: {int(differences.sum())} artwork pixels changed; '
                         f'first at ({x}, {y}), expected {expected_colors[y, x]:03x}, '
                         f'rendered {actual[y, x]:03x}')
    # Return the verified palette indices to build the preview from the
    # reconstructed output, rather than bypassing the exporter.
    result = np.empty_like(expected)
    for index in reversed(range(len(expected_palette))):
        color = expected_palette[index]
        result[actual == color] = index
    return result
