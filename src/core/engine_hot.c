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
 * Per-node board code, C reference version for native builds. The X16 uses
 * engine_asm.s, which must behave identically (same nodes, same scores).
 */

#ifndef __CC65__

#include "engine.h"
#include "engine_int.h"

uint8_t bd[128];
uint8_t stm, castle, ep, fifty, sply;
uint16_t hash_lo, hash_hi;
uint32_t nodes;

uint16_t ms_top;
uint8_t mv_from[MS_SIZE], mv_to[MS_SIZE], mv_flags[MS_SIZE], mv_score[MS_SIZE];

int16_t psq_score;
int16_t npm[2];
uint8_t pawn_count[2], bishop_count[2], pawn_files[16], ksq[2];
uint16_t pawn_hash;
uint8_t pawn_hash2;
uint8_t rep_count;
uint8_t mk_from, mk_to, mk_flags, att_sq;

uint8_t zob_pages[12][256], psq_pages[7][256], pawn_cache[4][PC_SIZE];
uint8_t att_kinds[256];
int8_t att_step[256];
uint8_t history_table[16][64], rep_pages[4][256];

// undo information per ply
static uint8_t u_from[MAX_PLY], u_to[MAX_PLY], u_flags[MAX_PLY], u_captured[MAX_PLY];
static uint8_t u_castle[MAX_PLY], u_ep[MAX_PLY], u_fifty[MAX_PLY];
static uint16_t u_hash_lo[MAX_PLY], u_hash_hi[MAX_PLY];

static const int8_t knight_steps[8] = {33, 31, 18, 14, -33, -31, -18, -14};
static const int8_t king_steps[8] = {1, -1, 16, -16, 17, 15, -17, -15};
static const int8_t diagonal_steps[4] = {17, 15, -17, -15};
static const int8_t straight_steps[4] = {1, -1, 16, -16};

#define ZPAGE(p)        ZOB_PAGES[((p) & 7) - 1 + (((p) & 8) ? 6 : 0)]
#define PSQ(t, sq)      ((int16_t)(PSQ_PAGES[t][sq] | (PSQ_PAGES[t][(sq) | 0x80] << 8)))

/*****************************************************************************
 * BOARD UPDATES
 *****************************************************************************/

static uint16_t z0, z1;             // key of the last piece hashed

static void hash_piece(uint8_t p, uint8_t sq) {
    uint8_t* page = ZPAGE(p);
    uint8_t s = SQ64(sq);

    z0 = page[s] | (page[s | 0x40] << 8);
    z1 = page[s | 0x80] | (page[s | 0xC0] << 8);
    hash_lo ^= z0;
    hash_hi ^= z1;
}

static void piece_add(uint8_t p, uint8_t sq) {
    uint8_t c = p >> 3, t = p & 7;

    bd[sq] = p;
    hash_piece(p, sq);
    if(c) psq_score -= PSQ(t, sq ^ 0x70);
    else psq_score += PSQ(t, sq);
    if(t == PAWN) {
        pawn_count[c]++;
        pawn_files[(c << 3) | (sq & 7)] |= 1 << (sq >> 4);
        pawn_hash ^= z0;
        pawn_hash2 ^= (uint8_t)z1;
    } else if(t == KING) {
        ksq[c] = sq;
    } else {
        npm[c] += piece_value[t];
        if(t == BISHOP) bishop_count[c]++;
    }
}

static void piece_remove(uint8_t sq) {
    uint8_t p = bd[sq];
    uint8_t c = p >> 3, t = p & 7;

    bd[sq] = 0;
    hash_piece(p, sq);
    if(c) psq_score += PSQ(t, sq ^ 0x70);
    else psq_score -= PSQ(t, sq);
    if(t == PAWN) {
        pawn_count[c]--;
        pawn_files[(c << 3) | (sq & 7)] &= ~(1 << (sq >> 4));
        pawn_hash ^= z0;
        pawn_hash2 ^= (uint8_t)z1;
    } else if(t != KING) {
        npm[c] -= piece_value[t];
        if(t == BISHOP) bishop_count[c]--;
    }
}

void board_put(uint8_t piece) {
    piece_add(piece, mk_to);
}

void refresh_check(void) {
}

uint8_t validate_move(void) {
    if((mk_from | mk_to) & 0x88) return 0xFF;
    return find_move_flags(mk_from, mk_to, mk_flags & F_PROMO_MASK);
}

static void hash_state(void) {
    hash_lo ^= zob_castle_lo[castle];
    hash_hi ^= zob_castle_hi[castle];
    if(ep != NO_SQ) {
        hash_lo ^= zob_ep_lo[ep & 7];
        hash_hi ^= zob_ep_hi[ep & 7];
    }
}

static void rep_push(void) {
    REP_PAGES[0][rep_count] = (uint8_t)hash_lo;
    REP_PAGES[1][rep_count] = hash_lo >> 8;
    REP_PAGES[2][rep_count] = (uint8_t)hash_hi;
    REP_PAGES[3][rep_count] = hash_hi >> 8;
    rep_count++;
}

uint8_t make_move(void) {
    uint8_t from = mk_from, to = mk_to, fl = mk_flags;
    uint8_t p = bd[from];
    uint8_t mover = stm >> 3;
    uint8_t capsq = (fl & F_EP) ? ((from & 0xF0) | (to & 0x0F)) : to;
    uint8_t u = sply;

    u_from[u] = from;
    u_to[u] = to;
    u_flags[u] = fl;
    u_captured[u] = bd[capsq];
    u_castle[u] = castle;
    u_ep[u] = ep;
    u_fifty[u] = fifty;
    u_hash_lo[u] = hash_lo;
    u_hash_hi[u] = hash_hi;
    rep_push();

    hash_state();                               // remove old castle/ep keys
    if(bd[capsq]) piece_remove(capsq);
    piece_remove(from);
    piece_add((fl & F_PROMO_MASK) ? (stm | (fl & F_PROMO_MASK)) : p, to);
    if(fl & F_CASTLE) {
        if(to > from) {
            piece_add(bd[from + 3], from + 1);
            piece_remove(from + 3);
        } else {
            piece_add(bd[from - 4], from - 1);
            piece_remove(from - 4);
        }
    }
    castle &= castle_keep[from] & castle_keep[to];
    ep = (fl & F_DOUBLE) ? ((from + to) >> 1) : NO_SQ;
    fifty = (TYPE(p) == PAWN || u_captured[u]) ? 0 : fifty + 1;
    hash_state();
    stm ^= BLACK_SIDE;
    hash_lo ^= zob_side_lo;
    hash_hi ^= zob_side_hi;
    sply++;

    att_sq = ksq[mover];
    return !square_attacked(stm);
}

void unmake_move(void) {
    uint8_t u = --sply;
    uint8_t from = u_from[u], to = u_to[u], fl = u_flags[u];
    uint8_t p;

    stm ^= BLACK_SIDE;
    p = (fl & F_PROMO_MASK) ? (stm | PAWN) : bd[to];
    piece_remove(to);
    piece_add(p, from);
    if(fl & F_CASTLE) {
        if(to > from) {
            piece_add(bd[from + 1], from + 3);
            piece_remove(from + 1);
        } else {
            piece_add(bd[from - 1], from - 4);
            piece_remove(from - 1);
        }
    }
    if(u_captured[u]) {
        piece_add(u_captured[u], (fl & F_EP) ? ((from & 0xF0) | (to & 0x0F)) : to);
    }
    castle = u_castle[u];
    ep = u_ep[u];
    fifty = u_fifty[u];
    hash_lo = u_hash_lo[u];
    hash_hi = u_hash_hi[u];
    rep_count--;
}

void make_null(void) {
    uint8_t u = sply;

    u_ep[u] = ep;
    u_hash_lo[u] = hash_lo;
    u_hash_hi[u] = hash_hi;
    rep_push();
    if(ep != NO_SQ) {
        hash_lo ^= zob_ep_lo[ep & 7];
        hash_hi ^= zob_ep_hi[ep & 7];
        ep = NO_SQ;
    }
    stm ^= BLACK_SIDE;
    hash_lo ^= zob_side_lo;
    hash_hi ^= zob_side_hi;
    sply++;
}

void unmake_null(void) {
    uint8_t u = --sply;

    stm ^= BLACK_SIDE;
    ep = u_ep[u];
    hash_lo = u_hash_lo[u];
    hash_hi = u_hash_hi[u];
    rep_count--;
}

/**
 * @brief Has the current position occurred before (game or search path)?
 *
 * The repetition list holds the positions before each move, so entries two,
 * four, ... plies back have the same side to move.
 */
uint8_t is_repetition(void) {
    uint8_t i, n, k;

    if(fifty < 4) return 0;
    n = fifty > rep_count ? rep_count : fifty;
    for(i=2; i<=n; i+=2) {
        k = rep_count - i;
        if(REP_PAGES[0][k] == (uint8_t)hash_lo && REP_PAGES[1][k] == (hash_lo >> 8) &&
           REP_PAGES[2][k] == (uint8_t)hash_hi && REP_PAGES[3][k] == (hash_hi >> 8)) return 1;
    }
    return 0;
}

/*****************************************************************************
 * ATTACKS AND MOVE GENERATION
 *****************************************************************************/

uint8_t square_attacked(uint8_t by) {
    uint8_t sq = att_sq, i, t, p;
    int8_t step;

    if(by == 0) {
        t = sq - 15;
        if(!OFFB(t) && bd[t] == PAWN) return 1;
        t = sq - 17;
        if(!OFFB(t) && bd[t] == PAWN) return 1;
    } else {
        t = sq + 15;
        if(!OFFB(t) && bd[t] == (BLACK_SIDE | PAWN)) return 1;
        t = sq + 17;
        if(!OFFB(t) && bd[t] == (BLACK_SIDE | PAWN)) return 1;
    }
    for(i=0; i<8; i++) {
        t = sq + knight_steps[i];
        if(!OFFB(t) && bd[t] == (by | KNIGHT)) return 1;
        t = sq + king_steps[i];
        if(!OFFB(t) && bd[t] == (by | KING)) return 1;
    }
    for(i=0; i<4; i++) {
        step = diagonal_steps[i];
        for(t = sq + step; !OFFB(t); t += step) {
            p = bd[t];
            if(p) {
                if(p == (by | BISHOP) || p == (by | QUEEN)) return 1;
                break;
            }
        }
        step = straight_steps[i];
        for(t = sq + step; !OFFB(t); t += step) {
            p = bd[t];
            if(p) {
                if(p == (by | ROOK) || p == (by | QUEEN)) return 1;
                break;
            }
        }
    }
    return 0;
}

uint8_t in_check(void) {
    att_sq = ksq[stm >> 3];
    return square_attacked(stm ^ BLACK_SIDE);
}

static uint8_t castle_path_safe(uint8_t a, uint8_t b, uint8_t c, uint8_t them) {
    att_sq = a;
    if(square_attacked(them)) return 0;
    att_sq = b;
    if(square_attacked(them)) return 0;
    att_sq = c;
    return !square_attacked(them);
}

#define ADD(f, t, fl) do { mv_from[n] = (f); mv_to[n] = (t); mv_flags[n] = (fl); n++; } while(0)

uint16_t generate_moves(uint8_t captures_only) {
    uint16_t n = ms_top;
    uint8_t sq, p, t, q, i, them, forward, start_rank, last_rank;
    int8_t step;
    const int8_t* steps;
    uint8_t nsteps, slide;

    if(n > MS_SIZE - MAX_MOVES) return n;       // move stack full: no moves
    them = stm ^ BLACK_SIDE;
    forward = stm ? (uint8_t)-16 : 16;
    start_rank = stm ? 6 : 1;
    last_rank = stm ? 0 : 7;

    for(sq=0; sq<128; sq++) {
        if(OFFB(sq)) {
            sq += 7;
            continue;
        }
        p = bd[sq];
        if(!p || (p & BLACK_SIDE) != stm) continue;

        if(TYPE(p) == PAWN) {
            t = sq + forward;
            if(!bd[t]) {
                if((t >> 4) == last_rank) {
                    ADD(sq, t, QUEEN);
                    if(!captures_only) {
                        ADD(sq, t, ROOK);
                        ADD(sq, t, BISHOP);
                        ADD(sq, t, KNIGHT);
                    }
                } else if(!captures_only) {
                    ADD(sq, t, 0);
                    t += forward;
                    if((sq >> 4) == start_rank && !bd[t]) ADD(sq, t, F_DOUBLE);
                }
            }
            for(i=0; i<2; i++) {
                t = sq + forward + (i ? 1 : -1);
                if(OFFB(t)) continue;
                q = bd[t];
                if(q && (q & BLACK_SIDE) == them) {
                    if((t >> 4) == last_rank) {
                        ADD(sq, t, F_CAPTURE | QUEEN);
                        if(!captures_only) {
                            ADD(sq, t, F_CAPTURE | ROOK);
                            ADD(sq, t, F_CAPTURE | BISHOP);
                            ADD(sq, t, F_CAPTURE | KNIGHT);
                        }
                    } else {
                        ADD(sq, t, F_CAPTURE);
                    }
                } else if(t == ep) {
                    ADD(sq, t, F_CAPTURE | F_EP);
                }
            }
            continue;
        }

        switch(TYPE(p)) {
            case KNIGHT: steps = knight_steps; nsteps = 8; slide = 0; break;
            case BISHOP: steps = diagonal_steps; nsteps = 4; slide = 1; break;
            case ROOK: steps = straight_steps; nsteps = 4; slide = 1; break;
            case QUEEN: steps = king_steps; nsteps = 8; slide = 1; break;
            default: steps = king_steps; nsteps = 8; slide = 0; break;
        }
        for(i=0; i<nsteps; i++) {
            step = steps[i];
            for(t = sq + step; !OFFB(t); t += step) {
                q = bd[t];
                if(!q) {
                    if(!captures_only) ADD(sq, t, 0);
                } else {
                    if((q & BLACK_SIDE) == them) ADD(sq, t, F_CAPTURE);
                    break;
                }
                if(!slide) break;
            }
        }
    }

    if(!captures_only) {
        if(stm == 0) {
            if((castle & 1) && !bd[0x05] && !bd[0x06] && castle_path_safe(0x04, 0x05, 0x06, them))
                ADD(0x04, 0x06, F_CASTLE);
            if((castle & 2) && !bd[0x01] && !bd[0x02] && !bd[0x03] && castle_path_safe(0x04, 0x03, 0x02, them))
                ADD(0x04, 0x02, F_CASTLE);
        } else {
            if((castle & 4) && !bd[0x75] && !bd[0x76] && castle_path_safe(0x74, 0x75, 0x76, them))
                ADD(0x74, 0x76, F_CASTLE);
            if((castle & 8) && !bd[0x71] && !bd[0x72] && !bd[0x73] && castle_path_safe(0x74, 0x73, 0x72, them))
                ADD(0x74, 0x72, F_CASTLE);
        }
    }
    ms_top = n;
    return n;
}

/*****************************************************************************
 * EVALUATION
 *****************************************************************************/

/**
 * @brief Missing pawn cover in front of a king on its first two ranks
 */
static int16_t king_shelter(uint8_t c) {
    uint8_t k = ksq[c], f = k & 7, r = k >> 4;
    uint8_t cover, i;
    int16_t penalty = 0;

    if(c ? r < 6 : r > 1) return 0;
    cover = c ? 0x60 : 0x06;                    // ranks 2-3 resp. 7-6
    for(i = f ? f - 1 : 0; i <= f + 1 && i < 8; i++) {
        if(!(pawn_files[(c << 3) | i] & cover)) penalty += 15;
    }
    return penalty;
}

/**
 * @brief Drive a bare king to the edge and bring the other king closer
 */
static int16_t mop_up(uint8_t loser, uint8_t winner) {
    uint8_t lf = loser & 7, wf = winner & 7, lr = loser >> 4, wr = winner >> 4;
    uint8_t df = lf > wf ? lf - wf : wf - lf;
    uint8_t dr = lr > wr ? lr - wr : wr - lr;
    return 10 * center_dist[loser] + 4 * (14 - df - dr);
}

int16_t evaluate(void) {
    int16_t s = psq_score;
    uint16_t slot;

    if(npm[0] + npm[1] <= 1300) {
        s += king_endgame[ksq[0]] - king_endgame[ksq[1] ^ 0x70];
        if(s > 200 && pawn_count[1] == 0) s += mop_up(ksq[1], ksq[0]);
        if(s < -200 && pawn_count[0] == 0) s -= mop_up(ksq[0], ksq[1]);
    } else {
        s += king_shelter(1) - king_shelter(0);
    }
    if(bishop_count[0] >= 2) s += 30;
    if(bishop_count[1] >= 2) s -= 30;

    slot = pawn_hash & (PC_SIZE - 1);
    if(PAWN_CACHE[0][slot] == pawn_hash2 && PAWN_CACHE[1][slot] == (pawn_hash >> 8)) {
        s += (int16_t)(PAWN_CACHE[2][slot] | (PAWN_CACHE[3][slot] << 8));
    } else {
        s += pawn_structure_compute();
    }
    return (stm ? -s : s) + 10;
}

#endif
