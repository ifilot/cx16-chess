/*
 * Native UCI front end for the CX16-CHESS engine, for testing it against
 * other engines on the host. The engine code is the same that runs on the
 * X16; "setoption name NPS value N" converts time controls into node limits
 * so the engine plays as it would on the real machine.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/core/rules.h"
#include "../src/core/engine.h"

static unsigned long nps = 0;       /* 0: ignore time, use depth/nodes only */
static uint16_t noise, seed = 1;

static void sync_engine(void) {
    engine_set_position(board, side, castling, ep_square, halfmove_clock);
}

static int apply_uci_move(const char* s) {
    int i;
    uint8_t from = SQ(s[0] - 'a', s[1] - '1'), to = SQ(s[2] - 'a', s[3] - '1');
    uint8_t promo = 0;

    if(s[4] == 'q') promo = QUEEN;
    if(s[4] == 'r') promo = ROOK;
    if(s[4] == 'b') promo = BISHOP;
    if(s[4] == 'n') promo = KNIGHT;
    rules_generate_legal();
    for(i=0; i<legal_count; i++) {
        if(legal_moves[i].from == from && legal_moves[i].to == to &&
           (legal_moves[i].promo == promo || !(legal_moves[i].flags & MF_PROMOTION))) {
            rules_make(&legal_moves[i]);
            rules_commit();
            return 1;
        }
    }
    return 0;
}

static void print_move(uint8_t from, uint8_t to, uint8_t promo) {
    printf("%c%c%c%c%s", 'a' + FILE_OF(from), '1' + RANK_OF(from), 'a' + FILE_OF(to),
           '1' + RANK_OF(to), promo ? (promo == QUEEN ? "q" : promo == ROOK ? "r" :
           promo == BISHOP ? "b" : "n") : "");
}

static void position(char* args) {
    char* moves = strstr(args, "moves");
    char* tok;

    if(moves) *moves = 0;
    if(strncmp(args, "startpos", 8) == 0) rules_new_game();
    else if(strncmp(args, "fen", 3) == 0) rules_load_fen(args + 4);
    sync_engine();
    engine_record_position();
    if(moves) {
        for(tok = strtok(moves + 5, " \n"); tok; tok = strtok(NULL, " \n")) {
            if(!apply_uci_move(tok)) break;
            sync_engine();
            engine_record_position();
        }
    }
}

static void go(char* args) {
    engine_result_t r;
    unsigned depth = 0;
    unsigned long nodes = 0, movetime = 0, wtime = 0, btime = 0, winc = 0, binc = 0;
    char* p;
    int i;

    if((p = strstr(args, "depth"))) depth = atoi(p + 6);
    if((p = strstr(args, "nodes"))) nodes = atol(p + 6);
    if((p = strstr(args, "movetime"))) movetime = atol(p + 9);
    if((p = strstr(args, "wtime"))) wtime = atol(p + 6);
    if((p = strstr(args, "btime"))) btime = atol(p + 6);
    if((p = strstr(args, "winc"))) winc = atol(p + 5);
    if((p = strstr(args, "binc"))) binc = atol(p + 5);
    if(nps && !nodes) {
        if(!movetime && (wtime || btime)) {
            unsigned long t = side ? btime : wtime, inc = side ? binc : winc;
            movetime = t / 30 + inc;
        }
        if(movetime) nodes = nps * movetime / 1000;
    }
    sync_engine();
    engine_search(depth, 0, nodes, &r);
    printf("info depth %u score cp %d nodes %lu pv", r.depth, r.score, (unsigned long)r.nodes);
    for(i=0; i<16 && (r.pv[2*i] != r.pv[2*i+1]); i++) {
        putchar(' ');
        print_move(r.pv[2*i], r.pv[2*i+1], 0);
    }
    printf("\nbestmove ");
    if(r.from == r.to) printf("0000");
    else print_move(r.from, r.to, r.promo);
    printf("\n");
    fflush(stdout);
}

int main(void) {
    char line[8192];

    engine_init();
    rules_new_game();
    while(fgets(line, sizeof(line), stdin)) {
        if(strncmp(line, "uci", 3) == 0 && (line[3] == '\n' || line[3] == '\r')) {
            printf("id name CX16-CHESS\nid author Ivo Filot\n"
                   "option name NPS type spin default 0 min 0 max 100000000\n"
                   "option name Noise type spin default 0 min 0 max 2000\n"
                   "option name Seed type spin default 1 min 1 max 65535\nuciok\n");
        } else if(strncmp(line, "isready", 7) == 0) {
            printf("readyok\n");
        } else if(strncmp(line, "ucinewgame", 10) == 0) {
            engine_new_game();
        } else if(strncmp(line, "setoption name NPS value", 24) == 0) {
            nps = atol(line + 25);
        } else if(strncmp(line, "setoption name Noise value ", 26) == 0) {
            noise = atoi(line + 26);
            engine_set_weakness(noise, seed);
        } else if(strncmp(line, "setoption name Seed value ", 25) == 0) {
            seed = atoi(line + 25);
            engine_set_weakness(noise, seed);
        } else if(strncmp(line, "position", 8) == 0) {
            engine_clear_history();
            position(line + 9);
        } else if(strncmp(line, "go", 2) == 0) {
            go(line + 2);
        } else if(strncmp(line, "perft", 5) == 0) {
            sync_engine();
            printf("nodes %lu", (unsigned long)engine_perft(atoi(line + 6)));
            printf(" hash %d\n", (int16_t)engine_perft_hash);
        } else if(strncmp(line, "eval", 4) == 0) {
            sync_engine();
            printf("eval %d\n", engine_evaluate());
        } else if(strncmp(line, "quit", 4) == 0) {
            break;
        }
        fflush(stdout);
    }
    return 0;
}
