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

#include <cx16.h>
#include <cbm.h>
#include <ascii_charmap.h>
#pragma static-locals (on)
#include <string.h>

#include "video.h"

#define SPRITE_ATTR     0xFC00      // in VRAM bank 1
#define AUTO_INC_1      0x10

/**
 * @brief Point data port 0 at a layer-1 map entry
 */
static void layer1_address(uint8_t col, uint8_t row) {
    VERA.control = 0;
    VERA.address = (uint16_t)VRAM_L1_MAP + ((uint16_t)row << 8) + (col << 1);
    VERA.address_hi = AUTO_INC_1 | (uint8_t)(VRAM_L1_MAP >> 16);
}

/**
 * @brief Point data port 0 at a layer-0 map entry
 */
static void layer0_address(uint8_t col, uint8_t row) {
    VERA.control = 0;
    VERA.address = (uint16_t)VRAM_L0_MAP + ((uint16_t)row << 7) + (col << 1);
    VERA.address_hi = AUTO_INC_1 | (uint8_t)(VRAM_L0_MAP >> 16);
}

/**
 * @brief Load a headerless file straight into VRAM
 */
static uint8_t load_vram(const char* filename, uint32_t addr) {
    cbm_k_setnam(filename);
    cbm_k_setlfs(0, 8, 2);
    return cbm_k_load(2 + (uint8_t)(addr >> 16), (uint16_t)addr) != 0;
}

/**
 * @brief Set sprite attributes (except the position)
 */
static void sprite_setup(uint8_t n, uint32_t addr, uint8_t z, uint8_t size) {
    VERA.control = 0;
    VERA.address = SPRITE_ATTR + (n << 3);
    VERA.address_hi = AUTO_INC_1 | 1;
    VERA.data0 = (uint8_t)(addr >> 5);
    VERA.data0 = (uint8_t)(addr >> 13);         // 4 bpp
    VERA.address = SPRITE_ATTR + (n << 3) + 6;
    VERA.data0 = z << 2;
    VERA.data0 = size;
}

/**
 * @brief Set up 640x480 with two 4bpp tile layers and load all graphics
 */
uint8_t video_init(void) {
    uint8_t ok;

    VERA.control = 0;
    VERA.display.video &= 0x0F;                 // hide everything while loading
    VERA.display.hscale = 128;
    VERA.display.vscale = 128;

    ok = load_vram("L0TILES.DAT", VRAM_L0_TILES) &&
         load_vram("L0MAP.DAT", VRAM_L0_MAP) &&
         load_vram("L1TILES.DAT", VRAM_L1_TILES) &&
         load_vram("SPRITES.DAT", VRAM_SPRITES) &&
         load_vram("PALETTE.DAT", 0x1FA00UL);
    if(!ok) {
        return 0;
    }
    video_clear_layer1();

    // layer 0: background, 64x32 map of 16x16 tiles at 4 bpp, scrolled 8 px
    VERA.layer0.config = 0x12;
    VERA.layer0.mapbase = VRAM_L0_MAP >> 9;
    VERA.layer0.tilebase = (VRAM_L0_TILES >> 9) | 0x03;
    VERA.layer0.hscroll = SCROLL;
    VERA.layer0.vscroll = SCROLL;

    // layer 1: pieces and text, 128x64 map of 8x8 tiles at 4 bpp
    VERA.layer1.config = 0x62;
    VERA.layer1.mapbase = VRAM_L1_MAP >> 9;
    VERA.layer1.tilebase = VRAM_L1_TILES >> 9;
    VERA.layer1.hscroll = 0;
    VERA.layer1.vscroll = 0;

    sprite_setup(SPRITE_POINTER, VRAM_POINTER, 3, 0x50);   // 16x16
    sprite_setup(SPRITE_CURSOR, VRAM_CURSOR, 0, 0xF0);     // 64x64, hidden

    VERA.display.video = (VERA.display.video & 0x0F) | 0x70;
    return 1;
}

/**
 * @brief Clear all of layer 1 (pieces and text)
 */
void video_clear_layer1(void) {
    uint16_t i;

    layer1_address(0, 0);
    for(i=0; i<128*64; i++) {
        VERA.data0 = 0;
        VERA.data0 = 0;
    }
}

/**
 * @brief Copy a w x h block of map entries into layer 0
 */
void video_layer0_block(uint8_t col, uint8_t row, uint8_t w, uint8_t h,
                        const uint16_t* entries) {
    uint8_t x, y;

    for(y=0; y<h; y++) {
        layer0_address(col, row + y);
        for(x=0; x<w; x++) {
            VERA.data0 = (uint8_t)*entries;
            VERA.data0 = (uint8_t)(*entries >> 8);
            entries++;
        }
    }
}

/**
 * @brief Draw an 8x16 text string on layer 1 in the given palette colour
 *
 * Glyph code c uses tiles 2(c-32) (top half) and 2(c-32)+1 (bottom half).
 */
void video_text(uint8_t col, uint8_t row, const char* s, uint8_t color) {
    const uint8_t* p;
    uint16_t tile;
    uint8_t half;

    color <<= 4;
    for(half=0; half<2; half++) {
        layer1_address(col, row + half);
        for(p = (const uint8_t*)s; *p; p++) {
            tile = L1_FONT + ((uint16_t)(*p - 32) << 1) + half;
            VERA.data0 = (uint8_t)tile;
            VERA.data0 = (uint8_t)(tile >> 8) | color;
        }
    }
}

/**
 * @brief Draw text centred on pixel column cx (rounded to the 8 px grid)
 */
void video_text_centered(uint16_t cx, uint8_t row, const char* s, uint8_t color) {
    uint16_t x = cx - (strlen(s) << 2) + 4;
    video_text(x >> 3, row, s, color);
}

/**
 * @brief Blank n 8x16 character cells on layer 1
 */
void video_text_clear(uint8_t col, uint8_t row, uint8_t n) {
    uint8_t i, half;

    for(half=0; half<2; half++) {
        layer1_address(col, row + half);
        for(i=0; i<n; i++) {
            VERA.data0 = 0;
            VERA.data0 = 0;
        }
    }
}

/**
 * @brief Draw 16x32 clock digits ('0'-'9', ':' is 8 px wide)
 */
void video_digits(uint8_t col, uint8_t row, const char* s, uint8_t color) {
    const char* p;
    uint16_t tile;
    uint8_t y;

    color <<= 4;
    for(y=0; y<4; y++) {
        layer1_address(col, row + y);
        for(p = s; *p; p++) {
            if(*p == ':') {
                tile = L1_COLON + y;
                VERA.data0 = (uint8_t)tile;
                VERA.data0 = (uint8_t)(tile >> 8) | color;
            } else {
                tile = L1_DIGITS + ((*p - '0') << 3) + (y << 1);
                VERA.data0 = (uint8_t)tile;
                VERA.data0 = (uint8_t)(tile >> 8) | color;
                tile++;
                VERA.data0 = (uint8_t)tile;
                VERA.data0 = (uint8_t)(tile >> 8) | color;
            }
        }
    }
}

/**
 * @brief Draw a 48x48 piece (0-11), or clear the cell when piece is 0xFF
 */
void video_piece(uint8_t col, uint8_t row, uint8_t piece) {
    uint16_t tile = L1_PIECES + piece * 36;
    uint8_t x, y;

    for(y=0; y<6; y++) {
        layer1_address(col, row + y);
        if(piece == 0xFF) {
            for(x=0; x<6; x++) {
                VERA.data0 = 0;
                VERA.data0 = 0;
            }
        } else {
            for(x=0; x<6; x++) {
                VERA.data0 = (uint8_t)tile;
                VERA.data0 = (uint8_t)(tile >> 8);
                tile++;
            }
        }
    }
}

/**
 * @brief Show the 64x64 cursor sprite at pixel position, or hide it
 */
void video_cursor(uint8_t visible, uint16_t x, uint16_t y) {
    VERA.control = 0;
    VERA.address = SPRITE_ATTR + (SPRITE_CURSOR << 3) + 2;
    VERA.address_hi = AUTO_INC_1 | 1;
    VERA.data0 = (uint8_t)x;
    VERA.data0 = (uint8_t)(x >> 8);
    VERA.data0 = (uint8_t)y;
    VERA.data0 = (uint8_t)(y >> 8);
    VERA.data0 = visible ? (3 << 2) : 0;
}
