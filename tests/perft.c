/*
 * Host-side move generator test: perft node counts and SAN output of the
 * cc65 rules code, compiled with the native C compiler.
 */
#include <stdio.h>
#include <string.h>

#include "../src/core/rules.h"

static unsigned long perft(int depth) {
    move_t moves[MAX_MOVES];
    unsigned long nodes = 0;
    int i, n;

    n = rules_generate_legal();
    if(depth == 1) return n;
    memcpy(moves, legal_moves, n * sizeof(move_t));
    for(i=0; i<n; i++) {
        rules_make(&moves[i]);
        nodes += perft(depth - 1);
        rules_unmake();
    }
    return nodes;
}

static int failures;

static void check_perft(const char* fen, int depth, unsigned long expected) {
    unsigned long got;

    if(!rules_load_fen(fen)) {
        printf("FAIL bad fen %s\n", fen);
        failures++;
        return;
    }
    got = perft(depth);
    printf("%s perft(%d) = %lu (expected %lu) %s\n", got == expected ? "ok  " : "FAIL",
           depth, got, expected, fen);
    if(got != expected) failures++;
}

static void check_san(const char* fen, const char* expected_list) {
    char buf[8], all[2048] = "";
    move_t moves[MAX_MOVES], m;
    int i, n;

    rules_load_fen(fen);
    n = rules_generate_legal();
    memcpy(moves, legal_moves, n * sizeof(move_t));
    for(i=0; i<n; i++) {
        rules_generate_legal();         /* rules_san overwrites legal_moves */
        m = moves[i];
        rules_san(&m, buf);
        strcat(all, buf);
        strcat(all, " ");
    }
    for(i=0; expected_list[i]; ) {
        char token[16];
        int n = 0;
        while(expected_list[i] == ' ') i++;
        while(expected_list[i] && expected_list[i] != ' ') token[n++] = expected_list[i++];
        token[n] = ' ';
        token[n + 1] = 0;
        if(n && !strstr(all, token)) {
            printf("FAIL san '%s' missing in: %s\n", token, all);
            failures++;
        }
    }
}

static void divide(const char* fen, int depth) {
    move_t moves[MAX_MOVES];
    int i, n;

    rules_load_fen(fen);
    n = rules_generate_legal();
    memcpy(moves, legal_moves, n * sizeof(move_t));
    for(i=0; i<n; i++) {
        rules_make(&moves[i]);
        printf("%c%c%c%c %lu\n", 'a' + FILE_OF(moves[i].from), '1' + RANK_OF(moves[i].from),
               'a' + FILE_OF(moves[i].to), '1' + RANK_OF(moves[i].to),
               depth > 1 ? perft(depth - 1) : 1UL);
        rules_unmake();
    }
}

int main(int argc, char** argv) {
    const char* start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    const char* kiwipete = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";

    if(argc == 3) {     /* perft divide for debugging: ./perft FEN DEPTH */
        divide(argv[1], argv[2][0] - '0');
        return 0;
    }

    check_perft(start, 1, 20);
    check_perft(start, 2, 400);
    check_perft(start, 3, 8902);
    check_perft(start, 4, 197281);
    check_perft(kiwipete, 1, 48);
    check_perft(kiwipete, 2, 2039);
    check_perft(kiwipete, 3, 97862);
    check_perft("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 4, 43238);
    check_perft("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", 3, 9467);
    check_perft("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", 3, 62379);
    check_perft("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", 3, 89890);

    /* SAN: disambiguation, castling, promotion, en passant, check and mate */
    check_san("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "O-O O-O-O Rb1 Rxa8+ Rxh8+ Kd1");
    check_san("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1", "O-O O-O-O Rh8+ Ra8+ Rf1 Rd1");
    check_san("4k3/8/8/8/8/8/8/R4RK1 w - - 0 1", "Rae1+ Rfe1+ Rab1 Rfb1");
    check_san("4k3/8/8/1N3N2/8/1N6/8/4K3 w - - 0 1", "N3d4 Nb5d4 Nfd4 Nbd6+ Nfd6+");
    check_san("7k/P7/8/8/8/8/8/K7 w - - 0 1", "a8=Q+ a8=R+ a8=B a8=N");
    check_san("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "exd6 e6");
    check_san("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "Ra8#");

    printf(failures ? "%d FAILURES\n" : "all tests passed\n", failures);
    return failures != 0;
}
