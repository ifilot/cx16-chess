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
; Show paper and the centered native Loading label before any disk reads.
; ONCE constructors run before BSS clearing, so both this code and its bitmap
; are reclaimed as game state. The cover itself remains resident in VRAM.
;
; VRAM layout of the cover (see also transition.c):
;   $1E000  32x32 cover map, all tile 0
;   $1E800  tile 0: solid paper
;   $1EA00  64x16 Loading label, sprite 2
;
        .constructor boot_loading
        .export boot_loading_ready

VERA_ADDR_LO = $9F20
VERA_ADDR_MI = $9F21
VERA_ADDR_HI = $9F22
VERA_DATA = $9F23
VERA_CTRL = $9F25
VERA_VIDEO = $9F29

.segment "ONCE"

; Point data port 0 at $1<middle><low>, incrementing by one.
.macro address low, middle
        lda #low
        sta VERA_ADDR_LO
        lda #middle
        sta VERA_ADDR_MI
        lda #$11
        sta VERA_ADDR_HI
.endmacro

;------------------------------------------------------------------------------
; ROUTINE boot_loading
;
; Constructor: set up 640x480, the paper palette entries, the cover map,
; paper tile and Loading sprite, and show them on layer 0 and sprite 2.
;------------------------------------------------------------------------------
boot_loading:
        ; Disable an inherited KERNAL pointer before drawing/loading any art.
        ; Do not install its default bitmap in our layer-1 tile memory.
        lda #0
        ldx #0
        ldy #0
        jsr $FF68
        stz VERA_CTRL
        lda VERA_VIDEO
        and #$0F
        sta VERA_VIDEO
        lda #128
        sta $9F2A               ; 640x480, unscaled
        sta $9F2B
        stz $9F2C               ; black border
        ; Set just the paper, red ink and muted figurine palette entries.
        address $04, $FA
        lda #$DB
        sta VERA_DATA
        lda #$0E
        sta VERA_DATA
        address $E2, $FA
        lda #$11
        sta VERA_DATA
        lda #$09
        sta VERA_DATA
        address $A2, $FA
        lda #$75
        sta VERA_DATA
        lda #$09
        sta VERA_DATA
        address $00, $E0         ; blank, wrapping 32x32 cover map
        ldx #8
        ldy #0
clear_map:
        stz VERA_DATA
        iny
        bne clear_map
        dex
        bne clear_map
        address $00, $E8         ; one solid paper tile
        ldx #32
        lda #$22
paper:
        sta VERA_DATA
        dex
        bne paper
        address $00, $EA         ; 64x16 Loading sprite
        ldx #0
label:
        lda loading_pixels,x
        sta VERA_DATA
        inx
        bne label
label_second:
        lda loading_pixels + 256,x
        sta VERA_DATA
        inx
        bne label_second
        address $00, $FC         ; hide inherited KERNAL sprites
        ldx #4
        ldy #0
clear_sprites:
        stz VERA_DATA
        iny
        bne clear_sprites
        dex
        bne clear_sprites
        address $10, $FC
        ldx #0
attributes:
        lda loading_attributes,x
        sta VERA_DATA
        inx
        cpx #8
        bne attributes
        lda #$02
        sta $9F2D               ; layer 0, 32x32, 4bpp
        lda #$F0
        sta $9F2E               ; map $1E000
        lda #$F4
        sta $9F2F               ; tile $1E800, 8x8
        stz $9F30
        stz $9F31
        stz $9F32
        stz $9F33
        lda VERA_VIDEO
        ora #$50                ; paper and label, scene layers hidden
        sta VERA_VIDEO
boot_loading_ready:
        rts

; Sprite 2 attributes, copied to $1FC10
loading_attributes:
        .byte $50, $0F          ; image $1EA00, 4bpp
        .word 289, 232          ; visible ink centered at (320,240)
        .byte $0C, $77          ; front depth, 64x16, red palette

; Expand native 8x8 glyph bits to 4bpp, with four transparent pixels each side.
.macro glyph bits
        .repeat 4, pair
        .byte (((bits >> (7 - pair * 2)) & 1) << 4) | ((bits >> (6 - pair * 2)) & 1)
        .endrepeat
.endmacro
; One pixel row of the label: the seven letters of LOADING between margins.
.macro row letter_l, letter_o, letter_a, letter_d, letter_i, letter_n, letter_g
        .word 0
        glyph letter_l
        glyph letter_o
        glyph letter_a
        glyph letter_d
        glyph letter_i
        glyph letter_n
        glyph letter_g
        .word 0
.endmacro
; A one-pixel ink rule above or below the letters.
.macro rule
        .word 0
        .repeat 27
        .byte $11
        .endrepeat
        .byte $10, 0, 0         ; ink spans x=4..58
.endmacro
loading_pixels:
        .res 64, 0             ; rows 0..1
        rule                   ; row 2
        .res 64, 0             ; rows 3..4
        row $C0, $7C, $38, $F8, $7E, $C6, $7E
        row $C0, $C6, $6C, $CC, $18, $E6, $C0
        row $C0, $C6, $C6, $C6, $18, $F6, $C0
        row $C0, $C6, $C6, $C6, $18, $DE, $DE
        row $C0, $C6, $FE, $C6, $18, $CE, $C6
        row $C0, $C6, $C6, $CC, $18, $C6, $C6
        row $FE, $7C, $C6, $F8, $7E, $C6, $7E
        .res 64, 0             ; rows 12..13
        rule                   ; row 14
        .res 32, 0             ; row 15
        .assert * - loading_pixels = 512, error, "Loading sprite must be 64x16"
