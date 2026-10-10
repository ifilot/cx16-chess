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
 * Screen: masthead strip, the 448x448 board, a status bar below. The side
 * columns (players, clocks, move list) can be switched on and off.
 */

#include <ascii_charmap.h>
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

#define CLOCK_START     (30 * 60)       // seconds per player
#define BOARD_PIXELS    (8 * SQUARE)

// tile cell of the top-left board square; a square is 7x7 tiles
#define SQ_COL          (BOARD_X / 8)
#define SQ_ROW          (BOARD_Y / 8)

// text rows
#define ROW_STATUS      (STATUS_Y / 8)
#define ROW_PLATE_TOP   ((PLATE_Y_TOP + 8) / 8)
#define ROW_PLATE_BOT   ((PLATE_Y_BOTTOM + 8) / 8)
#define ROW_CLOCK_TOP   ((CLOCK_Y_TOP + 16) / 8)
#define ROW_CLOCK_BOT   ((CLOCK_Y_BOTTOM + 16) / 8)
#define LEFT_CX         ((LEFT_X0 + LEFT_X1 + 1) / 2)
#define MOVES_COL       (RIGHT_X0 / 8 + 1)
#define MOVES_ROW       (MOVES_Y / 8)

#define MARK_TARGET     1
#define MARK_CAPTURE    2
#define NOT_DRAWN       0xFF

// input phases of the playing field
#define INPUT_MOVE      0
#define INPUT_PROMOTE   1

static uint8_t input_phase;
static uint8_t flipped;                 // black at the bottom
static uint8_t theme;                   // THEME_NEWSPRINT or THEME_WOOD
static uint8_t info;                    // side columns shown
static uint8_t thinking;                // the engine is busy
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
    return flipped ? SQ(7 - col, row) : SQ(col, 7 - row);
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

            idx = (r << 3) | f;
            col = flipped ? 7 - f : f;
            row = flipped ? r : 7 - r;
            if(state != drawn_state[idx]) {
                drawn_state[idx] = state;
                // a1 is a dark square; per theme the table holds light squares first
                video_square(SQ_COL + col * 7, SQ_ROW + row * 7,
                             ((theme << 1) + !((f + r) & 1)) * SQ_STATES + state);
            }
            if(piece != drawn_piece[idx]) {
                drawn_piece[idx] = piece;
                video_piece(SQ_COL + col * 7, SQ_ROW + row * 7,
                            piece == EMPTY ? 0xFF : (COLOR(piece) ? 6 : 0) + TYPE(piece) - 1);
                if(row == 7) {                      // file letter in the corner
                    video_tile(SQ_COL + col * 7, SQ_ROW + 7 * 7 + 6, L1_FILES + f, COL_INK);
                }
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
 * @brief Rank numbers on both sides of the board
 */
static void draw_labels(void) {
    uint8_t i, row;

    buf[1] = 0;
    for(i=0; i<8; i++) {
        buf[0] = '1' + (flipped ? i : 7 - i);
        row = SQ_ROW + i * 7 + 3;
        video_text(RANK_LABEL_COL_LEFT, row, buf, COL_INK);
        video_text(RANK_LABEL_COL_RIGHT, row, buf, COL_INK);
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
 * @brief Evaluation as "+0.35", "-1.20" or "+#3" (mate in 3), white's view
 */
static void format_eval(void) {
    int16_t e = match_eval;
    uint16_t a = e < 0 ? -e : e;
    char* p = buf;

    *p++ = e < 0 ? '-' : '+';
    if(a > ENGINE_MATE - 512) {
        a = (ENGINE_MATE - a + 1) >> 1;
        *p++ = '#';
        if(a >= 10) *p++ = '0' + a / 10;
        *p++ = '0' + a % 10;
    } else {
        if(a >= 1000) *p++ = '0' + (a / 1000) % 10;
        *p++ = '0' + (a / 100) % 10;
        *p++ = '.';
        *p++ = '0' + (a / 10) % 10;
        *p++ = '0' + a % 10;
    }
    *p = 0;
}

/**
 * @brief Whose move it is, check, thinking, promotion or the result
 */
static void draw_turn(void) {
    const char* a = (side == WHITE) ? STR_WHITE : STR_BLACK;
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
        a = STR_COMPUTER;
        b = STR_THINKS;
    } else if(input_phase == INPUT_PROMOTE) {
        a = STR_PROMOTE;
    } else if(check_square != NO_SQUARE) {
        a = STR_CHECK;
        b = (side == WHITE) ? STR_WHITE_DAT : STR_BLACK_DAT;
        color = COL_RED;
    }
    strcpy(buf, a);
    if(b) {
        strcat(buf, " ");
        strcat(buf, b);
    }
    video_text_clear(STATUS_TURN_COL, ROW_STATUS, 10);
    video_text(STATUS_TURN_COL, ROW_STATUS, buf, color);
}

/**
 * @brief Best move and evaluation from the engine
 */
static void draw_analysis(void) {
    video_text_clear(STATUS_BEST_COL, ROW_STATUS, 7);
    video_text_clear(STATUS_EVAL_COL, ROW_STATUS, 7);
    figurines(match_best, buf);
    video_text(STATUS_BEST_COL, ROW_STATUS, buf, COL_INK);
    if(match_eval_valid) {
        format_eval();
        video_text(STATUS_EVAL_COL, ROW_STATUS, buf, COL_INK);
    }
}

/**
 * @brief Clocks: both in the status bar, and in the side column boxes
 */
static void draw_clocks(void) {
    uint8_t top = flipped ? WHITE : BLACK;
    uint8_t color, row, active;

    format_clock(WHITE, 0);
    buf[5] = ' ';
    format_clock(BLACK, 6);
    video_text(STATUS_CLOCK_COL, ROW_STATUS, buf, COL_INK);
    if(!info) return;
    for(color=WHITE; ; color=BLACK) {
        row = (color == top) ? ROW_CLOCK_TOP : ROW_CLOCK_BOT;
        active = (match_state == MATCH_PLAYING && side == color);
        video_tint(LEFT_X0 / 8, row - 2, 9, 6, active);
        format_clock(color, 0);
        video_text_centered(LEFT_CX, row, buf, active ? COL_CREAM : COL_INK);
        if(color == BLACK) break;
    }
}

/**
 * @brief Player name and colour on the plates of the side column
 */
static void draw_plates(void) {
    uint8_t top = flipped ? WHITE : BLACK;
    uint8_t color, row, computer;

    for(color=WHITE; ; color=BLACK) {
        row = (color == top) ? ROW_PLATE_TOP : ROW_PLATE_BOT;
        computer = match_computer & (color == WHITE ? COMPUTER_WHITE : COMPUTER_BLACK);
        video_text_centered(LEFT_CX, row, computer ? STR_COMPUTER : STR_HUMAN, COL_CREAM);
        video_text_centered(LEFT_CX, row + 2, color == WHITE ? STR_WHITE : STR_BLACK, COL_CREAM);
        if(color == BLACK) break;
    }
}

/**
 * @brief The move list of the side column: one half move per row, the move
 *        in progress tinted
 */
static void draw_moves(void) {
    uint16_t first, n;
    uint8_t k, row, current;
    char san[8];

    if(!info) return;
    first = ply + 1 > MOVE_ROWS ? ply + 1 - MOVE_ROWS : 0;
    for(k=0; k<MOVE_ROWS; k++) {
        n = first + k;
        row = MOVES_ROW + k * 2;
        current = (n == ply && match_state == MATCH_PLAYING);
        video_tint(RIGHT_X0 / 8, row, 9, 2, current);
        video_text_clear(MOVES_COL, row, 9);
        if(n > ply || (n == ply && match_state != MATCH_PLAYING)) continue;
        buf[0] = buf[1] = ' ';
        if(!(n & 1)) {                              // white's move: its number
            if((n >> 1) + 1 >= 10) buf[0] = '0' + ((n >> 1) + 1) / 10 % 10;
            buf[1] = '0' + ((n >> 1) + 1) % 10;
        }
        buf[2] = ' ';
        if(n < ply) {
            match_san(n, san);
            figurines(san, buf + 3);
        } else {
            strcpy(buf + 3, STR_PLACEHOLDER);
        }
        video_text(MOVES_COL, row, buf, current ? COL_CREAM : COL_INK);
    }
}

/**
 * @brief Show or hide the side columns
 */
static void set_info(uint8_t on) {
    info = on;
    video_show_info(on);
    video_clear_block(0, SQ_ROW, RANK_LABEL_COL_LEFT, 56);
    video_clear_block(RANK_LABEL_COL_RIGHT + 1, SQ_ROW, 80 - RANK_LABEL_COL_RIGHT - 1, 56);
    if(on) {
        draw_plates();
        draw_clocks();
        draw_moves();
    }
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
    if(info) {
        draw_plates();
        draw_moves();
    }
}

/*****************************************************************************
 * INPUT
 *****************************************************************************/

static void clear_selection(void) {
    selected = NO_SQUARE;
    memset(marks, 0, sizeof(marks));
}

static void select_square(uint8_t sq) {
    uint8_t i;

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
        clear_selection();
    }
    board_refresh();
}

/**
 * @brief Run the engine (for its own move or an analysis)
 */
static void engine_turn(uint8_t analyse) {
    thinking = 1;
    input_phase = INPUT_MOVE;
    clear_selection();
    board_refresh();
    draw_turn();
    if(analyse) {
        match_analyse(playfield_tick);
    } else {
        match_computer_move(playfield_tick);
    }
    thinking = 0;
    refresh_all();
}

static void flip_board(void) {
    flipped ^= 1;
    cursor_col = 7 - cursor_col;
    cursor_row = 7 - cursor_row;
    draw_labels();
    set_info(info);
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
    if(info) draw_plates();
}

/*****************************************************************************
 * PUBLIC INTERFACE
 *****************************************************************************/

void playfield_new(void) {
    match_new(CLOCK_START, match_computer);
    input_phase = INPUT_MOVE;
    flipped = (match_computer == COMPUTER_WHITE);
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
    set_info(info);
    refresh_all();
    update_cursor();
}

void playfield_tick(void) {
    clock_t now = clock();
    clock_t delta = now - last_clock;

    last_clock = now;
    if(match_tick(delta > 120 ? 120 : (uint8_t)delta)) {
        draw_clocks();
        if(match_state == MATCH_OVER) {
            input_phase = INPUT_MOVE;
            clear_selection();
            refresh_all();
        }
    }
}

void playfield_update(void) {
    if(match_computer_to_move()) engine_turn(0);
}

void playfield_key(uint8_t key) {
    switch(key) {
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
            playfield_new();
            return;
        case 'T': case 't':
            theme ^= 1;
            redraw_board();
            return;
        case 'C': case 'c':
            cycle_computer();
            return;
        case 'I': case 'i': case KEY_TAB:
            set_info(!info);
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

void playfield_mouse(uint16_t x, uint16_t y, uint8_t buttons) {
    static uint16_t last_x, last_y;
    static uint8_t last_buttons;
    uint8_t pressed = (buttons & 1) && !(last_buttons & 1);

    if(x != last_x || y != last_y) {
        if(cursor_visible) {
            cursor_visible = 0;
            update_cursor();
        }
        last_x = x;
        last_y = y;
    }
    last_buttons = buttons;
    if(!pressed) return;

    if(x >= BOARD_X && x < BOARD_X + BOARD_PIXELS && y >= BOARD_Y && y < BOARD_Y + BOARD_PIXELS) {
        cursor_col = (x - BOARD_X) / SQUARE;
        cursor_row = (y - BOARD_Y) / SQUARE;
        activate(square_at(cursor_col, cursor_row));
    } else if(y >= STATUS_Y) {                      // status bar buttons
        if(x >= ANALYSE_X0 && x <= ANALYSE_X1) playfield_key('A');
        else if(x >= INFO_X0 && x <= INFO_X1) playfield_key('I');
    }
}
