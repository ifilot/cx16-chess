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

#include "sound.h"

/*
 * Resident sound state. The rest of the sound code lives in the audio
 * bank and is only reachable once CHESS.BIN has been loaded.
 */

uint8_t sound_ready;
uint8_t sound_effects_enabled;
uint8_t sound_music_enabled;

/**
 * @brief Start the sound engine; CHESS.BIN must already be loaded
 *
 * Code and audio were loaded together by video_init().
 */
void sound_init(void) {
    sound_event(SOUND_INIT);
}
