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

#ifdef __CC65__
#include <ascii_charmap.h>      // SAN letters must match the ASCII font
#pragma static-locals (on)
#endif
#include <string.h>

#include "rules.h"

uint8_t board[128];
uint8_t side;
uint8_t castling;
uint8_t ep_square;
uint8_t halfmove_clock;
uint16_t ply;

move_t legal_moves[MAX_MOVES];
uint8_t legal_count;

typedef struct {
    move_t move;
    uint8_t captured;
    uint8_t castling;
    uint8_t ep_square;
    uint8_t halfmove_clock;
} undo_t;

static undo_t history[UNDO_DEPTH];
static uint8_t history_len;
static uint8_t king_sq[2];

static const int8_t knight_steps[8] = {33, 31, 18, 14, -33, -31, -18, -14};
static const int8_t king_steps[8] = {1, -1, 16, -16, 17, 15, -17, -15};
static const int8_t diagonal_steps[4] = {17, 15, -17, -15};
static const int8_t straight_steps[4] = {1, -1, 16, -16};
static const uint8_t back_rank[8] = {ROOK, KNIGHT, BISHOP, QUEEN, KING, BISHOP, KNIGHT, ROOK};

#define KING_INDEX(color) ((color) >> 3)

/**
 * @brief Set up the initial position
 */
void rules_new_game(void) {
    uint8_t f;

    memset(board, EMPTY, sizeof(board));
    for(f=0; f<8; f++) {
        board[SQ(f, 0)] = WHITE | back_rank[f];
        board[SQ(f, 1)] = WHITE | PAWN;
        board[SQ(f, 6)] = BLACK | PAWN;
        board[SQ(f, 7)] = BLACK | back_rank[f];
    }
    side = WHITE;
    castling = CASTLE_WK | CASTLE_WQ | CASTLE_BK | CASTLE_BQ;
    ep_square = NO_SQUARE;
    halfmove_clock = 0;
    ply = 0;
    history_len = 0;
    king_sq[0] = SQ(4, 0);
    king_sq[1] = SQ(4, 7);
}

#if defined(__CC65__) && defined(NO_TEST_HOOKS)
#pragma code-name (push, "UICODE")
#endif
void rules_capture(rules_position_t* position) {
    memcpy(position->board, board, 128);
    position->side = side;
    position->castling = castling;
    position->ep_square = ep_square;
    position->halfmove_clock = halfmove_clock;
    position->ply = ply;
}

void rules_restore(const rules_position_t* position) {
    uint8_t square;
    memcpy(board, position->board, 128);
    side = position->side;
    castling = position->castling;
    ep_square = position->ep_square;
    halfmove_clock = position->halfmove_clock;
    ply = position->ply;
    history_len = 0;
    for(square = 0; square < 128; square++) {
        if(!OFFBOARD(square) && TYPE(board[square]) == KING)
            king_sq[COLOR(board[square]) >> 3] = square;
    }
    rules_generate_legal();
}

#if defined(__CC65__) && defined(NO_TEST_HOOKS)
#pragma code-name (pop)
#endif

#ifndef NO_TEST_HOOKS
/**
 * @brief Set up a position from FEN; returns 0 on malformed input
 */
uint8_t rules_load_fen(const char* fen) {
    static const char letters[] = "pnbrqk";
    const char* l;
    uint8_t file = 0, rank = 7, c;

    memset(board, EMPTY, sizeof(board));
    king_sq[0] = king_sq[1] = NO_SQUARE;
    for(; *fen && *fen != ' '; fen++) {
        c = *fen;
        if(c == '/') {
            if(rank == 0) return 0;
            rank--;
            file = 0;
        } else if(c >= '1' && c <= '8') {
            file += c - '0';
        } else {
            for(l = letters; *l && *l != (c | 0x20); l++);
            if(!*l || file > 7) return 0;
            board[SQ(file, rank)] = (l - letters + 1) | ((c & 0x20) ? BLACK : WHITE);
            if(*l == 'k') king_sq[(c & 0x20) ? 1 : 0] = SQ(file, rank);
            file++;
        }
    }
    if(king_sq[0] == NO_SQUARE || king_sq[1] == NO_SQUARE || *fen++ != ' ') return 0;

    side = (*fen == 'b') ? BLACK : WHITE;
    fen += 2;
    castling = 0;
    for(; *fen && *fen != ' '; fen++) {
        if(*fen == 'K') castling |= CASTLE_WK;
        if(*fen == 'Q') castling |= CASTLE_WQ;
        if(*fen == 'k') castling |= CASTLE_BK;
        if(*fen == 'q') castling |= CASTLE_BQ;
    }
    ep_square = NO_SQUARE;
    if(*fen == ' ' && fen[1] >= 'a' && fen[1] <= 'h') {
        ep_square = SQ(fen[1] - 'a', fen[2] - '1');
    }
    halfmove_clock = 0;
    ply = 0;
    history_len = 0;
    return 1;
}
#endif

/**
 * @brief Is square attacked by the pieces of colour by?
 *
 * Squares are 8-bit, so stepping off the board wraps into the 0x88 guard
 * bits and is caught by OFFBOARD.
 */
uint8_t rules_attacked(uint8_t sq, uint8_t by) {
    uint8_t i, t, p;
    int8_t step;

    // pawns attack diagonally forward, so look backwards from the square
    if(by == WHITE) {
        t = sq - 15;
        if(!OFFBOARD(t) && board[t] == (WHITE | PAWN)) return 1;
        t = sq - 17;
        if(!OFFBOARD(t) && board[t] == (WHITE | PAWN)) return 1;
    } else {
        t = sq + 15;
        if(!OFFBOARD(t) && board[t] == (BLACK | PAWN)) return 1;
        t = sq + 17;
        if(!OFFBOARD(t) && board[t] == (BLACK | PAWN)) return 1;
    }

    for(i=0; i<8; i++) {
        t = sq + knight_steps[i];
        if(!OFFBOARD(t) && board[t] == (by | KNIGHT)) return 1;
        t = sq + king_steps[i];
        if(!OFFBOARD(t) && board[t] == (by | KING)) return 1;
    }

    for(i=0; i<4; i++) {
        step = diagonal_steps[i];
        for(t = sq + step; !OFFBOARD(t); t += step) {
            p = board[t];
            if(p != EMPTY) {
                if(p == (by | BISHOP) || p == (by | QUEEN)) return 1;
                break;
            }
        }
        step = straight_steps[i];
        for(t = sq + step; !OFFBOARD(t); t += step) {
            p = board[t];
            if(p != EMPTY) {
                if(p == (by | ROOK) || p == (by | QUEEN)) return 1;
                break;
            }
        }
    }
    return 0;
}

/**
 * @brief Square of the king of the given colour
 */
uint8_t rules_king_square(uint8_t color) {
    return king_sq[KING_INDEX(color)];
}

/**
 * @brief Is the side to move in check?
 */
uint8_t rules_in_check(void) {
    return rules_attacked(king_sq[KING_INDEX(side)], side ^ BLACK);
}

static move_t* gen_out;
static uint8_t gen_count;

static void add_move(uint8_t from, uint8_t to, uint8_t flags) {
    move_t* m = &gen_out[gen_count++];
    m->from = from;
    m->to = to;
    m->promo = EMPTY;
    m->flags = flags;
}

static void add_pawn_move(uint8_t from, uint8_t to, uint8_t flags) {
    uint8_t promo;
    uint8_t rank = RANK_OF(to);

    if(rank == 0 || rank == 7) {
        for(promo = QUEEN; promo >= KNIGHT; promo--) {
            add_move(from, to, flags | MF_PROMOTION);
            gen_out[gen_count - 1].promo = promo;
        }
    } else {
        add_move(from, to, flags);
    }
}

static void gen_steps(uint8_t from, const int8_t* steps, uint8_t n, uint8_t slide) {
    uint8_t i, t, p;
    int8_t step;

    for(i=0; i<n; i++) {
        step = steps[i];
        for(t = from + step; !OFFBOARD(t); t += step) {
            p = board[t];
            if(p == EMPTY) {
                add_move(from, t, 0);
            } else {
                if(COLOR(p) != side) add_move(from, t, MF_CAPTURE);
                break;
            }
            if(!slide) break;
        }
    }
}

/**
 * @brief Generate pseudo-legal moves (own king may be left in check)
 */
static uint8_t gen_pseudo(move_t* out) {
    uint8_t sq, p, t, them;
    uint8_t forward, start_rank;

    gen_out = out;
    gen_count = 0;
    them = side ^ BLACK;
    forward = (side == WHITE) ? 16 : (uint8_t)-16;
    start_rank = (side == WHITE) ? 1 : 6;

    for(sq=0; sq<128; sq++) {
        if(OFFBOARD(sq)) {
            sq += 7;
            continue;
        }
        p = board[sq];
        if(p == EMPTY || COLOR(p) != side) continue;

        switch(TYPE(p)) {
            case PAWN:
                t = sq + forward;
                if(board[t] == EMPTY) {
                    add_pawn_move(sq, t, 0);
                    t += forward;       // keep the 8-bit wrap-around for black
                    if(RANK_OF(sq) == start_rank && board[t] == EMPTY) {
                        add_move(sq, t, MF_DOUBLE);
                    }
                }
                t = sq + forward - 1;
                if(!OFFBOARD(t)) {
                    if(board[t] != EMPTY && COLOR(board[t]) == them) add_pawn_move(sq, t, MF_CAPTURE);
                    else if(t == ep_square) add_move(sq, t, MF_CAPTURE | MF_ENPASSANT);
                }
                t = sq + forward + 1;
                if(!OFFBOARD(t)) {
                    if(board[t] != EMPTY && COLOR(board[t]) == them) add_pawn_move(sq, t, MF_CAPTURE);
                    else if(t == ep_square) add_move(sq, t, MF_CAPTURE | MF_ENPASSANT);
                }
                break;
            case KNIGHT:
                gen_steps(sq, knight_steps, 8, 0);
                break;
            case BISHOP:
                gen_steps(sq, diagonal_steps, 4, 1);
                break;
            case ROOK:
                gen_steps(sq, straight_steps, 4, 1);
                break;
            case QUEEN:
                gen_steps(sq, king_steps, 8, 1);
                break;
            case KING:
                gen_steps(sq, king_steps, 8, 0);
                break;
        }
    }

    // castling: path empty, king not in, through or into check
    if(side == WHITE) {
        if((castling & CASTLE_WK) && board[SQ(5,0)] == EMPTY && board[SQ(6,0)] == EMPTY &&
           !rules_attacked(SQ(4,0), BLACK) && !rules_attacked(SQ(5,0), BLACK) &&
           !rules_attacked(SQ(6,0), BLACK)) {
            add_move(SQ(4,0), SQ(6,0), MF_CASTLE);
        }
        if((castling & CASTLE_WQ) && board[SQ(1,0)] == EMPTY && board[SQ(2,0)] == EMPTY &&
           board[SQ(3,0)] == EMPTY && !rules_attacked(SQ(4,0), BLACK) &&
           !rules_attacked(SQ(3,0), BLACK) && !rules_attacked(SQ(2,0), BLACK)) {
            add_move(SQ(4,0), SQ(2,0), MF_CASTLE);
        }
    } else {
        if((castling & CASTLE_BK) && board[SQ(5,7)] == EMPTY && board[SQ(6,7)] == EMPTY &&
           !rules_attacked(SQ(4,7), WHITE) && !rules_attacked(SQ(5,7), WHITE) &&
           !rules_attacked(SQ(6,7), WHITE)) {
            add_move(SQ(4,7), SQ(6,7), MF_CASTLE);
        }
        if((castling & CASTLE_BQ) && board[SQ(1,7)] == EMPTY && board[SQ(2,7)] == EMPTY &&
           board[SQ(3,7)] == EMPTY && !rules_attacked(SQ(4,7), WHITE) &&
           !rules_attacked(SQ(3,7), WHITE) && !rules_attacked(SQ(2,7), WHITE)) {
            add_move(SQ(4,7), SQ(2,7), MF_CASTLE);
        }
    }
    return gen_count;
}

/**
 * @brief Castling rights lost when a piece leaves or arrives on a square
 */
static uint8_t castle_loss(uint8_t sq) {
    switch(sq) {
        case SQ(0,0): return CASTLE_WQ;
        case SQ(7,0): return CASTLE_WK;
        case SQ(4,0): return CASTLE_WK | CASTLE_WQ;
        case SQ(0,7): return CASTLE_BQ;
        case SQ(7,7): return CASTLE_BK;
        case SQ(4,7): return CASTLE_BK | CASTLE_BQ;
    }
    return 0;
}

/**
 * @brief Play a move; returns 0 when it leaves the own king in check
 */
uint8_t rules_make(const move_t* m) {
    undo_t* u = &history[history_len++];
    uint8_t from = m->from;
    uint8_t to = m->to;
    uint8_t piece = board[from];
    uint8_t mover = side;
    uint8_t capsq;

    u->move = *m;
    u->captured = board[to];
    u->castling = castling;
    u->ep_square = ep_square;
    u->halfmove_clock = halfmove_clock;

    board[to] = (m->flags & MF_PROMOTION) ? (side | m->promo) : piece;
    board[from] = EMPTY;

    if(m->flags & MF_ENPASSANT) {
        // the captured pawn stands beside the moving pawn (a separate
        // variable: cc65 2.19 miscompiles the index expression here)
        capsq = (from & 0xF0) | (to & 0x0F);
        u->captured = board[capsq];
        board[capsq] = EMPTY;
    }
    if(m->flags & MF_CASTLE) {
        if(to > from) {
            board[from + 1] = board[from + 3];
            board[from + 3] = EMPTY;
        } else {
            board[from - 1] = board[from - 4];
            board[from - 4] = EMPTY;
        }
    }
    if(TYPE(piece) == KING) king_sq[KING_INDEX(side)] = to;

    castling &= ~(castle_loss(from) | castle_loss(to));
    ep_square = (m->flags & MF_DOUBLE) ? ((from + to) >> 1) : NO_SQUARE;
    if(TYPE(piece) == PAWN || (m->flags & MF_CAPTURE)) {
        halfmove_clock = 0;
    } else {
        halfmove_clock++;
    }
    side ^= BLACK;
    ply++;

    return !rules_attacked(king_sq[KING_INDEX(mover)], side);
}

/**
 * @brief Make the moves played so far permanent
 */
void rules_commit(void) {
    history_len = 0;
}

/**
 * @brief Take back the most recent move
 */
void rules_unmake(void) {
    undo_t* u = &history[--history_len];
    const move_t* m = &u->move;
    uint8_t from = m->from;
    uint8_t to = m->to;
    uint8_t piece, capsq;

    side ^= BLACK;
    ply--;
    castling = u->castling;
    ep_square = u->ep_square;
    halfmove_clock = u->halfmove_clock;

    piece = (m->flags & MF_PROMOTION) ? (side | PAWN) : board[to];
    board[from] = piece;
    if(m->flags & MF_ENPASSANT) {
        board[to] = EMPTY;
        capsq = (from & 0xF0) | (to & 0x0F);
        board[capsq] = u->captured;
    } else {
        board[to] = u->captured;
    }
    if(m->flags & MF_CASTLE) {
        if(to > from) {
            board[from + 3] = board[from + 1];
            board[from + 1] = EMPTY;
        } else {
            board[from - 4] = board[from - 1];
            board[from - 1] = EMPTY;
        }
    }
    if(TYPE(piece) == KING) king_sq[KING_INDEX(side)] = from;
}

/**
 * @brief Fill legal_moves with all legal moves of the side to move
 */
uint8_t rules_generate_legal(void) {
    uint8_t i, n;

    n = gen_pseudo(legal_moves);
    legal_count = 0;
    for(i=0; i<n; i++) {
        if(rules_make(&legal_moves[i])) {
            legal_moves[legal_count++] = legal_moves[i];
        }
        rules_unmake();
    }
    return legal_count;
}

/**
 * @brief Does the side to move have at least one legal move?
 *
 * Overwrites legal_moves (see rules_san).
 */
#if defined(__CC65__) && defined(NO_TEST_HOOKS)
#pragma code-name (push, "MENUCODE")
#endif
static uint8_t has_legal_move(void) {
    uint8_t i, n, ok;

    n = gen_pseudo(legal_moves);
    for(i=0; i<n; i++) {
        ok = rules_make(&legal_moves[i]);
        rules_unmake();
        if(ok) return 1;
    }
    return 0;
}

static const char piece_letters[] = " PNBRQK";

/**
 * @brief Write the SAN of a legal move into buf (8 bytes)
 */
#if defined(__CC65__) && defined(NO_TEST_HOOKS)
static void banked_san(const move_t* m, char* buf) {
#else
void rules_san(const move_t* m, char* buf) {
#endif
    uint8_t piece = board[m->from];
    uint8_t type = TYPE(piece);
    uint8_t i, ambiguous = 0, same_file = 0, same_rank = 0;
    const move_t* other;
    char* p = buf;

    if(m->flags & MF_CASTLE) {
        *p++ = 'O'; *p++ = '-'; *p++ = 'O';
        if(FILE_OF(m->to) == 2) {
            *p++ = '-'; *p++ = 'O';
        }
    } else {
        if(type != PAWN) {
            *p++ = piece_letters[type];
            for(i=0; i<legal_count; i++) {
                other = &legal_moves[i];
                if(other->to == m->to && other->from != m->from && board[other->from] == piece) {
                    ambiguous = 1;
                    if(FILE_OF(other->from) == FILE_OF(m->from)) same_file = 1;
                    if(RANK_OF(other->from) == RANK_OF(m->from)) same_rank = 1;
                }
            }
            if(ambiguous) {
                if(!same_file) {
                    *p++ = 'a' + FILE_OF(m->from);
                } else if(!same_rank) {
                    *p++ = '1' + RANK_OF(m->from);
                } else {
                    *p++ = 'a' + FILE_OF(m->from);
                    *p++ = '1' + RANK_OF(m->from);
                }
            }
        } else if(m->flags & MF_CAPTURE) {
            *p++ = 'a' + FILE_OF(m->from);
        }
        if(m->flags & MF_CAPTURE) *p++ = 'x';
        *p++ = 'a' + FILE_OF(m->to);
        *p++ = '1' + RANK_OF(m->to);
        if(m->flags & MF_PROMOTION) {
            *p++ = '=';
            *p++ = piece_letters[m->promo];
        }
    }

    rules_make(m);
    if(rules_in_check()) {
        *p++ = has_legal_move() ? '+' : '#';
    }
    rules_unmake();
    *p = 0;
}

#if defined(__CC65__) && defined(NO_TEST_HOOKS)
#pragma code-name (pop)
void rules_san(const move_t* m, char* buf) {
    uint8_t saved = *(uint8_t*)0;
    *(uint8_t*)0 = 21;
    banked_san(m, buf);
    *(uint8_t*)0 = saved;
}
#endif

/**
 * @brief Neither side can possibly mate (K v K, K+minor v K)
 */
uint8_t rules_insufficient_material(void) {
    uint8_t sq, t, minors = 0;

    for(sq=0; sq<128; sq++) {
        if(OFFBOARD(sq)) {
            sq += 7;
            continue;
        }
        t = TYPE(board[sq]);
        if(t == PAWN || t == ROOK || t == QUEEN) return 0;
        if(t == KNIGHT || t == BISHOP) minors++;
    }
    return minors <= 1;
}
