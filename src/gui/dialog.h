#ifndef DIALOG_H
#define DIALOG_H
#include <stdint.h>
#define DIALOG_NONE 0
#define DIALOG_RESUME 1
#define DIALOG_MENU 2
#define DIALOG_LOADED 3
/* Bank 22 must be selected for the whole dialog lifetime. */
void dialog_open(uint8_t load);
uint8_t dialog_key(uint8_t key);
uint8_t dialog_mouse(uint16_t x, uint16_t y, uint8_t buttons);
#endif
