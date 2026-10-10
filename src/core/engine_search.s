;**************************************************************************
;                                                                         *
;   Author: Ivo Filot <ivo@ivofilot.nl>                                   *
;                                                                         *
;   CX16-CHESS is free software:                                          *
;   you can redistribute it and/or modify it under the terms of the       *
;   GNU General Public License as published by the Free Software          *
;   Foundation, either version 3 of the License, or (at your option)      *
;   any later version.                                                    *
;                                                                         *
;   CX16-CHESS is distributed in the hope that it will be useful,         *
;   but WITHOUT ANY WARRANTY; without even the implied warranty           *
;   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.               *
;   See the GNU General Public License for more details.                  *
;                                                                         *
;   You should have received a copy of the GNU General Public License     *
;   along with this program.  If not, see http://www.gnu.org/licenses/.   *
;                                                                         *
;**************************************************************************

;
; The search of the engine in 65C02 assembly: search() and quiesce() of
; engine.c, which are the reference. Both must visit exactly the same nodes.
;
; Recursion uses JSR; the variables of a node live in arrays indexed by its
; ply (n_* below). While a move is made, the node's ply is sply - 1.
;

        .setcpu "65C02"
        .macpack longbranch

        .export _search_entry, _s_depth, _s_alpha, _s_beta, _s_null
        ; internal routines, exported for the profiler (tools/profile_engine.py)
        .export count_node, set_ptrs, score_moves, pick_move, tt_probe, tt_store
        .export remember_quiet, search_node, quiesce_node, history_slot

        .import _bd, _stm, _fifty, _sply, _hash_lo, _hash_hi, _nodes, _ms_top
        .import _mv_from, _mv_to, _mv_flags, _mv_score
        .import _npm, _pawn_count, _mk_from, _mk_to, _mk_flags, _att_sq
        .import _make_move, _unmake_move, _make_null, _unmake_null
        .import _square_attacked, _in_check, _generate_moves, _evaluate
        .import _is_repetition, _validate_move, sq64tab
        .import _search_aborted, _search_poll, _killer_from, _killer_to

RAM_BANK        = $00
ENGINE_BANK     = 1
TT_FIRST_BANK   = 2
HISTORY_PAGE    = $B6

MAX_PLY         = 40
MS_LIMIT        = 768 - 224     ; MS_SIZE - MAX_MOVES
NO_SQ           = $80
F_PROMO         = $07
F_CAPTURE       = $08
F_EP            = $10
TT_EXACT        = 1
TT_LOWER        = 2
TT_UPPER        = 3
MATE            = 30000
MATE_BOUND      = MATE - 512

;--------------------------------------------------------------------------
        .segment "ZEROPAGE"
pf:             .res 2          ; move list of the current node
pt:             .res 2
pfl:            .res 2
psc:            .res 2
ttp:            .res 2          ; transposition table entry
hptr:           .res 2          ; history counter page

;--------------------------------------------------------------------------
        .segment "BSS"
_s_depth:       .res 1          ; arguments of search_node
_s_alpha:       .res 2
_s_beta:        .res 2
_s_null:        .res 1
r_lo:           .res 1          ; result of a node
r_hi:           .res 1
sc_lo:          .res 1          ; negated result of the last child
sc_hi:          .res 1
poll_count:     .res 1
tmp:            .res 1
tmp2:           .res 1

; per-node variables, indexed by ply
n_depth:        .res MAX_PLY
n_alo:          .res MAX_PLY
n_ahi:          .res MAX_PLY
n_blo:          .res MAX_PLY
n_bhi:          .res MAX_PLY
n_a0lo:         .res MAX_PLY
n_a0hi:         .res MAX_PLY
n_bestlo:       .res MAX_PLY
n_besthi:       .res MAX_PLY
n_evlo:         .res MAX_PLY
n_evhi:         .res MAX_PLY
n_firstlo:      .res MAX_PLY
n_firsthi:      .res MAX_PLY
n_cnt:          .res MAX_PLY
n_k:            .res MAX_PLY
n_check:        .res MAX_PLY
n_legal:        .res MAX_PLY
n_quiet:        .res MAX_PLY
n_futile:       .res MAX_PLY
n_null:         .res MAX_PLY
n_red:          .res MAX_PLY
n_hf:           .res MAX_PLY    ; hash move
n_ht:           .res MAX_PLY
n_bf:           .res MAX_PLY    ; best move
n_bt:           .res MAX_PLY
n_bfl:          .res MAX_PLY
n_mf:           .res MAX_PLY    ; move being searched
n_mt:           .res MAX_PLY
n_mfl:          .res MAX_PLY
n_flat:         .res MAX_PLY    ; remaining moves all score 0: keep their order
n_hp:           .res MAX_PLY    ; promotion piece of the hash move
n_sf:           .res MAX_PLY    ; validated hash move, skipped later
n_st:           .res MAX_PLY
n_sfl:          .res MAX_PLY    ; its flags, $FF: none
n_stage:        .res MAX_PLY    ; 1: trying the hash move, 2: generated moves

; transposition table probe result
tt_hit:         .res 1
tt_from:        .res 1
tt_to:          .res 1
tt_slo:         .res 1
tt_shi:         .res 1
tt_depth:       .res 1
tt_bound:       .res 1
tt_promo:       .res 1

;--------------------------------------------------------------------------
        .segment "RODATA"
victim:         .byte 0, 1, 3, 3, 5, 9, 0, 0
val_lo:         .byte 0, <100, <320, <330, <500, <900, 0, 0
val_hi:         .byte 0, >100, >320, >330, >500, >900, 0, 0
depth_sq:       .byte 0, 1, 4, 9, 16, 25, 36, 49, 64
fut_lo:         .byte 0, <150, <300, <500   ; futility margins per depth
fut_hi:         .byte 0, >150, >300, >500
lmp_count:      .byte 0, 8, 14              ; quiet moves searched near the horizon

;--------------------------------------------------------------------------
; 16-bit helpers

; N set when (alo,ahi) < (blo,bhi), signed
.macro CMPW alo, ahi, blo, bhi
        sec
        lda alo
        sbc blo
        lda ahi
        sbc bhi
        bvc :+
        eor #$80
:
.endmacro

.macro NEG_SC
        sec
        lda #0
        sbc r_lo
        sta sc_lo
        lda #0
        sbc r_hi
        sta sc_hi
.endmacro

;--------------------------------------------------------------------------
; exchange entries n_k,x and tmp of a move list
.macro SWAP PTR
        ldy tmp
        lda (PTR),y
        pha
        ldy n_k,x
        lda (PTR),y
        ldy tmp
        sta (PTR),y
        ldy n_k,x
        pla
        sta (PTR),y
.endmacro

;--------------------------------------------------------------------------
; Child with the full window: search(depth - 1, -beta, -alpha, 1) of node X
; (inline: a JSR per ply is all the 256-byte hardware stack can afford)
.macro CHILD_FULL
        lda n_depth,x
        dec a
        sta _s_depth
        sec
        lda #0
        sbc n_blo,x
        sta _s_alpha
        lda #0
        sbc n_bhi,x
        sta _s_alpha+1
        sec
        lda #0
        sbc n_alo,x
        sta _s_beta
        lda #0
        sbc n_ahi,x
        sta _s_beta+1
        lda #1
        sta _s_null
        jsr search_node
        NEG_SC
        ldx _sply
        dex
.endmacro

;--------------------------------------------------------------------------
        .segment "CODE"

;
; int16_t search_entry(void): search(s_depth, s_alpha, s_beta, s_null)
;
_search_entry:
        jsr search_node
        lda r_lo
        ldx r_hi
        rts

;
; Count a node and check the limits every 256 nodes
;
count_node:
        inc _nodes
        bne :+
        inc _nodes+1
        bne :+
        inc _nodes+2
        bne :+
        inc _nodes+3
:       inc poll_count
        bne :+
        jsr _search_poll
:       rts

;
; Point pf/pt/pfl/psc at the move list of node X
;
set_ptrs:
        clc
        lda n_firstlo,x
        adc #<_mv_from
        sta pf
        lda n_firsthi,x
        adc #>_mv_from
        sta pf+1
        clc
        lda n_firstlo,x
        adc #<_mv_to
        sta pt
        lda n_firsthi,x
        adc #>_mv_to
        sta pt+1
        clc
        lda n_firstlo,x
        adc #<_mv_flags
        sta pfl
        lda n_firsthi,x
        adc #>_mv_flags
        sta pfl+1
        clc
        lda n_firstlo,x
        adc #<_mv_score
        sta psc
        lda n_firsthi,x
        adc #>_mv_score
        sta psc+1
        rts

;
; ms_top = first of node X
;
release_moves:
        lda n_firstlo,x
        sta _ms_top
        lda n_firsthi,x
        sta _ms_top+1
        rts

;
; Point hptr/Y at HISTORY[piece A][square64 of X]
;
history_slot:
        sta tmp
        lsr
        lsr
        clc
        adc #HISTORY_PAGE
        sta hptr+1
        stz hptr
        lda tmp
        and #3
        lsr
        ror
        ror
        ora sq64tab,x
        tay
        rts

;
; Ordering scores for the moves of node X (see score_moves in engine.c)
;
score_moves:
        ldy #0
@loop:  tya
        cmp n_cnt,x
        bcc :+
        rts
:       lda (pf),y
        cmp n_hf,x
        jne @nohash
        lda (pt),y
        cmp n_ht,x
        jne @nohash
        lda #255
        jmp @store
@nohash:
        lda (pfl),y
        bit #(F_CAPTURE | F_PROMO)
        jeq @quiet
        bit #F_EP
        jeq @capture
        lda #(151 + 8 - 1)
        jmp @store
@capture:
        and #F_PROMO
        cmp #5
        bne :+
        lda #(151 + 32)         ; queen promotion
        bra :++
:       lda #151
:       sta tmp
        phy
        lda (pt),y              ; + 8 * victim
        tay
        lda _bd,y
        and #7
        tay
        lda victim,y
        asl
        asl
        asl
        clc
        adc tmp
        sta tmp
        ply
        phy
        lda (pf),y              ; - attacker
        tay
        lda _bd,y
        and #7
        tay
        lda tmp
        sec
        sbc victim,y
        ply
        jmp @store
@quiet: lda (pf),y
        cmp _killer_from,x
        jne @k2
        lda (pt),y
        cmp _killer_to,x
        jne @k2
        lda #150
        bra @store
@k2:    lda (pf),y
        cmp _killer_from+MAX_PLY,x
        jne @hist
        lda (pt),y
        cmp _killer_to+MAX_PLY,x
        jne @hist
        lda #149
        bra @store
@hist:  phy
        phx
        lda (pt),y
        tax
        lda (pf),y
        tay
        lda _bd,y
        jsr history_slot
        lda (hptr),y
        plx
        ply
        cmp #141
        jcc @store
        lda #140
@store: sta (psc),y
        iny
        jmp @loop

;
; Bring the best scored move of k..cnt-1 of node X to position k
;
pick_move:
        lda n_flat,x
        jne @done
        lda n_k,x
        sta tmp                 ; best
        tay
        lda (psc),y
        sta tmp2                ; best score
@scan:  iny
        tya
        cmp n_cnt,x
        jcs @swap
        lda (psc),y
        cmp tmp2
        jeq @scan
        jcc @scan
        sta tmp2
        sty tmp
        bra @scan
@swap:  ldy n_k,x
        cpy tmp
        jeq @done
        SWAP pf
        SWAP pt
        SWAP pfl
        SWAP psc
@done:  rts

;
; Locate the TT entry of the current position: bank and ttp
;
tt_addr:
        lda _hash_lo+1
        lsr
        lsr
        and #15
        clc
        adc #TT_FIRST_BANK
        sta RAM_BANK
        lda _hash_lo
        asl
        asl
        asl
        sta ttp
        lda _hash_lo+1
        and #3
        asl
        asl
        asl
        sta tmp
        lda _hash_lo
        lsr
        lsr
        lsr
        lsr
        lsr
        ora tmp
        ora #$A0
        sta ttp+1
        rts

;
; Probe the TT: tt_hit and the tt_* fields (score relative to the root)
;
tt_probe:
        jsr tt_addr
        stz tt_hit
        ldy #0
        lda (ttp),y
        cmp _hash_hi
        jne @done
        iny
        lda (ttp),y
        cmp _hash_hi+1
        jne @done
        iny
        lda (ttp),y
        sta tt_from
        iny
        lda (ttp),y
        sta tt_to
        ora tt_from
        jeq @done
        iny
        lda (ttp),y
        sta tt_slo
        iny
        lda (ttp),y
        sta tt_shi
        iny
        lda (ttp),y
        sta tt_depth
        iny
        lda (ttp),y
        and #F_PROMO
        sta tt_promo
        lda (ttp),y
        lsr
        lsr
        lsr
        lsr
        sta tt_bound
        inc tt_hit
        ; mate scores are stored relative to the node
        CMPW #<MATE_BOUND, #>MATE_BOUND, tt_slo, tt_shi
        jpl @notwin             ; MATE_BOUND >= score
        sec
        lda tt_slo
        sbc _sply
        sta tt_slo
        jcs @done
        dec tt_shi
        bra @done
@notwin:
        CMPW tt_slo, tt_shi, #<(-MATE_BOUND), #>(-MATE_BOUND)
        jpl @done
        clc
        lda tt_slo
        adc _sply
        sta tt_slo
        jcc @done
        inc tt_shi
@done:  lda #ENGINE_BANK
        sta RAM_BANK
        rts

;
; Store node X in the TT: depth, best, bound A, best move
;
tt_store:
        sta tmp2                ; bound
        jsr tt_addr
        ldy #0
        lda (ttp),y
        cmp _hash_hi
        jne @store
        iny
        lda (ttp),y
        cmp _hash_hi+1
        jne @store
        ldy #6
        lda (ttp),y             ; keep a deeper entry unless exact
        cmp n_depth,x
        jeq @store
        jcc @store
        lda tmp2
        cmp #TT_EXACT
        jeq @store
        jmp @done
@store: ldy #0
        lda _hash_hi
        sta (ttp),y
        iny
        lda _hash_hi+1
        sta (ttp),y
        iny
        lda n_bf,x
        sta (ttp),y
        iny
        lda n_bt,x
        sta (ttp),y
        lda n_bestlo,x          ; score relative to the node
        sta sc_lo
        lda n_besthi,x
        sta sc_hi
        CMPW #<MATE_BOUND, #>MATE_BOUND, sc_lo, sc_hi
        jpl @notwin
        clc
        lda sc_lo
        adc _sply
        sta sc_lo
        jcc @write
        inc sc_hi
        bra @write
@notwin:
        CMPW sc_lo, sc_hi, #<(-MATE_BOUND), #>(-MATE_BOUND)
        jpl @write
        sec
        lda sc_lo
        sbc _sply
        sta sc_lo
        jcs @write
        dec sc_hi
@write: ldy #4
        lda sc_lo
        sta (ttp),y
        iny
        lda sc_hi
        sta (ttp),y
        iny
        lda n_depth,x
        sta (ttp),y
        iny
        lda tmp2
        asl
        asl
        asl
        asl
        sta tmp
        lda n_bfl,x
        and #F_PROMO
        ora tmp
        sta (ttp),y
@done:  lda #ENGINE_BANK
        sta RAM_BANK
        rts

;
; Killer and history update for the quiet cutoff move of node X
;
remember_quiet:
        lda n_mf,x
        cmp _killer_from,x
        jne @shift
        lda n_mt,x
        cmp _killer_to,x
        jeq @history
@shift: lda _killer_from,x
        sta _killer_from+MAX_PLY,x
        lda _killer_to,x
        sta _killer_to+MAX_PLY,x
        lda n_mf,x
        sta _killer_from,x
        lda n_mt,x
        sta _killer_to,x
@history:
        phx
        ldy n_mf,x
        lda n_mt,x
        tax
        lda _bd,y
        jsr history_slot
        lda (hptr),y
        cmp #(255 - 64 + 1)
        jcc @add
        phy                     ; age all counters
        ldx #4
        lda #HISTORY_PAGE
        sta hptr+1
@page:  ldy #0
@half:  lda (hptr),y
        lsr
        sta (hptr),y
        iny
        jne @half
        inc hptr+1
        dex
        jne @page
        ply
        plx
        phx
        lda n_mf,x              ; recompute the slot
        tay
        lda n_mt,x
        tax
        lda _bd,y
        jsr history_slot
@add:   plx
        lda n_depth,x
        cmp #9
        bcc :+
        lda #8
:       phy
        tay
        lda depth_sq,y
        ply
        clc
        adc (hptr),y
        sta (hptr),y
        rts

;--------------------------------------------------------------------------
; Node exits: the value goes to r_lo/r_hi

ret_zero:
        stz r_lo
        stz r_hi
        rts

ret_eval:
        jsr _evaluate
        sta r_lo
        stx r_hi
        rts

;
; Search node: search(s_depth, s_alpha, s_beta, s_null)
;
search_node:
        ldx _sply
        lda _s_depth
        sta n_depth,x
        lda _s_alpha
        sta n_alo,x
        sta n_a0lo,x
        lda _s_alpha+1
        sta n_ahi,x
        sta n_a0hi,x
        lda _s_beta
        sta n_blo,x
        lda _s_beta+1
        sta n_bhi,x
        lda _s_null
        sta n_null,x

        cpx #0                  ; draws by repetition, fifty moves, material
        jeq @nodraw
        jsr _is_repetition
        cmp #0
        jne ret_zero
        lda _fifty
        cmp #100
        jcs ret_zero
        lda _pawn_count
        ora _pawn_count+1
        jne @nodraw
        clc
        lda _npm
        adc _npm+2
        tay
        lda _npm+1
        adc _npm+3
        cmp #>330               ; npm[0] + npm[1] <= 330
        jcc ret_zero
        jne @nodraw
        cpy #<(330 + 1)
        jcc ret_zero
@nodraw:
        jsr _in_check
        ldx _sply
        sta n_check,x
        cmp #0
        beq :+
        cpx #(MAX_PLY / 2)      ; check extension in the first half of the plies
        bcs :+
        inc n_depth,x
:       lda n_depth,x
        jeq @quiesce
        jpl @full
@quiesce:
        lda n_alo,x
        sta _s_alpha
        lda n_ahi,x
        sta _s_alpha+1
        jmp quiesce_node

@full:  jsr count_node
        lda _search_aborted
        jne ret_zero
        ldx _sply
        cpx #(MAX_PLY - 1)
        jcs ret_eval

        jsr tt_probe
        ldx _sply
        lda #NO_SQ
        sta n_hf,x
        sta n_ht,x
        lda tt_hit
        jeq @nott
        lda tt_from
        sta n_hf,x
        lda tt_to
        sta n_ht,x
        lda tt_promo
        sta n_hp,x
        cpx #0
        jeq @nott
        lda tt_depth
        cmp n_depth,x
        jcc @nott
        lda tt_bound
        cmp #TT_EXACT
        jeq @ttret
        cmp #TT_LOWER
        jne @ttupper
        CMPW tt_slo, tt_shi, {n_blo,x}, {n_bhi,x}
        jmi @nott
        bra @ttret
@ttupper:
        CMPW {n_alo,x}, {n_ahi,x}, tt_slo, tt_shi
        jmi @nott
@ttret: lda tt_slo
        sta r_lo
        lda tt_shi
        sta r_hi
        rts

@nott:  stz n_futile,x
        lda n_check,x
        beq :+
        jmp @movegen
:       jsr _evaluate
        ldy _sply
        sta n_evlo,y
        txa
        sta n_evhi,y
        ldx _sply

        ; reverse futility: depth <= 2, not root, beta not a mate score
        lda n_depth,x
        cmp #3
        jcs @nullmove
        cpx #0
        jeq @nullmove
        CMPW #<(-MATE_BOUND), #>(-MATE_BOUND), {n_blo,x}, {n_bhi,x}
        jpl @nullmove           ; beta <= -MATE_BOUND
        CMPW {n_blo,x}, {n_bhi,x}, #<MATE_BOUND, #>MATE_BOUND
        jpl @nullmove           ; beta >= MATE_BOUND
        lda #120
        ldy n_depth,x
        cpy #1
        beq :+
        lda #240
:       sta tmp
        sec                     ; sc = ev - margin
        lda n_evlo,x
        sbc tmp
        sta sc_lo
        lda n_evhi,x
        sbc #0
        sta sc_hi
        CMPW sc_lo, sc_hi, {n_blo,x}, {n_bhi,x}
        jmi @nullmove
        lda n_evlo,x
        sta r_lo
        lda n_evhi,x
        sta r_hi
        rts

@nullmove:
        lda n_null,x
        jeq @futility
        lda n_depth,x
        cmp #3
        jcc @futility
        CMPW {n_blo,x}, {n_bhi,x}, #<MATE_BOUND, #>MATE_BOUND
        jpl @futility
        lda _stm                ; side to move has pieces
        lsr
        lsr
        tay
        lda _npm,y
        ora _npm+1,y
        jeq @futility
        CMPW {n_evlo,x}, {n_evhi,x}, {n_blo,x}, {n_bhi,x}
        jmi @futility
        jsr _make_null
        ldx _sply
        dex
        lda n_depth,x
        sec
        sbc #3
        sta _s_depth
        sec                     ; window (-beta, -beta + 1)
        lda #0
        sbc n_blo,x
        sta _s_alpha
        lda #0
        sbc n_bhi,x
        sta _s_alpha+1
        clc
        lda _s_alpha
        adc #1
        sta _s_beta
        lda _s_alpha+1
        adc #0
        sta _s_beta+1
        stz _s_null
        jsr search_node
        NEG_SC
        jsr _unmake_null
        ldx _sply
        lda _search_aborted
        beq :+
        jmp ret_zero
:       CMPW sc_lo, sc_hi, {n_blo,x}, {n_bhi,x}
        jmi @futility
        lda n_blo,x
        sta r_lo
        lda n_bhi,x
        sta r_hi
        rts

@futility:
        lda n_depth,x           ; depth 1-3 and ev + margin <= alpha
        beq @movegen
        cmp #4
        jcs @movegen
        tay
        clc
        lda n_evlo,x
        adc fut_lo,y
        sta sc_lo
        lda n_evhi,x
        adc fut_hi,y
        sta sc_hi
        CMPW {n_alo,x}, {n_ahi,x}, sc_lo, sc_hi
        jmi @movegen
        lda #1
        sta n_futile,x

@movegen:
        lda _ms_top
        sta n_firstlo,x
        lda _ms_top+1
        sta n_firsthi,x
        cmp #>MS_LIMIT          ; move stack full: evaluate
        jcc @room
        bne :+
        lda _ms_top
        cmp #<(MS_LIMIT + 1)
        jcc @room
:       jmp ret_eval
@room:  lda #<(-MATE)
        sta n_bestlo,x
        lda #>(-MATE)
        sta n_besthi,x
        stz n_legal,x
        stz n_quiet,x
        lda #NO_SQ
        sta n_bf,x
        sta n_bt,x
        stz n_bfl,x

        ; the hash move is tried before the other moves are generated
        lda #$FF
        sta n_sfl,x             ; no move to skip later
        lda n_hf,x
        cmp #NO_SQ
        beq @generate
        sta _mk_from
        lda n_ht,x
        sta _mk_to
        lda n_hp,x
        sta _mk_flags
        jsr _validate_move
        ldx _sply
        cmp #$FF
        beq @generate
        sta n_sfl,x
        sta n_mfl,x
        sta _mk_flags
        lda n_hf,x
        sta n_sf,x
        sta n_mf,x
        sta _mk_from
        lda n_ht,x
        sta n_st,x
        sta n_mt,x
        sta _mk_to
        lda #1
        sta n_stage,x
        jmp @try

@generate:
        ldx _sply
        lda #2
        sta n_stage,x
        lda #0
        jsr _generate_moves
        ldx _sply
        sec
        sbc n_firstlo,x
        sta n_cnt,x
        jsr set_ptrs
        lda #NO_SQ              ; no hash move bonus: it was tried first
        sta n_hf,x
        sta n_ht,x
        jsr score_moves
        stz n_flat,x
        stz n_k,x

@loop:  ldx _sply
        lda n_k,x
        cmp n_cnt,x
        bcc :+
        jmp @done
:       jsr set_ptrs
        jsr pick_move
        ldy n_k,x
        lda (pf),y
        sta n_mf,x
        sta _mk_from
        lda (pt),y
        sta n_mt,x
        sta _mk_to
        lda (pfl),y
        sta n_mfl,x
        sta _mk_flags
        cmp n_sfl,x             ; skip the hash move, it was searched already
        bne @try
        lda n_mf,x
        cmp n_sf,x
        bne @try
        lda n_mt,x
        cmp n_st,x
        jeq @next
@try:
        jsr _make_move
        cmp #0
        jne @legal
        jsr _unmake_move
        jmp @next
@legal: ldx _sply
        dex
        inc n_legal,x
        lda n_futile,x          ; futility: skip quiet non-checking moves
        jeq @search
        lda n_legal,x
        cmp #2
        jcc @search
        lda n_mfl,x
        and #(F_CAPTURE | F_PROMO)
        jne @search
        jsr _in_check
        cmp #0
        jne @search
        jsr _unmake_move
        jmp @next

@search:
        ldx _sply               ; late move pruning: depth <= 2, not in check,
        dex                     ; quiet, not checking, after the first moves
        lda n_depth,x
        cmp #3
        bcs @dosearch
        lda n_check,x
        bne @dosearch
        ldy n_depth,x
        lda n_legal,x
        cmp lmp_count,y
        beq @dosearch
        bcc @dosearch
        lda n_mfl,x
        and #(F_CAPTURE | F_PROMO)
        bne @dosearch
        jsr _in_check
        cmp #0
        bne @dosearch
        jsr _unmake_move
        jmp @next

@dosearch:
        ldx _sply
        dex
        lda n_legal,x
        cmp #1
        jne @late
        CHILD_FULL
        jmp @searched
@late:  stz n_red,x
        lda n_depth,x
        cmp #3
        jcc @nolmr
        lda n_check,x
        jne @nolmr
        lda n_mfl,x
        and #(F_CAPTURE | F_PROMO)
        jne @nolmr
        inc n_quiet,x
        lda n_quiet,x
        cmp #4
        jcc @nolmr
        jsr _in_check
        ldx _sply
        dex
        cmp #0
        jne @nolmr
        lda #1
        sta n_red,x
@nolmr: lda n_depth,x           ; zero window at depth - 1 - reduction
        sec
        sbc #1
        sbc n_red,x
        sta _s_depth
        lda n_alo,x             ; (-alpha - 1, -alpha) = (~alpha, -alpha)
        eor #$FF
        sta _s_alpha
        lda n_ahi,x
        eor #$FF
        sta _s_alpha+1
        sec
        lda #0
        sbc n_alo,x
        sta _s_beta
        lda #0
        sbc n_ahi,x
        sta _s_beta+1
        lda #1
        sta _s_null
        jsr search_node
        NEG_SC
        ldx _sply
        dex
        ; re-search when score > alpha and (reduced or score < beta)
        CMPW {n_alo,x}, {n_ahi,x}, sc_lo, sc_hi
        jpl @searched
        lda n_red,x
        bne @research
        CMPW sc_lo, sc_hi, {n_blo,x}, {n_bhi,x}
        jpl @searched
@research:
        CHILD_FULL

@searched:
        jsr _unmake_move
        ldx _sply
        lda _search_aborted
        beq :+
        jsr release_moves
        jmp ret_zero
:       CMPW {n_bestlo,x}, {n_besthi,x}, sc_lo, sc_hi
        jpl @next               ; best >= score
        lda sc_lo
        sta n_bestlo,x
        lda sc_hi
        sta n_besthi,x
        lda n_mf,x
        sta n_bf,x
        lda n_mt,x
        sta n_bt,x
        lda n_mfl,x
        sta n_bfl,x
        CMPW {n_alo,x}, {n_ahi,x}, sc_lo, sc_hi
        jpl @next               ; alpha >= score
        lda sc_lo
        sta n_alo,x
        lda sc_hi
        sta n_ahi,x
        CMPW sc_lo, sc_hi, {n_blo,x}, {n_bhi,x}
        jmi @next
        lda n_mfl,x             ; beta cutoff
        and #(F_CAPTURE | F_PROMO)
        jne @done
        jsr remember_quiet
        bra @done

@next:  ldx _sply
        lda n_stage,x
        cmp #1
        bne :+
        jmp @generate           ; the hash move is done: now the others
:       inc n_k,x
        jmp @loop

@done:  ldx _sply
        jsr release_moves
        lda n_legal,x
        jne @store
        lda n_check,x           ; no legal move: mate or stalemate
        bne :+
        jmp ret_zero
:       clc                     ; -MATE + sply
        lda #<(-MATE)
        adc _sply
        sta r_lo
        lda #>(-MATE)
        adc #0
        sta r_hi
        rts

@store: CMPW {n_bestlo,x}, {n_besthi,x}, {n_blo,x}, {n_bhi,x}
        bmi :+
        lda #TT_LOWER
        bra @bound
:       CMPW {n_a0lo,x}, {n_a0hi,x}, {n_bestlo,x}, {n_besthi,x}
        bmi :+
        lda #TT_UPPER
        bra @bound
:       lda #TT_EXACT
@bound: jsr tt_store
        ldx _sply
        lda n_bestlo,x
        sta r_lo
        lda n_besthi,x
        sta r_hi
        rts

;
; Quiescence node: quiesce(s_alpha, s_beta) at ply sply
;
quiesce_node:
        ldx _sply
        lda _s_alpha
        sta n_alo,x
        lda _s_alpha+1
        sta n_ahi,x
        lda _s_beta
        sta n_blo,x
        lda _s_beta+1
        sta n_bhi,x
        jsr count_node
        lda _search_aborted
        beq :+
        jmp ret_zero
:       jsr _evaluate
        ldy _sply
        sta n_evlo,y
        txa
        sta n_evhi,y
        ldx _sply
        CMPW {n_evlo,x}, {n_evhi,x}, {n_blo,x}, {n_bhi,x}
        bmi :+
        jmp @ret_stand          ; stand pat >= beta
:       CMPW {n_alo,x}, {n_ahi,x}, {n_evlo,x}, {n_evhi,x}
        bpl :+
        lda n_evlo,x
        sta n_alo,x
        lda n_evhi,x
        sta n_ahi,x
:       cpx #(MAX_PLY - 1)
        bcc :+
        jmp @ret_stand
:       lda _ms_top
        sta n_firstlo,x
        lda _ms_top+1
        sta n_firsthi,x
        cmp #>MS_LIMIT
        jcc @room
        bne :+
        lda _ms_top
        cmp #<(MS_LIMIT + 1)
        jcc @room
:       jmp @ret_stand
@room:  lda #NO_SQ
        sta n_hf,x
        sta n_ht,x
        lda #1
        jsr _generate_moves
        ldx _sply
        sec
        sbc n_firstlo,x
        sta n_cnt,x
        jsr set_ptrs
        jsr score_moves
        stz n_flat,x
        stz n_k,x

@loop:  ldx _sply
        lda n_k,x
        cmp n_cnt,x
        bcc :+
        jmp @ret_alpha
:       jsr set_ptrs
        jsr pick_move
        ldy n_k,x
        lda (pf),y
        sta n_mf,x
        lda (pt),y
        sta n_mt,x
        lda (pfl),y
        sta n_mfl,x
        and #F_PROMO
        jne @make

        ; delta pruning: stand + value(victim) + 200 < alpha (not e.p.)
        ldy n_mt,x
        lda _bd,y
        and #7
        sta tmp                 ; victim type
        lda n_mfl,x
        and #F_EP
        jne @losing
        ldy tmp
        clc
        lda n_evlo,x
        adc val_lo,y
        sta sc_lo
        lda n_evhi,x
        adc val_hi,y
        sta sc_hi
        clc
        lda sc_lo
        adc #200
        sta sc_lo
        lda sc_hi
        adc #0
        sta sc_hi
        CMPW sc_lo, sc_hi, {n_alo,x}, {n_ahi,x}
        jpl @losing
        jmp @next
@losing:                        ; value(victim) < value(attacker) and defended
        ldy tmp
        lda val_lo,y
        sta sc_lo
        lda val_hi,y
        sta sc_hi
        ldy n_mf,x
        lda _bd,y
        and #7
        tay                     ; attacker type
        CMPW sc_lo, sc_hi, {val_lo,y}, {val_hi,y}
        jpl @make
        lda n_mt,x
        sta _att_sq
        lda _stm
        eor #8
        jsr _square_attacked
        cmp #0
        jeq @make
        jmp @next

@make:  ldx _sply
        lda n_mf,x
        sta _mk_from
        lda n_mt,x
        sta _mk_to
        lda n_mfl,x
        sta _mk_flags
        jsr _make_move
        cmp #0
        bne :+
        jsr _unmake_move
        jmp @next
:       ldx _sply
        dex
        sec                     ; quiesce(-beta, -alpha)
        lda #0
        sbc n_blo,x
        sta _s_alpha
        lda #0
        sbc n_bhi,x
        sta _s_alpha+1
        sec
        lda #0
        sbc n_alo,x
        sta _s_beta
        lda #0
        sbc n_ahi,x
        sta _s_beta+1
        jsr quiesce_node
        NEG_SC
        jsr _unmake_move
        ldx _sply
        lda _search_aborted
        jne @ret_alpha
        CMPW {n_alo,x}, {n_ahi,x}, sc_lo, sc_hi
        jpl @next               ; alpha >= score
        CMPW sc_lo, sc_hi, {n_blo,x}, {n_bhi,x}
        bmi :+
        jsr release_moves       ; score >= beta
        lda sc_lo
        sta r_lo
        lda sc_hi
        sta r_hi
        rts
:       lda sc_lo
        sta n_alo,x
        lda sc_hi
        sta n_ahi,x
@next:  ldx _sply
        inc n_k,x
        jmp @loop

@ret_alpha:
        ldx _sply
        jsr release_moves
        lda n_alo,x
        sta r_lo
        lda n_ahi,x
        sta r_hi
        rts
@ret_stand:
        lda n_evlo,x
        sta r_lo
        lda n_evhi,x
        sta r_hi
        rts
