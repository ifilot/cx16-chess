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

#ifndef _START_H
#define _START_H

#include <stdint.h>

/*
 * The menus before a game: the main menu, New Game setup, Options and
 * About. The code executes in RAM bank 21, which must be selected while
 * calling these functions.
 */

// results of start_key() and start_mouse()
#define START_NONE      0       // stay in the menus
#define START_NEW       1       // start a new game with the start_* settings
#define START_CONTINUE  2       // resume the game held in RAM
#define START_ERROR     3       // artwork could not be loaded; quit
#define START_LOAD      4       // open the load dialog

extern uint8_t start_computer;          // COMPUTER_* chosen in New Game
extern uint8_t start_difficulty;        // DIFFICULTY_* (White's in CPU vs CPU)
extern uint8_t start_black_difficulty;  // DIFFICULTY_* of Black in CPU vs CPU
extern uint8_t start_piece_set;         // 0 Victorian, 1 Continental, 2 Letterpress

/**
 * @brief Load the start screen and draw the main menu
 *
 * @param can_continue 1 when a game in RAM can be continued
 *
 * @return 0 when the artwork could not be loaded
 */
uint8_t start_open(uint8_t can_continue);

/**
 * @brief Handle a key press in the menus
 *
 * @param key PETSCII keycode returned by GETIN
 *
 * @return One of the START_* values
 */
uint8_t start_key(uint8_t key);

/**
 * @brief Handle the mouse; hovering selects, a new left click activates
 *
 * @param x       Pointer position in screen pixels
 * @param y       Pointer position in screen pixels
 * @param buttons KERNAL mouse button bits; bit 0 is the left button
 *
 * @return One of the START_* values
 */
uint8_t start_mouse(uint16_t x, uint16_t y, uint8_t buttons);

#endif // _START_H
