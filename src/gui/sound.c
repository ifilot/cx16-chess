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

#include <cbm.h>
#include <ascii_charmap.h>
#include "sound.h"
#include "music.h"
#include "match.h"
#include "video.h"

/* Sound events are nonrecursive; they run in the main loop or engine poll. */
#pragma static-locals(on)
#pragma code-name("AUDIOCODE")
#pragma rodata-name("AUDIOCODE")
#pragma bss-name("AUDIOBSS")

/*
 * Sound events, executed in audio bank 45 through sound_event() in
 * sound_low.s. Chooses the music for each scene and the effect for each
 * move, and draws the MUSIC and SOUNDS controls of Options and the pause
 * dialog. Music tracks live in their own RAM banks (the *_BANK values).
 */

void sound_engine_init(void);
void __fastcall__ sound_music(uint8_t bank);
void __fastcall__ sound_music_volume(uint8_t attenuation);
void __fastcall__ sound_effects_volume(uint8_t attenuation);

static uint8_t sound_scene;             // bank of the music playing, 0xFF for none
static uint8_t sound_track;             // bank of the current game's track
static uint8_t next_track;              // index into tracks[] for the next new game
static uint8_t result_played;           // 1 once this game's result jingle started
static uint16_t previous_clock;         // last clock second seen by SOUND_CLOCK
static const uint8_t tracks[] = {MUSIC_GAME_BANK, MUSIC_GAME2_BANK, MUSIC_GAME3_BANK, MUSIC_GAME4_BANK};

/**
 * @brief Play the win, lose or draw jingle once per game
 *
 * Human-versus-computer games play the jingle from the human's point of
 * view; other games use the win jingle for any decisive result.
 */
static void result(void) {
    uint8_t bank = MUSIC_DRAW_BANK, winner;
    if(result_played) return;
    result_played = 1;
    if(match_result >= RESULT_WHITE_MATES && match_result <= RESULT_BLACK_ON_TIME) {
        winner = (match_result == RESULT_WHITE_MATES || match_result == RESULT_WHITE_ON_TIME) ? COMPUTER_WHITE : COMPUTER_BLACK;
        bank = match_computer != COMPUTER_BOTH && (match_computer & winner) ? MUSIC_LOSE_BANK : MUSIC_WIN_BANK;
    }
    sound_scene = bank;
    sound_music(bank);
}

/**
 * @brief Carry out a sound event in the audio bank
 *
 * @param event One of the SOUND_* values; SOUND_OPTIONS and SOUND_PAUSE
 *              plus the menu selection draw the audio controls
 */
void __fastcall__ sound_dispatch(uint8_t event) {
    if(event == SOUND_INIT) {
        sound_scene = 0xFF;
        sound_track = next_track = result_played = 0;
        sound_music_enabled = sound_effects_enabled = 1;
        previous_clock = 0;
        sound_engine_init();
        sound_ready = 1;
    } else if(event == SOUND_MENU) {
        if(sound_scene != MUSIC_TITLE_BANK) {
            sound_scene = MUSIC_TITLE_BANK;
            sound_music(sound_scene);
        }
    } else if(event == SOUND_NEW || event == SOUND_RESUME) {
        if(event == SOUND_NEW) {
            // each new game rotates to the next of the four tracks
            sound_track = tracks[next_track];
            next_track = (next_track + 1) & 3;
            result_played = 0;
            sound_sfx(SFX_START);
        }
        if(match_state == MATCH_OVER) {
            /* A finished game stays quiet after its one-shot result jingle. */
            if(sound_scene == MUSIC_TITLE_BANK) result_played = 0;
            result();
        } else {
            if(!sound_track) sound_track = tracks[0];
            if(sound_scene != sound_track) {
                sound_scene = sound_track;
                sound_music(sound_scene);
            }
            result_played = 0;
        }
        previous_clock = 0;
    } else if(event == SOUND_RESULT) {
        if(match_state == MATCH_OVER) result();
    } else if(event == SOUND_CLOCK) {
        // tick once per second while a human has less than ten seconds left
        if(match_clock[side == WHITE ? 0 : 1] != previous_clock) {
            previous_clock = match_clock[side == WHITE ? 0 : 1];
            if(previous_clock && previous_clock < 10 && !match_computer_to_move()) sound_sfx(SFX_CLOCK);
        }
    } else if(event == SOUND_MOVE || event == SOUND_CPU_MOVE) {
        // one effect per move, by priority: check, promotion, castle, capture
        if(rules_in_check()) sound_sfx(SFX_CHECK);
        else if(match_last_flags & MF_PROMOTION) sound_sfx(SFX_PROMOTE);
        else if(match_last_flags & MF_CASTLE) sound_sfx(SFX_CASTLE);
        else if(match_last_flags & MF_CAPTURE) sound_sfx(SFX_CAPTURE);
        else sound_sfx(event == SOUND_CPU_MOVE ? SFX_MOVE_CPU : SFX_MOVE);
        if(match_state == MATCH_OVER) result();
    } else if(event >= SOUND_OPTIONS) {
        // the audio controls; they are entries 2/3 in Options and 3/4 when paused
        uint8_t pause = event >= SOUND_PAUSE;
        uint8_t selected = event - (pause ? SOUND_PAUSE : SOUND_OPTIONS);
        video_text_centered(pause ? 304 : 560, pause ? 37 : 33,
            sound_music_enabled ? "MUSIC: ON " : "MUSIC: OFF", selected == (pause ? 3 : 2) ? COL_RED : COL_INK);
        video_text_centered(pause ? 304 : 560, pause ? 42 : 37,
            sound_effects_enabled ? "SOUNDS: ON " : "SOUNDS: OFF", selected == (pause ? 4 : 3) ? COL_RED : COL_INK);
    } else if(event == SOUND_APPLY) {
        // attenuation 63 silences a priority without stopping it
        sound_music_volume(sound_music_enabled ? 0 : 63);
        sound_effects_volume(sound_effects_enabled ? 0 : 63);
    } else if(event == SOUND_MUSIC_TOGGLE) {
        sound_music_enabled ^= 1;
        sound_music_volume(sound_music_enabled ? 0 : 63);
    } else if(event == SOUND_EFFECTS_TOGGLE) {
        sound_effects_enabled ^= 1;
        sound_effects_volume(sound_effects_enabled ? 0 : 63);
    }
}
