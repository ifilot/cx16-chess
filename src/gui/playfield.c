/**************************************************************************
 *                                                                        *
 *   Author: Ivo Filot <ivo@ivofilot.nl>                                  *
 *                                                                        *
 *   CX16-CHESS is free software:                                         *
 *   you can redistribute it and/or modify it under the terms of the      *
 *   GNU General Public License as published by the Free Software         *
 *   Foundation, either version 3 of the License, or (at your option)     *
 *   any later version.                                                   *
 *                                                                        *
 *   CX16-CHESS is distributed in the hope that it will be useful,        *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty          *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.              *
 *   See the GNU General Public License for more details.                 *
 *                                                                        *
 *   You should have received a copy of the GNU General Public License    *
 *   along with this program.  If not, see http://www.gnu.org/licenses/.  *
 *                                                                        *
 **************************************************************************/

/*
 * The playing field: draws the game held by match.c and turns mouse and
 * keyboard input into moves. All game logic lives in core/; this file only
 * knows how things look.
 *
 * Screen: a 448x448 board on the left, clocks and a paired scorecard on
 * the right, with a signed evaluation bar and animated thinking indicator.
 */

#include <ascii_charmap.h>
#include <cbm.h>
#include <cx16.h>
#pragma static-locals (on)
#include <string.h>
#include <time.h>

#include "gfx.h"
#include "video.h"
#include "rules.h"
#include "engine.h"
#include "match.h"
#include "strings.h"
#include "playfield.h"
#include "sound.h"
#pragma code-name ("DRAGCODE")
#pragma rodata-name ("DRAGCODE")

#define CLOCK_START     (30 * 60)       // seconds per player
#define BOARD_PIXELS    (8 * SQUARE)

// tile cell of the top-left board square; a square is 7x7 tiles
#define SQ_COL          (BOARD_X / 8)
#define SQ_ROW          (BOARD_Y / 8)

// text rows
#define LEFT_CX         ((LEFT_X0 + LEFT_X1 + 1) / 2)
#define MOVES_ROW       (MOVES_Y / 8)

#define MARK_TARGET     1
#define MARK_CAPTURE    2
#define NOT_DRAWN       0xFF

// input phases of the playing field
#define INPUT_MOVE      0
#define INPUT_PROMOTE   1

static uint8_t input_phase;
uint8_t playfield_new_requested;
uint8_t playfield_flipped;           // black at the bottom
uint8_t playfield_theme = THEME_NEWSPRINT;
uint8_t playfield_info = 1;          // score sheet shown
static uint16_t thinking_frame;
#pragma bss-name ("DRAGBSS")
static uint8_t thinking;                // the engine is busy
static uint8_t dragging;
void playfield_cancel_drag(void);       // resident bank-switching entry point
static uint8_t selected;                // square of the selected piece
static uint8_t check_square;            // king in check
static uint8_t marks[128];              // legal destinations of the selection
static uint8_t drawn_state[64];         // what is on screen, per square
static uint8_t drawn_piece[64];

static uint8_t cursor_col, cursor_row;  // keyboard cursor (screen coordinates)
static uint8_t cursor_visible;

static uint8_t promo_from, promo_to;    // pending promotion
static const uint8_t promo_choices[4] = {QUEEN, KNIGHT, ROOK, BISHOP};

static clock_t last_clock;
static char buf[24];

/*****************************************************************************
 * BOARD
 *****************************************************************************/

static uint8_t square_at(uint8_t col, uint8_t row) {
    return playfield_flipped ? SQ(7 - col, row) : SQ(col, 7 - row);
}

/**
 * @brief Index into promo_choices of a promotion-picker square, or 0xFF
 */
static uint8_t picker_slot(uint8_t sq) {
    uint8_t i;

    if(input_phase != INPUT_PROMOTE || FILE_OF(sq) != FILE_OF(promo_to)) return 0xFF;
    i = (side == WHITE) ? 7 - RANK_OF(sq) : RANK_OF(sq);
    return i < 4 ? i : 0xFF;
}

/**
 * @brief Redraw the squares whose highlight or piece changed
 */
static void board_refresh(void) {
    uint8_t f, r, sq, idx, state, piece, slot, col, row;

    for(r=0; r<8; r++) {
        for(f=0; f<8; f++) {
            sq = SQ(f, r);
            piece = board[sq];
            if(marks[sq] & MARK_CAPTURE) state = SQ_CAPTURE;
            else if(marks[sq] & MARK_TARGET) state = SQ_TARGET;
            else if(sq == selected) state = SQ_SELECTED;
            else if(sq == check_square) state = SQ_CHECK;
            else if(sq == match_last_from || sq == match_last_to) state = SQ_LASTMOVE;
            else state = SQ_NORMAL;

            slot = picker_slot(sq);
            if(slot != 0xFF) {
                piece = side | promo_choices[slot];
                state = SQ_SELECTED;
            }

            if(dragging && sq == selected) piece = EMPTY;
            idx = (r << 3) | f;
            col = playfield_flipped ? 7 - f : f;
            row = playfield_flipped ? r : 7 - r;
            if(state != drawn_state[idx]) {
                drawn_state[idx] = state;
                // a1 is a dark square; per theme the table holds light squares first
                video_square(SQ_COL + col * 7, SQ_ROW + row * 7,
                             ((playfield_theme << 1) + !((f + r) & 1)) * SQ_STATES + state);
            }
            if(piece != drawn_piece[idx]) {
                drawn_piece[idx] = piece;
                video_piece(SQ_COL + col * 7, SQ_ROW + row * 7,
                            piece == EMPTY ? 0xFF : (COLOR(piece) ? 6 : 0) + TYPE(piece) - 1);
            }
        }
    }
}

static void redraw_board(void) {
    memset(drawn_state, NOT_DRAWN, sizeof(drawn_state));
    memset(drawn_piece, NOT_DRAWN, sizeof(drawn_piece));
    board_refresh();
}

/**
 * @brief Ranks on the left and files below the board
 */
static void draw_labels(void) {
    uint8_t i, row;

    buf[1] = 0;
    for(i=0; i<8; i++) {
        buf[0] = '1' + (playfield_flipped ? i : 7 - i);
        row = SQ_ROW + i * 7 + 3;
        video_text(RANK_LABEL_COL_LEFT, row, buf, COL_INK);
    }
    for(i=0; i<8; i++) {
        video_tile(SQ_COL + i * 7 + 3, 58, L1_FILES + (playfield_flipped ? 7 - i : i), COL_INK);
    }
}

static void update_cursor(void) {
    video_cursor(cursor_visible, BOARD_X - 4 + cursor_col * SQUARE,
                 BOARD_Y - 4 + cursor_row * SQUARE);
}

/*****************************************************************************
 * STATUS BAR AND SIDE COLUMNS
 *****************************************************************************/

/**
 * @brief "MM:SS" of a clock into buf at offset at
 */
static void format_clock(uint8_t color, uint8_t at) {
    uint16_t t = match_clock[color >> 3];

    buf[at] = '0' + (t / 60) / 10;
    buf[at + 1] = '0' + (t / 60) % 10;
    buf[at + 2] = ':';
    buf[at + 3] = '0' + (t % 60) / 10;
    buf[at + 4] = '0' + (t % 60) % 10;
    buf[at + 5] = 0;
}

/**
 * @brief A move in figurine notation, without the '=' of promotions
 */
static void figurines(const char* san, char* out) {
    for(; *san; san++) {
        switch(*san) {
            case '=': break;
            case 'N': *out++ = FIGURINE_CODE + KNIGHT; break;
            case 'B': *out++ = FIGURINE_CODE + BISHOP; break;
            case 'R': *out++ = FIGURINE_CODE + ROOK; break;
            case 'Q': *out++ = FIGURINE_CODE + QUEEN; break;
            case 'K': *out++ = FIGURINE_CODE + KING; break;
            default: *out++ = *san;
        }
    }
    *out = 0;
}

/**
 * @brief Check, promotion or the result; normal turns need no status label
 */
static void draw_turn(void) {
    const char* a = 0;
    const char* b = 0;
    uint8_t color = COL_INK;

    if(match_state == MATCH_OVER) {
        color = COL_RED;
        b = STR_DRAWN;
        switch(match_result) {
            case RESULT_WHITE_MATES:   a = STR_MATE; b = STR_WHITE_WINS; break;
            case RESULT_BLACK_MATES:   a = STR_MATE; b = STR_BLACK_WINS; break;
            case RESULT_WHITE_ON_TIME: a = STR_TIME; b = STR_WHITE_WINS; break;
            case RESULT_BLACK_ON_TIME: a = STR_TIME; b = STR_BLACK_WINS; break;
            case RESULT_STALEMATE:     a = STR_STALEMATE; break;
            case RESULT_REPETITION:    a = STR_REPETITION; break;
            case RESULT_TIME_MATERIAL: a = STR_TIME; break;
            default:                   a = STR_DRAW; break;
        }
    } else if(thinking) {
        return;
    } else if(input_phase == INPUT_PROMOTE) {
        a = STR_PROMOTE;
        b = 0;
    } else if(check_square != NO_SQUARE) {
        a = STR_CHECK;
        b = (side == WHITE) ? STR_WHITE_DAT : STR_BLACK_DAT;
        color = COL_RED;
    }
    video_text_clear(61, 55, 19);
    if(!a) return;
    strcpy(buf, a);
    if(b) {
        strcat(buf, " ");
        strcat(buf, b);
    }
    video_text_centered(LEFT_CX, 55, buf, color);
}

/**
 * @brief Evaluation bar: Black to the left, White to the right
 */
static void draw_analysis(void) {
    int16_t e = match_eval_valid ? match_eval : 0;
    uint16_t magnitude = e < 0 ? -e : e;
    uint8_t width, i, part;

    /* +/- seven pawns fills its half; mate scores saturate safely. */
    if(magnitude > 700) magnitude = 700;
    width = magnitude * 56 / 700;
    for(i=0; i<7; i++) {
        part = width >= 8 ? 8 : width;
        video_tile(70 + i, 7, L1_BAR + (e > 0 ? part : 0), COL_RED);
        video_tile(69 - i, 7, L1_BAR + (e < 0 && part ? 8 + part : 0), COL_INK);
        width -= part;
    }
}

/** Compact clocks following WHITE / BLACK on a single text line. */
static void draw_clocks(void) {
    uint8_t top = playfield_flipped ? WHITE : BLACK;
    uint8_t color, row, active;

    for(color=WHITE; ; color=BLACK) {
        row = (color == top ? PLATE_Y_TOP : PLATE_Y_BOTTOM) / 8;
        active = (match_state == MATCH_PLAYING && side == color);
        strcpy(buf, color == WHITE ? "WHITE  " : "BLACK  ");
        format_clock(color, 7);
        /* Clock labels have a fixed width; overwrite without blanking them. */
        video_text_centered(LEFT_CX, row, buf, active ? COL_RED : COL_INK);
        if(color == BLACK) break;
    }
}

/** Rotate two figurines four times a second; percentage is time budget used. */
static void draw_thinking(uint16_t now) {
    uint16_t frame = now / 15;
    uint16_t elapsed = now - match_think_start;
    uint8_t percent, phase;
    char icon[3];

    if(frame == thinking_frame) return;
    thinking_frame = frame;
    percent = match_think_budget ?
              ((uint32_t)elapsed * 100 / match_think_budget) : 0;
    if(match_think_budget && (elapsed >= match_think_budget || percent > 99)) percent = 99;
    phase = frame % 6;
    /* Each moving figurine and its adjacent space occupy three cells. */
    icon[2] = 0;
    icon[(phase & 1) ^ 1] = ' ';
    icon[phase & 1] = FIGURINE_CODE + 1 + phase;
    video_text(61, 55, icon, COL_INK);
    icon[phase & 1] = FIGURINE_CODE + 1 + (phase + 3) % 6;
    video_text(64, 55, icon, COL_RED);
    if(match_think_depth) {
        strcpy(buf, "PLY 0   ");
        buf[4] = '0' + match_think_depth;
    } else {
        strcpy(buf, "TIME 00%");
        buf[5] = '0' + percent / 10;
        buf[6] = '0' + percent % 10;
    }
    video_text(69, 55, buf, COL_INK);
}

/**
 * @brief Scrolling score sheet: one numbered white/black pair per row
 */
static void draw_moves(void) {
    uint16_t first, n, number;
    uint8_t k, row, column;
    char san[8];

    if(!playfield_info) return;
    first = ply / 2 >= MOVE_ROWS ? ply / 2 - MOVE_ROWS + 1 : 0;
    for(k=0; k<MOVE_ROWS; k++) {
        row = MOVES_ROW + k * 2;
        video_text_clear(61, row, 19);
        number = first + k + 1;
        if((first + k) * 2 > ply) continue;
        buf[0] = number >= 100 ? '0' + number / 100 % 10 : ' ';
        buf[1] = number >= 10 ? '0' + number / 10 % 10 : ' ';
        buf[2] = '0' + number % 10;
        buf[3] = 0;
        video_text(61, row, buf, COL_INK);
        for(column=0; column<2; column++) {
            n = (first + k) * 2 + column;
            if(n >= ply) continue;
            match_san(n, san);
            figurines(san, buf);
            /* Figurines occupy 16px; other notation keeps its 8px advance. */
            video_text(column ? 72 : 64, row, buf, COL_INK);
        }
    }
}

/**
 * @brief Show or hide the score sheet while keeping clocks visible
 */
static void set_info(uint8_t on) {
    playfield_info = on;
    video_show_info(on);
    video_clear_block(61, MOVES_ROW, 19, MOVE_ROWS * 2);
    draw_clocks();
    if(on) draw_moves();
}

/**
 * @brief Redraw everything that depends on the game state
 */
static void refresh_all(void) {
    check_square = (match_state == MATCH_PLAYING && rules_in_check()) ?
                   rules_king_square(side) : NO_SQUARE;
    board_refresh();
    draw_turn();
    draw_analysis();
    draw_clocks();
    if(playfield_info) draw_moves();
}

/*****************************************************************************
 * INPUT
 *****************************************************************************/

static void clear_selection(void) {
    if(dragging) playfield_cancel_drag();
    selected = NO_SQUARE;
    memset(marks, 0, sizeof(marks));
}

static void select_square(uint8_t sq) {
    uint8_t i;
    sound_sfx(SFX_PICKUP);

    clear_selection();
    selected = sq;
    for(i=0; i<legal_count; i++) {
        if(legal_moves[i].from == sq) {
            marks[legal_moves[i].to] |= (legal_moves[i].flags & MF_CAPTURE) ? MARK_CAPTURE : MARK_TARGET;
        }
    }
}

static void play(const move_t* m) {
    input_phase = INPUT_MOVE;
    clear_selection();
    match_play(m);
    sound_event(SOUND_MOVE);
    refresh_all();
}

static void cancel_promotion(void) {
    input_phase = INPUT_MOVE;
    clear_selection();
    board_refresh();
    draw_turn();
}

/**
 * @brief Click or Return on a board square
 */
static void activate(uint8_t sq) {
    const move_t* m;
    uint8_t slot;

    if(match_state != MATCH_PLAYING || match_computer_to_move()) return;

    if(input_phase == INPUT_PROMOTE) {
        slot = picker_slot(sq);
        if(slot == 0xFF) {
            cancel_promotion();
        } else {
            play(match_find_move(promo_from, promo_to, promo_choices[slot]));
        }
        return;
    }

    if(selected != NO_SQUARE && marks[sq]) {
        m = match_find_move(selected, sq, EMPTY);
        if(m->flags & MF_PROMOTION) {
            promo_from = selected;
            promo_to = sq;
            input_phase = INPUT_PROMOTE;
            clear_selection();
            board_refresh();
            draw_turn();
        } else {
            play(m);
        }
        return;
    }

    if(board[sq] != EMPTY && COLOR(board[sq]) == side && sq != selected) {
        select_square(sq);
    } else {
        if(selected != NO_SQUARE) sound_sfx(SFX_ILLEGAL);
        clear_selection();
    }
    board_refresh();
}

/**
 * @brief Run the engine (for its own move or an analysis)
 */
/* Let a demo finish its current search early when Escape is pressed. */
extern uint8_t search_aborted;
#pragma bss-name (push, "BSS")
uint8_t playfield_pending_key;
#pragma bss-name (pop)
void demo_poll(void);  /* Resident callback: the engine can select any RAM bank. */
void playfield_demo_poll(void) {
    uint8_t key;
    playfield_tick();
    if(match_computer == COMPUTER_BOTH) {
        key = cbm_k_getin();
        if(key == KEY_ESCAPE) {
            playfield_pending_key = key;
            search_aborted = 1;
        }
    }
}

static void engine_turn(uint8_t analyse) {
    uint16_t previous_ply = ply;
    thinking = 1;
    thinking_frame = 0xFFFF;
    video_text_clear(61, 55, 19);
    input_phase = INPUT_MOVE;
    clear_selection();
    board_refresh();
    draw_turn();
    if(analyse) {
        match_analyse(playfield_tick);
    } else {
        match_computer_move(demo_poll);
        sound_event(ply != previous_ply ? SOUND_CPU_MOVE : SOUND_RESULT);
    }
    thinking = 0;
    refresh_all();
}

static void flip_board(void) {
    playfield_flipped ^= 1;
    cursor_col = 7 - cursor_col;
    cursor_row = 7 - cursor_row;
    draw_labels();
    set_info(playfield_info);
    redraw_board();
    update_cursor();
}

/**
 * @brief Cycle who the computer plays: black, white, nobody
 */
static void cycle_computer(void) {
    switch(match_computer) {
        case COMPUTER_BLACK: match_computer = COMPUTER_WHITE; break;
        case COMPUTER_WHITE: match_computer = COMPUTER_NONE; break;
        default:             match_computer = COMPUTER_BLACK; break;
    }
    input_phase = INPUT_MOVE;
    clear_selection();
    board_refresh();
    draw_turn();
    draw_clocks();
}

/*****************************************************************************
 * PUBLIC INTERFACE
 *****************************************************************************/

void playfield_new_banked(void) {
    playfield_new_requested = 0;
    match_new(CLOCK_START, match_computer);
    sound_event(SOUND_NEW);
    input_phase = INPUT_MOVE;
    playfield_flipped = (match_computer == COMPUTER_WHITE);
    thinking = 0;
    clear_selection();
    memset(drawn_state, NOT_DRAWN, sizeof(drawn_state));
    memset(drawn_piece, NOT_DRAWN, sizeof(drawn_piece));
    last_clock = clock();
    cursor_col = 4;
    cursor_row = 6;
    cursor_visible = 0;

    video_clear_layer1();
    draw_labels();
    video_show_info(playfield_info);
    refresh_all();
    update_cursor();
}

void playfield_resume_banked(void) {
    sound_event(SOUND_RESUME);
    last_clock = clock();
    video_clear_layer1();
    draw_labels();
    video_show_info(playfield_info);
    memset(drawn_state, NOT_DRAWN, sizeof(drawn_state));
    memset(drawn_piece, NOT_DRAWN, sizeof(drawn_piece));
    refresh_all();
    update_cursor();
}

void playfield_loaded_banked(void) {
    input_phase = INPUT_MOVE;
    thinking = 0;
    cursor_visible = 0;
    cursor_col = 4;
    cursor_row = 6;
    clear_selection();
    playfield_resume();
}

void playfield_tick_banked(void) {
    clock_t now = clock();
    clock_t delta = now - last_clock;

    last_clock = now;
    if(thinking && match_state == MATCH_PLAYING) draw_thinking((uint16_t)now);
    if(match_tick(delta > 120 ? 120 : (uint8_t)delta)) {
        sound_event(SOUND_CLOCK);
        sound_event(SOUND_RESULT);
        draw_clocks();
        if(match_state == MATCH_OVER) {
            input_phase = INPUT_MOVE;
            clear_selection();
            refresh_all();
        }
    }
}

void playfield_update_banked(void) {
    if(match_computer_to_move()) engine_turn(0);
}

void playfield_key_banked(uint8_t key) {
    if(dragging) { clear_selection(); board_refresh(); }
    switch(key) {
        case 'V': case 'v': sound_event(SOUND_MUSIC_TOGGLE); return;
        case 'S': case 's': sound_event(SOUND_EFFECTS_TOGGLE); return;
        case KEY_UP:
            if(cursor_visible && cursor_row > 0) cursor_row--;
            break;
        case KEY_DOWN:
            if(cursor_visible && cursor_row < 7) cursor_row++;
            break;
        case KEY_LEFT:
            if(cursor_visible && cursor_col > 0) cursor_col--;
            break;
        case KEY_RIGHT:
            if(cursor_visible && cursor_col < 7) cursor_col++;
            break;
        case KEY_RETURN:
        case KEY_SPACE:
            if(cursor_visible) activate(square_at(cursor_col, cursor_row));
            break;
        case KEY_ESCAPE:
            if(input_phase == INPUT_PROMOTE) {
                cancel_promotion();
            } else {
                clear_selection();
                board_refresh();
            }
            return;
        case 'F': case 'f':
            flip_board();
            return;
        case 'N': case 'n':
            playfield_new_requested = 1;
            return;
        case 'T': case 't':
            playfield_theme = (playfield_theme + 1) % THEMES;
            redraw_board();
            return;
        case 'C': case 'c':
            cycle_computer();
            return;
        case 'I': case 'i': case KEY_TAB:
            set_info(!playfield_info);
            return;
        case 'A': case 'a':
            if(match_state == MATCH_PLAYING && !match_computer_to_move()) engine_turn(1);
            return;
        default:
            return;
    }
    cursor_visible = 1;
    update_cursor();
}

/* Board UI, drag input and VRAM copying run in bank 23. Sprite 15 is above the board;
 * sprites 0/1 belong to the pointer/cursor and 2..14 to the loading cover. */
#pragma code-name ("DRAGCODE")
#pragma bss-name ("DRAGBSS")
#define DRAG_ATTR 0xFC78
static uint8_t grab_x, grab_y, drag_toggle, last_buttons;
static uint16_t last_x, last_y;

static void drag_address(uint16_t address) {
    VERA.control = 0;
    VERA.address = address;
    VERA.address_hi = 0x11;
}
void playfield_drag_stop(void) {
    drag_address(DRAG_ATTR + 6);
    VERA.data0 = 0;
    dragging = 0;
}
void playfield_drag_init(void) {
    last_buttons = 0;
    last_x = last_y = 0;
    playfield_drag_stop();
}
static void drag_position(uint16_t x, uint16_t y) {
    x -= grab_x;
    y -= grab_y;
    drag_address(DRAG_ATTR + 2);
    VERA.data0 = x;
    VERA.data0 = x >> 8;
    VERA.data0 = y;
    VERA.data0 = y >> 8;
    VERA.data0 = 12;
}
/* Assemble the current set's 49 resident piece tiles into a padded 64x64
 * sprite. Both VERA ports stream VRAM; no disk access or RAM image is needed. */
static void drag_image(uint8_t piece) {
    uint16_t n, tile;
    uint8_t y, x, b;
    tile = L1_PIECES + ((COLOR(piece) ? 6 : 0) + TYPE(piece) - 1) * 49;
    drag_address((uint16_t)VRAM_DRAG);
    for(n = 0; n < 2048; n++) VERA.data0 = 0;
    for(y = 0; y < SQUARE; y++) {
        drag_address((uint16_t)VRAM_DRAG + (y + 4) * 32 + 2);
        for(x = 0; x < 7; x++) {
            VERA.control = 1;
            VERA.address = (uint16_t)VRAM_L1_TILES + (tile + (y >> 3) * 7 + x) * 32 + (y & 7) * 4;
            VERA.address_hi = 0x11;
            VERA.control = 0;
            for(b = 0; b < 4; b++) VERA.data0 = VERA.data1;
        }
    }
    drag_address(DRAG_ATTR);
    VERA.data0 = (uint8_t)(VRAM_DRAG >> 5);
    VERA.data0 = (uint8_t)(VRAM_DRAG >> 13);
    drag_address(DRAG_ATTR + 6);
    VERA.data0 = 0;
    VERA.data0 = 0xF0;           // 64x64, 4bpp, palette 0
}
void playfield_drag_mouse(uint16_t x, uint16_t y, uint8_t buttons) {
    uint8_t pressed = (buttons & 1) && !(last_buttons & 1);
    uint8_t inside = x >= BOARD_X && x < BOARD_X + BOARD_PIXELS &&
                     y >= BOARD_Y && y < BOARD_Y + BOARD_PIXELS;
    uint8_t sq;

    if(x != last_x || y != last_y) {
        if(cursor_visible) {
            cursor_visible = 0;
            update_cursor();
        }
        last_x = x;
        last_y = y;
    }
    last_buttons = buttons;
    if(inside) {
        cursor_col = (x - BOARD_X) / SQUARE;
        cursor_row = (y - BOARD_Y) / SQUARE;
        sq = square_at(cursor_col, cursor_row);
    }
    if(dragging) {
        if(buttons & 1) {
            drag_position(x, y);
            return;
        }
        playfield_drag_stop();
        if(inside && sq == selected) {
            if(drag_toggle) clear_selection();
            board_refresh();          // a click still selects/deselects
        } else if(inside && marks[sq]) {
            activate(sq);             // captures, castling, en passant, promotion
        } else {
            sound_sfx(SFX_ILLEGAL);
            clear_selection();
            board_refresh();          // illegal/off-board drop returns the piece
        }
        return;
    }
    if(!pressed || !inside) return;
    if(input_phase == INPUT_MOVE && match_state == MATCH_PLAYING &&
       !match_computer_to_move() && board[sq] != EMPTY && COLOR(board[sq]) == side) {
        drag_toggle = sq == selected;
        select_square(sq);
        grab_x = x - (BOARD_X + cursor_col * SQUARE) + 4;
        grab_y = y - (BOARD_Y + cursor_row * SQUARE) + 4;
        drag_image(board[sq]);
        drag_position(x, y);
        dragging = 1;
        board_refresh();
    } else activate(sq);
}
