"""Approved native indicators: 05 selection, 02 movement, 04 captures.

Index zero is transparent. Paper keylines separate masthead red from ink.
"""
import numpy as np
from palette import PAPER, RED


def paper_keyline(mask):
    padded = np.pad(mask, 1)
    border = np.zeros_like(mask)
    for y in range(3):
        for x in range(3):
            border |= padded[y:y + mask.shape[0], x:x + mask.shape[1]]
    pixels = np.zeros(mask.shape, np.uint8)
    pixels[border] = PAPER
    pixels[mask] = RED
    return pixels


def selection():
    mask = np.zeros((56, 56), bool)
    for x, y, dx, dy in ((1, 1, 1, 1), (54, 1, -1, 1),
                         (1, 54, 1, -1), (54, 54, -1, -1)):
        for length in range(18):
            for thickness in range(3):
                mask[y + dy * thickness, x + dx * length] = True
                mask[y + dy * length, x + dx * thickness] = True
    return paper_keyline(mask)


def movement():
    y, x = np.mgrid[:56, :56]
    radius = (x - 27.5) ** 2 + (y - 27.5) ** 2
    return paper_keyline((radius <= 6.5 ** 2) & (radius >= 4.5 ** 2))


def capture():
    y, x = np.mgrid[:56, :56]
    return paper_keyline((x + y < 10) | ((55 - x) + y < 10) |
                         (x + (55 - y) < 10) | ((55 - x) + (55 - y) < 10))


def cursor():
    pixels = np.zeros((64, 64), np.uint8)
    pixels[4:60, 4:60] = selection()
    return pixels
