#include <ascii_charmap.h>
#pragma static-locals (on)
/* The menu executes only while RAM bank 21 is selected. */
#pragma code-name ("MENUCODE")
#pragma rodata-name ("MENUCODE")
#include "video.h"
#include "playfield.h"
#include "match.h"
#include "start.h"

uint8_t start_computer = COMPUTER_BLACK;
uint8_t start_difficulty = 1;
uint8_t start_piece_set;
static uint8_t selection, setup, resumable, last_buttons;
static const char* const sides[] = {"WHITE", "BLACK", "TWO PLAYERS"};
static const char* const levels[] = {"EASY", "NORMAL", "HARD"};
static const uint8_t computers[] = {COMPUTER_BLACK, COMPUTER_WHITE, COMPUTER_NONE};
static uint8_t player_side;
static const char* const boards[] = {"FINE HATCH", "WOOD", "CROSSHATCH", "COARSE HATCH"};
static const char* const pieces[] = {"VICTORIAN", "CONTINENTAL", "LETTERPRESS"};
static const uint8_t back_rank[] = {3, 1, 2, 4, 5, 2, 1, 3};
static const char arrow_left[] = {MENU_ARROW_LEFT, 0};
static const char arrow_right[] = {MENU_ARROW_RIGHT, 0};

static void draw_setting(uint8_t row, const char* value, uint8_t active, uint8_t enabled) {
    uint8_t color = enabled ? (active ? COL_RED : COL_INK) : COL_GREY;
    video_text_centered(480, row, value, enabled ? COL_INK : COL_GREY);
    video_text(44, row, arrow_left, color);
    video_text(75, row, arrow_right, color);
}

/* Preview the initial position without starting or altering a match. The
 * resident video functions restore bank 21 after consulting square tables. */
static void draw_preview(void) {
    uint8_t f, r, piece;
    char label[2];
    label[1] = 0;
    for(r=0; r<8; r++) {
        label[0] = '8' - r;
        video_text(RANK_LABEL_COL_LEFT, 4 + r * 7, label, COL_INK);
        video_tile(6 + r * 7, 58, L1_FILES + r, COL_INK);
        for(f=0; f<8; f++) {
            video_square(3 + f * 7, 1 + r * 7,
                         ((playfield_theme << 1) + ((f + r) & 1)) * SQ_STATES);
            piece = r == 0 ? back_rank[f] + 6 : r == 1 ? 6 :
                    r == 6 ? 0 : r == 7 ? back_rank[f] : 0xFF;
            video_piece(3 + f * 7, 1 + r * 7, piece);
        }
    }
}

static void draw_option_setting(uint8_t row, const char* value, uint8_t active) {
    video_text_centered(560, row, value, COL_INK);
    video_text(61, row, arrow_left, active ? COL_RED : COL_INK);
    video_text(78, row, arrow_right, active ? COL_RED : COL_INK);
}

static void draw_menu(void) {
    uint8_t i, color;
    const char* label;
    if(setup == 2) {
        video_clear_block(61, 17, 19, 43);
        video_text(61, 17, "BOARD", COL_RED);
        draw_option_setting(20, boards[playfield_theme], selection == 0);
        video_text(61, 26, "CHESS SET", COL_RED);
        draw_option_setting(29, pieces[start_piece_set], selection == 1);
        video_text_centered(560, 39, "DONE", selection == 2 ? COL_RED : COL_INK);
        if(selection == 2) video_text(61, 39, arrow_right, COL_RED);
        video_text_centered(560, 48, "UP/DOWN SELECT", COL_INK);
        video_text_centered(560, 51, "LEFT/RIGHT CHANGE", COL_INK);
        video_text_centered(560, 54, "ENTER DONE", COL_INK);
        video_text_centered(560, 57, "ESC BACK", COL_INK);
        video_present();
        return;
    }
    if(setup == 1) {
        /* Clear the menu area only: layer 1 also holds queen artwork. */
        video_clear_block(40, 17, 40, 43);
        video_text(44, 17, "PLAY AS", COL_RED);
        draw_setting(20, sides[player_side], selection == 0, 1);
        video_text(44, 26, "CPU DIFFICULTY", COL_RED);
        label = levels[start_difficulty];
        if(player_side == 2) label = "NOT USED";
        draw_setting(29, label, selection == 1, player_side != 2);
        video_text(44, 32, player_side == 2 ? "LOCAL TWO PLAYER" : start_difficulty == 0 ? "2 SEC / MOVE" : start_difficulty == 1 ? "10 SEC / MOVE" : "20 SEC / MOVE", COL_GREY);
        video_text(44, 39, "START GAME", selection == 2 ? COL_RED : COL_INK);
        if(selection == 2) video_text(42, 39, arrow_right, COL_RED);
        video_text_centered(480, 48, "UP/DOWN SELECT", COL_INK);
        video_text_centered(480, 51, "LEFT/RIGHT CHANGE", COL_INK);
        video_text_centered(480, 54, "ENTER START", COL_INK);
        video_text_centered(480, 57, "ESC BACK", COL_INK);
        video_present();
        return;
    }
    video_clear_block(0, 46, 80, 14);
    for(i=0; i<3; i++) {
        label = i == 0 ? "NEW GAME" : i == 1 ? "CONTINUE" : "OPTIONS";
        color = i == selection ? COL_RED : COL_INK;
        if(i == 1 && !resumable) color = COL_GREY;
        video_text_centered(320, 47 + i * 3, label, color);
    }
    video_text_centered(320, 57, "UP/DOWN  ENTER TO SELECT", COL_INK);
    video_present();
}

uint8_t start_open(uint8_t can_continue) {
    resumable = can_continue;
    selection = setup = last_buttons = 0;
    if(!video_show_start()) return 0;
    draw_menu();
    return 1;
}

static uint8_t change(uint8_t backward) {
    if(setup == 2) {
        if(selection == 0) {
            playfield_theme = backward ? (playfield_theme == 0 ? THEMES - 1 : playfield_theme - 1) : (playfield_theme + 1) % THEMES;
        } else if(selection == 1) {
            start_piece_set = backward ? (start_piece_set == 0 ? 2 : start_piece_set - 1) : (start_piece_set + 1) % 3;
            if(!video_load_piece_set()) return START_ERROR;
        } else return START_NONE;
        draw_preview();
        draw_menu();
        return START_NONE;
    }
    if(selection == 0) {
        player_side = backward ? (player_side == 0 ? 2 : player_side - 1) : (player_side + 1) % 3;
    } else if(selection == 1 && player_side != 2) {
        start_difficulty = backward ? (start_difficulty == 0 ? 2 : start_difficulty - 1) : (start_difficulty + 1) % 3;
    }
    draw_menu();
    return START_NONE;
}

static uint8_t activate(void) {
    if(setup == 2) {
        if(selection != 2) return change(0);
        setup = selection = 0;
        if(!video_show_start()) return START_ERROR;
        draw_menu();
    } else if(setup == 1) {
        if(selection == 2) {
            start_computer = computers[player_side];
            return START_NEW;
        }
        return change(0);
    } else if(selection == 1) {
        if(resumable) return START_CONTINUE;
    } else {
        if(selection == 2) {
            if(!video_show_options()) return START_ERROR;
            setup = 2;
            draw_preview();
        } else {
            if(!video_show_setup()) return START_ERROR;
            setup = 1;
        }
        selection = 0;
        draw_menu();
    }
    return START_NONE;
}

uint8_t start_key(uint8_t key) {
    switch(key) {
        case KEY_UP:
            selection = selection == 0 ? 2 : selection - 1;
            if(!setup && !resumable && selection == 1) selection = 0;
            break;
        case KEY_DOWN:
            selection = selection == 2 ? 0 : selection + 1;
            if(!setup && !resumable && selection == 1) selection = 2;
            break;
        case KEY_LEFT: case KEY_RIGHT:
            if(setup) return change(key == KEY_LEFT);
            return START_NONE;
        case KEY_RETURN: case KEY_SPACE:
            if(setup) selection = 2;
            return activate();
        case KEY_ESCAPE:
            if(setup) {
                setup = selection = 0;
                if(!video_show_start()) return START_ERROR;
            } else if(resumable) return START_CONTINUE;
            break;
        case 'N': case 'n':
            if(!setup) { selection = 0; return activate(); }
            return START_NONE;
        case 'C': case 'c':
            if(!setup && resumable) return START_CONTINUE;
            return START_NONE;
        case 'O': case 'o':
            if(!setup) { selection = 2; return activate(); }
            return START_NONE;
        default: return START_NONE;
    }
    draw_menu();
    return START_NONE;
}

uint8_t start_mouse(uint16_t x, uint16_t y, uint8_t buttons) {
    uint8_t pressed = (buttons & 1) && !(last_buttons & 1);
    last_buttons = buttons;
    if(!pressed) return START_NONE;
    if(setup == 2) {
        if(x < 488 || x >= 632) return START_NONE;
        if(y >= 136 && y < 184) selection = 0;
        else if(y >= 208 && y < 248) selection = 1;
        else if(y >= 304 && y < 336) selection = 2;
        else return START_NONE;
        if(selection < 2) return change(x < 512);
    } else if(setup == 1) {
        if(x < 344 || x >= 616) return START_NONE;
        if(y >= 136 && y < 184) selection = 0;
        else if(y >= 208 && y < 248) selection = 1;
        else if(y >= 304 && y < 336) selection = 2;
        else return START_NONE;
        if(selection < 2) {
            return change(x < 376);  /* left triangle decrements, right/value increments */
        }
    } else {
        if(x < 240 || x >= 400) return START_NONE;
        if(y >= 376 && y < 392) selection = 0;
        else if(y >= 400 && y < 416) {
            if(!resumable) return START_NONE;
            selection = 1;
        }
        else if(y >= 424 && y < 440) selection = 2;
        else return START_NONE;
    }
    draw_menu();
    return activate();
}
