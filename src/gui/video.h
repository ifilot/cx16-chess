/**************************************************************************
 *                                                                        *
 *   Author: Ivo Filot <ivo@ivofilot.nl>                                  *
 *                                                                        *
 *   CX16-CHESS is free software:                                         *
 *   you can redistribute it and/or modify it under the terms of the      *
 *   GNU General Public License as published by the Free Software         *
 *   Foundation, either version 3 of the License, or (at your option)     *
 *   any later version.                                                   *
 *                                                                        *
 *   CX16-CHESS is distributed in the hope that it will be useful,        *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty          *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.              *
 *   See the GNU General Public License for more details.                 *
 *                                                                        *
 *   You should have received a copy of the GNU General Public License    *
 *   along with this program.  If not, see http://www.gnu.org/licenses/.  *
 *                                                                        *
 **************************************************************************/

#ifndef _VIDEO_H
#define _VIDEO_H

#include <stdint.h>

#include "gfx.h"

// palette indices (see assets/scripts/palette.py)
#define COL_INK         1
#define COL_PAPER       2
#define COL_RED         7
#define COL_CREAM       9
#define COL_GREY        10

#define SPRITE_POINTER  0
#define SPRITE_CURSOR   1

/**
 * @brief Set up 640x480 with two 4bpp tile layers and load all graphics
 *
 * @return 0 when a graphics file could not be loaded
 */
uint8_t video_init(void);

/**
 * @brief Clear all of layer 1 (pieces and text)
 */
void video_clear_layer1(void);

/**
 * @brief Copy a w x h block of map entries into layer 0
 */
void video_layer0_block(uint8_t col, uint8_t row, uint8_t w, uint8_t h,
                        const uint16_t* entries);

/**
 * @brief Draw an 8x16 text string on layer 1 in the given palette colour
 */
void video_text(uint8_t col, uint8_t row, const char* s, uint8_t color);

/**
 * @brief Draw text centred on pixel column cx (rounded to the 8 px grid)
 */
void video_text_centered(uint16_t cx, uint8_t row, const char* s, uint8_t color);

/**
 * @brief Blank n 8x16 character cells on layer 1
 */
void video_text_clear(uint8_t col, uint8_t row, uint8_t n);

/**
 * @brief Draw 16x32 clock digits ('0'-'9', ':' is 8 px wide)
 */
void video_digits(uint8_t col, uint8_t row, const char* s, uint8_t color);

/**
 * @brief Draw a 48x48 piece (0-11), or clear the cell when piece is 0xFF
 */
void video_piece(uint8_t col, uint8_t row, uint8_t piece);

/**
 * @brief Show the 64x64 cursor sprite at pixel position, or hide it
 */
void video_cursor(uint8_t visible, uint16_t x, uint16_t y);

#endif // _VIDEO_H
