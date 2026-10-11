; Resident entries keep the caller's RAM bank and fastcall A argument intact.
.export _playfield_mouse, _playfield_cancel_drag
.import _playfield_drag_mouse, _playfield_drag_stop
.segment "CODE"
.macro banked_entry name, target
        .export name
        .import target
name:
        tay
        lda $00
        pha
        lda #23
        sta $00
        tya
        jsr target
        pla
        sta $00
        rts
.endmacro
banked_entry _playfield_new, _playfield_new_banked
banked_entry _playfield_resume, _playfield_resume_banked
banked_entry _playfield_loaded, _playfield_loaded_banked
banked_entry _playfield_tick, _playfield_tick_banked
banked_entry _playfield_update, _playfield_update_banked
banked_entry _playfield_key, _playfield_key_banked
banked_entry _demo_poll, _playfield_demo_poll
banked_entry _dialog_build_rules, _dialog_build_rules_banked
_playfield_mouse:
        tay
        lda $00
        pha
        lda #23
        sta $00
        tya
        jsr _playfield_drag_mouse
        pla
        sta $00
        rts
_playfield_cancel_drag:
        lda $00
        pha
        lda #23
        sta $00
        jsr _playfield_drag_stop
        pla
        sta $00
        rts

; Menu hint formatting shares bank 23 to leave room in the menu bank.
.export _start_draw_time
.import _menu_draw_time
_start_draw_time:
        tay
        lda $00
        pha
        lda #23
        sta $00
        tya
        jsr _menu_draw_time
        pla
        sta $00
        rts

.export _gui_mouse_hit
.import _menu_mouse_hit
_gui_mouse_hit:
        tay
        lda $00
        pha
        lda #23
        sta $00
        tya
        jsr _menu_mouse_hit
        tay
        pla
        sta $00
        tya
        rts
