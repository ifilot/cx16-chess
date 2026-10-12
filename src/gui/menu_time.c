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

#include <ascii_charmap.h>
#include <stdint.h>
#include <string.h>
#include "video.h"

/* Menu helpers are nonrecursive and run only in the main loop. */
#pragma static-locals (on)
#pragma code-name ("DRAGCODE")
#pragma rodata-name ("DRAGCODE")
#pragma bss-name ("DRAGBSS")

/*
 * The average move time line of the New Game setup. It lives in board
 * bank 23 to leave room in the menu bank.
 */

/* Measured averages at 8 MHz, rounded for display and indexed by
 * DIFFICULTY_*; positions vary widely. IDs retain legacy 5-ply saves.
 * Weak levels and 1 ply take about 0.4 seconds. */
static const char* const seconds[] = {
    "0.7", "1.5", "4", "10", "26", "0.4", "0.4", "0.4", "60", "204"
};
static char hint[33];                   // the 32-character line being built

/**
 * @brief Draw the average calculation time per move below the settings
 *
 * Called through the resident start_draw_time() entry with RAM bank 23
 * selected.
 *
 * @param white   DIFFICULTY_* of the (White) computer
 * @param black   DIFFICULTY_* of Black in CPU vs CPU
 * @param players Side setting: 0 White, 1 Black, 2 CPU vs CPU, 3 two players
 */
void menu_draw_time(uint8_t white, uint8_t black, uint8_t players) {
    uint8_t length;
    if(players == 3) {
        strcpy(hint, "LOCAL TWO PLAYER");
    } else {
        strcpy(hint, players == 2 ? "AVG: W ~" : "AVG. ~");
        strcat(hint, seconds[white]);
        if(players == 2) {
            strcat(hint, "S / B ~");
            strcat(hint, seconds[black]);
            strcat(hint, "S PER MOVE");
        } else strcat(hint, " SEC / MOVE");
    }
    /* Replace the whole line when changing to a shorter value or mode. */
    length = strlen(hint);
    memset(hint + length, ' ', 32 - length);
    hint[32] = 0;
    video_text(44, 32, hint, COL_GREY);
}
