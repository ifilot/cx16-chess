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

#ifndef _RULES_H
#define _RULES_H

#include <stdint.h>

/*
 * The board uses the 0x88 layout: square = rank * 16 + file, and a square is
 * on the board when (square & 0x88) == 0. Rank 0 is white's first rank.
 */
#define SQ(file, rank)  (((rank) << 4) | (file))
#define FILE_OF(sq)     ((sq) & 7)
#define RANK_OF(sq)     ((sq) >> 4)
#define OFFBOARD(sq)    ((sq) & 0x88)
#define NO_SQUARE       0x80

// pieces: type in the lower three bits, colour in bit 3
#define EMPTY           0
#define PAWN            1
#define KNIGHT          2
#define BISHOP          3
#define ROOK            4
#define QUEEN           5
#define KING            6
#define WHITE           0
#define BLACK           8
#define TYPE(p)         ((p) & 7)
#define COLOR(p)        ((p) & 8)

// castling rights
#define CASTLE_WK       1
#define CASTLE_WQ       2
#define CASTLE_BK       4
#define CASTLE_BQ       8

// move flags
#define MF_CAPTURE      0x01
#define MF_ENPASSANT    0x02
#define MF_CASTLE       0x04
#define MF_DOUBLE       0x08
#define MF_PROMOTION    0x10

#define MAX_MOVES       224
#define MAX_HISTORY     400     // longest game, in half moves
#define UNDO_DEPTH      8       // moves that can be taken back with rules_unmake

typedef struct {
    uint8_t from;
    uint8_t to;
    uint8_t promo;      // piece type, or EMPTY
    uint8_t flags;
} move_t;

extern uint8_t board[128];
extern uint8_t side;            // WHITE or BLACK to move
extern uint8_t castling;
extern uint8_t ep_square;       // NO_SQUARE when en passant is impossible
extern uint8_t halfmove_clock;
extern uint16_t ply;            // half moves since the initial position

// legal moves of the current position, refreshed by rules_generate_legal()
extern move_t legal_moves[MAX_MOVES];
extern uint8_t legal_count;

/**
 * @brief Set up the initial position
 */
void rules_new_game(void);

#ifndef NO_TEST_HOOKS
/**
 * @brief Set up a position from FEN; returns 0 on malformed input
 *
 * Only placement, side, castling and en passant fields are used.
 */
uint8_t rules_load_fen(const char* fen);
#endif

/**
 * @brief Is square attacked by the pieces of colour by?
 */
uint8_t rules_attacked(uint8_t sq, uint8_t by);

/**
 * @brief Is the side to move in check?
 */
uint8_t rules_in_check(void);

/**
 * @brief Square of the king of the given colour
 */
uint8_t rules_king_square(uint8_t color);

/**
 * @brief Fill legal_moves with all legal moves of the side to move
 */
uint8_t rules_generate_legal(void);

/**
 * @brief Play a move; returns 0 when it leaves the own king in check
 *
 * The move is always made; call rules_unmake() to take it back.
 */
uint8_t rules_make(const move_t* m);

/**
 * @brief Take back the most recent move
 */
void rules_unmake(void);

/**
 * @brief Make the moves played so far permanent (forget their undo data)
 *
 * Call after every game move; only UNDO_DEPTH moves can be pending.
 */
void rules_commit(void);

/**
 * @brief Write the SAN of a legal move (of the side to move) into buf
 *
 * Needs legal_moves to be current and overwrites it (regenerate it
 * afterwards); m must not point into legal_moves. Adds '+' or '#'. buf
 * must hold 8 bytes.
 */
void rules_san(const move_t* m, char* buf);

/**
 * @brief Neither side can possibly mate (K v K, K+minor v K)
 */
uint8_t rules_insufficient_material(void);

#endif // _RULES_H
