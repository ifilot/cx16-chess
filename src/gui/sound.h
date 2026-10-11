#ifndef CHESS_SOUND_H
#define CHESS_SOUND_H
#include <stdint.h>
#include "sfx.h"

#define SOUND_INIT 0
#define SOUND_MENU 1
#define SOUND_NEW 2
#define SOUND_RESUME 3
#define SOUND_RESULT 4
#define SOUND_CLOCK 5
#define SOUND_MOVE 6
#define SOUND_CPU_MOVE 7
#define SOUND_MUSIC_TOGGLE 8
#define SOUND_EFFECTS_TOGGLE 9
#define SOUND_APPLY 10
/* Add the menu selection to redraw both controls in the spacious audio bank. */
#define SOUND_OPTIONS 16
#define SOUND_PAUSE 24

/* Resident entries preserve the active RAM bank. No disk I/O after startup. */
void sound_init(void);
void __fastcall__ sound_event(uint8_t event);
void __fastcall__ sound_sfx(uint16_t offset);
extern uint8_t sound_ready;
extern uint8_t sound_effects_enabled;
extern uint8_t sound_music_enabled;
#endif
