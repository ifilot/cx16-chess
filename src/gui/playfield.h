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
 * moves.
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

/**
 * @brief Start a new game and draw the complete playing field
 */
void playfield_new(void);
/* Redraw a paused game and reset its wall-clock sampling point. */
void playfield_resume(void);
extern uint8_t playfield_new_requested;
extern uint8_t playfield_pending_key;
extern uint8_t playfield_theme;
extern uint8_t playfield_flipped, playfield_info;
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
 */
void playfield_key(uint8_t key);

/**
 * @brief Handle the mouse; call once per frame
 */
void playfield_mouse(uint16_t x, uint16_t y, uint8_t buttons);

#endif // _PLAYFIELD_H
