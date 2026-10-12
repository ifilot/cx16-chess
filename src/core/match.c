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
#include <ascii_charmap.h>
/* The game controller is nonrecursive; the engine has its own stacks. */
#pragma static-locals (on)
#endif
#include <string.h>
#include <time.h>

#include "rules.h"
#include "engine.h"
#include "match.h"

/*
 * The game controller: plays moves through rules.c, keeps the SAN and
 * coordinate lists of the game, runs the clocks, detects the end of the
 * game and asks the engine for moves. See match.h.
 */

uint8_t match_state;
uint8_t match_result;
uint8_t match_computer;
uint8_t match_difficulty = DEFAULT_DIFFICULTY;
uint8_t match_black_difficulty = DEFAULT_DIFFICULTY;
uint8_t match_think_depth;
uint16_t match_clock[2];
uint16_t match_think_start, match_think_budget;
uint8_t match_last_from;
uint8_t match_last_to;
uint8_t match_last_flags;
uint8_t match_eval_valid;
int16_t match_eval;
char match_best[8];

#define ANALYSIS_TIME   (10 * 60)       // jiffies

static uint8_t jiffy_count;             // jiffies towards the next clock second

/*
 * The SAN of every half move, 8 bytes each. On the X16 the list lives in
 * RAM bank MATCH_BANK (the engine uses banks 1-18).
 */
#define SAN_SIZE        8
#ifdef __CC65__
#define RAM_BANK        (*(volatile uint8_t*)0x00)
#define MATCH_BANK      19
#define SAN_LIST        ((char*)0xA000)
#else
static char SAN_LIST[MAX_HISTORY * SAN_SIZE];
#endif

/* Coordinate history is separate from SAN so disk saves can replay all rules
 * and rebuild the engine's repetition history. Bank 24 is not engine scratch. */
#ifdef __CC65__
#define MOVE_LIST ((uint8_t*)0xA000)
#else
static uint8_t MOVE_LIST[MAX_HISTORY * 3];
#endif

/**
 * @brief Copy from, to and promotion of a played half move (0 = white's
 *        first); the flags of move are left untouched
 */
void match_move_at(uint16_t index, move_t* move) {
    uint8_t from, to, promo;
#ifdef __CC65__
    uint8_t saved = RAM_BANK;
    RAM_BANK = 24;
#endif
    index *= 3;
    from = MOVE_LIST[index];
    to = MOVE_LIST[index + 1];
    promo = MOVE_LIST[index + 2];
#ifdef __CC65__
    RAM_BANK = saved;
#endif
    move->from = from;
    move->to = to;
    move->promo = promo;
}

/**
 * @brief Store from, to and promotion of the move about to be played
 */
static void record_move(const move_t* move) {
    uint16_t index = ply * 3;
    uint8_t from = move->from, to = move->to, promo = move->promo;
#ifdef __CC65__
    uint8_t saved = RAM_BANK;
    RAM_BANK = 24;
#endif
    MOVE_LIST[index] = from;
    MOVE_LIST[index + 1] = to;
    MOVE_LIST[index + 2] = promo;
#ifdef __CC65__
    RAM_BANK = saved;
#endif
}

/**
 * @brief Jiffies (0..59) counted towards the next clock second, for saves
 */
uint8_t match_clock_fraction(void) { return jiffy_count; }

/**
 * @brief Restore the jiffies counted towards the next clock second
 */
void match_restore_fraction(uint8_t value) { jiffy_count = value; }

/**
 * @brief Store the SAN of a half move in the banked SAN list
 */
static void san_store(uint16_t half_move, const char* san) {
#ifdef __CC65__
    uint8_t saved = RAM_BANK;
    RAM_BANK = MATCH_BANK;
#endif
    memcpy(SAN_LIST + half_move * SAN_SIZE, san, SAN_SIZE);
#ifdef __CC65__
    RAM_BANK = saved;
#endif
}

/**
 * @brief Copy the SAN of a played half move (0 = white's first) into buf
 */
void match_san(uint16_t half_move, char* buf) {
#ifdef __CC65__
    uint8_t saved = RAM_BANK;
    RAM_BANK = MATCH_BANK;
#endif
    memcpy(buf, SAN_LIST + half_move * SAN_SIZE, SAN_SIZE);
#ifdef __CC65__
    RAM_BANK = saved;
#endif
}

/**
 * @brief Hand the current position to the engine and record it
 */
static void engine_sync(void) {
    engine_set_position(board, side, castling, ep_square, halfmove_clock);
    engine_record_position();
}

/**
 * @brief Prepare the legal moves of the new position and detect the end
 */
static void check_end(void) {
    rules_generate_legal();
    if(legal_count == 0) {
        if(rules_in_check()) {
            match_result = (side == WHITE) ? RESULT_BLACK_MATES : RESULT_WHITE_MATES;
        } else {
            match_result = RESULT_STALEMATE;
        }
    } else if(halfmove_clock >= 100) {
        match_result = RESULT_FIFTY_MOVES;
    } else if(rules_insufficient_material()) {
        match_result = RESULT_MATERIAL;
    } else if(engine_repetitions() >= 3) {
        match_result = RESULT_REPETITION;
    } else if(ply >= MAX_HISTORY - 1) {
        match_result = RESULT_LENGTH;
    }
    if(match_result != RESULT_NONE) match_state = MATCH_OVER;
}

/**
 * @brief Prepare the engine; call once at start-up
 */
void match_init(void) {
    engine_init();
}

/**
 * @brief Start a new game from the initial position
 *
 * Seeds the engine's weakening noise from the clock, so weak levels play
 * differently in every game.
 *
 * @param seconds  time per player
 * @param computer COMPUTER_* bits
 */
void match_new(uint16_t seconds, uint8_t computer) {
    rules_new_game();
    engine_new_game();
    engine_set_weakness(0, (uint16_t)clock() | 1);
    engine_sync();
    rules_generate_legal();
    match_state = MATCH_PLAYING;
    match_result = RESULT_NONE;
    match_computer = computer;
    match_clock[0] = match_clock[1] = seconds;
    match_last_from = match_last_to = NO_SQUARE;
    match_last_flags = 0;
    match_eval_valid = 0;
    match_best[0] = 0;
    jiffy_count = 0;
}

/**
 * @brief Play a legal move (an entry of legal_moves) and record it
 *
 * Ignored once the game is over.
 */
void match_play(const move_t* m) {
    move_t mv;
    char san[SAN_SIZE];

    if(match_state != MATCH_PLAYING) return;
    mv = *m;
    rules_san(&mv, san);
    san_store(ply, san);
    record_move(&mv);
    rules_make(&mv);
    rules_commit();
    match_best[0] = 0;
    match_last_from = mv.from;
    match_last_to = mv.to;
    match_last_flags = mv.flags;
    engine_sync();
    check_end();
}

/**
 * @brief Find the legal move from-to (promo: piece type, or EMPTY for the
 *        first matching one); NULL if there is none
 */
const move_t* match_find_move(uint8_t from, uint8_t to, uint8_t promo) {
    uint8_t i;

    for(i=0; i<legal_count; i++) {
        if(legal_moves[i].from == from && legal_moves[i].to == to &&
           (promo == EMPTY || legal_moves[i].promo == promo)) {
            return &legal_moves[i];
        }
    }
    return 0;
}

/**
 * @brief Run the clock of the side to move
 *
 * A flag fall without mating material for the opponent is a draw.
 *
 * @return 1 when a displayed second changed or the game ended
 */
uint8_t match_tick(uint8_t jiffies) {
    uint8_t idx, changed = 0;

    if(match_state != MATCH_PLAYING) return 0;
    jiffy_count += jiffies;
    while(jiffy_count >= 60) {
        jiffy_count -= 60;
        idx = side >> 3;
        if(match_clock[idx] == 0) continue;
        changed = 1;
        if(--match_clock[idx] == 0) {
            if(rules_insufficient_material()) {
                match_result = RESULT_TIME_MATERIAL;
            } else {
                match_result = (side == WHITE) ? RESULT_BLACK_ON_TIME : RESULT_WHITE_ON_TIME;
            }
            match_state = MATCH_OVER;
        }
    }
    return changed;
}

/**
 * @brief Is the engine to move?
 */
uint8_t match_computer_to_move(void) {
    return match_state == MATCH_PLAYING &&
           (match_computer & ((side == WHITE) ? COMPUTER_WHITE : COMPUTER_BLACK));
}

/**
 * @brief Requested search depth, independently selectable for each CPU.
 */
static uint8_t cpu_difficulty(void) {
    return match_computer == COMPUTER_BOTH && side == BLACK ? match_black_difficulty : match_difficulty;
}

static engine_result_t result;          // result of the last search

/**
 * @brief Search the current position; keeps the evaluation (white's view)
 *
 * @param poll    Called regularly while the engine thinks
 * @param depth   Maximum depth, 0 for no limit
 * @param jiffies Time limit, 0 for no limit
 */
static void think(void (*poll)(void), uint8_t depth, uint16_t jiffies) {
    match_think_start = (uint16_t)clock();
    match_think_budget = jiffies;
    match_think_depth = depth;
    engine_poll = poll;
    engine_search(depth, jiffies, 0, &result);
    engine_poll = 0;
    match_eval = (side == WHITE) ? result.score : -result.score;
    match_eval_valid = 1;
}

/**
 * @brief Let the engine analyse the position for the side to move: sets
 *        match_best and match_eval
 *
 * Analysis searches at full strength for ANALYSIS_TIME.
 */
void match_analyse(void (*poll)(void)) {
    const move_t* m;
    move_t mv;

    if(match_state != MATCH_PLAYING) return;
    engine_set_weakness(0, 0);
    think(poll, 0, ANALYSIS_TIME);
    m = match_find_move(result.from, result.to, result.promo ? result.promo : EMPTY);
    if(m) {
        mv = *m;
        rules_san(&mv, match_best);             // overwrites legal_moves
        rules_generate_legal();
    }
}

/**
 * @brief Let the engine choose and play a move at the current difficulty
 *
 * Maps DIFFICULTY_* to a search depth and root noise. Plays the first
 * legal move if the search returned none (e.g. when it was aborted).
 */
void match_computer_move(void (*poll)(void)) {
    const move_t* m;
    uint8_t difficulty = cpu_difficulty();

    engine_set_weakness(difficulty == DIFFICULTY_BEGINNER ? BEGINNER_NOISE :
                       difficulty == DIFFICULTY_EASY ? EASY_NOISE : 0, 0);
    think(poll, difficulty >= DIFFICULTY_SEVEN_PLY ? difficulty - 1 :
          difficulty < DIFFICULTY_ONE_PLY ? difficulty + 2 : 1, 0);
    m = match_find_move(result.from, result.to, result.promo ? result.promo : EMPTY);
    if(!m && legal_count) m = &legal_moves[0];  // never stall the game
    if(m) match_play(m);
}
