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
; Resident entry points into board bank 23. Each entry saves the caller's
; RAM bank ($00), selects bank 23, calls the banked routine and restores
; the caller's bank. They keep the fastcall argument in A (and X) intact;
; further arguments are on the C stack and pass through untouched.
;
.export _playfield_mouse, _playfield_cancel_drag
.import _playfield_drag_mouse, _playfield_drag_stop
.segment "CODE"

;------------------------------------------------------------------------------
; MACRO banked_entry name, target
;
; Define the resident routine `name` that calls `target` in RAM bank 23.
; A is parked in Y while the bank is switched; X is not touched. The return
; value of `target` in A is lost, so only void routines use this macro.
;------------------------------------------------------------------------------
.macro banked_entry name, target
        .export name
        .import target
name:
        tay                     ; keep the fastcall argument
        lda $00
        pha                     ; save the caller's RAM bank
        lda #23
        sta $00
        tya
        jsr target
        pla
        sta $00                 ; restore the caller's RAM bank
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

;------------------------------------------------------------------------------
; ROUTINE _playfield_mouse
;
; void playfield_mouse(uint16_t x, uint16_t y, uint8_t buttons) calls
; playfield_drag_mouse() in bank 23. `buttons` is in A; x and y stay on the
; C stack for the callee.
;------------------------------------------------------------------------------
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

;------------------------------------------------------------------------------
; ROUTINE _playfield_cancel_drag
;
; void playfield_cancel_drag(void) calls playfield_drag_stop() in bank 23.
;------------------------------------------------------------------------------
_playfield_cancel_drag:
        lda $00
        pha
        lda #23
        sta $00
        jsr _playfield_drag_stop
        pla
        sta $00
        rts

;------------------------------------------------------------------------------
; ROUTINE _start_draw_time
;
; void start_draw_time(uint8_t white, uint8_t black, uint8_t players) calls
; menu_draw_time() in bank 23. Menu hint formatting shares bank 23 to leave
; room in the menu bank. `players` is in A; the rest is on the C stack.
;------------------------------------------------------------------------------
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

;------------------------------------------------------------------------------
; ROUTINE _gui_mouse_hit
;
; uint8_t gui_mouse_hit(uint16_t x, uint16_t y, uint8_t layout) calls
; menu_mouse_hit() in bank 23 and returns its result in A. `layout` is in
; A; x and y are on the C stack.
;------------------------------------------------------------------------------
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
        tay                     ; keep the result while restoring the bank
        pla
        sta $00
        tya
        rts
