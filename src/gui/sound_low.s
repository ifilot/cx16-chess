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
; Resident audio routines around ZSMKit. Music plays on ZSMKit priority 0
; and sound effects on priority 1. Every routine restores the caller's
; RAM bank ($00).
;
.import zsm_init_engine, zsmkit_setisr, zsm_setmem, zsm_setloop, zsm_play, zsm_setatten
.import _sound_ready, _sound_effects_enabled, _sound_dispatch
.export _sound_engine_init, _sound_music, _sound_sfx, _sound_event, _sound_music_volume
.export _bank_load_raw
.export _sound_effects_volume
.segment "CODE"

;------------------------------------------------------------------------------
; ROUTINE _bank_load_raw
;
; uint8_t __fastcall__ bank_load_raw(uint8_t bank) loads the file set up
; with SETNAM/SETLFS headerless into banked RAM, starting at $A000 of
; `bank` (in A). KERNAL LOAD continues into the next bank at $C000.
; Returns 1 on success and 0 on failure. KERNAL LOAD reports failure in
; carry, regardless of its returned address.
;------------------------------------------------------------------------------
_bank_load_raw:
        tay
        lda $00
        pha
        sty $00                 ; first bank to fill
        lda #0                  ; LOAD, not VERIFY
        ldx #<$A000
        ldy #>$A000
        jsr $FFD5               ; LOAD
        lda #0
        bcs load_failed
        inc a
load_failed:
        tay
        pla
        sta $00
        tya
        rts

;------------------------------------------------------------------------------
; ROUTINE _sound_event
;
; void __fastcall__ sound_event(uint8_t event) runs sound_dispatch() in
; audio bank 45. Events other than SOUND_INIT (0) are ignored until
; sound_ready is set.
;------------------------------------------------------------------------------
_sound_event:
        cmp #0
        beq dispatch            ; SOUND_INIT always runs
        ldx _sound_ready
        beq done
dispatch:
        tay
        lda $00
        pha
        lda #45
        sta $00
        tya
        jsr _sound_dispatch
        pla
        sta $00
done:   rts

;------------------------------------------------------------------------------
; ROUTINE _sound_engine_init
;
; void sound_engine_init(void) starts ZSMKit with its state in bank 44 and
; installs its interrupt handler, so playback continues during searches.
;------------------------------------------------------------------------------
_sound_engine_init:
        lda #44                 ; 23 holds the board GUI, 25 holds effects
        jsr zsm_init_engine
        jmp zsmkit_setisr

;------------------------------------------------------------------------------
; ROUTINE _sound_music
;
; void __fastcall__ sound_music(uint8_t bank) plays the ZSM track that
; starts at $A000 of RAM bank `bank` (in A) on priority 0. The loop offset
; in the ZSM header decides between looping and one-shot playback.
;------------------------------------------------------------------------------
_sound_music:
        tay
        lda $00
        pha
        sty $00
        lda #<$A000
        ldy #>$A000
        ldx #0                  ; priority 0: music
        jsr zsm_setmem
        ldx #0
        jsr zsm_play
        pla
        sta $00
        rts

;------------------------------------------------------------------------------
; ROUTINE _sound_sfx
;
; void __fastcall__ sound_sfx(uint16_t offset) plays the effect at header
; offset `offset` (A low, X high) within SFX.BIN in bank 25, on priority 1
; and never looping. Does nothing before sound_ready or with effects off.
;
; Hardware stack while calling zsm_setmem
;            +------------------+
;            | caller's bank    |
;            +------------------+
;  $0102,x ->| address low byte |
;            +------------------+
;------------------------------------------------------------------------------
_sound_sfx:
        ldy _sound_ready
        beq sfx_done
        ldy _sound_effects_enabled
        beq sfx_done
        clc
        adc #<$A000             ; address = $A000 + offset
        pha
        txa
        adc #>$A000
        tay                     ; Y = address high byte
        lda $00
        pha
        lda #25
        sta $00
        tsx
        lda $0102,x             ; A = address low byte
        ldx #1                  ; priority 1: effects
        jsr zsm_setmem
        ldx #1
        clc                     ; carry clear: do not loop
        jsr zsm_setloop
        ldx #1
        jsr zsm_play
        pla
        sta $00
        pla                     ; drop the address low byte
sfx_done: rts

;------------------------------------------------------------------------------
; ROUTINES _sound_music_volume, _sound_effects_volume
;
; void __fastcall__ sound_music_volume(uint8_t attenuation) and
; sound_effects_volume() set the attenuation (in A) of music or effects;
; 0 is full volume and 63 silent.
;------------------------------------------------------------------------------
_sound_music_volume:
        ldx #0
        jmp zsm_setatten
_sound_effects_volume:
        ldx #1
        jmp zsm_setatten
