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
; CHESS.PRG keeps root move arrays at $0400-$05BF and its C stack at
; $05C0-$07FF. ENGINE.PRG uses this RAM for its mailbox instead. This frees
; 1 KB of main RAM between the arrays and stack;
; the program is linked with __STACKSIZE__=0 (see Makefile).
;
        .include "zeropage.inc"
        .constructor golden_stack

GOLDEN_TOP = $0800

.segment "ONCE"

;------------------------------------------------------------------------------
; ROUTINE golden_stack
;
; Constructor: point the cc65 C stack pointer (sp) at the top of golden RAM.
; The stack grows down from $0800.
;------------------------------------------------------------------------------
golden_stack:
        lda #<GOLDEN_TOP
        sta sp
        lda #>GOLDEN_TOP
        sta sp+1
        rts
