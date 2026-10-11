#include <cx16.h>
#include "transition.h"
#include "gfx.h"
#pragma static-locals (on)
#pragma code-name ("MENUCODE")
#pragma rodata-name ("MENUCODE")

/* A wrapping 32x32 map and a solid paper tile, outside every scene asset.
 * Sprite 2 holds the native font label. No disk reads are needed. */
#define COVER_MAP 0x1E000UL
#define COVER_TILE 0x1E800UL
#define LABEL 0x1EA00UL
#define FIGURES 0x1EE00UL
static const uint16_t positions[][2] = {
    {72,64}, {256,96}, {480,48}, {568,152}, {128,200}, {408,168},
    {48,352}, {216,304}, {496,336}, {352,400}, {136,424}, {568,424}
};
static uint8_t config, tilebase;
uint8_t transition_covered, transition_cursor, transition_mapbase;
static void address(uint16_t low) {
    VERA.control = 0;
    VERA.address = low;
    VERA.address_hi = 0x11;
}
/* Double the six resident scorecard glyphs into soft, 32px silhouettes.
 * Data port 1 reads tiles while port 0 writes sprites, entirely in VRAM. */
static void build_figures(void) {
    uint8_t piece, y, half, col, value;
    for(piece = 0; piece < 6; piece++) {
        address((uint16_t)FIGURES + piece * 512);
        for(y = 0; y < 32; y++) {
            for(half = 0; half < 2; half++) {
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
/* The ONCE constructor already installed the paper, label and cover map.
 * Font-derived silhouettes become available after the shared font loads. */
void transition_startup(void) {
    config = 0x62;
    transition_mapbase = VRAM_L0_MAP_PLAIN >> 9;
    tilebase = VRAM_L0_TILES >> 9;
    build_figures();
    figurines(1);
}
void transition_begin(void) {
    if(transition_covered) return;
    config = VERA.layer0.config;
    transition_mapbase = VERA.layer0.mapbase;
    tilebase = VERA.layer0.tilebase;
    address(0xFC0E); transition_cursor = VERA.data0;
    address(0xFC06); VERA.data0 = 0;
    address(0xFC0E); VERA.data0 = 0;
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
    VERA.display.video = (VERA.display.video & 15) | 0x50;
    transition_covered = 1;
}
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
void transition_finish(void) {
    uint8_t saved = *(uint8_t*)0;
    *(uint8_t*)0 = 21;
    finish();
    *(uint8_t*)0 = saved;
}
