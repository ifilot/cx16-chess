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
 */

#include <ascii_charmap.h>
#pragma static-locals (on)
#include <string.h>
#include <time.h>

#define GFX_TABLES
#include "gfx.h"
#include "video.h"
#include "rules.h"
#include "match.h"
#include "strings.h"
#include "playfield.h"

#define CLOCK_START     (30 * 60)       // seconds per player
#define PANEL_CX        ((LEFT_X0 + LEFT_X1 + 1) / 2)
#define BOARD_PIXELS    (8 * SQUARE)

// layer-0 tile and layer-1 cell of the top-left board square
#define SQ_L0_COL       ((BOARD_X + SCROLL) / 16)
#define SQ_L0_ROW       ((BOARD_Y + SCROLL) / 16)
#define SQ_L1_COL       (BOARD_X / 8)
#define SQ_L1_ROW       (BOARD_Y / 8)

// layer-1 text rows inside the left panel
#define ROW_PLATE_TOP   ((PLATE_Y_TOP + 8) / 8)
#define ROW_PLATE_BOT   ((PLATE_Y_BOTTOM + 8) / 8)
#define ROW_CLOCK_TOP   ((CLOCK_Y_TOP + 8) / 8)
#define ROW_CLOCK_BOT   ((CLOCK_Y_BOTTOM + 8) / 8)
#define ROW_STATUS      ((STATUS_Y + 8) / 8)
#define COL_CLOCK       ((LEFT_X0 + 4) / 8)

#define MARK_TARGET     1
#define MARK_CAPTURE    2
#define NOT_DRAWN       0xFF

// input phases of the playing field
#define INPUT_MOVE      0
#define INPUT_PROMOTE   1

static uint8_t input_phase;
static uint8_t flipped;                 // black at the bottom
static uint8_t theme;                   // THEME_NEWSPRINT or THEME_WOOD
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

/*****************************************************************************
 * BOARD
 *****************************************************************************/

/**
 * @brief Board square shown at a screen cell
 */
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
                video_layer0_block(SQ_L0_COL + col * 3, SQ_L0_ROW + row * 3, 3, 3,
                    &square_tiles[(((theme << 1) + !((f + r) & 1)) * SQ_STATES + state) * 9]);
            }
            if(piece != drawn_piece[idx]) {
                drawn_piece[idx] = piece;
                video_piece(SQ_L1_COL + col * 6, SQ_L1_ROW + row * 6,
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
 * @brief Draw the rank and file coordinates around the board
 */
static void draw_labels(void) {
    char s[2];
    uint8_t i;

    s[1] = 0;
    for(i=0; i<8; i++) {
        s[0] = '1' + (flipped ? i : 7 - i);
        video_text(RANK_LABEL_X / 8, (BOARD_Y + 16) / 8 + i * 6, s, COL_INK);
        s[0] = 'a' + (flipped ? 7 - i : i);
        video_text(SQ_L1_COL + 3 + i * 6, FILE_LABEL_Y / 8, s, COL_INK);
    }
}

/**
 * @brief Move the keyboard cursor sprite to the cursor square
 */
static void update_cursor(void) {
    video_cursor(cursor_visible, BOARD_X - 8 + cursor_col * SQUARE,
                 BOARD_Y - 8 + cursor_row * SQUARE);
}

/*****************************************************************************
 * SIDE PANELS
 *****************************************************************************/

/**
 * @brief Draw who plays (player or computer) and which colour on the plates
 */
static void draw_plates(void) {
    uint8_t top = flipped ? WHITE : BLACK;
    uint8_t row, color, computer;

    for(color=WHITE; ; color=BLACK) {
        row = (color == top) ? ROW_PLATE_TOP : ROW_PLATE_BOT;
        computer = match_computer & (color == WHITE ? COMPUTER_WHITE : COMPUTER_BLACK);
        video_text_clear(1, row, 9);
        video_text_clear(1, row + 2, 9);
        video_text_centered(PANEL_CX, row, computer ? STR_COMPUTER : STR_HUMAN, COL_CREAM);
        video_text_centered(PANEL_CX, row + 2, color == WHITE ? STR_WHITE : STR_BLACK, COL_CREAM);
        if(color == BLACK) break;
    }
}

/**
 * @brief Draw the clock of one player; the running clock is shown in red
 */
static void draw_clock(uint8_t color) {
    uint16_t t = match_clock[color >> 3];
    uint8_t minutes = t / 60;
    uint8_t seconds = t % 60;
    uint8_t top = (color == (flipped ? WHITE : BLACK));
    uint8_t active = (match_state == MATCH_PLAYING && side == color);
    char s[6];

    s[0] = '0' + minutes / 10;
    s[1] = '0' + minutes % 10;
    s[2] = ':';
    s[3] = '0' + seconds / 10;
    s[4] = '0' + seconds % 10;
    s[5] = 0;
    if(top) {
        video_layer0_block(CLOCK_REG_COL_TOP, CLOCK_REG_ROW_TOP, CLOCK_REG_W, CLOCK_REG_H,
                           active ? clock_top_active : clock_top_idle);
    } else {
        video_layer0_block(CLOCK_REG_COL_BOTTOM, CLOCK_REG_ROW_BOTTOM, CLOCK_REG_W, CLOCK_REG_H,
                           active ? clock_bottom_active : clock_bottom_idle);
    }
    video_digits(COL_CLOCK, top ? ROW_CLOCK_TOP : ROW_CLOCK_BOT, s, active ? COL_CREAM : COL_INK);
}

/**
 * @brief Two-line status box: whose move, check, thinking, promotion, result
 */
static void draw_status(void) {
    const char* line1 = STR_TO_MOVE;
    const char* line2 = (side == WHITE) ? STR_WHITE_GEN : STR_BLACK_GEN;
    uint8_t color1 = COL_INK;

    if(match_state == MATCH_OVER) {
        color1 = COL_RED;
        line2 = STR_DRAWN;
        switch(match_result) {
            case RESULT_WHITE_MATES:   line1 = STR_MATE; line2 = STR_WHITE_WINS; break;
            case RESULT_BLACK_MATES:   line1 = STR_MATE; line2 = STR_BLACK_WINS; break;
            case RESULT_WHITE_ON_TIME: line1 = STR_TIME; line2 = STR_WHITE_WINS; break;
            case RESULT_BLACK_ON_TIME: line1 = STR_TIME; line2 = STR_BLACK_WINS; break;
            case RESULT_STALEMATE:     line1 = STR_STALEMATE; break;
            case RESULT_REPETITION:    line1 = STR_REPETITION; break;
            case RESULT_TIME_MATERIAL: line1 = STR_TIME; break;
            default:                   line1 = STR_DRAW; break;
        }
    } else if(thinking) {
        line1 = STR_COMPUTER;
        line2 = STR_THINKS;
    } else if(input_phase == INPUT_PROMOTE) {
        line1 = STR_PROMOTE;
        line2 = "";
    } else if(check_square != NO_SQUARE) {
        line1 = STR_CHECK;
        line2 = (side == WHITE) ? STR_WHITE_DAT : STR_BLACK_DAT;
        color1 = COL_RED;
    }
    video_text_clear(1, ROW_STATUS, 9);
    video_text_clear(1, ROW_STATUS + 2, 9);
    video_text_centered(PANEL_CX, ROW_STATUS, line1, color1);
    video_text_centered(PANEL_CX, ROW_STATUS + 2, line2, COL_INK);
}

/**
 * @brief Draw one move of the list in figurine notation
 *
 * Piece letters become figurine glyphs, as in printed chess columns, and the
 * '=' of promotions is left out (e.g. "exd8♕+"). A move in a normal game
 * then takes at most six characters, so both columns of a row stay apart.
 */
static void draw_move_text(uint8_t col, uint8_t row, uint16_t half_move, uint8_t color) {
    char san[8], buf[8];
    char* p = buf;
    const char* q;

    match_san(half_move, san);
    for(q = san; *q; q++) {
        switch(*q) {
            case '=': break;
            case 'N': *p++ = FIGURINE_CODE + KNIGHT; break;
            case 'B': *p++ = FIGURINE_CODE + BISHOP; break;
            case 'R': *p++ = FIGURINE_CODE + ROOK; break;
            case 'Q': *p++ = FIGURINE_CODE + QUEEN; break;
            case 'K': *p++ = FIGURINE_CODE + KING; break;
            default: *p++ = *q;
        }
    }
    *p = 0;
    video_text(col, row, buf, color);
}

/**
 * @brief Draw the move list, scrolled so the current move is visible
 *
 * Each row holds one full move: number (columns 0-1), white's move (from
 * column 3) and black's move (from column 10). The row of the move in
 * progress is highlighted and shows '---' for the side to move.
 */
static void draw_moves(void) {
    uint16_t current, first, n, white_ply;
    uint8_t k, hl, row, col = MOVE_TEXT_X / 8;
    uint8_t over = (match_state == MATCH_OVER);
    uint8_t color;
    char num[3];

    current = over ? (ply + 1) >> 1 : (ply >> 1) + 1;
    if(current == 0) current = 1;
    first = current > MOVE_ROWS ? current - MOVE_ROWS + 1 : 1;

    for(k=0; k<MOVE_ROWS; k++) {
        n = first + k;
        hl = (n == current);
        color = hl ? COL_CREAM : COL_INK;
        row = MOVES_Y / 8 + k * 2;
        video_layer0_block(MOVE_REGION_COL, MOVE_REGION_ROW + k, MOVE_REGION_W, 1,
                           &move_row_tiles[((k & 1) * 2 + hl) * MOVE_REGION_W]);
        video_text_clear(col, row, 16);
        if(n > current) continue;

        num[0] = (n >= 10) ? '0' + (n / 10) % 10 : ' ';
        num[1] = '0' + n % 10;
        num[2] = 0;
        video_text(col, row, num, hl ? COL_CREAM : COL_GREY);

        white_ply = (n - 1) << 1;
        if(white_ply < ply) {
            draw_move_text(col + 3, row, white_ply, color);
            if(white_ply + 1 < ply) {
                draw_move_text(col + 10, row, white_ply + 1, color);
            } else if(!over) {
                video_text(col + 10, row, STR_PLACEHOLDER, COL_CREAM);
            }
        } else if(!over) {
            video_text(col + 3, row, STR_PLACEHOLDER, COL_CREAM);
        }
    }
}

/**
 * @brief Redraw everything that depends on the game state
 */
static void refresh_all(void) {
    check_square = (match_state == MATCH_PLAYING && rules_in_check()) ?
                   rules_king_square(side) : NO_SQUARE;
    board_refresh();
    draw_plates();
    draw_clock(WHITE);
    draw_clock(BLACK);
    draw_status();
    draw_moves();
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
    draw_status();
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
            draw_status();
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

static void flip_board(void) {
    flipped ^= 1;
    cursor_col = 7 - cursor_col;
    cursor_row = 7 - cursor_row;
    draw_labels();
    draw_plates();
    draw_clock(WHITE);
    draw_clock(BLACK);
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
    draw_plates();
    draw_status();
}

/*****************************************************************************
 * PUBLIC INTERFACE
 *****************************************************************************/

/**
 * @brief Start a new game and draw the complete playing field
 */
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
    refresh_all();
    update_cursor();
}

/**
 * @brief Run the clocks; call once per frame (and while the engine thinks)
 */
void playfield_tick(void) {
    clock_t now = clock();
    clock_t delta = now - last_clock;

    last_clock = now;
    if(match_tick(delta > 120 ? 120 : (uint8_t)delta)) {
        draw_clock(side);
        if(match_state == MATCH_OVER) {
            input_phase = INPUT_MOVE;
            clear_selection();
            refresh_all();
        }
    }
}

/**
 * @brief Let the computer move when it is its turn
 */
void playfield_update(void) {
    if(!match_computer_to_move()) return;
    thinking = 1;
    input_phase = INPUT_MOVE;
    clear_selection();
    board_refresh();
    draw_status();
    match_computer_move(playfield_tick);
    thinking = 0;
    refresh_all();
}

/**
 * @brief Handle a key press
 */
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
        case 'F':
        case 'f':
            flip_board();
            return;
        case 'N':
        case 'n':
            playfield_new();
            return;
        case 'T':
        case 't':
            theme ^= 1;
            redraw_board();
            return;
        case 'C':
        case 'c':
            cycle_computer();
            return;
        default:
            return;
    }
    cursor_visible = 1;
    update_cursor();
}

/**
 * @brief Handle the mouse; call once per frame
 */
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

    if(pressed && x >= BOARD_X && x < BOARD_X + BOARD_PIXELS &&
       y >= BOARD_Y && y < BOARD_Y + BOARD_PIXELS) {
        cursor_col = (x - BOARD_X) / SQUARE;
        cursor_row = (y - BOARD_Y) / SQUARE;
        activate(square_at(cursor_col, cursor_row));
    }
}
