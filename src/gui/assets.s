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
; Indexed CHESS.DAT loader. Device 8, data channel 2, command channel 15.
; Seek/open/validation code lives in bank 21. The reader stays resident so
; SQTILES can be loaded with RAM bank 20 active without executing banked code.
; Documented KERNAL APIs only: POSITION, MACPTR, ACPTR fallback.
;
; CHESS.DAT starts with a 16-byte build stamp that must match the stamp
; compiled into assets.inc, followed by the resources. assets.inc also
; holds the index: per resource a 32-bit file offset and a 16-bit length.
; Both channels stay open between resources until asset_close().
;
        .include "zeropage.inc"
        .macpack longbranch
        .repeat 26, letter
            .charmap $41+letter, $41+letter ; filenames/commands use ASCII
        .endrepeat
        .export _asset_prepare, _asset_read, _asset_stream, _asset_close
        .export asset_abort, asset_remaining, asset_count, asset_slot, asset_opened
        .export asset_stamp, asset_command, asset_address

.segment "BSS"
_asset_stream:  .res 1                  ; 1: write every byte to VERA DATA0
asset_remaining: .res 2                 ; bytes still to read
asset_address: .res 2                   ; destination of the next read
asset_count: .res 1                     ; bytes delivered by the last read
asset_slot: .res 1                      ; offset of the resource's index record
asset_opened: .res 1                    ; 1 while both channels are open
asset_stamp: .res 16                    ; build stamp read from the file
asset_command: .res 6                   ; "P", channel, 32-bit offset

.segment "CODE"

;------------------------------------------------------------------------------
; ROUTINE _asset_close
;
; void asset_close(void) closes the data and command channels, if open, so
; other code (saves, preferences) can use the drive.
;------------------------------------------------------------------------------
_asset_close:
        lda asset_opened
        beq close_done
        lda $01
        pha
        stz $01                 ; public KERNAL entry points are in ROM bank 0
        jsr $FFCC               ; CLRCHN
        lda #2
        jsr $FFC3               ; CLOSE data channel
        lda #15
        jsr $FFC3               ; CLOSE command channel
        stz asset_opened
        pla
        sta $01
close_done:
        rts

;------------------------------------------------------------------------------
; ROUTINE _asset_read
;
; uint8_t __fastcall__ asset_read(uint16_t address) reads the bytes left
; by asset_prepare() to `address` (A low, X high). With asset_stream set,
; every byte goes to the same address (VERA DATA0, $9F23). Returns 1 on
; success; on failure both channels are closed and 0 is returned.
;------------------------------------------------------------------------------
_asset_read:
        sta asset_address
        stx asset_address+1
        lda $01
        pha
        stz $01                 ; public KERNAL entry points are in ROM bank 0
read_next:
        lda asset_remaining
        ora asset_remaining+1
        beq read_done
        lda #255                ; never use A=0 (ROM may read up to 512 bytes)
        ldx asset_remaining+1
        bne request_ready
        lda asset_remaining
request_ready:
        pha
        lda _asset_stream
        lsr a                   ; C=1 writes repeatedly to VERA DATA0
        pla
        ldx asset_address
        ldy asset_address+1
        jsr $FF44               ; MACPTR may return a short successful read
        bcs read_single
        cpy #0                  ; request was at most 255 bytes
        bne asset_abort
        cpx #0
        beq asset_abort         ; prevent an endless loop on zero progress
        stx asset_count
        bra read_status
read_single:
        lda asset_address
        sta ptr1
        lda asset_address+1
        sta ptr1+1
        jsr $FFA5               ; ACPTR fallback for devices without MACPTR
        ldy #0
        sta (ptr1),y
        lda #1
        sta asset_count
read_status:
        jsr $FFB7               ; errors and premature EOF are failures
        bne asset_abort
        sec
        lda asset_remaining
        sbc asset_count
        sta asset_remaining
        lda asset_remaining+1
        sbc #0
        sta asset_remaining+1
        bcc asset_abort
        lda _asset_stream
        bne read_next
        clc
        lda asset_address
        adc asset_count
        sta asset_address
        bcc read_next
        inc asset_address+1
        bra read_next
read_done:
        jsr $FFCC               ; restore keyboard input after file I/O
        pla
        sta $01
        lda #1
        ldx #0
        rts
; Close both channels and return 0; the caller's ROM bank is on the stack.
asset_abort:
        jsr $FFCC
        lda #2
        jsr $FFC3
        lda #15
        jsr $FFC3
        stz asset_opened
        pla
        sta $01
        lda #0
        ldx #0
        rts

.segment "MENUCODE"

;------------------------------------------------------------------------------
; ROUTINE _asset_prepare
;
; uint8_t __fastcall__ asset_prepare(uint8_t resource) seeks to resource
; `resource` (an ASSET_* index, in A) and sets the byte count for
; asset_read(). The first call opens both channels and checks the build
; stamp. Returns 1 on success and 0 on failure.
;------------------------------------------------------------------------------
_asset_prepare:
        asl a                   ; index records are six bytes each
        sta asset_slot
        asl a
        clc
        adc asset_slot
        sta asset_slot
        lda $01
        pha
        stz $01
        lda asset_opened
        bne seek_resource
        lda #15
        ldx #8
        ldy #15
        jsr $FFBA               ; SETLFS command channel
        lda #0
        jsr $FFBD               ; SETNAM empty command
        jsr $FFC0               ; OPEN
        jcs prepare_failed
        lda #2
        ldx #8
        ldy #2
        jsr $FFBA
        lda #asset_name_end-asset_name
        ldx #<asset_name
        ldy #>asset_name
        jsr $FFBD
        jsr $FFC0
        jcs prepare_failed
        ldx #2
        jsr $FFC6               ; CHKIN data channel
        jcs prepare_failed
        stz _asset_stream
        lda #16
        sta asset_remaining
        stz asset_remaining+1
        lda #<asset_stamp
        ldx #>asset_stamp
        jsr _asset_read
        cmp #0
        jeq prepare_failed
        ldx #15
check_stamp:
        lda asset_stamp,x
        cmp asset_expected,x    ; reject data from a different graphics build
        jne prepare_failed
        dex
        bpl check_stamp
        lda #1
        sta asset_opened
seek_resource:
        ldx asset_slot
        ldy #0
copy_offset:
        lda asset_index,x
        sta asset_command+2,y
        inx
        iny
        cpy #4
        bne copy_offset
        lda asset_index,x
        sta asset_remaining
        lda asset_index+1,x
        sta asset_remaining+1
        lda #'P'                ; POSITION channel 2 to the 32-bit offset
        sta asset_command
        lda #2
        sta asset_command+1
        lda #8
        jsr $FFB1               ; LISTEN
        lda #$6F
        jsr $FF93               ; SECOND command channel
        ldy #0
send_command:
        phy
        lda asset_command,y
        jsr $FFA8               ; CIOUT
        ply
        iny
        cpy #6
        bne send_command
        jsr $FFAE               ; UNLSN executes POSITION
        lda #8
        jsr $FFB4               ; TALK
        lda #$6F
        jsr $FF96               ; TKSA command channel
        jsr $FFA5
        cmp #'0'
        jne prepare_failed
        jsr $FFA5
        cmp #'0'
        jne prepare_failed
        ldx #64                 ; consume the entire DOS status line
read_dos_status:
        phx
        jsr $FFA5
        plx
        cmp #13
        beq dos_status_done
        dex
        bne read_dos_status
        jmp prepare_failed
dos_status_done:
        jsr $FFAB               ; UNTALK
        ldx #2
        jsr $FFC6               ; CHKIN resets status and selects file
        jcs prepare_failed
        pla
        sta $01
        lda #1
        ldx #0
        rts
prepare_failed:
        jmp asset_abort
.segment "RODATA"
; OPEN must be able to read the filename regardless of the selected RAM bank.
asset_name:
        .byte "CHESS.DAT,S,R"
asset_name_end:
.segment "MENUCODE"
        .include "assets.inc"
