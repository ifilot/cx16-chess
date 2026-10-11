#include <cbm.h>
#include <ascii_charmap.h>
#include <cx16.h>
#include <string.h>
#include "sound.h"
#pragma static-locals(on)

uint8_t sound_ready;
uint8_t sound_effects_enabled;
uint8_t sound_music_enabled;
static char filename[12];
uint8_t __fastcall__ sound_load_raw(uint8_t bank);
/* SETNAM retains its pointer: copy banked names before switching banks. */
uint8_t __fastcall__ sound_load_file(const char* name, uint8_t bank) {
    strcpy(filename, name);
    cbm_k_setnam(filename);
    cbm_k_setlfs(0, 8, 2);
    return sound_load_raw(bank);
}
void sound_init(void) {
    if(sound_load_file("AUDIO.BIN", 45)) sound_event(SOUND_INIT);
}
