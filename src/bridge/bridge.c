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
 * Headless engine harness (ENGINE.PRG): runs commands posted in the mailbox
 * described in bridge.h. Contains no graphics code at all.
 */

#include <ascii_charmap.h>
#include <string.h>

#include "rules.h"
#include "engine.h"
#include "bridge.h"

static uint32_t rules_perft(uint8_t depth) {
    static move_t lists[5][MAX_MOVES];
    move_t* moves = lists[depth];
    uint32_t nodes = 0;
    uint8_t i, n;

    n = rules_generate_legal();
    if(depth == 1) return n;
    memcpy(moves, legal_moves, n * sizeof(move_t));
    for(i=0; i<n; i++) {
        rules_make(&moves[i]);
        nodes += rules_perft(depth - 1);
        rules_unmake();
    }
    return nodes;
}

/**
 * @brief Play the moves listed at MOVES_ADDR, recording every position
 */
static void replay_moves(void) {
    const uint8_t* p = (const uint8_t*)MOVES_ADDR;
    uint8_t n = *p++, i, k;

    engine_record_position();
    for(i=0; i<n; i++, p+=3) {
        rules_generate_legal();
        for(k=0; k<legal_count; k++) {
            if(legal_moves[k].from == p[0] && legal_moves[k].to == p[1] &&
               legal_moves[k].promo == p[2]) {
                break;
            }
        }
        if(k == legal_count) break;
        rules_make(&legal_moves[k]);
        rules_commit();
        engine_set_position(board, side, castling, ep_square, halfmove_clock);
        engine_record_position();
    }
    BRIDGE.replayed = i;
}

void main(void) {
    static engine_result_t result;
    char fen[128];
    uint8_t cmd, k;

    engine_init();
    BRIDGE.status = STATUS_READY;
    while(1) {
        cmd = BRIDGE.cmd;
        if(cmd == CMD_NONE) continue;
        BRIDGE.status = STATUS_BUSY;
        BRIDGE.cmd = CMD_NONE;

        // rules.c parses the FEN; the engine takes the board from there
        memcpy(fen, (const char*)BRIDGE.fen, sizeof(fen));
        fen[sizeof(fen) - 1] = 0;
        if(!rules_load_fen(fen)) {
            BRIDGE.status = STATUS_ERROR;
            continue;
        }
        if(BRIDGE.flags & BRIDGE_FRESH) engine_new_game();
        engine_clear_history();
        engine_set_position(board, side, castling, ep_square, halfmove_clock);
        if(cmd == CMD_SEARCH) replay_moves();
        switch(cmd) {
            case CMD_PERFT:
                BRIDGE.nodes = engine_perft(BRIDGE.depth);
                BRIDGE.score = engine_perft_hash;
                break;
            case CMD_SEARCH:
                engine_search(BRIDGE.depth, BRIDGE.time_limit, 0, &result);
                BRIDGE.nodes = result.nodes;
                BRIDGE.best_from = result.from;
                BRIDGE.best_to = result.to;
                BRIDGE.best_promo = result.promo;
                BRIDGE.depth_done = result.depth;
                BRIDGE.score = result.score;
                BRIDGE.jiffies = result.time;
                memcpy((void*)BRIDGE.pv, result.pv, sizeof(result.pv));
                // cross-check: the move must be legal according to rules.c
                rules_generate_legal();
                BRIDGE.illegal = 1;
                for(k=0; k<legal_count; k++) {
                    if(legal_moves[k].from == result.from && legal_moves[k].to == result.to) BRIDGE.illegal = 0;
                }
                if(BRIDGE.illegal || legal_count == 0) {
                    engine_debug_board((uint8_t*)DEBUG_ADDR);
                    memcpy((uint8_t*)DEBUG_ADDR + 128, board, 128);
                }
                break;
            case CMD_LIST:
                *(uint8_t*)LIST_ADDR = engine_legal_moves((uint8_t*)LIST_ADDR + 1);
                break;
            case CMD_RULES_PERFT:
                BRIDGE.nodes = (BRIDGE.depth >= 1 && BRIDGE.depth <= 4) ? rules_perft(BRIDGE.depth) : 0;
                break;
            case CMD_VALIDATE:
                ((uint8_t*)LIST_ADDR)[3] = engine_validate(((uint8_t*)LIST_ADDR)[0],
                    ((uint8_t*)LIST_ADDR)[1], ((uint8_t*)LIST_ADDR)[2]);
                break;
            case CMD_EVAL:
                BRIDGE.score = engine_evaluate();
                break;
            default:
                BRIDGE.status = STATUS_ERROR;
                continue;
        }
        BRIDGE.status = STATUS_DONE;
    }
}
