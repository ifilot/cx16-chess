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
#include "assets.h"
#include "start.h"
#include "transition.h"

#define SPRITE_ATTR     0xFC00      // in VRAM bank 1
#define AUTO_INC_1      0x10
#define RAM_BANK        (*(volatile uint8_t*)0x00)
#define SQUARE_TABLE    ((const uint16_t*)0xA000)   // SQTILES.DAT in GUI_BANK

static uint8_t game_tables_loaded;

/**
 * @brief Point data port 0 at an entry of a 128-column map
 */
static void map_address(uint32_t map, uint8_t col, uint8_t row) {
    VERA.control = 0;
    VERA.address = (uint16_t)map + ((uint16_t)row << 8) + (col << 1);
    VERA.address_hi = AUTO_INC_1 | (uint8_t)(map >> 16);
}

/* View loaders run in menu bank 21; only the bulk reader is resident. */
static uint8_t load_vram(uint8_t resource, uint32_t addr);
static uint8_t load_shared(void);

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
    VERA.display.border = 0;                   // opaque artwork's black underlay
    VERA.display.hscale = 128;
    VERA.display.vscale = 128;

    /* Load banked loader/menu code before reading the graphics container. */
    RAM_BANK = 22;
    cbm_k_setnam("UI.BIN");
    cbm_k_setlfs(0, 8, 2);
    ok = cbm_k_load(0, 0xA000) != 0;
    if(!ok) { RAM_BANK = saved; return 0; }
    RAM_BANK = 21;
    cbm_k_setnam("MENU.BIN");
    cbm_k_setlfs(0, 8, 2);
    ok = cbm_k_load(0, 0xA000) != 0;
    if(ok) ok = load_shared();
    RAM_BANK = saved;
    if(!ok) return 0;
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

    /* Keep layers hidden until the opening artwork and labels are ready. */
    return 1;
}

void video_present(void) {
    transition_finish();
    VERA.control = 0;
    VERA.display.video |= 0x70;
}

void video_show_info(uint8_t on) {
    uint8_t value = (on ? VRAM_L0_MAP_INFO : VRAM_L0_MAP_PLAIN) >> 9;
    if(transition_covered) transition_mapbase = value;
    else VERA.layer0.mapbase = value;
}

/* Artwork shares VRAM with the playing field; read only the view's resources.
 * Engine banks, game history and pointer stay resident; each view loads its palette. */
/* Bank switching must run in resident code, never in MENUCODE at $A000. */
static uint8_t load_game_tables(void) {
    uint8_t ok, saved = RAM_BANK;
    if(!asset_prepare(ASSET_SQTILES)) return 0;
    asset_stream = 0;
    RAM_BANK = GUI_BANK;
    ok = asset_read(0xA000);
    RAM_BANK = saved;
    /* The INFO map is outside menu VRAM and stays resident as well. */
    if(!ok || !load_vram(ASSET_L0INFO, VRAM_L0_MAP_INFO)) return 0;
    game_tables_loaded = 1;
    return 1;
}

#pragma code-name (push, "MENUCODE")
static uint8_t load_vram(uint8_t resource, uint32_t addr) {
    if(!asset_prepare(resource)) return 0;
    VERA.control = 0;
    VERA.address = (uint16_t)addr;
    VERA.address_hi = AUTO_INC_1 | (uint8_t)(addr >> 16);
    asset_stream = 1;
    return asset_read(0x9F23);
}

static uint8_t load_shared(void) {
    return load_vram(ASSET_SPRITES, VRAM_SPRITES) &&
           load_vram(ASSET_FONT, VRAM_L1_TILES);
}

uint8_t video_show_start(void) {
    uint8_t ok;
    transition_begin();
    video_cursor(0, 0, 0);
    ok = load_vram(ASSET_SPLTILE, VRAM_L0_TILES) &&
         load_vram(ASSET_SPLMAP, VRAM_L0_MAP_PLAIN) &&
         load_vram(ASSET_SPL1ART, VRAM_L1_TILES + L1_PIECES * 32UL) &&
         load_vram(ASSET_SPL1MAP, VRAM_L1_MAP) &&
         load_vram(ASSET_PALETTE, 0x1FA00UL);
    video_show_info(0);
    return ok;
}

uint8_t video_show_setup(void) {
    uint8_t ok;
    transition_begin();
    ok = load_vram(ASSET_SETTILE, VRAM_L0_TILES) &&
         load_vram(ASSET_SETMAP, VRAM_L0_MAP_PLAIN) &&
         load_vram(ASSET_SET1ART, VRAM_L1_TILES + L1_PIECES * 32UL) &&
         load_vram(ASSET_SET1MAP, VRAM_L1_MAP) &&
         load_vram(ASSET_SETPAL, 0x1FA00UL);
    video_show_info(0);
    return ok;
}

uint8_t video_show_about(void) {
    uint8_t ok;
    transition_begin();
    ok = load_vram(ASSET_ABTTILE, VRAM_L0_TILES) &&
         load_vram(ASSET_ABTMAP, VRAM_L0_MAP_PLAIN) &&
         load_vram(ASSET_ABT1ART, VRAM_L1_TILES + L1_PIECES * 32UL) &&
         load_vram(ASSET_ABT1MAP, VRAM_L1_MAP) &&
         load_vram(ASSET_SETPAL, 0x1FA00UL);
    video_show_info(0);
    return ok;
}

uint8_t video_load_piece_set(void) {
    transition_begin();
    return load_vram(start_piece_set == 1 ? ASSET_ENGART :
                     start_piece_set == 2 ? ASSET_LETART : ASSET_L1ART,
                     VRAM_L1_TILES + L1_PIECES * 32UL);
}

uint8_t video_show_options(void) {
    if(!video_show_game()) return 0;
    if(!load_vram(ASSET_OPTMAP, VRAM_L0_MAP_PLAIN)) return 0;
    video_clear_layer1();
    video_show_info(0);
    return 1;
}

uint8_t video_show_game(void) {
    uint8_t ok;
    transition_begin();
    if(!game_tables_loaded && !load_game_tables()) return 0;
    ok = load_vram(ASSET_L0TILES, VRAM_L0_TILES) &&
         load_vram(ASSET_L0PLAIN, VRAM_L0_MAP_PLAIN) &&
         video_load_piece_set() &&
         load_vram(ASSET_PALETTE, 0x1FA00UL);
    video_show_info(1);
    return ok;
}

#pragma code-name (pop)

void video_clear_layer1(void) {
    map_address(VRAM_L1_MAP, 0, 0);
    /* 64 pages of 256 bytes; VERA auto-increments after every store. */
    asm("lda #0");
    asm("ldx #64");
page:
    asm("ldy #0");
byte:
    asm("sta $9F23");
    asm("iny");
    asm("bne %g", byte);
    asm("dex");
    asm("bne %g", page);
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

/**
 * @brief First tile of a glyph: two tiles per code of the FONT_RANGEs
 */
static uint16_t glyph_tile(uint8_t c) {
    uint8_t slot;

    if(c == MENU_ARROW_LEFT) slot = FONT_RANGE1_SLOT;
    else if(c == MENU_ARROW_RIGHT) slot = FONT_RANGE2_SLOT;
    else if(c >= FONT_RANGE0_FIRST && c <= FONT_RANGE0_LAST) slot = c - FONT_RANGE0_FIRST;
    else slot = 0;               // space for unsupported character codes
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
            if(*p > FIGURINE_CODE && *p <= FIGURINE_CODE + 6) {
                /* A figurine occupies two 8px columns on each tile row. */
                tile = L1_FIGURINES + ((uint16_t)(*p - FIGURINE_CODE - 1) << 2) + (half << 1);
                VERA.data0 = (uint8_t)tile;
                VERA.data0 = (uint8_t)(tile >> 8) | color;
                tile++;
            } else {
                tile = glyph_tile(*p) + half;
            }
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
    transition_cursor = visible ? (3 << 2) : 0;
    VERA.data0 = transition_covered ? 0 : transition_cursor;
}
