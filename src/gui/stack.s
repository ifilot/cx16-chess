;
; CHESS.PRG keeps root move arrays at $0400-$05BF and its C stack at
; $05C0-$07FF. ENGINE.PRG uses this RAM for its mailbox instead. This frees
; 1 KB of main RAM between the arrays and stack;
; the program is linked with __STACKSIZE__=0 (see Makefile).
;
        .include "zeropage.inc"
        .constructor golden_stack

GOLDEN_TOP = $0800

.segment "ONCE"

golden_stack:
        lda #<GOLDEN_TOP
        sta sp
        lda #>GOLDEN_TOP
        sta sp+1
        rts
