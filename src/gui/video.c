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
#define AUTO_INC_2      0x20
#define RAM_BANK        (*(volatile uint8_t*)0x00)
#define SQUARE_TABLE    ((const uint16_t*)0xA000)   // SQTILES.DAT in GUI_BANK

/**
 * @brief Point data port 0 at an entry of a 128-column map
 */
static void map_address(uint32_t map, uint8_t col, uint8_t row) {
    VERA.control = 0;
    VERA.address = (uint16_t)map + ((uint16_t)row << 8) + (col << 1);
    VERA.address_hi = AUTO_INC_1 | (uint8_t)(map >> 16);
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

uint8_t video_init(void) {
    uint8_t ok, saved = RAM_BANK;

    VERA.control = 0;
    VERA.display.video &= 0x0F;                 // hide everything while loading
    VERA.display.hscale = 128;
    VERA.display.vscale = 128;

    ok = load_vram("L0TILES.DAT", VRAM_L0_TILES) &&
         load_vram("L0PLAIN.DAT", VRAM_L0_MAP_PLAIN) &&
         load_vram("L0INFO.DAT", VRAM_L0_MAP_INFO) &&
         load_vram("L1TILES.DAT", VRAM_L1_TILES) &&
         load_vram("SPRITES.DAT", VRAM_SPRITES) &&
         load_vram("PALETTE.DAT", 0x1FA00UL);
    if(ok) {                                    // square variants into banked RAM
        RAM_BANK = GUI_BANK;
        cbm_k_setnam("SQTILES.DAT");
        cbm_k_setlfs(0, 8, 2);
        ok = cbm_k_load(0, 0xA000) != 0;
        RAM_BANK = saved;
    }
    if(!ok) {
        return 0;
    }
    video_clear_layer1();

    // layer 0: background, 128x64 map of 8x8 tiles at 4 bpp
    VERA.layer0.config = 0x62;
    VERA.layer0.mapbase = VRAM_L0_MAP_PLAIN >> 9;
    VERA.layer0.tilebase = VRAM_L0_TILES >> 9;
    VERA.layer0.hscroll = 0;
    VERA.layer0.vscroll = 0;

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

void video_show_info(uint8_t on) {
    VERA.layer0.mapbase = (on ? VRAM_L0_MAP_INFO : VRAM_L0_MAP_PLAIN) >> 9;
}

void video_clear_layer1(void) {
    uint16_t i;

    map_address(VRAM_L1_MAP, 0, 0);
    for(i=0; i<128*64; i++) {
        VERA.data0 = 0;
        VERA.data0 = 0;
    }
}

void video_square(uint8_t col, uint8_t row, uint8_t v) {
    const uint16_t* entries;
    uint8_t x, y, saved = RAM_BANK;
    uint32_t map = VRAM_L0_MAP_PLAIN;

    RAM_BANK = GUI_BANK;
    for(;;) {
        entries = SQUARE_TABLE + v * 49;
        for(y=0; y<7; y++) {
            map_address(map, col, row + y);
            for(x=0; x<7; x++) {
                VERA.data0 = (uint8_t)*entries;
                VERA.data0 = (uint8_t)(*entries >> 8);
                entries++;
            }
        }
        if(map == VRAM_L0_MAP_INFO) break;
        map = VRAM_L0_MAP_INFO;
    }
    RAM_BANK = saved;
}

void video_tint(uint8_t col, uint8_t row, uint8_t w, uint8_t h, uint8_t on) {
    uint16_t addr;
    uint8_t x, y, pal = on ? (TINT_ROW << 4) : 0;

    for(y=0; y<h; y++) {
        // high bytes of the entries: read through port 1, write through port 0
        addr = (uint16_t)VRAM_L0_MAP_INFO + ((uint16_t)(row + y) << 8) + (col << 1) + 1;
        VERA.control = 1;
        VERA.address = addr;
        VERA.address_hi = AUTO_INC_2 | (uint8_t)(VRAM_L0_MAP_INFO >> 16);
        VERA.control = 0;
        VERA.address = addr;
        VERA.address_hi = AUTO_INC_2 | (uint8_t)(VRAM_L0_MAP_INFO >> 16);
        for(x=0; x<w; x++) {
            VERA.data0 = (VERA.data1 & 0x0F) | pal;
        }
    }
}

/**
 * @brief First tile of a glyph: two tiles per code of the FONT_RANGEs
 */
static uint16_t glyph_tile(uint8_t c) {
    uint8_t slot;

    if(c >= FONT_RANGE4_FIRST) slot = c - FONT_RANGE4_FIRST + FONT_RANGE4_SLOT;
    else if(c >= FONT_RANGE3_FIRST && c <= FONT_RANGE3_LAST) slot = c - FONT_RANGE3_FIRST + FONT_RANGE3_SLOT;
    else if(c == FONT_RANGE2_FIRST) slot = FONT_RANGE2_SLOT;
    else if(c >= FONT_RANGE1_FIRST && c <= FONT_RANGE1_LAST) slot = c - FONT_RANGE1_FIRST + FONT_RANGE1_SLOT;
    else if(c >= FONT_RANGE0_FIRST && c <= FONT_RANGE0_LAST) slot = c - FONT_RANGE0_FIRST;
    else slot = 0;
    return L1_FONT + ((uint16_t)slot << 1);
}

void video_text(uint8_t col, uint8_t row, const char* s, uint8_t color) {
    const uint8_t* p;
    uint16_t tile;
    uint8_t half;

    color <<= 4;
    for(half=0; half<2; half++) {
        map_address(VRAM_L1_MAP, col, row + half);
        for(p = (const uint8_t*)s; *p; p++) {
            tile = glyph_tile(*p) + half;
            VERA.data0 = (uint8_t)tile;
            VERA.data0 = (uint8_t)(tile >> 8) | color;
        }
    }
}

void video_text_centered(uint16_t cx, uint8_t row, const char* s, uint8_t color) {
    uint16_t x = cx - (strlen(s) << 2) + 4;
    video_text(x >> 3, row, s, color);
}

void video_clear_block(uint8_t col, uint8_t row, uint8_t w, uint8_t h) {
    uint8_t x, y;

    for(y=0; y<h; y++) {
        map_address(VRAM_L1_MAP, col, row + y);
        for(x=0; x<w; x++) {
            VERA.data0 = 0;
            VERA.data0 = 0;
        }
    }
}

void video_text_clear(uint8_t col, uint8_t row, uint8_t n) {
    video_clear_block(col, row, n, 2);
}

void video_digits(uint8_t col, uint8_t row, const char* s, uint8_t color) {
    const char* p;
    uint16_t tile;
    uint8_t y;

    color <<= 4;
    for(y=0; y<4; y++) {
        map_address(VRAM_L1_MAP, col, row + y);
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

void video_piece(uint8_t col, uint8_t row, uint8_t piece) {
    uint16_t tile = L1_PIECES + piece * 49;
    uint8_t x, y;

    if(piece == 0xFF) {
        video_clear_block(col, row, 7, 7);
        return;
    }
    for(y=0; y<7; y++) {
        map_address(VRAM_L1_MAP, col, row + y);
        for(x=0; x<7; x++) {
            VERA.data0 = (uint8_t)tile;
            VERA.data0 = (uint8_t)(tile >> 8);
            tile++;
        }
    }
}

void video_tile(uint8_t col, uint8_t row, uint16_t tile, uint8_t color) {
    map_address(VRAM_L1_MAP, col, row);
    VERA.data0 = (uint8_t)tile;
    VERA.data0 = (uint8_t)(tile >> 8) | (color << 4);
}

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
