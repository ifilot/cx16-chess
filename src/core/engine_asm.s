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
; Per-node board code of the engine in 65C02 assembly: the X16 version of
; engine_hot.c, which is the reference. Both must behave identically.
; (Not named engine_hot.s: cl65 uses that name for the compiled C file.)
;
; All routines expect RAM bank ENGINE_BANK (1) to be selected; the banked
; tables are described in engine_int.h.
;

        .setcpu "65C02"
        .macpack longbranch

        .export _bd, _stm, _castle, _ep, _fifty, _sply, _hash_lo, _hash_hi, _nodes
        .export _ms_top, _mv_from, _mv_to, _mv_flags, _mv_score
        .export _psq_score, _npm, _pawn_count, _bishop_count, _pawn_files
        .export _pawn_hash, _pawn_hash2, _ksq, _rep_count
        .export _mk_from, _mk_to, _mk_flags, _att_sq
        .export _make_move, _unmake_move, _make_null, _unmake_null
        .export _square_attacked, _in_check, _generate_moves, _evaluate
        .export _is_repetition, _board_put, _refresh_check, _pawn_structure_compute
        .export _validate_move
        ; internal routines, exported for the profiler (tools/profile_engine.py)
        .export hash_piece, piece_add, piece_remove, hash_state, save_hash
        .export compute_check, emit, pawn_capture, castle_safe, shelter, mop_up
        .export sq64tab

        .import _king_endgame, _center_dist, _castle_keep
        .import _zob_castle_lo, _zob_castle_hi, _zob_ep_lo, _zob_ep_hi
        .import _zob_side_lo, _zob_side_hi

; banked tables (bank 1)
ZOB_PAGE        = $A0           ; Zobrist page of piece index 0
PSQ_PAGE        = $AB           ; + piece type
REP0            = $BA00
REP1            = $BB00
REP2            = $BC00
REP3            = $BD00
ATT_KINDS       = $BE00         ; attack vectors, see engine_int.h
ATT_STEP        = $BF00
PAWN_BANK       = 18            ; pawn structure cache, 2048 entries
ENGINE_BANK     = 1
RAM_BANK        = $00
ATT_DIAG        = $08
ATT_STRAIGHT    = $10
ATT_KNIGHT      = $04
ATT_KING        = $20
ATT_WPAWN       = $01
ATT_BPAWN       = $02
KNIGHT          = 2
BISHOP          = 3
ROOK            = 4
QUEEN           = 5

MAX_PLY         = 40
MS_LIMIT        = 768 - 224     ; MS_SIZE - MAX_MOVES
NO_SQ           = $80
PAWN            = 1
KING            = 6
F_CAPTURE       = $08
F_EP            = $10
F_CASTLE        = $20
F_DOUBLE        = $40

;--------------------------------------------------------------------------
        .segment "ZEROPAGE"
zptr:           .res 2          ; table page pointer (low byte always 0)
mfp:            .res 2          ; move stack pointers for the generator
mtp:            .res 2
mflp:           .res 2
t_p:            .res 1          ; piece_add / piece_remove
t_sq:           .res 1
z0lo:           .res 1          ; first key half of the last hashed piece
z0hi:           .res 1
z1lo:           .res 1
no_hash:        .res 1          ; set while unmaking: hashes are restored instead
e_s:            .res 2          ; evaluation accumulator
pcp:            .res 2          ; pawn cache pointer
tmp:            .res 1

;--------------------------------------------------------------------------
        .segment "BSS"
_bd:            .res 128
_stm:           .res 1
_castle:        .res 1
_ep:            .res 1
_fifty:         .res 1
_sply:          .res 1
_hash_lo:       .res 2
_hash_hi:       .res 2
_nodes:         .res 4
_ms_top:        .res 2
_mv_from:       .res 768       ; MS_SIZE
_mv_to:         .res 768
_mv_flags:      .res 768
_mv_score:      .res 768
_psq_score:     .res 2
_npm:           .res 4
_pawn_count:    .res 2
_bishop_count:  .res 2
_pawn_files:    .res 16
_pawn_hash:     .res 2
_pawn_hash2:    .res 1
_ksq:           .res 2
_rep_count:     .res 1
_mk_from:       .res 1
_mk_to:         .res 1
_mk_flags:      .res 1
_att_sq:        .res 1

; undo information per ply
u_from:         .res MAX_PLY
u_to:           .res MAX_PLY
u_flags:        .res MAX_PLY
u_captured:     .res MAX_PLY
u_castle:       .res MAX_PLY
u_ep:           .res MAX_PLY
u_fifty:        .res MAX_PLY
u_h0:           .res MAX_PLY
u_h1:           .res MAX_PLY
u_h2:           .res MAX_PLY
u_h3:           .res MAX_PLY
u_ph0:          .res MAX_PLY    ; pawn hash
u_ph1:          .res MAX_PLY
u_ph2:          .res MAX_PLY

; is the side to move in check, per ply (maintained by make_move)
chk_flag:       .res MAX_PLY + 1

; scratch
v_p:            .res 1          ; validate_move
v_t:            .res 1
v_d:            .res 1
v_fwd:          .res 1
v_step:         .res 1
v_promo:        .res 1
m_k:            .res 1
m_kind:         .res 1
m_step:         .res 1
m_capsq:        .res 1
m_piece:        .res 1
m_mover:        .res 1
m_from:         .res 1
m_to:           .res 1
m_flags:        .res 1
m_rook:         .res 1
a_by:           .res 1
a_n:            .res 1
a_b:            .res 1
a_r:            .res 1
a_q:            .res 1
a_k:            .res 1
g_caps:         .res 1
g_n:            .res 1
g_them:         .res 1
g_fwd:          .res 1
g_start:        .res 1
g_last:         .res 1
g_sq:           .res 1
g_to:           .res 1
g_step:         .res 1
g_di:           .res 1
g_dend:         .res 1
g_slide:        .res 1
r_n:            .res 1
sh_cover:       .res 1
sh_pen:         .res 1
sh_base:        .res 1
sh_i:           .res 1
sh_fmax:        .res 1
mp_c:           .res 1
mp_d:           .res 1
mp_t:           .res 1

;--------------------------------------------------------------------------
        .segment "RODATA"

sq64tab:
        .repeat 128, I
        .byte ((I + (I & 7)) >> 1) & $3F
        .endrep

; Zobrist and piece-square table page per piece code
zpage:  .byte 0, ZOB_PAGE+0, ZOB_PAGE+1, ZOB_PAGE+2, ZOB_PAGE+3, ZOB_PAGE+4, ZOB_PAGE+5, 0
        .byte 0, ZOB_PAGE+6, ZOB_PAGE+7, ZOB_PAGE+8, ZOB_PAGE+9, ZOB_PAGE+10, ZOB_PAGE+11, 0
ppage:  .byte 0, PSQ_PAGE+1, PSQ_PAGE+2, PSQ_PAGE+3, PSQ_PAGE+4, PSQ_PAGE+5, PSQ_PAGE+6, 0
        .byte 0, PSQ_PAGE+1, PSQ_PAGE+2, PSQ_PAGE+3, PSQ_PAGE+4, PSQ_PAGE+5, PSQ_PAGE+6, 0
colour: .byte 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1

; piece values per type (non-pawn material)
val_lo: .byte 0, <100, <320, <330, <500, <900, 0
val_hi: .byte 0, >100, >320, >330, >500, >900, 0

bitrank:  .byte $01, $02, $04, $08, $10, $20, $40, $80
nbitrank: .byte $FE, $FD, $FB, $F7, $EF, $DF, $BF, $7F

knight_off: .byte 33, 31, 18, 14, <-33, <-31, <-18, <-14
king_off:   .byte 1, <-1, 16, <-16, 17, 15, <-17, <-15
; generator directions: orthogonal 0-3, diagonal 4-7, knight 8-15
dir_off:    .byte 1, <-1, 16, <-16, 17, 15, <-17, <-15
            .byte 33, 31, 18, 14, <-33, <-31, <-18, <-14
diag_off    = dir_off + 4
orth_off    = dir_off
; per piece type: first direction, end, sliding
dir_first:  .byte 0, 0, 8, 4, 0, 0, 0
dir_end:    .byte 0, 0, 16, 8, 4, 8, 8
dir_slide:  .byte 0, 0, 0, 1, 1, 1, 0
; pawn structure tables
popcount:
        .repeat 256, I
        .byte (I & 1) + ((I >> 1) & 1) + ((I >> 2) & 1) + ((I >> 3) & 1) + ((I >> 4) & 1) + ((I >> 5) & 1) + ((I >> 6) & 1) + ((I >> 7) & 1)
        .endrep
highbit:                        ; highest set bit (rank of white's front pawn)
        .byte 0
        .repeat 255, I
        .byte 7 - ((I+1) < $80) - ((I+1) < $40) - ((I+1) < $20) - ((I+1) < $10) - ((I+1) < $08) - ((I+1) < $04) - ((I+1) < $02)
        .endrep
lowbit:                         ; lowest set bit (rank of black's front pawn)
        .byte 0
        .repeat 255, I
        .byte ((((I+1) & $01) = 0) + (((I+1) & $03) = 0) + (((I+1) & $07) = 0) + (((I+1) & $0F) = 0) + (((I+1) & $1F) = 0) + (((I+1) & $3F) = 0) + (((I+1) & $7F) = 0)) & 7
        .endrep
above:  .byte $FE, $FC, $F8, $F0, $E0, $C0, $80, $00   ; ranks in front of white
below:  .byte $00, $01, $03, $07, $0F, $1F, $3F, $7F   ; ranks in front of black
times12: .byte 0, 12, 24, 36, 48, 60, 72, 84, 96
passed_bonus: .byte 0, 10, 15, 25, 40, 65, 100, 0

; attack vector kinds of a sliding piece type
slide_kind: .byte 0, 0, 0, ATT_DIAG, ATT_STRAIGHT, ATT_DIAG | ATT_STRAIGHT, 0, 0

;--------------------------------------------------------------------------
; store the move g_sq-g_to with flags A (inline version of emit)
.macro EMIT
        ldy g_n
        sta (mflp),y
        lda g_sq
        sta (mfp),y
        lda g_to
        sta (mtp),y
        inc g_n
.endmacro

;--------------------------------------------------------------------------
        .segment "CODE"

;
; Hash piece Y on square X into the position hash; keeps the first key
; half in z0lo/z0hi for the pawn hash.
;
hash_piece:
        lda zpage,y
        sta zptr+1
        stz zptr
        ldy sq64tab,x
        lda (zptr),y
        sta z0lo
        eor _hash_lo
        sta _hash_lo
        tya
        ora #$40
        tay
        lda (zptr),y
        sta z0hi
        eor _hash_lo+1
        sta _hash_lo+1
        tya
        eor #$C0
        tay
        lda (zptr),y
        sta z1lo
        eor _hash_hi
        sta _hash_hi
        tya
        ora #$40
        tay
        lda (zptr),y
        eor _hash_hi+1
        sta _hash_hi+1
        rts

;
; Put piece A on the empty square X and update all incremental terms.
;
piece_add:
        sta _bd,x
        sta t_p
        stx t_sq
        tay
        lda no_hash
        bne :+
        jsr hash_piece
:
        ldy t_p
        lda ppage,y
        sta zptr+1
        cpy #8
        jcs @black
        ldy t_sq                ; white: psq_score += psq[t][sq]
        clc
        lda (zptr),y
        adc _psq_score
        sta _psq_score
        tya
        ora #$80
        tay
        lda (zptr),y
        adc _psq_score+1
        sta _psq_score+1
        bra @kind
@black: lda t_sq                ; black: psq_score -= psq[t][sq ^ $70]
        eor #$70
        tay
        sec
        lda _psq_score
        sbc (zptr),y
        sta _psq_score
        tya
        ora #$80
        tay
        lda _psq_score+1
        sbc (zptr),y
        sta _psq_score+1
@kind:  ldy t_p
        ldx colour,y
        lda t_p
        and #7
        cmp #PAWN
        jeq @pawn
        cmp #KING
        jeq @king
        tay
        cpy #3
        bne :+
        inc _bishop_count,x
:       txa
        asl
        tax
        clc
        lda _npm,x
        adc val_lo,y
        sta _npm,x
        lda _npm+1,x
        adc val_hi,y
        sta _npm+1,x
        rts
@king:  lda t_sq
        sta _ksq,x
        rts
@pawn:  inc _pawn_count,x
        txa
        asl
        asl
        asl
        sta tmp
        lda t_sq
        and #7
        ora tmp
        tax
        lda t_sq
        lsr
        lsr
        lsr
        lsr
        tay
        lda bitrank,y
        ora _pawn_files,x
        sta _pawn_files,x
        lda no_hash
        jne @nopawnhash
        lda _pawn_hash
        eor z0lo
        sta _pawn_hash
        lda _pawn_hash+1
        eor z0hi
        sta _pawn_hash+1
        lda _pawn_hash2
        eor z1lo
        sta _pawn_hash2
@nopawnhash:
        rts

;
; Remove the piece on square X and update all incremental terms.
;
piece_remove:
        lda _bd,x
        sta t_p
        stx t_sq
        stz _bd,x
        tay
        lda no_hash
        bne :+
        jsr hash_piece
:
        ldy t_p
        lda ppage,y
        sta zptr+1
        cpy #8
        jcs @black
        ldy t_sq                ; white: psq_score -= psq[t][sq]
        sec
        lda _psq_score
        sbc (zptr),y
        sta _psq_score
        tya
        ora #$80
        tay
        lda _psq_score+1
        sbc (zptr),y
        sta _psq_score+1
        bra @kind
@black: lda t_sq                ; black: psq_score += psq[t][sq ^ $70]
        eor #$70
        tay
        clc
        lda (zptr),y
        adc _psq_score
        sta _psq_score
        tya
        ora #$80
        tay
        lda (zptr),y
        adc _psq_score+1
        sta _psq_score+1
@kind:  ldy t_p
        ldx colour,y
        lda t_p
        and #7
        cmp #PAWN
        jeq @pawn
        cmp #KING
        jeq @done
        tay
        cpy #3
        bne :+
        dec _bishop_count,x
:       txa
        asl
        tax
        sec
        lda _npm,x
        sbc val_lo,y
        sta _npm,x
        lda _npm+1,x
        sbc val_hi,y
        sta _npm+1,x
@done:  rts
@pawn:  dec _pawn_count,x
        txa
        asl
        asl
        asl
        sta tmp
        lda t_sq
        and #7
        ora tmp
        tax
        lda t_sq
        lsr
        lsr
        lsr
        lsr
        tay
        lda nbitrank,y
        and _pawn_files,x
        sta _pawn_files,x
        lda no_hash
        jne @nopawnhash
        lda _pawn_hash
        eor z0lo
        sta _pawn_hash
        lda _pawn_hash+1
        eor z0hi
        sta _pawn_hash+1
        lda _pawn_hash2
        eor z1lo
        sta _pawn_hash2
@nopawnhash:
        rts

;
; void board_put(uint8_t piece): put a piece on square mk_to
;
_board_put:
        ldx _mk_to
        jmp piece_add

;
; XOR the castling and en passant keys into the hash
;
hash_state:
        lda _castle
        asl
        tax
        lda _hash_lo
        eor _zob_castle_lo,x
        sta _hash_lo
        lda _hash_lo+1
        eor _zob_castle_lo+1,x
        sta _hash_lo+1
        lda _hash_hi
        eor _zob_castle_hi,x
        sta _hash_hi
        lda _hash_hi+1
        eor _zob_castle_hi+1,x
        sta _hash_hi+1
        lda _ep
        jmi @done
        and #7
        asl
        tax
        lda _hash_lo
        eor _zob_ep_lo,x
        sta _hash_lo
        lda _hash_lo+1
        eor _zob_ep_lo+1,x
        sta _hash_lo+1
        lda _hash_hi
        eor _zob_ep_hi,x
        sta _hash_hi
        lda _hash_hi+1
        eor _zob_ep_hi+1,x
        sta _hash_hi+1
@done:  rts

hash_side:
        lda _hash_lo
        eor _zob_side_lo
        sta _hash_lo
        lda _hash_lo+1
        eor _zob_side_lo+1
        sta _hash_lo+1
        lda _hash_hi
        eor _zob_side_hi
        sta _hash_hi
        lda _hash_hi+1
        eor _zob_side_hi+1
        sta _hash_hi+1
        rts

;
; XOR the castling / en passant keys that changed during the move of undo
; slot sply (equivalent to removing all old keys and adding all new ones)
;
update_state_hash:
        ldx _sply
        lda u_castle,x
        cmp _castle
        jeq @ep
        asl
        tay
        jsr xor_castle
        lda _castle
        asl
        tay
        jsr xor_castle
        ldx _sply
@ep:    lda u_ep,x
        cmp _ep
        jeq @done
        lda u_ep,x
        bmi :+
        jsr xor_ep
:       lda _ep
        jmi @done
        jmp xor_ep
@done:  rts

xor_castle:                     ; Y = 2 * castling rights
        lda _hash_lo
        eor _zob_castle_lo,y
        sta _hash_lo
        lda _hash_lo+1
        eor _zob_castle_lo+1,y
        sta _hash_lo+1
        lda _hash_hi
        eor _zob_castle_hi,y
        sta _hash_hi
        lda _hash_hi+1
        eor _zob_castle_hi+1,y
        sta _hash_hi+1
        rts

xor_ep:                         ; A = en passant square
        and #7
        asl
        tay
        lda _hash_lo
        eor _zob_ep_lo,y
        sta _hash_lo
        lda _hash_lo+1
        eor _zob_ep_lo+1,y
        sta _hash_lo+1
        lda _hash_hi
        eor _zob_ep_hi,y
        sta _hash_hi
        lda _hash_hi+1
        eor _zob_ep_hi+1,y
        sta _hash_hi+1
        rts

;
; Save the hash in the undo slot X and push it on the repetition list
;
save_hash:
        lda _pawn_hash
        sta u_ph0,x
        lda _pawn_hash+1
        sta u_ph1,x
        lda _pawn_hash2
        sta u_ph2,x
        lda _hash_lo
        sta u_h0,x
        lda _hash_lo+1
        sta u_h1,x
        lda _hash_hi
        sta u_h2,x
        lda _hash_hi+1
        sta u_h3,x
        ldy _rep_count
        lda _hash_lo
        sta REP0,y
        lda _hash_lo+1
        sta REP1,y
        lda _hash_hi
        sta REP2,y
        lda _hash_hi+1
        sta REP3,y
        inc _rep_count
        rts

restore_hash:
        lda u_ph0,x
        sta _pawn_hash
        lda u_ph1,x
        sta _pawn_hash+1
        lda u_ph2,x
        sta _pawn_hash2
        lda u_h0,x
        sta _hash_lo
        lda u_h1,x
        sta _hash_lo+1
        lda u_h2,x
        sta _hash_hi
        lda u_h3,x
        sta _hash_hi+1
        dec _rep_count
        rts

;
; uint8_t make_move(void): play mk_from-mk_to (mk_flags); returns 0 when
; the move leaves the own king in check (undo it anyway)
;
_make_move:
        ldx _sply
        lda _mk_from
        sta u_from,x
        lda _mk_to
        sta u_to,x
        lda _mk_flags
        sta u_flags,x
        and #F_EP
        jeq @noep
        lda _mk_from            ; en passant: the pawn beside the mover
        and #$F0
        sta tmp
        lda _mk_to
        and #$0F
        ora tmp
        bra @capsq
@noep:  lda _mk_to
@capsq: sta m_capsq
        tay
        lda _bd,y
        sta u_captured,x
        lda _castle
        sta u_castle,x
        lda _ep
        sta u_ep,x
        lda _fifty
        sta u_fifty,x
        jsr save_hash
        lda _stm
        sta m_mover

        ldx m_capsq
        lda _bd,x
        jeq @nocap
        jsr piece_remove
@nocap: ldx _mk_from
        lda _bd,x
        sta m_piece
        jsr piece_remove
        lda _mk_flags
        and #7
        jeq @nopromo
        ora _stm
        bra @put
@nopromo:
        lda m_piece
@put:   ldx _mk_to
        jsr piece_add

        lda _mk_flags
        and #F_CASTLE
        jeq @nocastle
        lda _mk_to
        cmp _mk_from
        jcc @queenside
        lda _mk_from            ; rook from+3 to from+1
        clc
        adc #3
        tax
        lda _bd,x
        ldx _mk_from
        inx
        jsr piece_add
        lda _mk_from
        clc
        adc #3
        tax
        jsr piece_remove
        bra @nocastle
@queenside:
        lda _mk_from            ; rook from-4 to from-1
        sec
        sbc #4
        tax
        lda _bd,x
        ldx _mk_from
        dex
        jsr piece_add
        lda _mk_from
        sec
        sbc #4
        tax
        jsr piece_remove
@nocastle:
        ldx _mk_from
        lda _castle_keep,x
        ldx _mk_to
        and _castle_keep,x
        and _castle
        sta _castle

        lda _mk_flags
        and #F_DOUBLE
        jeq @noep2
        lda _mk_from
        clc
        adc _mk_to
        lsr
        bra @setep
@noep2: lda #NO_SQ
@setep: sta _ep

        lda m_piece
        and #7
        cmp #PAWN
        jeq @zero
        ldx _sply
        lda u_captured,x
        jne @zero
        inc _fifty
        bra @fifty_done
@zero:  stz _fifty
@fifty_done:
        jsr update_state_hash
        lda _stm
        eor #8
        sta _stm
        jsr hash_side
        inc _sply

        ; Legality. A side that was not in check can only expose its king
        ; along a line through the from-square, unless the king itself
        ; moved or en passant removed a second piece.
        ldx _sply
        lda chk_flag-1,x
        jne @fulltest
        lda m_piece
        and #7
        cmp #KING
        jeq @fulltest
        lda _mk_flags
        and #(F_EP | F_CASTLE)
        jne @fulltest
        lda m_mover
        lsr
        lsr
        lsr
        tax
        lda _ksq,x
        sta m_k
        lda _mk_from            ; is the from-square on a line with the king?
        sec
        sbc m_k
        clc
        adc #119
        tax
        lda ATT_KINDS,x
        and #(ATT_DIAG | ATT_STRAIGHT)
        jeq @legal
        sta m_kind
        lda ATT_STEP,x
        sta m_step
        ldx m_k
@walk:  txa                     ; first piece seen from the king on that line
        clc
        adc m_step
        tax
        and #$88
        jne @legal
        lda _bd,x
        jeq @walk
        eor m_mover
        and #8
        jeq @legal              ; own piece
        lda _bd,x
        and #7
        cmp #QUEEN
        jeq @illegal
        cmp #BISHOP
        bne :+
        lda m_kind
        and #ATT_DIAG
        jne @illegal
        bra @legal
:       cmp #ROOK
        jne @legal
        lda m_kind
        and #ATT_STRAIGHT
        jne @illegal
        bra @legal

@fulltest:
        lda m_mover             ; is the mover's king attacked?
        lsr
        lsr
        lsr
        tax
        lda _ksq,x
        sta _att_sq
        lda _stm
        jsr _square_attacked
        cmp #0
        jne @illegal
@legal: jsr compute_check
        lda #1
        ldx #0
        rts
@illegal:
        lda #0
        tax
        rts

;
; After a legal move: does it give check? Stores chk_flag[sply].
; Direct check by the piece on mk_to, or discovered through mk_from;
; castling and en passant use the full test.
;
compute_check:
        lda _stm
        lsr
        lsr
        lsr
        tax
        lda _ksq,x
        sta m_k                 ; the king that may be in check
        lda _mk_flags
        and #(F_EP | F_CASTLE)
        beq :+
        jmp @full
:       lda m_k                 ; direct: piece on mk_to towards the king
        sec
        sbc _mk_to
        clc
        adc #119
        tax
        lda ATT_KINDS,x
        jeq @disc
        sta m_kind
        ldy _mk_to
        lda _bd,y
        and #7
        tay
        cpy #PAWN
        jne @notpawn
        lda m_mover
        bne :+
        lda m_kind
        and #ATT_WPAWN
        jne @check
        bra @disc
:       lda m_kind
        and #ATT_BPAWN
        jne @check
        bra @disc
@notpawn:
        cpy #KNIGHT
        jne @slider
        lda m_kind
        and #ATT_KNIGHT
        jne @check
        bra @disc
@slider:
        lda m_kind
        and slide_kind,y
        jeq @disc
        lda ATT_STEP,x
        sta m_step
        ldx _mk_to
@path:  txa                     ; squares up to the king must be empty
        clc
        adc m_step
        tax
        cpx m_k
        jeq @check
        lda _bd,x
        jeq @path

@disc:  lda _mk_from            ; discovered: a slider behind mk_from
        sec
        sbc m_k
        clc
        adc #119
        tax
        lda ATT_KINDS,x
        and #(ATT_DIAG | ATT_STRAIGHT)
        jeq @none
        sta m_kind
        lda ATT_STEP,x
        sta m_step
        ldx m_k
@walk:  txa
        clc
        adc m_step
        tax
        and #$88
        jne @none
        lda _bd,x
        jeq @walk
        eor m_mover
        and #8
        jne @none               ; a piece of the side in check blocks
        lda _bd,x
        and #7
        cmp #QUEEN
        jeq @check
        cmp #BISHOP
        bne :+
        lda m_kind
        and #ATT_DIAG
        jne @check
        bra @none
:       cmp #ROOK
        jne @none
        lda m_kind
        and #ATT_STRAIGHT
        jne @check
@none:  lda #0
        bra @store
@check: lda #1
@store: ldx _sply
        sta chk_flag,x
        rts
@full:  lda m_k
        sta _att_sq
        lda m_mover
        jsr _square_attacked
        bra @store

;
; void refresh_check(void): full check test of the current position
;
_refresh_check:
        lda _stm
        lsr
        lsr
        lsr
        tax
        lda _ksq,x
        sta _att_sq
        lda _stm
        eor #8
        jsr _square_attacked
        ldx _sply
        sta chk_flag,x
        rts

;
; void unmake_move(void)
;
_unmake_move:
        lda #1                  ; hashes come back from the undo record
        sta no_hash
        dec _sply
        ldx _sply
        lda _stm
        eor #8
        sta _stm
        lda u_from,x
        sta m_from
        lda u_to,x
        sta m_to
        lda u_flags,x
        sta m_flags
        and #7
        jeq @nopromo
        lda _stm
        ora #PAWN
        bra @have
@nopromo:
        ldy m_to
        lda _bd,y
@have:  sta m_piece
        ldx m_to
        jsr piece_remove
        lda m_piece
        ldx m_from
        jsr piece_add

        lda m_flags
        and #F_CASTLE
        jeq @nocastle
        lda m_to
        cmp m_from
        jcc @queenside
        ldx m_from              ; rook from+1 back to from+3
        inx
        lda _bd,x
        sta m_rook
        lda m_from
        clc
        adc #3
        tax
        lda m_rook
        jsr piece_add
        ldx m_from
        inx
        jsr piece_remove
        bra @nocastle
@queenside:
        ldx m_from              ; rook from-1 back to from-4
        dex
        lda _bd,x
        sta m_rook
        lda m_from
        sec
        sbc #4
        tax
        lda m_rook
        jsr piece_add
        ldx m_from
        dex
        jsr piece_remove
@nocastle:
        ldx _sply
        lda u_captured,x
        jeq @nocap
        sta m_rook
        lda m_flags
        and #F_EP
        jeq @plain
        lda m_from
        and #$F0
        sta tmp
        lda m_to
        and #$0F
        ora tmp
        bra @capsq
@plain: lda m_to
@capsq: tax
        lda m_rook
        jsr piece_add
@nocap: ldx _sply
        lda u_castle,x
        sta _castle
        lda u_ep,x
        sta _ep
        lda u_fifty,x
        sta _fifty
        stz no_hash
        jmp restore_hash

;
; void make_null(void) / void unmake_null(void)
;
_make_null:
        ldx _sply
        lda _ep
        sta u_ep,x
        jsr save_hash
        lda _ep
        jmi @noep
        and #7
        asl
        tax
        lda _hash_lo
        eor _zob_ep_lo,x
        sta _hash_lo
        lda _hash_lo+1
        eor _zob_ep_lo+1,x
        sta _hash_lo+1
        lda _hash_hi
        eor _zob_ep_hi,x
        sta _hash_hi
        lda _hash_hi+1
        eor _zob_ep_hi+1,x
        sta _hash_hi+1
        lda #NO_SQ
        sta _ep
@noep:  lda _stm
        eor #8
        sta _stm
        jsr hash_side
        inc _sply
        ldx _sply               ; the opponent cannot be in check
        stz chk_flag,x
        rts

_unmake_null:
        dec _sply
        ldx _sply
        lda _stm
        eor #8
        sta _stm
        lda u_ep,x
        sta _ep
        jmp restore_hash

;
; uint8_t is_repetition(void)
;
_is_repetition:
        lda _fifty
        cmp #4
        jcc @no
        cmp _rep_count
        bcc :+
        lda _rep_count
:       sta r_n                 ; n = min(fifty, rep_count)
        lda _rep_count
        sec
        sbc #2
        tay                     ; k = rep_count - i
        ldx #2                  ; i
@loop:  cpx r_n
        jeq @test
        jcs @no
@test:  lda REP0,y
        cmp _hash_lo
        jne @next
        lda REP1,y
        cmp _hash_lo+1
        jne @next
        lda REP2,y
        cmp _hash_hi
        jne @next
        lda REP3,y
        cmp _hash_hi+1
        jne @next
        lda #1
        ldx #0
        rts
@next:  dey
        dey
        inx
        inx
        bra @loop
@no:    lda #0
        tax
        rts

;
; uint8_t square_attacked(uint8_t by): is att_sq attacked by colour by?
;
_square_attacked:
        sta a_by
        ora #2                  ; target piece codes of colour by
        sta a_n
        lda a_by
        ora #3
        sta a_b
        lda a_by
        ora #4
        sta a_r
        lda a_by
        ora #5
        sta a_q
        lda a_by
        ora #KING
        sta a_k

        lda a_by
        jne @bpawns
        lda _att_sq             ; white pawns attack from sq-15 and sq-17
        sec
        sbc #15
        tax
        and #$88
        bne :+
        lda _bd,x
        cmp #PAWN
        jeq @found
:       lda _att_sq
        sec
        sbc #17
        tax
        and #$88
        jne @knights
        lda _bd,x
        cmp #PAWN
        jeq @found
        bra @knights
@found: lda #1                  ; (within branch range of the pawn tests)
        ldx #0
        rts
@bpawns:
        lda _att_sq             ; black pawns attack from sq+15 and sq+17
        clc
        adc #15
        tax
        and #$88
        bne :+
        lda _bd,x
        cmp #(8 | PAWN)
        jeq @found
:       lda _att_sq
        clc
        adc #17
        tax
        and #$88
        jne @knights
        lda _bd,x
        cmp #(8 | PAWN)
        jeq @found

@knights:
        ldy #7
@kloop: lda _att_sq
        clc
        adc knight_off,y
        tax
        and #$88
        bne :+
        lda _bd,x
        cmp a_n
        jeq @yes
:       lda _att_sq
        clc
        adc king_off,y
        tax
        and #$88
        bne :+
        lda _bd,x
        cmp a_k
        jeq @yes
:       dey
        jpl @kloop

        ldy #3                  ; diagonal rays: bishops and queens
@dray:  ldx _att_sq
@dstep: txa
        clc
        adc diag_off,y
        tax
        and #$88
        jne @dnext
        lda _bd,x
        jeq @dstep
        cmp a_b
        jeq @yes
        cmp a_q
        jeq @yes
@dnext: dey
        jpl @dray

        ldy #3                  ; straight rays: rooks and queens
@oray:  ldx _att_sq
@ostep: txa
        clc
        adc orth_off,y
        tax
        and #$88
        jne @onext
        lda _bd,x
        jeq @ostep
        cmp a_r
        jeq @yes
        cmp a_q
        jeq @yes
@onext: dey
        jpl @oray
        lda #0
        tax
        rts
@yes:   lda #1
        ldx #0
        rts

;
; uint8_t in_check(void): is the side to move in check?
;
_in_check:
        ldx _sply
        lda chk_flag,x
        ldx #0
        rts

;
; Store the move g_sq-g_to with flags A
;
emit:   ldy g_n
        sta (mflp),y
        lda g_sq
        sta (mfp),y
        lda g_to
        sta (mtp),y
        inc g_n
        rts

;
; Pawn capture (or en passant) to square A
;
pawn_capture:
        sta g_to
        tax
        and #$88
        jne @done
        lda _bd,x
        jeq @ep
        eor _stm
        and #8
        jeq @done               ; own piece
        lda g_to
        lsr
        lsr
        lsr
        lsr
        cmp g_last
        jne @plain
        lda #(F_CAPTURE | 5)
        jsr emit
        lda g_caps
        jne @done
        lda #(F_CAPTURE | 4)
        jsr emit
        lda #(F_CAPTURE | 3)
        jsr emit
        lda #(F_CAPTURE | 2)
        jmp emit
@plain: lda #F_CAPTURE
        jmp emit
@ep:    lda g_to
        cmp _ep
        jne @done
        lda #(F_CAPTURE | F_EP)
        jmp emit
@done:  rts

;
; Are squares A, X and Y safe from the opponent (castling path)? Carry
; clear when safe.
;
castle_safe:
        sta g_to
        stx g_step
        sty g_di
        lda g_to
        sta _att_sq
        lda g_them
        jsr _square_attacked
        lsr                     ; A = 1 when attacked (flags are from ldx)
        jcs @unsafe
        lda g_step
        sta _att_sq
        lda g_them
        jsr _square_attacked
        lsr                     ; A = 1 when attacked (flags are from ldx)
        jcs @unsafe
        lda g_di
        sta _att_sq
        lda g_them
        jsr _square_attacked
        lsr                     ; A = 1 when attacked (flags are from ldx)
        jcs @unsafe
        clc
        rts
@unsafe:
        sec
        rts

;
; uint16_t generate_moves(uint8_t captures_only)
;
_generate_moves:
        sta g_caps
        lda _ms_top+1           ; move stack full: no moves
        cmp #>MS_LIMIT
        jcc @room
        jne @full
        lda _ms_top
        cmp #<(MS_LIMIT+1)
        jcc @room
@full:  lda _ms_top
        ldx _ms_top+1
        rts
@room:  clc
        lda #<_mv_from
        adc _ms_top
        sta mfp
        lda #>_mv_from
        adc _ms_top+1
        sta mfp+1
        clc
        lda #<_mv_to
        adc _ms_top
        sta mtp
        lda #>_mv_to
        adc _ms_top+1
        sta mtp+1
        clc
        lda #<_mv_flags
        adc _ms_top
        sta mflp
        lda #>_mv_flags
        adc _ms_top+1
        sta mflp+1
        stz g_n

        lda _stm
        eor #8
        sta g_them
        lda _stm
        jeq @white
        lda #$F0
        sta g_fwd
        lda #6
        sta g_start
        stz g_last
        bra @scan
@white: lda #$10
        sta g_fwd
        lda #1
        sta g_start
        lda #7
        sta g_last
@scan:  stz g_sq

@square:
        ldx g_sq
        lda _bd,x
        jeq @next
        tay
        eor _stm
        and #8
        jne @next               ; opponent's piece
        tya
        and #7
        cmp #PAWN
        jeq @pawn
        jmp @piece

@next:  inc g_sq
        lda g_sq
        bit #8
        beq :+
        clc
        adc #8
        sta g_sq
:       bpl @square
        jmp @castling

@pawn:  lda g_sq
        clc
        adc g_fwd
        sta g_to
        tax
        lda _bd,x
        jne @pcaps              ; blocked
        lda g_to
        lsr
        lsr
        lsr
        lsr
        cmp g_last
        jne @push
        lda #5                  ; promotions
        EMIT
        lda g_caps
        jne @pcaps
        lda #4
        EMIT
        lda #3
        EMIT
        lda #2
        EMIT
        bra @pcaps
@push:  lda g_caps
        jne @pcaps
        lda #0
        EMIT
        lda g_sq
        lsr
        lsr
        lsr
        lsr
        cmp g_start
        jne @pcaps
        lda g_to
        clc
        adc g_fwd
        sta g_to
        tax
        lda _bd,x
        jne @pcaps
        lda #F_DOUBLE
        EMIT
@pcaps: lda g_sq
        clc
        adc g_fwd
        dec a
        jsr pawn_capture
        lda g_sq
        clc
        adc g_fwd
        inc a
        jsr pawn_capture
        jmp @next

@piece: tax                     ; A = piece type
        lda dir_first,x
        sta g_di
        lda dir_end,x
        sta g_dend
        lda dir_slide,x
        sta g_slide
@dir:   ldy g_di
        lda dir_off,y
        sta g_step
        lda g_sq
        sta g_to
@ray:   lda g_to
        clc
        adc g_step
        sta g_to
        tax
        and #$88
        jne @nextdir
        lda _bd,x
        jne @hit
        lda g_caps
        bne :+
        lda #0
        EMIT
:       lda g_slide
        jne @ray
        bra @nextdir
@hit:   eor _stm
        and #8
        jeq @nextdir            ; own piece
        lda #F_CAPTURE
        EMIT
@nextdir:
        inc g_di
        lda g_di
        cmp g_dend
        jne @dir
        jmp @next

@castling:
        lda g_caps
        beq :+
        jmp @finish
:       lda _stm
        jne @bcastle
        lda _castle             ; white king side
        and #1
        jeq @wq
        lda _bd+$05
        ora _bd+$06
        jne @wq
        lda #$04
        ldx #$05
        ldy #$06
        jsr castle_safe
        jcs @wq
        lda #$04
        sta g_sq
        lda #$06
        sta g_to
        lda #F_CASTLE
        EMIT
@wq:    lda _castle             ; white queen side
        and #2
        jeq @finish
        lda _bd+$01
        ora _bd+$02
        ora _bd+$03
        jne @finish
        lda #$04
        ldx #$03
        ldy #$02
        jsr castle_safe
        jcs @finish
        lda #$04
        sta g_sq
        lda #$02
        sta g_to
        lda #F_CASTLE
        EMIT
        jmp @finish
@bcastle:
        lda _castle             ; black king side
        and #4
        jeq @bq
        lda _bd+$75
        ora _bd+$76
        jne @bq
        lda #$74
        ldx #$75
        ldy #$76
        jsr castle_safe
        jcs @bq
        lda #$74
        sta g_sq
        lda #$76
        sta g_to
        lda #F_CASTLE
        EMIT
@bq:    lda _castle             ; black queen side
        and #8
        jeq @finish
        lda _bd+$71
        ora _bd+$72
        ora _bd+$73
        jne @finish
        lda #$74
        ldx #$73
        ldy #$72
        jsr castle_safe
        jcs @finish
        lda #$74
        sta g_sq
        lda #$72
        sta g_to
        lda #F_CASTLE
        EMIT

@finish:
        clc
        lda _ms_top
        adc g_n
        sta _ms_top
        lda _ms_top+1
        adc #0
        sta _ms_top+1
        tax
        lda _ms_top
        rts

;
; Evaluation helpers: add / subtract a signed or unsigned byte to e_s
;
add_s8: ldx #0
        cmp #$80
        bcc :+
        dex
:       clc
        adc e_s
        sta e_s
        txa
        adc e_s+1
        sta e_s+1
        rts

sub_s8: sta tmp
        ldx #0
        cmp #$80
        bcc :+
        dex
:       sec
        lda e_s
        sbc tmp
        sta e_s
        stx tmp
        lda e_s+1
        sbc tmp
        sta e_s+1
        rts

add_u8: clc
        adc e_s
        sta e_s
        bcc :+
        inc e_s+1
:       rts

sub_u8: sta tmp
        sec
        lda e_s
        sbc tmp
        sta e_s
        bcs :+
        dec e_s+1
:       rts

;
; Pawn shelter penalty of colour X (0/1) in A
;
shelter:
        lda _ksq,x
        lsr
        lsr
        lsr
        lsr
        cpx #0
        jne @black
        cmp #2
        jcs @zero
        lda #$06
        bra @go
@black: cmp #6
        jcc @zero
        lda #$60
@go:    sta sh_cover
        stz sh_pen
        txa
        asl
        asl
        asl
        sta sh_base
        lda _ksq,x
        and #7
        sta sh_i
        inc a
        sta sh_fmax             ; f + 1
        lda sh_i
        jeq @loop
        dec sh_i                ; start at f - 1
@loop:  lda sh_i
        cmp #8
        jcs @done
        cmp sh_fmax
        beq :+
        jcs @done
:       ora sh_base
        tay
        lda _pawn_files,y
        and sh_cover
        bne :+
        lda sh_pen
        clc
        adc #15
        sta sh_pen
:       inc sh_i
        bra @loop
@done:  lda sh_pen
        rts
@zero:  lda #0
        rts

;
; Mop-up bonus in A: X = losing king, Y = winning king
;
mop_up: lda _center_dist,x
        sta mp_c
        txa
        and #7
        sta tmp
        tya
        and #7
        sec
        sbc tmp
        bcs :+
        eor #$FF
        inc a
:       sta mp_d                ; |file difference|
        txa
        lsr
        lsr
        lsr
        lsr
        sta tmp
        tya
        lsr
        lsr
        lsr
        lsr
        sec
        sbc tmp
        bcs :+
        eor #$FF
        inc a
:       clc
        adc mp_d                ; + |rank difference|
        sta mp_d
        lda #14
        sec
        sbc mp_d
        asl
        asl
        sta mp_t                ; 4 * (14 - distance)
        lda mp_c
        asl
        sta tmp
        asl
        asl
        clc
        adc tmp                 ; 10 * centre distance
        clc
        adc mp_t
        rts

;
; uint8_t validate_move(void): flags of the pseudo-legal move mk_from-mk_to
; with promotion piece mk_flags (bits 0-2), or $FF. Produces exactly the
; flags generate_moves() would give the move.
;
_validate_move:
        lda _mk_from
        ora _mk_to
        and #$88
        jne @bad
        lda _mk_flags
        and #7
        sta v_promo
        ldx _mk_from
        lda _bd,x
        jeq @bad
        sta v_p
        eor _stm
        and #8
        jne @bad                ; not the side to move's piece
        ldy _mk_to
        lda _bd,y
        sta v_t
        beq :+
        eor _stm
        and #8
        jeq @bad                ; own piece on the target
:       lda _mk_to
        sec
        sbc _mk_from
        sta v_d
        clc
        adc #119
        tax                     ; attack vector index
        lda v_p
        and #7
        cmp #PAWN
        jeq @pawn
        tay
        lda v_promo             ; only pawns promote
        jne @bad
        cpy #KING
        beq @king
        cpy #KNIGHT
        bne @slider
        lda ATT_KINDS,x
        and #ATT_KNIGHT
        jeq @bad
        bra @plain
@slider:
        lda ATT_KINDS,x
        and slide_kind,y
        jeq @bad
        lda ATT_STEP,x
        sta v_step
        lda _mk_from
@path:  clc                     ; the squares in between must be empty
        adc v_step
        cmp _mk_to
        beq @plain
        tay
        lda _bd,y
        jne @bad
        tya
        bra @path
@plain: lda v_t
        beq :+
        lda #F_CAPTURE
:       ldx #0
        rts

@king:  lda ATT_KINDS,x
        and #ATT_KING
        bne @plain
        lda #$04                ; castling from e1 / e8
        ldx _stm
        beq :+
        lda #$74
:       cmp _mk_from
        jne @bad
        lda v_d
        cmp #2
        beq @kside
        cmp #<-2
        jne @bad
        lda _stm                ; queen side: rights, b/c/d empty, e/d/c safe
        beq :+
        lda #8
        bra :++
:       lda #2
:       and _castle
        jeq @bad
        ldx _mk_from
        lda _bd-1,x
        ora _bd-2,x
        ora _bd-3,x
        jne @bad
        lda _stm
        eor #8
        sta g_them
        lda _mk_from
        tax
        dex
        txa
        tay
        dey
        lda _mk_from
        jsr castle_safe
        jcs @bad
        lda #F_CASTLE
        ldx #0
        rts
@kside: lda _stm                ; king side: rights, f/g empty, e/f/g safe
        beq :+
        lda #4
        bra :++
:       lda #1
:       and _castle
        jeq @bad
        ldx _mk_from
        lda _bd+1,x
        ora _bd+2,x
        jne @bad
        lda _stm
        eor #8
        sta g_them
        lda _mk_from
        tax
        inx
        txa
        tay
        iny
        lda _mk_from
        jsr castle_safe
        jcs @bad
        lda #F_CASTLE
        ldx #0
        rts

@pawn:  lda _stm
        beq :+
        lda #$F0
        bra :++
:       lda #$10
:       sta v_fwd
        lda v_d
        cmp v_fwd
        beq @push
        lda v_fwd
        asl
        cmp v_d
        beq @double
        lda v_fwd
        dec a
        cmp v_d
        beq @pcapture
        lda v_fwd
        inc a
        cmp v_d
        beq @pcapture
@bad:   lda #$FF
        ldx #0
        rts
@push:  lda v_t
        bne @bad
        jmp promotion
@double:
        lda v_t
        bne @bad
        lda v_promo
        bne @bad
        lda _mk_from            ; from the pawn's start rank
        lsr
        lsr
        lsr
        lsr
        ldx _stm
        beq :+
        eor #7                  ; black: rank 6 -> 1
:       cmp #1
        bne @bad
        lda _mk_from
        clc
        adc v_fwd
        tax
        lda _bd,x
        bne @bad
        lda #F_DOUBLE
        ldx #0
        rts
@pcapture:
        lda v_t
        beq :+
        jsr promotion
        cmp #$FF
        beq @bad
        ora #F_CAPTURE
        ldx #0
        rts
:       lda _mk_to              ; en passant
        cmp _ep
        bne @bad
        lda v_promo
        bne @bad
        lda #(F_CAPTURE | F_EP)
        ldx #0
        rts

;
; Pawn move to mk_to: the promotion piece must be given exactly on the last
; rank; returns it (or $FF) in A
;
promotion:
        lda _mk_to
        lsr
        lsr
        lsr
        lsr
        ldx _stm
        beq :+
        eor #7                  ; black: rank 0 -> 7
:       cmp #7
        bne @noprom
        lda v_promo
        cmp #KNIGHT
        bcc @bad
        cmp #QUEEN+1
        bcs @bad
        ldx #0
        rts
@noprom:
        lda v_promo
        bne @bad
        ldx #0
        rts
@bad:   lda #$FF
        ldx #0
        rts

;
; int16_t pawn_structure_compute(void): doubled, isolated and passed pawns
; (C reference in engine_board.c); stores the result in the pawn cache
;
ps_f    = mp_c                  ; (scratch of mop_up, not used meanwhile)
ps_m    = mp_d
ps_r    = mp_t

_pawn_structure_compute:
        stz e_s                 ; e_s is saved by the caller
        stz e_s+1
        stz ps_f
@file:  ldx ps_f
        lda _pawn_files,x       ; white pawns on this file
        jeq @black
        sta ps_m
        tay
        lda popcount,y
        tay
        cpy #2                  ; doubled: -12 per extra pawn
        bcc :+
        lda times12-1,y
        jsr sub_u8
        ldy ps_m
        lda popcount,y
        tay
:       jsr neighbours_w        ; isolated: -12 per pawn
        bne :+
        lda times12,y
        jsr sub_u8
:       ldy ps_m                ; passed: no black pawn ahead on f-1..f+1
        lda highbit,y
        sta ps_r
        tay
        lda above,y
        jsr ahead_b
        jne @black
        ldy ps_r
        lda passed_bonus,y
        jsr add_u8
@black: ldx ps_f
        lda _pawn_files+8,x
        jeq @next
        sta ps_m
        tay
        lda popcount,y
        tay
        cpy #2
        bcc :+
        lda times12-1,y
        jsr add_u8
        ldy ps_m
        lda popcount,y
        tay
:       jsr neighbours_b
        bne :+
        lda times12,y
        jsr add_u8
:       ldy ps_m
        lda lowbit,y
        sta ps_r
        tay
        lda below,y
        jsr ahead_w
        jne @next
        lda #7
        sec
        sbc ps_r
        tay
        lda passed_bonus,y
        jsr sub_u8
@next:  inc ps_f
        lda ps_f
        cmp #8
        jne @file

        lda #PAWN_BANK          ; store in the cache
        sta RAM_BANK
        lda _pawn_hash+1
        and #7
        ora #$A0
        sta pcp+1
        stz pcp
        ldy _pawn_hash
        lda _pawn_hash2
        sta (pcp),y
        lda pcp+1
        ora #$08
        sta pcp+1
        lda _pawn_hash+1
        sta (pcp),y
        lda pcp+1
        eor #$18
        sta pcp+1
        lda e_s
        sta (pcp),y
        lda pcp+1
        ora #$08
        sta pcp+1
        lda e_s+1
        sta (pcp),y
        lda #ENGINE_BANK
        sta RAM_BANK
        lda e_s
        ldx e_s+1
        rts

; Z clear when a neighbouring file (ps_f +- 1) has a white / black pawn
; (preserves Y)
neighbours_w:
        lda #0
        ldx ps_f
        beq :+
        lda _pawn_files-1,x
:       cpx #7
        beq :+
        ora _pawn_files+1,x
:       cmp #0
        rts
neighbours_b:
        lda #0
        ldx ps_f
        beq :+
        lda _pawn_files+8-1,x
:       cpx #7
        beq :+
        ora _pawn_files+8+1,x
:       cmp #0
        rts

; Z clear when the opponent has a pawn in mask A on files ps_f-1..ps_f+1
ahead_b:
        sta tmp
        ldx ps_f
        lda _pawn_files+8,x
        cpx #0
        beq :+
        ora _pawn_files+8-1,x
:       cpx #7
        beq :+
        ora _pawn_files+8+1,x
:       and tmp
        rts
ahead_w:
        sta tmp
        ldx ps_f
        lda _pawn_files,x
        cpx #0
        beq :+
        ora _pawn_files-1,x
:       cpx #7
        beq :+
        ora _pawn_files+1,x
:       and tmp
        rts

;
; int16_t evaluate(void): static evaluation, side to move's view
;
_evaluate:
        lda _psq_score
        sta e_s
        lda _psq_score+1
        sta e_s+1

        clc                     ; endgame when npm[0] + npm[1] <= 1300
        lda _npm
        adc _npm+2
        tax
        lda _npm+1
        adc _npm+3
        cmp #>1300
        jcc @endgame
        jne @middlegame
        cpx #<(1300+1)
        jcs @middlegame

@endgame:
        ldx _ksq
        lda _king_endgame,x
        jsr add_s8
        lda _ksq+1
        eor #$70
        tax
        lda _king_endgame,x
        jsr sub_s8
        lda _pawn_count+1       ; s > 200 and black has no pawns
        jne @mop2
        sec
        lda e_s
        sbc #201
        lda e_s+1
        sbc #0
        jmi @mop2
        ldx _ksq+1
        ldy _ksq
        jsr mop_up
        jsr add_u8
@mop2:  lda _pawn_count         ; s < -200 and white has no pawns
        jne @common
        clc
        lda e_s
        adc #200
        lda e_s+1
        adc #0
        jpl @common
        ldx _ksq
        ldy _ksq+1
        jsr mop_up
        jsr sub_u8
        bra @common

@middlegame:
        ldx #1
        jsr shelter
        jsr add_u8
        ldx #0
        jsr shelter
        jsr sub_u8

@common:
        lda _bishop_count
        cmp #2
        bcc :+
        lda #30
        jsr add_u8
:       lda _bishop_count+1
        cmp #2
        bcc :+
        lda #30
        jsr sub_u8
:       lda #PAWN_BANK          ; pawn structure from the cache
        sta RAM_BANK
        lda _pawn_hash+1        ; entry pawn_hash & 2047
        and #7
        ora #$A0
        sta pcp+1
        stz pcp
        ldy _pawn_hash
        lda (pcp),y
        cmp _pawn_hash2
        jne @miss
        lda pcp+1
        ora #$08
        sta pcp+1
        lda (pcp),y
        cmp _pawn_hash+1
        jne @miss
        lda pcp+1
        eor #$18                ; $A8.. -> $B0..: value low byte
        sta pcp+1
        clc
        lda (pcp),y
        adc e_s
        sta e_s
        lda pcp+1
        ora #$08
        sta pcp+1
        lda (pcp),y
        adc e_s+1
        sta e_s+1
        lda #ENGINE_BANK
        sta RAM_BANK
        bra @side
@miss:  lda #ENGINE_BANK
        sta RAM_BANK
        lda e_s+1               ; the pawn evaluation uses e_s itself
        pha
        lda e_s
        pha
        jsr _pawn_structure_compute
        pla
        clc
        adc e_s
        sta e_s
        pla
        adc e_s+1
        sta e_s+1

@side:  lda _stm
        jeq @plus
        sec
        lda #0
        sbc e_s
        sta e_s
        lda #0
        sbc e_s+1
        sta e_s+1
@plus:  clc                     ; tempo bonus
        lda e_s
        adc #10
        pha
        lda e_s+1
        adc #0
        tax
        pla
        rts
