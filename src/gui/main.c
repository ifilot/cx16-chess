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
#include <ascii_charmap.h>
#pragma static-locals (on)

#include "video.h"
#include "match.h"
#include "playfield.h"
#include "start.h"
#include "storage.h"
#include "dialog.h"

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
    uint8_t key, action, menu = 1, has_game = 0, release_mouse = 0, dialog = 0, initialized = 0;

    mouse_init();
    if(!video_init()) {
        return;
    }
    *(volatile uint8_t*)0x00 = 22;
    storage_preferences_load();
    *(volatile uint8_t*)0x00 = 21;
    if(!start_open(0)) return;

    while(1) {
        wait_frame();
        mouse_read();
        key = playfield_pending_key ? playfield_pending_key : cbm_k_getin();
        playfield_pending_key = 0;
        if(dialog) {
            action = DIALOG_NONE;
            if(!(mouse_buttons & 1)) release_mouse = 0;
            if(!release_mouse) action = dialog_mouse(MOUSE_X, MOUSE_Y, mouse_buttons);
            if(!action && key) action = dialog_key(key);
            if(action == DIALOG_MENU) {
                dialog = 0;
                menu = 1;
                *(volatile uint8_t*)0x00 = 21;
                if(!start_open(has_game)) return;
            } else if(action) {
                dialog = menu = 0;
                *(volatile uint8_t*)0x00 = 21;
                if(action == DIALOG_LOADED) {
                    if(!video_show_game()) return;
                    playfield_loaded();
                    has_game = 1;
                } else playfield_resume();
                video_present();
                release_mouse = 1;
            }
        } else if(menu) {
            action = start_mouse(MOUSE_X, MOUSE_Y, mouse_buttons);
            if(!action && key) action = start_key(key);
            if(action == START_ERROR) return;
            if(action == START_LOAD) {
                if(!initialized) { match_init(); initialized = 1; }
                *(volatile uint8_t*)0x00 = 22;
                dialog_open(1);
                dialog = release_mouse = 1;
            } else if(action) {
                if(!video_show_game()) return;
                if(action == START_NEW) {
                    if(!initialized) { match_init(); initialized = 1; }
                    match_computer = start_computer;
                    match_difficulty = start_difficulty;
                    match_black_difficulty = start_black_difficulty;
                    playfield_new();
                } else {
                    playfield_resume();
                }
                video_present();
                has_game = 1;
                menu = 0;
                /* Consume a held menu click before board input resumes. */
                release_mouse = 1;
            }
        } else if(key == KEY_ESCAPE) {
            playfield_tick();
            playfield_key(KEY_ESCAPE);
            *(volatile uint8_t*)0x00 = 22;
            dialog_open(0);
            dialog = release_mouse = 1;
        } else if(key == 'M' || key == 'm') {
            *(volatile uint8_t*)0x00 = 21;
            if(!start_open(has_game)) return;
            menu = 1;
        } else {
            if(!(mouse_buttons & 1)) release_mouse = 0;
            if(!release_mouse) playfield_mouse(MOUSE_X, MOUSE_Y, mouse_buttons);
            if(key) playfield_key(key);
            if(playfield_new_requested) {
                playfield_new_requested = 0;
                *(volatile uint8_t*)0x00 = 21;
                if(!start_open(has_game)) return;
                if(start_key('N') == START_ERROR) return;
                menu = 1;
            } else {
                playfield_tick();
                playfield_update();
            }
        }
    }
}
