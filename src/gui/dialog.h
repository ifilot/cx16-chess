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

#ifndef DIALOG_H
#define DIALOG_H

#include <stdint.h>

/*
 * The in-game dialogs drawn over the board: the pause menu, the save and
 * load slot tables and the replace confirmation. The code lives in RAM
 * bank 22, which must stay selected for the whole lifetime of a dialog.
 */

// results of dialog_key() and dialog_mouse()
#define DIALOG_NONE     0       // the dialog stays open
#define DIALOG_RESUME   1       // return to the game on the board
#define DIALOG_MENU     2       // return to the main menu
#define DIALOG_LOADED   3       // a saved game replaced the current one

/**
 * @brief Open the pause menu, or the load table directly
 *
 * @param load 1 to show the load slots, 0 for the pause menu
 */
void dialog_open(uint8_t load);

/**
 * @brief Handle a key press in the open dialog
 *
 * @param key PETSCII keycode returned by GETIN
 *
 * @return One of the DIALOG_* values
 */
uint8_t dialog_key(uint8_t key);

/**
 * @brief Handle the mouse; hovering selects, a new left click activates
 *
 * @param x       Pointer position in screen pixels
 * @param y       Pointer position in screen pixels
 * @param buttons KERNAL mouse button bits; bit 0 is the left button
 *
 * @return One of the DIALOG_* values
 */
uint8_t dialog_mouse(uint16_t x, uint16_t y, uint8_t buttons);

#endif // DIALOG_H
