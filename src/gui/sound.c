#include <cbm.h>
#include <ascii_charmap.h>
#include "sound.h"
#include "music.h"
#include "match.h"
#include "video.h"
#pragma static-locals(on)
#pragma code-name("AUDIOCODE")
#pragma rodata-name("AUDIOCODE")
#pragma bss-name("AUDIOBSS")

void sound_engine_init(void);
void __fastcall__ sound_music(uint8_t bank);
void __fastcall__ sound_music_volume(uint8_t attenuation);
void __fastcall__ sound_effects_volume(uint8_t attenuation);

static uint8_t sound_scene, sound_track, next_track, result_played;
static uint16_t previous_clock;
static const uint8_t tracks[] = {MUSIC_GAME_BANK, MUSIC_GAME2_BANK, MUSIC_GAME3_BANK, MUSIC_GAME4_BANK};

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
        if(match_clock[side == WHITE ? 0 : 1] != previous_clock) {
            previous_clock = match_clock[side == WHITE ? 0 : 1];
            if(previous_clock && previous_clock < 10 && !match_computer_to_move()) sound_sfx(SFX_CLOCK);
        }
    } else if(event == SOUND_MOVE || event == SOUND_CPU_MOVE) {
        if(rules_in_check()) sound_sfx(SFX_CHECK);
        else if(match_last_flags & MF_PROMOTION) sound_sfx(SFX_PROMOTE);
        else if(match_last_flags & MF_CASTLE) sound_sfx(SFX_CASTLE);
        else if(match_last_flags & MF_CAPTURE) sound_sfx(SFX_CAPTURE);
        else sound_sfx(event == SOUND_CPU_MOVE ? SFX_MOVE_CPU : SFX_MOVE);
        if(match_state == MATCH_OVER) result();
    } else if(event >= SOUND_OPTIONS) {
        uint8_t pause = event >= SOUND_PAUSE;
        uint8_t selected = event - (pause ? SOUND_PAUSE : SOUND_OPTIONS);
        video_text_centered(pause ? 304 : 560, pause ? 37 : 33,
            sound_music_enabled ? "MUSIC: ON " : "MUSIC: OFF", selected == (pause ? 3 : 2) ? COL_RED : COL_INK);
        video_text_centered(pause ? 304 : 560, pause ? 42 : 37,
            sound_effects_enabled ? "SOUNDS: ON " : "SOUNDS: OFF", selected == (pause ? 4 : 3) ? COL_RED : COL_INK);
    } else if(event == SOUND_APPLY) {
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
