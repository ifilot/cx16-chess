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

#include <stdint.h>
#include "storage.h"

/* Hit testing is nonrecursive and runs only in the main loop. */
#pragma static-locals (on)
#pragma code-name ("DRAGCODE")
#pragma bss-name ("DRAGBSS")

/*
 * Mouse hit testing for every menu and dialog, shared through the resident
 * gui_mouse_hit() entry in drag.s, which restores the caller's bank.
 */

/**
 * @brief Find the menu entry under the pointer
 *
 * @param x      Pointer position in screen pixels
 * @param y      Pointer position in screen pixels
 * @param layout 0 main menu, 1 setup, 2 setup with two CPUs, 3 options,
 *               4 about, 5 pause, 6 save/load slots, 7 replace confirmation
 *
 * @return Entry index, SAVE_SLOTS for BACK in the slot table, or 0xFF
 *         when the pointer is not over an entry
 */
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
        // dialogs on the board panel
        if(x < (layout == 6 ? 152 : 176) || x >= (layout == 6 ? 456 : 432)) return 0xFF;
        if(layout == 6) {
            if(x >= 272 && x < 336 && y >= 384 && y < 400) return SAVE_SLOTS;
            // slot rows are three tiles apart, starting at tile row 17
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
