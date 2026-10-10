;
; CHESS.PRG keeps its C stack in golden RAM ($0400-$07FF), which only the
; engine bridge (ENGINE.PRG) uses otherwise. This frees 1 KB of main RAM;
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
