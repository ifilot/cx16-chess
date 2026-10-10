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

#ifndef _ENGINE_H
#define _ENGINE_H

#include <stdint.h>

/*
 * The chess engine: a self-contained alpha-beta searcher with its own board
 * representation. It shares only the 0x88 square and piece encoding with
 * rules.h; positions are handed over with engine_set_position().
 *
 * Builds for the X16 (cc65) and natively (tests, UCI front end).
 */

#define ENGINE_MATE     30000       // scores beyond MATE - 512 are mates

typedef struct {
    uint8_t from;                   // 0x88 squares; from == to: no move
    uint8_t to;
    uint8_t promo;                  // piece type or 0
    uint8_t depth;                  // last completed iteration
    int16_t score;                  // centipawns, side to move's view
    uint32_t nodes;
    uint16_t time;                  // jiffies used (X16 only)
    uint8_t pv[32];                 // principal variation, from/to pairs
} engine_result_t;

/**
 * @brief Called regularly during a search (e.g. to keep a clock running)
 */
extern void (*engine_poll)(void);

/**
 * @brief Prepare tables; call once
 */
void engine_init(void);

/**
 * @brief Forget everything learned (transposition table, game history)
 */
void engine_new_game(void);

/**
 * @brief Forget the recorded game positions (before replaying a game)
 */
void engine_clear_history(void);

/**
 * @brief Set the position to search
 *
 * @param board    128-byte 0x88 board, rules.h piece encoding
 * @param side     0 (white) or 8 (black) to move
 * @param castling CASTLE_* bits as in rules.h
 * @param ep       en passant target square or 0x80
 * @param halfmove plies since the last capture or pawn move
 */
void engine_set_position(const uint8_t* board, uint8_t side, uint8_t castling,
                         uint8_t ep, uint8_t halfmove);

/**
 * @brief Remember the current position as played (for repetition draws)
 *
 * Call after engine_set_position() for every position of the game.
 */
void engine_record_position(void);

/**
 * @brief How often the recorded current position has occurred (>= 1)
 */
uint8_t engine_repetitions(void);

/**
 * @brief Find the best move; stops at max_depth, time (jiffies) or nodes
 *
 * A limit of 0 means no limit. The result always holds a legal move when
 * one exists.
 */
void engine_search(uint8_t max_depth, uint16_t time_limit, uint32_t node_limit,
                   engine_result_t* result);

/**
 * @brief Static evaluation of the current position, side to move's view
 */
int16_t engine_evaluate(void);

#ifndef NO_TEST_HOOKS
/**
 * @brief Write the legal moves as from/to pairs; returns their number
 */
uint8_t engine_legal_moves(uint8_t* out);

/**
 * @brief Flags of a pseudo-legal move, 0xFF if none (validator test hook)
 */
uint8_t engine_validate(uint8_t from, uint8_t to, uint8_t promo);

/**
 * @brief Count leaf nodes of the legal move tree (move generator test)
 */
uint32_t engine_perft(uint8_t depth);

/**
 * @brief Checksum of the hashes of all perft leaves (hashing test)
 */
extern uint16_t engine_perft_hash;

/**
 * @brief Copy the engine's board (debugging)
 */
void engine_debug_board(uint8_t* out);
#endif

#endif // _ENGINE_H
