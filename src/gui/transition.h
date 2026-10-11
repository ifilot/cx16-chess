#ifndef TRANSITION_H
#define TRANSITION_H
#include <stdint.h>
/* Begin executes in menu bank 21; finish is resident. */
void transition_begin(void);
void transition_finish(void);
extern uint8_t transition_covered, transition_cursor, transition_mapbase;
#endif
