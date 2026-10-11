#ifndef STORAGE_H
#define STORAGE_H
#include <stdint.h>
#define SAVE_SLOTS 9
/* These calls run with UI bank 22 selected. Slot numbers are zero based. */
/* Metadata from the newest checksum-valid generation; moves counts plies. */
typedef struct {
    uint16_t moves;
    uint8_t computer, difficulty, black_difficulty;
} save_info_t;
uint8_t storage_probe(uint8_t slot, save_info_t* info);
uint8_t storage_save(uint8_t slot);
uint8_t storage_load(uint8_t slot);
void storage_preferences_load(void);
uint8_t storage_preferences_save(void);
/* Resident trampoline, callable from menu bank 21. */
uint8_t preferences_save(void);
#endif
