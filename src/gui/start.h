#ifndef _START_H
#define _START_H

#include <stdint.h>

#define START_NONE 0
#define START_NEW 1
#define START_CONTINUE 2
#define START_ERROR 3

extern uint8_t start_computer;
extern uint8_t start_difficulty;
extern uint8_t start_piece_set;
uint8_t start_open(uint8_t can_continue);
uint8_t start_key(uint8_t key);
uint8_t start_mouse(uint16_t x, uint16_t y, uint8_t buttons);

#endif
