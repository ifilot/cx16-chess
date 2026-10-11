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
#define COL_GREY        10

#define SPRITE_POINTER  0
#define SPRITE_CURSOR   1

/*
 * Both layers use 8x8 tiles, addressed by (col, row) in 8-pixel units.
 * Layer 0 has two maps: PLAIN (board only) and INFO (with side columns).
 */

/**
 * @brief Set up 640x480 tile layers, pointer and resident font under the loading cover
 *
 * @return 0 when a graphics file could not be loaded
 */
uint8_t video_init(void);
/* View loads retain the Loading cover until the caller finishes drawing. */
void video_present(void);
uint8_t video_show_start(void);
uint8_t video_show_setup(void);
uint8_t video_show_about(void);
uint8_t video_show_game(void);
uint8_t video_show_options(void);
uint8_t video_load_piece_set(void);

/**
 * @brief Show the background with (1) or without (0) the side columns
 */
void video_show_info(uint8_t on);

/**
 * @brief Clear all of layer 1 (pieces and text)
 */
void video_clear_layer1(void);

/**
 * @brief Draw board square variant v (index into SQTILES.DAT) at a 7x7
 *        tile block, in both background maps
 */
void video_square(uint8_t col, uint8_t row, uint8_t v);

/**
 * @brief Draw bitmap text on layer 1; figurines occupy 16x16, text 8x16
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
 * @brief Blank a w x h block of layer-1 tiles
 */
void video_clear_block(uint8_t col, uint8_t row, uint8_t w, uint8_t h);

/**
 * @brief Draw a 56x56 piece (0-11), or clear the cell when piece is 0xFF
 */
void video_piece(uint8_t col, uint8_t row, uint8_t piece);

/**
 * @brief Put a single layer-1 tile
 */
void video_tile(uint8_t col, uint8_t row, uint16_t tile, uint8_t color);

/**
 * @brief Show the 64x64 cursor sprite at pixel position, or hide it
 */
void video_cursor(uint8_t visible, uint16_t x, uint16_t y);

#endif // _VIDEO_H
