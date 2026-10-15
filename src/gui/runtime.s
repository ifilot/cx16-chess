; CX16 r39+ startup/return path. Keep BASIC's zero page intact across cc65,
; including engine EXTZP, and use the current $00/$01 bank registers.
; This replaces the obsolete r37 startup shipped with cc65 2.19 for CHESS only.
.export __STARTUP__ : absolute = 1
.export _exit, runtime_start, runtime_restored
.import initlib, donelib, zerobss, callmain, _sound_shutdown, _asset_close
.import __MAIN_START__, __MAIN_SIZE__
.include "zeropage.inc"

.segment "STARTUP"
runtime_start:
        tsx
        stx saved_stack
        lda $00
        sta saved_bank
        ldx #$5D
save_zp:
        lda $22,x
        sta saved_zp,x
        dex
        bpl save_zp
        stz $01
        lda #1
        sta $00
        lda #<(__MAIN_START__ + __MAIN_SIZE__)
        sta sp
        lda #>(__MAIN_START__ + __MAIN_SIZE__)
        sta sp+1
        jsr initlib             ; includes golden_stack and loading cover
        jsr zerobss
        jsr callmain
_exit:
        jsr donelib
        jsr _sound_shutdown     ; remove ISR before BASIC can overwrite code
        jsr _asset_close
        jsr $FFCC               ; normal keyboard/screen channels
        lda #0
        tax
        tay
        jsr $FF68               ; disable game pointer
        stz $9F25               ; VERA DCSEL/ADDRSEL = 0
        jsr $FF81               ; CINT restores text, charset and palette
        ldx #$5D
restore_zp:
        lda saved_zp,x
        sta $22,x
        dex
        bpl restore_zp
        lda saved_bank
        sta $00
        lda #4
        sta $01                 ; BASIC ROM, as expected by SYS
        ldx saved_stack
        txs
runtime_restored:
        rts

; INIT is reserved in the PRG and survives BSS clearing and the golden stack.
.segment "INIT"
saved_stack: .res 1
saved_bank:  .res 1
saved_zp:    .res $5E
