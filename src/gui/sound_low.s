.import zsm_init_engine, zsmkit_setisr, zsm_setmem, zsm_setloop, zsm_play, zsm_setatten
.import _sound_ready, _sound_effects_enabled, _sound_dispatch
.export _sound_engine_init, _sound_music, _sound_sfx, _sound_event, _sound_music_volume
.export _sound_load_raw
.export _sound_effects_volume
.segment "CODE"

; KERNAL LOAD reports failure in carry, regardless of its returned address.
_sound_load_raw:
        tay
        lda $00
        pha
        sty $00
        lda #0
        ldx #<$A000
        ldy #>$A000
        jsr $FFD5
        lda #0
        bcs load_failed
        inc a
load_failed:
        tay
        pla
        sta $00
        tya
        rts

_sound_event:
        cmp #0
        beq dispatch
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

_sound_engine_init:
        lda #44                 ; 23 holds the board GUI, 25 holds effects
        jsr zsm_init_engine
        jmp zsmkit_setisr

; A is a RAM bank. Header loop offset controls loop/one-shot behavior.
_sound_music:
        tay
        lda $00
        pha
        sty $00
        lda #<$A000
        ldy #>$A000
        ldx #0
        jsr zsm_setmem
        ldx #0
        jsr zsm_play
        pla
        sta $00
        rts

; A/X is a header offset within SFX.BIN. Priority 1, never loop.
_sound_sfx:
        ldy _sound_ready
        beq sfx_done
        ldy _sound_effects_enabled
        beq sfx_done
        clc
        adc #<$A000
        pha
        txa
        adc #>$A000
        tay
        lda $00
        pha
        lda #25
        sta $00
        tsx
        lda $0102,x
        ldx #1
        jsr zsm_setmem
        ldx #1
        clc
        jsr zsm_setloop
        ldx #1
        jsr zsm_play
        pla
        sta $00
        pla
sfx_done: rts

_sound_music_volume:
        ldx #0
        jmp zsm_setatten
_sound_effects_volume:
        ldx #1
        jmp zsm_setatten
