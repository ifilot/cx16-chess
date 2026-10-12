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

#ifndef CHESS_SOUND_H
#define CHESS_SOUND_H

#include <stdint.h>

#include "sfx.h"

/*
 * Music and sound effects through ZSMKit. All audio is loaded into RAM
 * banks at startup with CHESS.BIN; no disk I/O happens afterwards. The
 * resident entry points preserve the active RAM bank, so any bank may call
 * them. Music plays on ZSMKit priority 0, effects on priority 1.
 */

// events for sound_event()
#define SOUND_INIT              0       // start ZSMKit; the only event before sound_ready
#define SOUND_MENU              1       // title theme
#define SOUND_NEW               2       // start a new game with the next track
#define SOUND_RESUME            3       // continue the music of the current game
#define SOUND_RESULT            4       // play the result jingle once a game is over
#define SOUND_CLOCK             5       // tick when the human has under ten seconds
#define SOUND_MOVE              6       // effect for the human's last move
#define SOUND_CPU_MOVE          7       // effect for the computer's last move
#define SOUND_MUSIC_TOGGLE      8       // switch music on or off
#define SOUND_EFFECTS_TOGGLE    9       // switch effects on or off
#define SOUND_APPLY             10      // apply both switches after loading preferences
/* Draw the MUSIC and SOUNDS controls: add the menu selection to the base,
 * so the selected control is drawn in red. The code lives in the audio bank,
 * which has room to spare. */
#define SOUND_OPTIONS           16      // controls in the Options screen
#define SOUND_PAUSE             24      // controls in the pause dialog

/**
 * @brief Start the sound engine; CHESS.BIN must already be loaded
 */
void sound_init(void);

/**
 * @brief Run a SOUND_* event in the audio bank, restoring the caller's bank
 *
 * Events other than SOUND_INIT are ignored until sound_ready is set.
 *
 * @param event One of the SOUND_* values
 */
void __fastcall__ sound_event(uint8_t event);

/**
 * @brief Play a sound effect, unless effects are switched off
 *
 * @param offset Header offset of the effect within SFX.BIN (an SFX_* value)
 */
void __fastcall__ sound_sfx(uint16_t offset);

extern uint8_t sound_ready;             // 1 once ZSMKit runs
extern uint8_t sound_effects_enabled;   // 1 when sound effects are on
extern uint8_t sound_music_enabled;     // 1 when music is on

#endif // CHESS_SOUND_H
