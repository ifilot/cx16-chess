#include "sound.h"

uint8_t sound_ready;
uint8_t sound_effects_enabled;
uint8_t sound_music_enabled;

/* Code and audio were loaded together by video_init. */
void sound_init(void) {
    sound_event(SOUND_INIT);
}
