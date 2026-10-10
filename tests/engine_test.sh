#!/bin/sh
# Engine move generator must match the rules module (perft) and find mates.
cd "$(dirname "$0")"
fail=0
check() {
    got=$(printf "position fen %s\n%s\nquit\n" "$1" "$2" | ./uci | grep "$3")
    case "$got" in *"$4"*) echo "ok   $2: $got";; *) echo "FAIL $2: expected '$4', got '$got'"; fail=1;; esac
}
check "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" "perft 4" nodes "197281"
check "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1" "perft 3" nodes "97862"
check "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1" "perft 4" nodes "43238"
check "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1" "perft 3" nodes "9467"
check "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8" "perft 3" nodes "62379"
check "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1" "go depth 3" bestmove "a1a8"
check "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4" "go depth 3" bestmove "h5f7"
exit $fail
