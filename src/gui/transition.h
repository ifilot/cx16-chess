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

#ifndef TRANSITION_H
#define TRANSITION_H

#include <stdint.h>

/*
 * The loading cover: plain paper with chess silhouettes and a Loading
 * label, shown while a scene loads. Layer 0 is pointed at a resident cover
 * map and restored afterwards, so the cover needs no disk reads.
 */

/**
 * @brief Build the silhouettes from the resident font and show them
 *
 * Runs once in menu bank 21, after the shared font has been loaded.
 */
void transition_startup(void);

/**
 * @brief Cover the screen and remember the layer-0 setup of the scene
 *
 * Executes in menu bank 21. Does nothing while the cover is shown.
 */
void transition_begin(void);

/**
 * @brief Remove the cover and restore layer 0 and the keyboard cursor
 *
 * Resident; selects bank 21 and restores the caller's bank.
 */
void transition_finish(void);

extern uint8_t transition_covered;      // 1 while the cover is shown
extern uint8_t transition_cursor;       // cursor sprite depth to restore afterwards
extern uint8_t transition_mapbase;      // layer-0 map base to restore afterwards

#endif // TRANSITION_H
