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

#ifndef _PLAYFIELD_H
#define _PLAYFIELD_H

#include <stdint.h>

/*
 * The playing field: draws the game of core/match.c and turns input into
 * moves. The code lives in RAM bank 23; the functions below are resident
 * entries in drag.s that select that bank and restore the caller's bank.
 */

// keycodes (PETSCII as returned by GETIN)
#define KEY_UP          0x91
#define KEY_DOWN        0x11
#define KEY_LEFT        0x9D
#define KEY_RIGHT       0x1D
#define KEY_RETURN      0x0D
#define KEY_SPACE       0x20
#define KEY_ESCAPE      0x1B
#define KEY_TAB         0x09

extern uint8_t playfield_new_requested; // set by N on the board: open New Game
extern uint8_t playfield_pending_key;   // Escape caught during a CPU vs CPU search
extern uint8_t playfield_theme;         // board style, THEME_*
extern uint8_t playfield_flipped;       // 1 when Black is at the bottom
extern uint8_t playfield_info;          // 1 when the move sheet is shown

/**
 * @brief Start a new game and draw the complete playing field
 */
void playfield_new(void);

/**
 * @brief Redraw a paused game and reset its wall-clock sampling point
 */
void playfield_resume(void);

/**
 * @brief Reset the input state for a game just loaded, then redraw it
 */
void playfield_loaded(void);

/**
 * @brief Run the clocks; call once per frame
 */
void playfield_tick(void);

/**
 * @brief Let the computer move when it is its turn; call once per frame
 */
void playfield_update(void);

/**
 * @brief Handle a key press
 *
 * @param key PETSCII keycode returned by GETIN
 */
void playfield_key(uint8_t key);

/**
 * @brief Handle the mouse: click to move, or drag and drop; call once per
 *        frame
 *
 * @param x       Pointer position in screen pixels
 * @param y       Pointer position in screen pixels
 * @param buttons KERNAL mouse button bits; bit 0 is the left button
 */
void playfield_mouse(uint16_t x, uint16_t y, uint8_t buttons);

#endif // _PLAYFIELD_H
