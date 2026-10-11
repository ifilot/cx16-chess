#include <stdint.h>
#include "storage.h"
#pragma static-locals (on)
#pragma code-name ("DRAGCODE")
#pragma bss-name ("DRAGBSS")

/* Shared hit testing, through a resident entry that restores the caller's bank.
 * Layouts: main, setup, two CPUs, options, about, pause, slots, replace. */
uint8_t menu_mouse_hit(uint16_t x, uint16_t y, uint8_t layout) {
    uint8_t index;
    if(layout == 0) {
        if(x >= 288 && x < 360 && y >= 368 && y < 448) return (y - 368) / 16;
    } else if(layout == 1 || layout == 2) {
        if(x < 344 || x >= 616) return 0xFF;
        if(y >= 136 && y < 184) return 0;
        if(y >= 208 && y < 248) return 1;
        if(layout == 2) {
            if(y >= 272 && y < 312) return 2;
            if(y >= 320 && y < 344) return 3;
        } else if(y >= 304 && y < 336) return 2;
    } else if(layout == 3) {
        if(x < 488 || x >= 632) return 0xFF;
        if(y >= 136 && y < 184) return 0;
        if(y >= 208 && y < 248) return 1;
        if(y >= 264 && y < 280) return 2;
        if(y >= 296 && y < 312) return 3;
        if(y >= 336 && y < 352) return 4;
        if(y >= 368 && y < 384) return 5;
    } else if(layout == 4) {
        if(x >= 440 && x < 520 && y >= 400 && y < 424) return 0;
    } else {
        if(x < (layout == 6 ? 152 : 176) || x >= (layout == 6 ? 456 : 432)) return 0xFF;
        if(layout == 6) {
            if(x >= 272 && x < 336 && y >= 384 && y < 400) return SAVE_SLOTS;
            for(index = 0; index < SAVE_SLOTS; index++)
                if(y >= (17 + index * 3) * 8 && y < (19 + index * 3) * 8) return index;
        } else if(layout == 7) {
            if(y >= 184 && y < 200) return 0;
            if(y >= 224 && y < 240) return 1;
        } else {
            if(y >= 176 && y < 192) return 0;
            if(y >= 216 && y < 232) return 1;
            if(y >= 256 && y < 272) return 2;
            if(y >= 296 && y < 312) return 3;
            if(y >= 336 && y < 352) return 4;
        }
    }
    return 0xFF;
}
