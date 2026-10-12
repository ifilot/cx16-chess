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

#ifndef _BRIDGE_H
#define _BRIDGE_H

#include <stdint.h>

/*
 * Mailbox for driving the engine from outside the machine (the AgentBridge
 * emulator writes and reads it directly). It lives in the free RAM at $0400,
 * below the program. tools/engine_bridge.py mirrors this layout.
 *
 * Protocol: write the FEN and parameters, then the command byte. The bridge
 * sets status to BUSY, clears the command, runs it and sets status to DONE
 * (or ERROR).
 */
#define BRIDGE_ADDR     0x0400

#define CMD_NONE        0
#define CMD_PERFT       1       // perft(depth) of the FEN position
#define CMD_SEARCH      2       // best move within depth / time limits
#define CMD_EVAL        3       // static evaluation of the FEN position
#define CMD_LIST        4       // legal moves: count at $0500, from/to pairs after it
#define CMD_RULES_PERFT 6       // perft(depth) with rules.c (tests the game's move rules)
#define CMD_VALIDATE    5       // flags of move $0500-$0501 (promo $0502) -> $0503

#define LIST_ADDR       0x0500
#define DEBUG_ADDR      0x0700  // engine board snapshot when 'illegal' is set
#define MOVES_ADDR      0x0600  // CMD_SEARCH: count, then from/to/promo triples played
                                // after the FEN position (for repetitions)

#define BRIDGE_FRESH    0x01    // flags: start a new game (clear TT, set weakness)

// status
#define STATUS_BOOT     0       // ENGINE.PRG has not started yet
#define STATUS_READY    1       // waiting for the first command
#define STATUS_BUSY     2       // running a command
#define STATUS_DONE     3       // results are in the mailbox
#define STATUS_ERROR    4       // malformed FEN or unknown command

typedef struct {
    uint8_t cmd;                // $0400
    uint8_t status;             // $0401
    uint8_t depth;              // $0402 maximum depth (search) or perft depth
    uint8_t flags;              // $0403 BRIDGE_FRESH: forget the TT first
    uint16_t time_limit;        // $0404 jiffies (1/60 s), 0 = no limit
    uint8_t replayed;           // $0406 CMD_SEARCH: history moves replayed
    uint8_t illegal;            // $0407 CMD_SEARCH: best move not legal (debug)
    uint32_t nodes;             // $0408 nodes visited
    uint8_t best_from;          // $040C 0x88 squares of the best move
    uint8_t best_to;            // $040D
    uint8_t best_promo;         // $040E piece type or 0
    uint8_t depth_done;         // $040F last completed iteration
    int16_t score;              // $0410 centipawns, side to move's view
    uint16_t jiffies;           // $0412 time used
    uint16_t noise;             // $0414 root move noise, centipawns
    uint16_t seed;              // $0416 reset random sequence on BRIDGE_FRESH
    uint8_t reserved2[8];       // $0418
    uint8_t pv[32];             // $0420 principal variation, from/to pairs
    uint8_t reserved3[64];      // $0440
    char fen[128];              // $0480 input position
} bridge_t;

#define BRIDGE (*(volatile bridge_t*)BRIDGE_ADDR)

#endif // _BRIDGE_H
