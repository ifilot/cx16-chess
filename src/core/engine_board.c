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
 * Engine board support shared by all builds: tables, position setup, the
 * repetition list, pawn structure (on pawn-cache misses only) and perft.
 * The per-node code is in engine_hot.c / engine_asm.s.
 */

#include <string.h>

#include "engine.h"
#include "engine_int.h"

#ifdef __CC65__
#pragma static-locals (on)
#endif

const int16_t piece_value[7] = {0, 100, 320, 330, 500, 900, 0};

int8_t king_endgame[128];
uint8_t center_dist[128];
uint8_t castle_keep[128];
uint16_t zob_castle_lo[16], zob_castle_hi[16];
uint16_t zob_ep_lo[8], zob_ep_hi[8];
uint16_t zob_side_lo, zob_side_hi;

// Piece-square tables (Michniewski's simplified evaluation), a8..h8 first.
static const int8_t pst[8][64] = {
    {0},
    {  0,  0,  0,  0,  0,  0,  0,  0,  50, 50, 50, 50, 50, 50, 50, 50,
      10, 10, 20, 30, 30, 20, 10, 10,   5,  5, 10, 25, 25, 10,  5,  5,
       0,  0,  0, 20, 20,  0,  0,  0,   5, -5,-10,  0,  0,-10, -5,  5,
       5, 10, 10,-20,-20, 10, 10,  5,   0,  0,  0,  0,  0,  0,  0,  0},
    {-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,  0,  0,  0,  0,-20,-40,
     -30,  0, 10, 15, 15, 10,  0,-30, -30,  5, 15, 20, 20, 15,  5,-30,
     -30,  0, 15, 20, 20, 15,  0,-30, -30,  5, 10, 15, 15, 10,  5,-30,
     -40,-20,  0,  5,  5,  0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50},
    {-20,-10,-10,-10,-10,-10,-10,-20, -10,  0,  0,  0,  0,  0,  0,-10,
     -10,  0,  5, 10, 10,  5,  0,-10, -10,  5,  5, 10, 10,  5,  5,-10,
     -10,  0, 10, 10, 10, 10,  0,-10, -10, 10, 10, 10, 10, 10, 10,-10,
     -10,  5,  0,  0,  0,  0,  5,-10, -20,-10,-10,-10,-10,-10,-10,-20},
    {  0,  0,  0,  0,  0,  0,  0,  0,   5, 10, 10, 10, 10, 10, 10,  5,
      -5,  0,  0,  0,  0,  0,  0, -5,  -5,  0,  0,  0,  0,  0,  0, -5,
      -5,  0,  0,  0,  0,  0,  0, -5,  -5,  0,  0,  0,  0,  0,  0, -5,
      -5,  0,  0,  0,  0,  0,  0, -5,   0,  0,  0,  5,  5,  0,  0,  0},
    {-20,-10,-10, -5, -5,-10,-10,-20, -10,  0,  0,  0,  0,  0,  0,-10,
     -10,  0,  5,  5,  5,  5,  0,-10,  -5,  0,  5,  5,  5,  5,  0, -5,
       0,  0,  5,  5,  5,  5,  0, -5, -10,  5,  5,  5,  5,  5,  0,-10,
     -10,  0,  5,  0,  0,  0,  0,-10, -20,-10,-10, -5, -5,-10,-10,-20},
    {-30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
     -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
     -20,-30,-30,-40,-40,-30,-30,-20, -10,-20,-20,-20,-20,-20,-20,-10,
      20, 20,  0,  0,  0,  0, 20, 20,  20, 30, 10,  0,  0, 10, 30, 20},
    // king in the endgame
    {-50,-40,-30,-20,-20,-30,-40,-50, -30,-20,-10,  0,  0,-10,-20,-30,
     -30,-10, 20, 30, 30, 20,-10,-30, -30,-10, 30, 40, 40, 30,-10,-30,
     -30,-10, 30, 40, 40, 30,-10,-30, -30,-10, 20, 30, 30, 20,-10,-30,
     -30,-30,  0,  0,  0,  0,-30,-30, -50,-30,-30,-30,-30,-30,-30,-50},
};


static uint16_t rng_state = 0xACE1;

static uint16_t rng(void) {
    rng_state ^= rng_state << 7;
    rng_state ^= rng_state >> 9;
    rng_state ^= rng_state << 8;
    return rng_state;
}

/**
 * @brief Fill evaluation and hashing tables (identical on every build)
 */
void board_init(void) {
    uint8_t t, r, f, sq, s, df, dr;
    uint16_t i, lo, hi;
    int16_t v;

    for(t=PAWN; t<=KING; t++) {
        for(r=0; r<8; r++) {
            for(f=0; f<8; f++) {
                sq = (r << 4) | f;
                v = piece_value[t] + pst[t][(7 - r) * 8 + f];
                PSQ_PAGES[t][sq] = (uint8_t)v;
                PSQ_PAGES[t][sq | 0x80] = (uint8_t)(v >> 8);
            }
        }
    }
    for(r=0; r<8; r++) {
        for(f=0; f<8; f++) {
            sq = (r << 4) | f;
            king_endgame[sq] = pst[7][(7 - r) * 8 + f] - pst[KING][(7 - r) * 8 + f];
            // separate statements: cc65 2.19 miscompiles a sum of two ?: terms
            df = f < 4 ? 3 - f : f - 4;
            dr = r < 4 ? 3 - r : r - 4;
            center_dist[sq] = df + dr;
        }
    }
    for(i=0; i<12; i++) {
        for(s=0; s<64; s++) {
            lo = rng();
            hi = rng();
            ZOB_PAGES[i][s] = (uint8_t)lo;
            ZOB_PAGES[i][s | 0x40] = lo >> 8;
            ZOB_PAGES[i][s | 0x80] = (uint8_t)hi;
            ZOB_PAGES[i][s | 0xC0] = hi >> 8;
        }
    }
    for(i=0; i<16; i++) {
        zob_castle_lo[i] = i ? rng() : 0;
        zob_castle_hi[i] = i ? rng() : 0;
    }
    for(i=0; i<8; i++) {
        zob_ep_lo[i] = rng();
        zob_ep_hi[i] = rng();
    }
    zob_side_lo = rng();
    zob_side_hi = rng();

    memset(castle_keep, 15, sizeof(castle_keep));
    castle_keep[0x00] = 15 & ~2;
    castle_keep[0x07] = 15 & ~1;
    castle_keep[0x04] = 15 & ~3;
    castle_keep[0x70] = 15 & ~8;
    castle_keep[0x77] = 15 & ~4;
    castle_keep[0x74] = 15 & ~12;

    // attack vectors: which pieces attack along target - attacker
    memset(ATT_KINDS, 0, 256);
    memset(ATT_STEP, 0, 256);
    for(r=0; r<15; r++) {
        for(f=0; f<15; f++) {
            int8_t dr = r - 7, df = f - 7, sr = 0, sf = 0;
            uint8_t k = 0, i = (uint8_t)(dr * 16 + df + 119);
            if(dr > 0) sr = 1;
            if(dr < 0) sr = -1;
            if(df > 0) sf = 1;
            if(df < 0) sf = -1;
            if(!dr && !df) continue;
            if(dr == 1 && (df == 1 || df == -1)) k |= ATT_WPAWN;
            if(dr == -1 && (df == 1 || df == -1)) k |= ATT_BPAWN;
            if((dr * dr + df * df) == 5) k |= ATT_KNIGHT;
            if(dr >= -1 && dr <= 1 && df >= -1 && df <= 1) k |= ATT_KING;
            if(dr == df || dr == -df) k |= ATT_DIAG;
            if(!dr || !df) k |= ATT_STRAIGHT;
            ATT_KINDS[i] = k;
            if(k & (ATT_DIAG | ATT_STRAIGHT)) ATT_STEP[i] = sr * 16 + sf;
        }
    }
}

void pawn_cache_clear(void) {
#ifdef __CC65__
    uint8_t saved = RAM_BANK;
    RAM_BANK = PAWN_BANK;
#endif
    memset(PAWN_CACHE, 0xFF, 2 * PC_SIZE);      // invalid check bytes
    memset(PAWN_CACHE[2], 0, 2 * PC_SIZE);
#ifdef __CC65__
    RAM_BANK = saved;
#endif
}

/*****************************************************************************
 * POSITION
 *****************************************************************************/

void engine_set_position(const uint8_t* board, uint8_t to_move, uint8_t castling,
                         uint8_t ep_square, uint8_t halfmove) {
    uint8_t sq;
    ENTER_ENGINE;

    memset(bd, 0, sizeof(bd));
    memset(npm, 0, sizeof(npm));
    memset(pawn_count, 0, sizeof(pawn_count));
    memset(bishop_count, 0, sizeof(bishop_count));
    memset(pawn_files, 0, sizeof(pawn_files));
    psq_score = 0;
    pawn_hash = 0;
    pawn_hash2 = 0;
    hash_lo = hash_hi = 0;
    for(sq=0; sq<128; sq++) {
        if(!OFFB(sq) && board[sq]) {
            mk_to = sq;
            board_put(board[sq]);
        }
    }
    stm = to_move;
    castle = castling & 15;
    ep = ep_square;
    fifty = halfmove;
    hash_lo ^= zob_castle_lo[castle];
    hash_hi ^= zob_castle_hi[castle];
    if(ep != NO_SQ) {
        hash_lo ^= zob_ep_lo[ep & 7];
        hash_hi ^= zob_ep_hi[ep & 7];
    }
    if(stm) {
        hash_lo ^= zob_side_lo;
        hash_hi ^= zob_side_hi;
    }
    sply = 0;
    refresh_check();
    LEAVE_ENGINE;
}

static uint8_t rep_matches(uint8_t k) {
    return REP_PAGES[0][k] == (uint8_t)hash_lo && REP_PAGES[1][k] == (hash_lo >> 8) &&
           REP_PAGES[2][k] == (uint8_t)hash_hi && REP_PAGES[3][k] == (hash_hi >> 8);
}

static void rep_store(void) {
    REP_PAGES[0][rep_count] = (uint8_t)hash_lo;
    REP_PAGES[1][rep_count] = hash_lo >> 8;
    REP_PAGES[2][rep_count] = (uint8_t)hash_hi;
    REP_PAGES[3][rep_count] = hash_hi >> 8;
    rep_count++;
}

void history_clear(void) {
    rep_count = 0;
}

void engine_record_position(void) {
    ENTER_ENGINE;
    if(fifty == 0) rep_count = 0;               // nothing before can repeat
    if(rep_count < HIST_SIZE - MAX_PLY) rep_store();
    LEAVE_ENGINE;
}

/**
 * @brief Before a search: drop the game's entry for the root position
 *
 * The first make_move() of the search pushes the root again; without this
 * the root would be counted twice. Returns 1 when an entry was dropped.
 */
uint8_t history_drop_root(void) {
    if(rep_count && rep_matches(rep_count - 1)) {
        rep_count--;
        return 1;
    }
    return 0;
}

uint8_t engine_repetitions(void) {
    uint8_t n = 1, k;
    ENTER_ENGINE;
    // the last entry is the current position; same side every two plies
    for(k = rep_count ? rep_count - 1 : 0; k >= 2; ) {
        k -= 2;
        if(rep_matches(k)) n++;
    }
    LEAVE_ENGINE;
    return n;
}

void history_restore_root(void) {
    rep_store();
}

uint8_t has_pieces(uint8_t color) {
    return npm[color >> 3] != 0;
}

uint8_t insufficient_material(void) {
    return pawn_count[0] == 0 && pawn_count[1] == 0 && npm[0] + npm[1] <= 330;
}

uint8_t find_move_flags(uint8_t from, uint8_t to, uint8_t promo) {
    uint16_t first = ms_top, last, i;
    uint8_t fl = 0xFF;

    last = generate_moves(0);
    for(i=first; i<last; i++) {
        if(mv_from[i] == from && mv_to[i] == to && (mv_flags[i] & F_PROMO_MASK) == promo) {
            fl = mv_flags[i];
            break;
        }
    }
    ms_top = first;
    return fl;
}

/*****************************************************************************
 * PAWN STRUCTURE
 *****************************************************************************/

#ifndef __CC65__
static const uint8_t passed_bonus[8] = {0, 10, 15, 25, 40, 65, 100, 0};

static uint8_t bit_count(uint8_t x) {
    uint8_t n = 0;

    while(x) {
        x &= x - 1;
        n++;
    }
    return n;
}


/**
 * @brief Doubled, isolated and passed pawns; stores the result in the cache
 *
 * Reference for the X16 version in engine_asm.s.
 */
int16_t pawn_structure_compute(void) {
    uint8_t f, m, n, r, ahead;
    uint8_t* w = pawn_files;
    uint8_t* b = pawn_files + 8;
    int16_t s = 0;

    for(f=0; f<8; f++) {
        m = w[f];
        if(m) {
            n = bit_count(m);
            if(n > 1) s -= 12 * (n - 1);
            if(!(f > 0 && w[f - 1]) && !(f < 7 && w[f + 1])) s -= 12 * n;
            for(r=7; !(m & (1 << r)); r--);         // most advanced pawn
            ahead = (uint8_t)(0xFF << (r + 1));
            if(!(b[f] & ahead) && !(f > 0 && (b[f - 1] & ahead)) &&
               !(f < 7 && (b[f + 1] & ahead))) s += passed_bonus[r];
        }
        m = b[f];
        if(m) {
            n = bit_count(m);
            if(n > 1) s += 12 * (n - 1);
            if(!(f > 0 && b[f - 1]) && !(f < 7 && b[f + 1])) s += 12 * n;
            for(r=0; !(m & (1 << r)); r++);
            ahead = (uint8_t)((1 << r) - 1);
            if(!(w[f] & ahead) && !(f > 0 && (w[f - 1] & ahead)) &&
               !(f < 7 && (w[f + 1] & ahead))) s -= passed_bonus[7 - r];
        }
    }
    {
        uint16_t slot = pawn_hash & (PC_SIZE - 1);
#ifdef __CC65__
        RAM_BANK = PAWN_BANK;
#endif
        PAWN_CACHE[0][slot] = pawn_hash2;
        PAWN_CACHE[1][slot] = pawn_hash >> 8;
        PAWN_CACHE[2][slot] = (uint8_t)s;
        PAWN_CACHE[3][slot] = (uint8_t)(s >> 8);
#ifdef __CC65__
        RAM_BANK = ENGINE_BANK;
#endif
    }
    return s;
}
#endif

int16_t engine_evaluate(void) {
    int16_t s;
    ENTER_ENGINE;
    s = evaluate();
    LEAVE_ENGINE;
    return s;
}

#ifndef NO_TEST_HOOKS
/*****************************************************************************
 * TEST HOOKS (engine harness and native tests only)
 *****************************************************************************/

uint8_t engine_validate(uint8_t from, uint8_t to, uint8_t promo) {
    uint8_t fl;
    ENTER_ENGINE;
    mk_from = from;
    mk_to = to;
    mk_flags = promo;
    fl = validate_move();
    LEAVE_ENGINE;
    return fl;
}

void engine_debug_board(uint8_t* out) {
    memcpy(out, bd, 128);
}

uint8_t engine_legal_moves(uint8_t* out) {
    uint16_t last, i;
    uint8_t n = 0;
    ENTER_ENGINE;

    ms_top = 0;
    last = generate_moves(0);
    for(i=0; i<last; i++) {
        if(MAKE(mv_from[i], mv_to[i], mv_flags[i])) {
            out[2 * n] = mv_from[i];
            out[2 * n + 1] = mv_to[i];
            n++;
        }
        unmake_move();
    }
    ms_top = 0;
    LEAVE_ENGINE;
    return n;
}

#ifdef __CC65__
#pragma static-locals (off)     // perft is recursive
#endif

uint16_t engine_perft_hash;

static uint32_t perft(uint8_t depth) {
    uint16_t first = ms_top, last, i;
    uint32_t count = 0;

    last = generate_moves(0);
    for(i=first; i<last; i++) {
        if(MAKE(mv_from[i], mv_to[i], mv_flags[i])) {
            if(depth > 1) {
                count += perft(depth - 1);
            } else {
                count++;
                engine_perft_hash = (engine_perft_hash << 1 | engine_perft_hash >> 15) ^ hash_lo ^ hash_hi;
            }
        }
        unmake_move();
    }
    ms_top = first;
    return count;
}

uint32_t engine_perft(uint8_t depth) {
    uint32_t n;
    ENTER_ENGINE;
    ms_top = 0;
    engine_perft_hash = 0;
    n = depth ? perft(depth) : 1;
    LEAVE_ENGINE;
    return n;
}
#endif
