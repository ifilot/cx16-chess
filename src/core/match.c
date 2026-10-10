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
#pragma static-locals (on)
#endif
#include <string.h>

#include "rules.h"
#include "engine.h"
#include "match.h"

uint8_t match_state;
uint8_t match_result;
uint8_t match_computer;
uint16_t match_clock[2];
uint8_t match_last_from;
uint8_t match_last_to;

static uint8_t jiffy_count;

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

void match_init(void) {
    engine_init();
}

void match_new(uint16_t seconds, uint8_t computer) {
    rules_new_game();
    engine_new_game();
    engine_sync();
    rules_generate_legal();
    match_state = MATCH_PLAYING;
    match_result = RESULT_NONE;
    match_computer = computer;
    match_clock[0] = match_clock[1] = seconds;
    match_last_from = match_last_to = NO_SQUARE;
    jiffy_count = 0;
}

void match_play(const move_t* m) {
    move_t mv;
    char san[SAN_SIZE];

    if(match_state != MATCH_PLAYING) return;
    mv = *m;
    rules_san(&mv, san);
    san_store(ply, san);
    rules_make(&mv);
    rules_commit();
    match_last_from = mv.from;
    match_last_to = mv.to;
    engine_sync();
    check_end();
}

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

uint8_t match_computer_to_move(void) {
    return match_state == MATCH_PLAYING &&
           (match_computer & ((side == WHITE) ? COMPUTER_WHITE : COMPUTER_BLACK));
}

/**
 * @brief Thinking time for the engine: a 30th of the remaining time,
 *        between 2 and 20 seconds (in jiffies)
 */
static uint16_t think_time(void) {
    uint16_t secs = match_clock[side >> 3] / 30;

    if(secs < 2) secs = 2;
    if(secs > 20) secs = 20;
    return secs * 60;
}

void match_computer_move(void (*poll)(void)) {
    static engine_result_t result;
    const move_t* m;

    engine_poll = poll;
    engine_search(0, think_time(), 0, &result);
    engine_poll = 0;
    m = match_find_move(result.from, result.to, result.promo ? result.promo : EMPTY);
    if(!m && legal_count) m = &legal_moves[0];  // never stall the game
    if(m) match_play(m);
}
