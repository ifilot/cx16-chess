#include <ascii_charmap.h>
#include <stdint.h>
#include <string.h>
#include "video.h"

#pragma static-locals (on)
#pragma code-name ("DRAGCODE")
#pragma rodata-name ("DRAGCODE")
#pragma bss-name ("DRAGBSS")

/* Measured averages at 8 MHz, rounded for display; positions vary widely.
 * IDs retain legacy 5-ply saves. Weak levels and 1 ply take about 0.4 seconds. */
static const char* const seconds[] = {
    "0.7", "1.5", "4", "10", "26", "0.4", "0.4", "0.4", "60", "204"
};
static char hint[33];

/* Called through the resident entry with RAM bank 23 selected. */
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
