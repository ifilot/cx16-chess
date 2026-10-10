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
#include <stdint.h>
#pragma static-locals (on)

#include "video.h"
#include "match.h"
#include "playfield.h"

// KERNAL mouse_get stores the pointer position in r0 (x) and r1 (y)
#define MOUSE_X     (*(volatile uint16_t*)0x02)
#define MOUSE_Y     (*(volatile uint16_t*)0x04)

static uint8_t mouse_buttons;

/**
 * @brief Enable the KERNAL mouse driver for the 640x480 screen
 *
 * screen_mode with carry set returns the text size (80x60) in X/Y, which
 * mouse_config uses as the pointer range in 8 pixel units.
 */
static void mouse_init(void) {
    asm("sec");
    asm("jsr $FF5F");
    asm("lda #1");
    asm("jsr $FF68");
}

/**
 * @brief Wait for the next 60 Hz jiffy
 *
 * Replaces cc65's waitvsync, which (in cc65 2.19) polls the jiffy counter
 * through the pre-R39 memory map and never returns on current ROMs.
 */
static uint8_t jiffy;
static void wait_frame(void) {
    asm("jsr $FFDE");               // RDTIM: A = low byte of the jiffy clock
    asm("sta %v", jiffy);
wait:
    asm("jsr $FFDE");
    asm("cmp %v", jiffy);
    asm("beq %g", wait);
}

static void mouse_read(void) {
    asm("ldx #2");
    asm("jsr $FF6B");
    asm("sta %v", mouse_buttons);
}

void main(void) {
    uint8_t key;

    mouse_init();
    if(!video_init()) {
        return;
    }
    match_init();
    match_computer = COMPUTER_BLACK;
    playfield_new();

    while(1) {
        wait_frame();
        mouse_read();
        playfield_mouse(MOUSE_X, MOUSE_Y, mouse_buttons);
        key = cbm_k_getin();
        if(key) {
            playfield_key(key);
        }
        playfield_tick();
        playfield_update();
    }
}
