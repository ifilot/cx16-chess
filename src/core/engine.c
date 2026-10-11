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
 * Search: iterative deepening, principal variation search with a
 * transposition table, null-move pruning, late move reductions, check
 * extensions, killer/history move ordering and a capture-only quiescence
 * search. The board, move generation and evaluation live in engine_board.c.
 */

#include <string.h>

#include "engine.h"
#include "engine_int.h"

#ifdef __CC65__
#include <time.h>
#pragma static-locals (on)      // no recursion in the X16 build of this file
#endif

void (*engine_poll)(void);

// search limits and bookkeeping (search_aborted is shared with engine_search.s)
static uint32_t node_limit;
static uint16_t time_limit;
static uint16_t time_start;
uint8_t search_aborted;
#define aborted search_aborted

// killer moves per ply (shared with engine_search.s)
uint8_t killer_from[2][MAX_PLY];
uint8_t killer_to[2][MAX_PLY];


// root move list (survives the move stack being reused by the search)
#if defined(__CC65__) && defined(NO_TEST_HOOKS)
#pragma bss-name (push, "GOLDENBSS")
#endif
static uint8_t root_from[MAX_MOVES];
static uint8_t root_to[MAX_MOVES];
#if defined(__CC65__) && defined(NO_TEST_HOOKS)
#pragma bss-name (pop)
#endif
static uint8_t root_flags[MAX_MOVES];
static uint8_t root_count;
static uint16_t weakness, random_state = 1;

void engine_set_weakness(uint16_t noise, uint16_t seed) {
    weakness = noise > 2000 ? 2000 : noise;
    if(seed) random_state = seed;
}

static uint16_t move_noise(void) {
    /* 16-bit xorshift; explicit truncation gives identical arithmetic on
     * cc65 and x64. No use of the platform's rand() or clock in tests. */
    random_state ^= (uint16_t)(random_state << 7);
    random_state ^= random_state >> 9;
    random_state ^= (uint16_t)(random_state << 8);
    return random_state % (weakness + 1);
}

/*****************************************************************************
 * TIME
 *****************************************************************************/

static uint16_t now(void) {
#ifdef __CC65__
    return (uint16_t)clock();
#else
    return 0;
#endif
}

/**
 * @brief Check the search limits; called every 256 nodes
 */
void search_poll(void) {
    if(node_limit && nodes >= node_limit) aborted = 1;
    if(time_limit && (uint16_t)(now() - time_start) >= time_limit) aborted = 1;
    if(engine_poll) {
        engine_poll();
#ifdef __CC65__
        RAM_BANK = ENGINE_BANK;                 // the callback may switch banks
#endif
    }
}

/*****************************************************************************
 * TRANSPOSITION TABLE
 *
 * 8-byte entries: hash check (16 bits), best move, score, depth and bound.
 * On the X16 the table fills banked RAM, 1024 entries per 8 KiB bank.
 *****************************************************************************/

#define TT_EXACT        1
#define TT_LOWER        2       // score is a lower bound (fail high)
#define TT_UPPER        3       // score is an upper bound (fail low)

typedef struct {
    uint16_t check;
    uint8_t from;
    uint8_t to;
    int16_t score;
    uint8_t depth;
    uint8_t bound_promo;        // bound << 4 | promotion flags
} tt_entry_t;

#ifdef __CC65__
#define TT_FIRST_BANK   2
#define TT_BANKS        16      // 128 KiB, 16384 entries

static tt_entry_t* tt_slot(void) {
    RAM_BANK = TT_FIRST_BANK + ((uint8_t)(hash_lo >> 10) & (TT_BANKS - 1));
    return (tt_entry_t*)(0xA000 + ((hash_lo & 1023) << 3));
}

static void tt_clear(void) {
    uint8_t bank, saved = RAM_BANK;

    for(bank=0; bank<TT_BANKS; bank++) {
        RAM_BANK = TT_FIRST_BANK + bank;
        memset((void*)0xA000, 0, 0x2000);
    }
    RAM_BANK = saved;
}
// the search runs with the engine bank selected
#define BANK_SAVE
#define BANK_RESTORE    RAM_BANK = ENGINE_BANK
#else
#define TT_SIZE         16384
static tt_entry_t tt_table[TT_SIZE];

static tt_entry_t* tt_slot(void) {
    return &tt_table[hash_lo & (TT_SIZE - 1)];
}

static void tt_clear(void) {
    memset(tt_table, 0, sizeof(tt_table));
}
#define BANK_SAVE
#define BANK_RESTORE
#endif

// mate scores are stored relative to the node, not the root
static int16_t score_to_tt(int16_t score) {
    if(score > ENGINE_MATE - 512) return score + sply;
    if(score < -ENGINE_MATE + 512) return score - sply;
    return score;
}

static int16_t score_from_tt(int16_t score) {
    if(score > ENGINE_MATE - 512) return score - sply;
    if(score < -ENGINE_MATE + 512) return score + sply;
    return score;
}

/**
 * @brief Copy the entry of the current position; returns 0 when absent
 */
static uint8_t tt_probe(tt_entry_t* out) {
    tt_entry_t* e;
    uint8_t hit;
    BANK_SAVE;

    e = tt_slot();
    hit = (e->check == hash_hi && (e->from | e->to));
    if(hit) {
        *out = *e;
        out->score = score_from_tt(out->score);
    }
    BANK_RESTORE;
    return hit;
}

static void tt_store(uint8_t depth, int16_t score, uint8_t bound,
                     uint8_t from, uint8_t to, uint8_t flags) {
    tt_entry_t* e;
    BANK_SAVE;

    e = tt_slot();
    // keep deeper entries of the same position; always replace others
    if(e->check != hash_hi || e->depth <= depth || bound == TT_EXACT) {
        e->check = hash_hi;
        e->from = from;
        e->to = to;
        e->score = score_to_tt(score);
        e->depth = depth;
        e->bound_promo = (bound << 4) | (flags & F_PROMO_MASK);
    }
    BANK_RESTORE;
}

/*****************************************************************************
 * MOVE ORDERING
 *****************************************************************************/

static const uint8_t victim_value[7] = {0, 1, 3, 3, 5, 9, 0};

/**
 * @brief Give the moves first..last-1 an ordering score
 *
 * Hash move first, then captures by MVV-LVA, killers, and the remaining
 * quiet moves by their history counter.
 */
static void score_moves(uint16_t first, uint16_t last, uint8_t hfrom, uint8_t hto) {
    uint16_t i;
    uint8_t from, to, fl, attacker;
    uint16_t h;

    for(i=first; i<last; i++) {
        from = mv_from[i];
        to = mv_to[i];
        fl = mv_flags[i];
        if(from == hfrom && to == hto) {
            mv_score[i] = 255;
        } else if(fl & (F_CAPTURE | F_PROMO_MASK)) {
            attacker = TYPE(bd[from]);
            // 151..254: above the killers, below the hash move
            mv_score[i] = 151 + (victim_value[TYPE(bd[to])] << 3) - victim_value[attacker] +
                          ((fl & F_PROMO_MASK) == QUEEN ? 32 : 0);
            if(fl & F_EP) mv_score[i] = 151 + 8 - 1;
        } else if(from == killer_from[0][sply] && to == killer_to[0][sply]) {
            mv_score[i] = 150;
        } else if(from == killer_from[1][sply] && to == killer_to[1][sply]) {
            mv_score[i] = 149;
        } else {
            h = HISTORY[bd[from]][SQ64(to)];
            mv_score[i] = h > 140 ? 140 : (uint8_t)h;
        }
    }
}

/**
 * @brief Move the best scored move of i..last-1 to position i
 */
static void pick_move(uint16_t i, uint16_t last) {
    uint16_t j, best = i;
    uint8_t t;

    for(j=i+1; j<last; j++) {
        if(mv_score[j] > mv_score[best]) best = j;
    }
    if(best != i) {
        t = mv_from[i]; mv_from[i] = mv_from[best]; mv_from[best] = t;
        t = mv_to[i]; mv_to[i] = mv_to[best]; mv_to[best] = t;
        t = mv_flags[i]; mv_flags[i] = mv_flags[best]; mv_flags[best] = t;
        t = mv_score[i]; mv_score[i] = mv_score[best]; mv_score[best] = t;
    }
}

#ifdef __CC65__
/*
 * On the X16 the search below is replaced by engine_search.s; the root
 * driver calls it through search_entry() with arguments in globals.
 */
extern int8_t s_depth;
extern int16_t s_alpha, s_beta;
extern uint8_t s_null;
int16_t search_entry(void);
#define SEARCH(d, a, b, n) (s_depth = (d), s_alpha = (a), s_beta = (b), s_null = (n), search_entry())
#else
#define SEARCH(d, a, b, n) search(d, a, b, n)

static uint8_t poll_count;

static void check_limits(void) {
    if(++poll_count) return;
    search_poll();
}

static void remember_quiet(uint8_t from, uint8_t to, uint8_t depth) {
    uint8_t* h;
    uint16_t i;

    if(killer_from[0][sply] != from || killer_to[0][sply] != to) {
        killer_from[1][sply] = killer_from[0][sply];
        killer_to[1][sply] = killer_to[0][sply];
        killer_from[0][sply] = from;
        killer_to[0][sply] = to;
    }
    h = &HISTORY[bd[from]][SQ64(to)];
    if(*h > 255 - 64) {                         // age all counters
        for(i=0; i<16 * 64; i++) (&HISTORY[0][0])[i] >>= 1;
    }
    *h += depth * depth > 64 ? 64 : depth * depth;
}

/*****************************************************************************
 * SEARCH
 *****************************************************************************/

/**
 * @brief Captures-only search until the position is quiet
 */
static int16_t quiesce(int16_t alpha, int16_t beta) {
    int16_t score, stand;
    uint16_t first, last, i;
    uint8_t from, to, fl;

    nodes++;
    check_limits();
    if(aborted) return 0;

    stand = evaluate();
    if(stand >= beta) return stand;
    if(stand > alpha) alpha = stand;
    if(sply >= MAX_PLY - 1) return stand;

    first = ms_top;
    if(first > MS_SIZE - MAX_MOVES) return stand;
    last = generate_moves(1);
    score_moves(first, last, NO_SQ, NO_SQ);
    for(i=first; i<last; i++) {
        pick_move(i, last);
        from = mv_from[i];
        to = mv_to[i];
        fl = mv_flags[i];
        // skip captures that cannot raise alpha, and losing captures
        if(!(fl & F_PROMO_MASK)) {
            if(stand + piece_value[TYPE(bd[to])] + 200 < alpha && !(fl & F_EP)) continue;
            att_sq = to;
            if(piece_value[TYPE(bd[to])] < piece_value[TYPE(bd[from])] &&
               square_attacked(stm ^ BLACK_SIDE)) continue;
        }
        if(!MAKE(from, to, fl)) {
            unmake_move();
            continue;
        }
        score = -quiesce(-beta, -alpha);
        unmake_move();
        if(aborted) break;
        if(score > alpha) {
            if(score >= beta) {
                ms_top = first;
                return score;
            }
            alpha = score;
        }
    }
    ms_top = first;
    return alpha;
}

/**
 * @brief Principal variation search to the given depth
 *
 * Mirrored instruction by instruction in engine_asm.s (search_node); keep
 * both in step.
 */
static int16_t search(int8_t depth, int16_t alpha, int16_t beta, uint8_t allow_null) {
    int16_t score, best, ev;
    uint16_t first, last, i;
    uint8_t from, to, fl, check, legal, bound, futile;
    uint8_t best_from = NO_SQ, best_to = NO_SQ, best_flags = 0;
    uint8_t hfrom = NO_SQ, hto = NO_SQ, hpromo = 0, hfl, stage, quiet_count = 0;
    int8_t reduction;
    tt_entry_t entry;
    int16_t alpha0 = alpha;

    if(sply && (is_repetition() || fifty >= 100 || insufficient_material())) return 0;

    check = in_check();
    if(check && sply < MAX_PLY / 2) depth++;    // check extension
    if(depth <= 0) return quiesce(alpha, beta);

    nodes++;
    check_limits();
    if(aborted) return 0;
    if(sply >= MAX_PLY - 1) return evaluate();

    // transposition table: cutoff or at least a move to try first
    if(tt_probe(&entry)) {
        hfrom = entry.from;
        hto = entry.to;
        hpromo = entry.bound_promo & F_PROMO_MASK;
        if(entry.depth >= depth && sply) {
            bound = entry.bound_promo >> 4;
            if(bound == TT_EXACT ||
               (bound == TT_LOWER && entry.score >= beta) ||
               (bound == TT_UPPER && entry.score <= alpha)) {
                return entry.score;
            }
        }
    }

    futile = 0;
    if(!check) {
        ev = evaluate();
        // reverse futility: far above beta close to the horizon
        if(depth <= 2 && sply && beta > -ENGINE_MATE + 512 && beta < ENGINE_MATE - 512 &&
           ev - (depth == 1 ? 120 : 240) >= beta) return ev;
        // null move: if passing still fails high, this position is too good
        if(allow_null && depth >= 3 && beta < ENGINE_MATE - 512 && has_pieces(stm) && ev >= beta) {
            make_null();
            score = -search(depth - 3, -beta, -beta + 1, 0);
            unmake_null();
            if(aborted) return 0;
            if(score >= beta) return beta;
        }
        // futility: quiet moves cannot lift a hopeless node near the horizon
        if(depth == 1 && ev + 150 <= alpha) futile = 1;
        if(depth == 2 && ev + 300 <= alpha) futile = 1;
        if(depth == 3 && ev + 500 <= alpha) futile = 1;
    }

    first = ms_top;
    if(first > MS_SIZE - MAX_MOVES) return evaluate();

    // the hash move is tried before the other moves are even generated
    hfl = 0xFF;
    if(hfrom != NO_SQ) {
        mk_from = hfrom;
        mk_to = hto;
        mk_flags = hpromo;
        hfl = validate_move();
    }
    stage = (hfl != 0xFF) ? 0 : 1;
    i = last = first;

    best = -ENGINE_MATE;
    legal = 0;
    for(;;) {
        if(stage == 0) {
            from = hfrom;
            to = hto;
            fl = hfl;
            stage = 1;
        } else {
            if(stage == 1) {
                last = generate_moves(0);
                score_moves(first, last, NO_SQ, NO_SQ);
                i = first;
                stage = 2;
            }
            if(i >= last) break;
            pick_move(i, last);
            from = mv_from[i];
            to = mv_to[i];
            fl = mv_flags[i];
            i++;
            if(from == hfrom && to == hto && fl == hfl) continue;   // done already
        }
        if(!MAKE(from, to, fl)) {
            unmake_move();
            continue;
        }
        legal++;
        if(futile && legal > 1 && !(fl & (F_CAPTURE | F_PROMO_MASK)) && !in_check()) {
            unmake_move();
            continue;
        }
        // late move pruning: near the horizon only the first quiet moves
        if(depth <= 2 && !check && legal > (depth == 1 ? 8 : 14) &&
           !(fl & (F_CAPTURE | F_PROMO_MASK)) && !in_check()) {
            unmake_move();
            continue;
        }

        if(legal == 1) {
            score = -search(depth - 1, -beta, -alpha, 1);
        } else {
            // late quiet moves are searched one ply shallower first
            reduction = 0;
            if(depth >= 3 && !check && !(fl & (F_CAPTURE | F_PROMO_MASK))) {
                quiet_count++;
                if(quiet_count > 3 && !in_check()) reduction = 1;
            }
            score = -search(depth - 1 - reduction, -alpha - 1, -alpha, 1);
            if(score > alpha && (reduction || score < beta)) {
                score = -search(depth - 1, -beta, -alpha, 1);
            }
        }
        unmake_move();
        if(aborted) {
            ms_top = first;
            return 0;
        }

        if(score > best) {
            best = score;
            best_from = from;
            best_to = to;
            best_flags = fl;
            if(score > alpha) {
                alpha = score;
                if(score >= beta) {
                    if(!(fl & (F_CAPTURE | F_PROMO_MASK))) remember_quiet(from, to, depth);
                    break;
                }
            }
        }
    }
    ms_top = first;

    if(legal == 0) {
        return check ? -ENGINE_MATE + sply : 0;
    }

    bound = best >= beta ? TT_LOWER : (best > alpha0 ? TT_EXACT : TT_UPPER);
    tt_store(depth, best, bound, best_from, best_to, best_flags);
    return best;
}
#endif

/**
 * @brief Collect the principal variation by following the hash moves
 */
static void collect_pv(engine_result_t* result) {
    uint8_t n = 0, i, fl;
    tt_entry_t entry;

    memset(result->pv, 0, sizeof(result->pv));
    while(n < 16 && tt_probe(&entry)) {
        fl = find_move_flags(entry.from, entry.to, entry.bound_promo & F_PROMO_MASK);
        if(fl == 0xFF) break;
        result->pv[2 * n] = entry.from;
        result->pv[2 * n + 1] = entry.to;
        n++;
        if(!MAKE(entry.from, entry.to, fl) || is_repetition()) {
            unmake_move();
            n--;
            break;
        }
    }
    for(i=0; i<n; i++) unmake_move();
}

/**
 * @brief Find the best move; stops at max_depth, time (jiffies) or nodes
 */
void engine_search(uint8_t max_depth, uint16_t time_lim, uint32_t node_lim,
                   engine_result_t* result) {
    uint8_t depth, i, j, best_index, root_recorded;
    int16_t alpha, beta, score, best_score, noisy_best, noisy_score;
    uint16_t first, last;
    ENTER_ENGINE;

    node_limit = node_lim;
    time_limit = time_lim;
    time_start = now();
    aborted = 0;
    nodes = 0;
    sply = 0;
    ms_top = 0;
    memset(killer_from, NO_SQ, sizeof(killer_from));
    memset(killer_to, NO_SQ, sizeof(killer_to));
    if(max_depth == 0 || max_depth > MAX_PLY - 8) max_depth = MAX_PLY - 8;

    memset(result, 0, sizeof(*result));
    root_recorded = history_drop_root();

    // legal root moves
    root_count = 0;
    last = generate_moves(0);
    for(first=0; first<last; first++) {
        if(MAKE(mv_from[first], mv_to[first], mv_flags[first])) {
            root_from[root_count] = mv_from[first];
            root_to[root_count] = mv_to[first];
            root_flags[root_count] = mv_flags[first];
            root_count++;
        }
        unmake_move();
    }
    ms_top = 0;
    if(root_count == 0) {
        result->score = in_check() ? -ENGINE_MATE : 0;
        if(root_recorded) history_restore_root();
        LEAVE_ENGINE;
        return;
    }
    // initial order: captures by MVV-LVA first
    for(i=0; i<root_count; i++) {
        mv_from[i] = root_from[i];
        mv_to[i] = root_to[i];
        mv_flags[i] = root_flags[i];
    }
    score_moves(0, root_count, NO_SQ, NO_SQ);
    for(i=0; i<root_count; i++) {
        pick_move(i, root_count);
        root_from[i] = mv_from[i];
        root_to[i] = mv_to[i];
        root_flags[i] = mv_flags[i];
    }
    result->from = root_from[0];
    result->to = root_to[0];
    result->promo = root_flags[0] & F_PROMO_MASK;

    for(depth=1; depth<=max_depth; depth++) {
        alpha = -ENGINE_MATE - 1;
        beta = ENGINE_MATE + 1;
        best_score = -ENGINE_MATE - 1;
        noisy_best = -ENGINE_MATE - 1;
        best_index = 0;
        for(i=0; i<root_count; i++) {
            MAKE(root_from[i], root_to[i], root_flags[i]);
            if(weakness) {
                score = -SEARCH(depth - 1, -ENGINE_MATE - 1, ENGINE_MATE + 1, 1);
            } else if(i == 0) {
                score = -SEARCH(depth - 1, -beta, -alpha, 1);
            } else {
                score = -SEARCH(depth - 1, -alpha - 1, -alpha, 1);
                if(score > alpha && !aborted) score = -SEARCH(depth - 1, -beta, -alpha, 1);
            }
            unmake_move();
            if(aborted) break;
            if(weakness) {
                /* Full-window scores above avoid ranking PVS bounds as if
                 * they were exact. Noise changes selection, never legality. */
                noisy_score = score + move_noise();
                if(noisy_score > noisy_best) {
                    noisy_best = noisy_score;
                    result->from = root_from[i];
                    result->to = root_to[i];
                    result->promo = root_flags[i] & F_PROMO_MASK;
                    result->score = score;
                }
            }
            if(score > best_score) {
                best_score = score;
                best_index = i;
                if(score > alpha) alpha = score;
                // a fully searched improvement is safe to play even if the
                // iteration does not finish
                if(!weakness) {
                    result->from = root_from[i];
                    result->to = root_to[i];
                    result->promo = root_flags[i] & F_PROMO_MASK;
                    result->score = score;
                }
            }
        }
        if(aborted && best_index == 0) break;

        // move the best root move to the front, keep the others in order
        if(best_index) {
            uint8_t f = root_from[best_index], to = root_to[best_index], fl = root_flags[best_index];
            for(j=best_index; j>0; j--) {
                root_from[j] = root_from[j - 1];
                root_to[j] = root_to[j - 1];
                root_flags[j] = root_flags[j - 1];
            }
            root_from[0] = f;
            root_to[0] = to;
            root_flags[0] = fl;
        }
        if(aborted) break;
        result->depth = depth;
        if(!weakness) result->score = best_score;
        tt_store(depth, best_score, TT_EXACT, root_from[0], root_to[0], root_flags[0]);
        // a forced mate has been found: deeper search cannot improve it
        if(best_score > ENGINE_MATE - 512 || best_score < -ENGINE_MATE + 512) {
            if(depth >= 2) break;
        }
        if(root_count == 1 && depth >= 4) break;
    }
    result->nodes = nodes;
    result->time = now() - time_start;
    collect_pv(result);
    if(weakness) {
        memset(result->pv, 0, sizeof(result->pv));
        result->pv[0] = result->from;
        result->pv[1] = result->to;
    }
    if(root_recorded) history_restore_root();
    LEAVE_ENGINE;
}

/**
 * @brief Forget everything learned (transposition table, game history)
 */
void engine_new_game(void) {
    ENTER_ENGINE;
    tt_clear();
    memset(HISTORY, 0, 16 * 64);
    pawn_cache_clear();
    history_clear();
    LEAVE_ENGINE;
}

void engine_clear_history(void) {
    ENTER_ENGINE;
    history_clear();
    LEAVE_ENGINE;
}

/**
 * @brief Prepare tables; call once
 */
void engine_init(void) {
    ENTER_ENGINE;
    board_init();
    LEAVE_ENGINE;
    engine_new_game();
}
