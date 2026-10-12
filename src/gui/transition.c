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
#include "transition.h"
#include "gfx.h"

/* Transitions are nonrecursive and run only in the main loop. */
#pragma static-locals (on)
#pragma code-name ("MENUCODE")
#pragma rodata-name ("MENUCODE")

/*
 * The loading cover. The ONCE constructor in loading.s installs the paper
 * tile, cover map and Loading label before any disk read. While a scene
 * loads, layer 0 shows the cover map, sprite 2 the Loading label, and
 * sprites 3..14 twelve chess silhouettes doubled from the resident
 * scorecard figurines.
 */

/* A wrapping 32x32 map and a solid paper tile, outside every scene asset.
 * Sprite 2 holds the native font label. No disk reads are needed. */
#define COVER_MAP 0x1E000UL
#define COVER_TILE 0x1E800UL
#define LABEL 0x1EA00UL
/* Six 512-byte images end at $1F800, below PSG registers at $1F9C0. */
#define FIGURES 0x1EC00UL
/* Pixel positions of the twelve silhouettes, sprites 3..14 */
static const uint16_t positions[][2] = {
    {72,64}, {256,96}, {480,48}, {568,152}, {128,200}, {408,168},
    {48,352}, {216,304}, {496,336}, {352,400}, {136,424}, {568,424}
};
static uint8_t config;                  // layer-0 config of the covered scene
static uint8_t tilebase;                // layer-0 tile base of the covered scene
uint8_t transition_covered, transition_cursor, transition_mapbase;

/**
 * @brief Point data port 0 at VRAM bank 1, incrementing by one
 *
 * @param low Address within bank 1 ($10000-$1FFFF)
 */
static void address(uint16_t low) {
    VERA.control = 0;
    VERA.address = low;
    VERA.address_hi = 0x11;
}

/**
 * @brief Build six 32x32 silhouette sprites from the scorecard figurines
 *
 * Doubles the six resident 16x16 glyphs into soft, 32px silhouettes in a
 * single colour. Data port 1 reads tiles while port 0 writes sprites,
 * entirely in VRAM.
 */
static void build_figures(void) {
    uint8_t piece, y, half, col, value;
    for(piece = 0; piece < 6; piece++) {
        address((uint16_t)FIGURES + piece * 512);
        for(y = 0; y < 32; y++) {
            for(half = 0; half < 2; half++) {
                // source row y/2 of the left or right 8-pixel half of the glyph
                VERA.control = 1;
                VERA.address = (uint16_t)(VRAM_L1_TILES + L1_FIGURINES * 32UL) + piece * 128 + (y >> 4) * 64 + half * 32 + ((y >> 1) & 7) * 4;
                VERA.address_hi = 0x11;
                VERA.control = 0;
                for(col = 0; col < 4; col++) {
                    value = VERA.data1;
                    VERA.data0 = (value & 0xF0) ? 0x11 : 0;
                    VERA.data0 = (value & 0x0F) ? 0x11 : 0;
                }
            }
        }
    }
}

/**
 * @brief Show or hide the twelve silhouette sprites
 *
 * Showing writes all attributes; hiding only clears their depth.
 *
 * @param visible 1 to show, 0 to hide
 */
static void figurines(uint8_t visible) {
    uint8_t index;
    uint16_t source;
    for(index = 0; index < 12; index++) {
        if(!visible) {
            address(0xFC1E + index * 8);
            VERA.data0 = 0;
            continue;
        }
        source = (FIGURES >> 5) + (index % 6) * 16;
        address(0xFC18 + index * 8);
        VERA.data0 = source; VERA.data0 = source >> 8;
        VERA.data0 = positions[index][0]; VERA.data0 = positions[index][0] >> 8;
        VERA.data0 = positions[index][1]; VERA.data0 = positions[index][1] >> 8;
        VERA.data0 = visible ? 12 | (index & 1) : 0;
        VERA.data0 = 0xA5; /* 32x32, muted brown; alternate mirrored pieces */
    }
}

/**
 * @brief Build the silhouettes from the resident font and show them
 *
 * The ONCE constructor already installed the paper, label and cover map.
 * Font-derived silhouettes become available after the shared font loads.
 * The scene to restore afterwards is the plain board map.
 */
void transition_startup(void) {
    config = 0x62;
    transition_mapbase = VRAM_L0_MAP_PLAIN >> 9;
    tilebase = VRAM_L0_TILES >> 9;
    build_figures();
    figurines(1);
}

/**
 * @brief Cover the screen and remember the layer-0 setup of the scene
 *
 * Hides the pointer and keyboard cursor, shows the Loading label and the
 * silhouettes, and points layer 0 at the cover map with layer 1 hidden.
 */
void transition_begin(void) {
    if(transition_covered) return;
    config = VERA.layer0.config;
    transition_mapbase = VERA.layer0.mapbase;
    tilebase = VERA.layer0.tilebase;
    address(0xFC0E); transition_cursor = VERA.data0;
    address(0xFC06); VERA.data0 = 0;
    address(0xFC0E); VERA.data0 = 0;
    // sprite 2: the Loading label
    address(0xFC10);
    VERA.data0 = (uint8_t)(LABEL >> 5);
    VERA.data0 = (uint8_t)(LABEL >> 13);
    /* Center the visible ink (local 31,8), rather than its 64x16 canvas. */
    VERA.data0 = 33; VERA.data0 = 1; /* x = 320 - 31 = 289 */
    VERA.data0 = 232; VERA.data0 = 0; /* y = 240 - 8 */
    VERA.data0 = 12; VERA.data0 = 0x77; /* 64x16, red palette */
    figurines(1);
    VERA.layer0.config = 0x02;
    VERA.layer0.mapbase = COVER_MAP >> 9;
    VERA.layer0.tilebase = COVER_TILE >> 9;
    // layer 0 and sprites on, layer 1 off
    VERA.display.video = (VERA.display.video & 15) | 0x50;
    transition_covered = 1;
}

/**
 * @brief Restore layer 0, the pointer and the cursor, and hide the cover
 *        sprites; does nothing when the screen is not covered
 */
static void finish(void) {
    if(transition_covered) {
        figurines(0);
        VERA.layer0.config = config;
        VERA.layer0.mapbase = transition_mapbase;
        VERA.layer0.tilebase = tilebase;
        address(0xFC16); VERA.data0 = 0;
        address(0xFC06); VERA.data0 = 12;
        address(0xFC0E); VERA.data0 = transition_cursor;
        transition_covered = 0;
    }
}

#pragma code-name ("CODE")
/**
 * @brief Remove the cover and restore layer 0 and the keyboard cursor
 *
 * Resident; selects bank 21 and restores the caller's bank.
 */
void transition_finish(void) {
    uint8_t saved = *(uint8_t*)0;
    *(uint8_t*)0 = 21;
    finish();
    *(uint8_t*)0 = saved;
}
