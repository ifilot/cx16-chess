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

/*
 * Internal interface of the engine. Not for use outside the engine.
 *
 *   engine.c        search (iterative deepening, PVS, TT, ordering)
 *   engine_board.c  tables, position setup, pawn structure, perft
 *   engine_hot.c    per-node board code in C (native builds)
 *   engine_asm.s    the same in 65C02 assembly (X16 builds)
 *
 * engine_hot.c and engine_asm.s implement exactly the same behaviour; the
 * native build serves as the reference for the assembly version.
 */

#ifndef _ENGINE_INT_H
#define _ENGINE_INT_H

#include <stdint.h>

#ifndef __CC65__
#define __fastcall__
#endif

#define MAX_PLY         40
#define MAX_MOVES       224     // most moves in any position is 218
#define MS_SIZE         768     // move stack shared by all plies
#define HIST_SIZE       256     // positions remembered for repetitions
#define NO_SQ           0x80

// pieces as in rules.h
#define PAWN            1
#define KNIGHT          2
#define BISHOP          3
#define ROOK            4
#define QUEEN           5
#define KING            6
#define BLACK_SIDE      8
#define TYPE(p)         ((p) & 7)
#define OFFB(sq)        ((sq) & 0x88)
#define SQ64(sq)        (((sq) + ((sq) & 7)) >> 1)

// move flags
#define F_PROMO_MASK    0x07    // promotion piece type
#define F_CAPTURE       0x08
#define F_EP            0x10
#define F_CASTLE        0x20
#define F_DOUBLE        0x40

/*****************************************************************************
 * STATE (defined in engine_hot.c / engine_asm.s)
 *****************************************************************************/

extern uint8_t bd[128];
extern uint8_t stm;             // side to move: 0 or BLACK_SIDE
extern uint8_t castle;
extern uint8_t ep;
extern uint8_t fifty;
extern uint8_t sply;            // search ply: depth below the root
extern uint16_t hash_lo, hash_hi;
extern uint32_t nodes;

extern uint16_t ms_top;
extern uint8_t mv_from[MS_SIZE];
extern uint8_t mv_to[MS_SIZE];
extern uint8_t mv_flags[MS_SIZE];
extern uint8_t mv_score[MS_SIZE];

// incrementally updated evaluation terms, index 0 = white, 1 = black
extern int16_t psq_score;       // material + piece-square, white's view
extern int16_t npm[2];          // non-pawn material
extern uint8_t pawn_count[2];
extern uint8_t bishop_count[2];
extern uint8_t pawn_files[16];  // [colour * 8 + file]: bit per rank with a pawn
extern uint16_t pawn_hash;      // hash of the pawns alone (24 bits with pawn_hash2)
extern uint8_t pawn_hash2;
extern uint8_t ksq[2];
extern uint8_t rep_count;       // entries in the repetition list

// arguments of make_move() and square_attacked()
extern uint8_t mk_from, mk_to, mk_flags;
extern uint8_t att_sq;

/*****************************************************************************
 * TABLES (filled by board_init in engine_board.c)
 *
 * The large tables are 256-byte pages; on the X16 they live in RAM bank
 * ENGINE_BANK ($A000-$BDFF):
 *   ZOB_PAGES[12]   Zobrist keys per piece: bytes 0..3 of the 32-bit key
 *                   at offsets 0, 64, 128, 192 + square (0-63)
 *   PSQ_PAGES[t]    value + piece-square bonus of type t (1-6), white's
 *                   view: low byte at [sq], high byte at [sq | 0x80]
 *   HISTORY[16]     search history counters per [piece][square 0-63]
 *   REP_PAGES[4]    hash bytes 0..3 of earlier positions
 *   ATT_KINDS       ($BE00) for a square difference d = target - attacker,
 *                   at [d + 119]: which pieces attack along it (ATT_*)
 *   ATT_STEP        ($BF00) unit step from attacker towards target
 *
 * The pawn structure cache has 2048 entries in RAM bank PAWN_BANK, indexed
 * by pawn_hash & 2047; four 2 KiB arrays hold the check bytes pawn_hash2
 * and pawn_hash >> 8, and the value (low, high byte).
 *****************************************************************************/

#define ATT_WPAWN       0x01
#define ATT_BPAWN       0x02
#define ATT_KNIGHT      0x04
#define ATT_DIAG        0x08
#define ATT_STRAIGHT    0x10
#define ATT_KING        0x20
#define PC_SIZE         2048

#ifdef __CC65__
#define RAM_BANK        (*(volatile uint8_t*)0x00)
#define ENGINE_BANK     1
#define ENTER_ENGINE    uint8_t caller_bank = RAM_BANK; RAM_BANK = ENGINE_BANK
#define LEAVE_ENGINE    RAM_BANK = caller_bank
#define PAWN_BANK       18
#define ZOB_PAGES       ((uint8_t (*)[256])0xA000)
#define PSQ_PAGES       ((uint8_t (*)[256])0xAB00)
#define HISTORY         ((uint8_t (*)[64])0xB600)
#define REP_PAGES       ((uint8_t (*)[256])0xBA00)
#define ATT_KINDS       ((uint8_t*)0xBE00)
#define ATT_STEP        ((int8_t*)0xBF00)
#define PAWN_CACHE      ((uint8_t (*)[PC_SIZE])0xA000)    // in PAWN_BANK
#else
#define ENTER_ENGINE
#define LEAVE_ENGINE
extern uint8_t zob_pages[12][256], psq_pages[7][256], pawn_cache[4][PC_SIZE];
extern uint8_t history_table[16][64], rep_pages[4][256];
extern uint8_t att_kinds[256];
extern int8_t att_step[256];
#define ZOB_PAGES       zob_pages
#define PSQ_PAGES       psq_pages
#define ATT_KINDS       att_kinds
#define ATT_STEP        att_step
#define PAWN_CACHE      pawn_cache
#define HISTORY         history_table
#define REP_PAGES       rep_pages
#endif

extern const int16_t piece_value[7];
extern int8_t king_endgame[128];    // endgame minus middlegame king bonus
extern uint8_t center_dist[128];    // king steps from the centre squares
extern uint8_t castle_keep[128];    // castling rights kept when a square is touched
extern uint16_t zob_castle_lo[16], zob_castle_hi[16];
extern uint16_t zob_ep_lo[8], zob_ep_hi[8];
extern uint16_t zob_side_lo, zob_side_hi;

/*****************************************************************************
 * PER-NODE FUNCTIONS (engine_hot)
 *****************************************************************************/

/**
 * @brief Make the move mk_from-mk_to (mk_flags); 0 if it leaves the king
 *        in check. Always undo with unmake_move(), also for illegal moves.
 */
uint8_t make_move(void);
#define MAKE(f, t, fl)  (mk_from = (f), mk_to = (t), mk_flags = (fl), make_move())
void unmake_move(void);
void make_null(void);
void unmake_null(void);

/**
 * @brief Is att_sq attacked by colour by (0 or BLACK_SIDE)?
 */
uint8_t __fastcall__ square_attacked(uint8_t by);
uint8_t in_check(void);

/**
 * @brief Append pseudo-legal moves at ms_top; returns (and sets) the new top
 */
uint16_t __fastcall__ generate_moves(uint8_t captures_only);

int16_t evaluate(void);
uint8_t is_repetition(void);

/**
 * @brief Flags of the pseudo-legal move mk_from-mk_to with promotion piece
 *        mk_flags (bits 0-2), or 0xFF when it is not a move here
 *
 * Checks moves from the transposition table, which may come from another
 * position after a hash collision.
 */
uint8_t validate_move(void);

/**
 * @brief Put a piece on the empty square mk_to (position setup)
 */
void __fastcall__ board_put(uint8_t piece);

/**
 * @brief Recompute whether the side to move is in check (position setup)
 *
 * The X16 build tracks the check status incrementally in make_move().
 */
void refresh_check(void);

/*****************************************************************************
 * SHARED C (engine_board.c)
 *****************************************************************************/

void board_init(void);
void history_clear(void);
uint8_t history_drop_root(void);
void history_restore_root(void);
uint8_t insufficient_material(void);
uint8_t has_pieces(uint8_t color);
int16_t pawn_structure_compute(void);
void pawn_cache_clear(void);

/**
 * @brief Flags of the pseudo-legal move from-to(-promo), or 0xFF
 */
uint8_t find_move_flags(uint8_t from, uint8_t to, uint8_t promo);

#endif // _ENGINE_INT_H
