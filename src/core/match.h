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

#ifndef _MATCH_H
#define _MATCH_H

#include <stdint.h>

#include "rules.h"

/*
 * The game controller: everything about a game except how it looks. It
 * owns the move list (in SAN), the clocks, the result and who plays which
 * side, and asks the engine for moves. The position itself is the one of
 * rules.h (board, side, legal_moves). Front ends only call these
 * functions and read the state below; they never touch the engine.
 */

// match_state
#define MATCH_PLAYING           0
#define MATCH_OVER              1

// match_result
#define RESULT_NONE             0
#define RESULT_WHITE_MATES      1
#define RESULT_BLACK_MATES      2
#define RESULT_WHITE_ON_TIME    3       // black's flag fell
#define RESULT_BLACK_ON_TIME    4
#define RESULT_STALEMATE        5
#define RESULT_REPETITION       6
#define RESULT_FIFTY_MOVES      7
#define RESULT_MATERIAL         8       // insufficient material
#define RESULT_TIME_MATERIAL    9       // flag fell, but no mate possible
#define RESULT_LENGTH           10      // move list full

// match_computer: sides played by the engine
#define COMPUTER_NONE           0
#define COMPUTER_WHITE          1
#define COMPUTER_BLACK          2

extern uint8_t match_state;
extern uint8_t match_result;
extern uint8_t match_computer;
extern uint16_t match_clock[2];         // seconds left, [0] white, [1] black
extern uint8_t match_last_from;         // most recent move, NO_SQUARE if none
extern uint8_t match_last_to;
extern uint8_t match_eval_valid;        // match_eval holds an engine evaluation
extern int16_t match_eval;              // centipawns, white's view (ENGINE_MATE scale)
extern char match_best[8];              // SAN of the move suggested by match_analyse, or 

/**
 * @brief Prepare the engine; call once at start-up
 */
void match_init(void);

/**
 * @brief Start a new game from the initial position
 *
 * @param seconds  time per player
 * @param computer COMPUTER_* bits
 */
void match_new(uint16_t seconds, uint8_t computer);

/**
 * @brief Play a legal move (an entry of legal_moves) and record it
 */
void match_play(const move_t* m);

/**
 * @brief Find the legal move from-to (promo: piece type, or EMPTY for the
 *        first matching one); NULL if there is none
 */
const move_t* match_find_move(uint8_t from, uint8_t to, uint8_t promo);

/**
 * @brief Run the clock of the side to move
 *
 * @return 1 when a displayed second changed or the game ended
 */
uint8_t match_tick(uint8_t jiffies);

/**
 * @brief Is the engine to move?
 */
uint8_t match_computer_to_move(void);

/**
 * @brief Let the engine choose and play a move (takes a while)
 *
 * The callback is called regularly while the engine thinks, e.g. to keep
 * the clocks on screen running; it may call match_tick().
 */
void match_computer_move(void (*poll)(void));

/**
 * @brief Let the engine analyse the position for the side to move: sets
 *        match_best and match_eval (takes a while, like match_computer_move)
 */
void match_analyse(void (*poll)(void));

/**
 * @brief Copy the SAN of a played half move (0 = white's first) into buf
 */
void match_san(uint16_t half_move, char* buf);

#endif // _MATCH_H
