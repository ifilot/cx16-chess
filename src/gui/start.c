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

#include <ascii_charmap.h>
/* Menu code is nonrecursive and runs only in the main loop. */
#pragma static-locals (on)
/* The menu executes only while RAM bank 21 is selected. */
#pragma code-name ("MENUCODE")
#pragma rodata-name ("MENUCODE")
#include "video.h"
#include "playfield.h"
#include "match.h"
#include "start.h"
#include "build_info.h"
#include "storage.h"
#include "sound.h"
#include <string.h>

/*
 * The menus before a game. setup selects the screen: 0 main menu, 1 New
 * Game setup, 2 Options (with a full-size board preview), 3 About. Menus
 * redraw only the controls whose focus or value changed.
 */

uint8_t start_computer = COMPUTER_BLACK;
uint8_t start_difficulty = DEFAULT_DIFFICULTY;
uint8_t start_black_difficulty = DEFAULT_DIFFICULTY;
uint8_t start_piece_set;
static uint8_t selection;               // focused entry of the current screen
static uint8_t setup;                   // 0 main, 1 setup, 2 options, 3 about
static uint8_t resumable;               // 1 when Continue is available
static uint8_t last_buttons;            // mouse buttons of the previous frame
static uint8_t drawn_selection;         // entry currently drawn in red
static char field[35];                  // scratch line for text_field()
static const char* preference_message;  // result of Save Preferences, or 0
static const char* const sides[] = {"WHITE", "BLACK", "CPU VS CPU", "TWO PLAYERS"}; // by player_side
/* Local benchmark estimates rounded to 50 Elo, indexed by DIFFICULTY_*. */
static const char* const levels[] = {
    "MEDIUM (~1350 ELO)", "CHALLENGING (~1400 ELO)", "STRONG (~1450 ELO)",
    "5 PLY (~1400 ELO)", "DEEP (~1450 ELO)", "CASUAL (~1200 ELO)",
    "EASY (~1100 ELO)", "BEGINNER (~800 ELO)",
    "VERY HARD (~1600 ELO)", "ANALYSIS (~1750 ELO)"
};
/* Keep legacy 5-ply saves playable, but omit that depth from the new ladder.
 * Left/Right step through DIFFICULTY_* IDs in order of strength. */
#pragma rodata-name (push, "RODATA")
static const uint8_t next_level[] = {1, 2, 4, 4, 8, 0, 5, 6, 9, 7};
static const uint8_t previous_level[] = {5, 0, 1, 2, 2, 6, 7, 9, 4, 8};
#pragma rodata-name (pop)
static const uint8_t computers[] = {COMPUTER_BLACK, COMPUTER_WHITE, COMPUTER_BOTH, COMPUTER_NONE}; // by player_side
static uint8_t player_side;             // 0 White, 1 Black, 2 CPU vs CPU, 3 two players
static const char* const boards[] = {"FINE HATCH", "WOOD", "CROSSHATCH", "COARSE HATCH"}; // by THEME_*
static const char* const pieces[] = {"VICTORIAN", "CONTINENTAL", "LETTERPRESS"};
static const uint8_t back_rank[] = {3, 1, 2, 4, 5, 2, 1, 3}; // piece images a..h: R N B Q K B N R
static const char arrow_left[] = {MENU_ARROW_LEFT, 0};
static const char arrow_right[] = {MENU_ARROW_RIGHT, 0};
static const char blank[] = " ";

/**
 * @brief Overwrite a complete text field in one pass, including old
 *        trailing ink
 *
 * @param col      Tile column of the field
 * @param row      Tile row of the field
 * @param width    Field width in characters, at most 34
 * @param value    Text to show
 * @param color    Palette ink (COL_*)
 * @param centered 1 to centre the text within the field
 */
static void text_field(uint8_t col, uint8_t row, uint8_t width, const char* value, uint8_t color, uint8_t centered) {
    uint8_t i, offset = centered ? (width - strlen(value) + 1) / 2 : 0;
    for(i = 0; i < width; i++) field[i] = ' ';
    for(i = 0; value[i]; i++) field[offset + i] = value[i];
    field[width] = 0;
    video_text(col, row, field, color);
}
void start_draw_time(uint8_t white, uint8_t black, uint8_t players); // resident entry in drag.s

/**
 * @brief Draw the average move time and, for levels above Strong, the red
 *        calculation-time warning
 */
static void setup_hint(void) {
    uint8_t slow = player_side != 3 &&
        (start_difficulty == 4 || start_difficulty >= DIFFICULTY_SEVEN_PLY ||
         (player_side == 2 && (start_black_difficulty == 4 || start_black_difficulty >= DIFFICULTY_SEVEN_PLY)));
    start_draw_time(start_difficulty, start_black_difficulty, player_side);
    text_field(44, 44, 32, slow ? "\x7F VERY HIGH CALCULATION TIMES \x7F" : "", COL_RED, 1);
}

/**
 * @brief Draw the side and difficulty values and their headings
 */
static void setup_values(void) {
    const char* level = levels[start_difficulty];
    if(player_side == 3) level = "NOT USED";
    text_field(45, 20, 30, sides[player_side], COL_INK, 1);
    text_field(44, 26, 14, player_side == 2 ? "WHITE CPU" : "CPU DIFFICULTY", COL_RED, 0);
    text_field(45, 29, 30, level, player_side == 3 ? COL_GREY : COL_INK, 1);
    if(player_side == 2) {
        video_text(44, 34, "BLACK CPU", COL_RED);
        text_field(45, 37, 30, levels[start_black_difficulty], COL_INK, 1);
    }
    setup_hint();
}

/**
 * @brief Draw one entry of the current screen, in red when focused
 *
 * Unavailable entries (Continue without a game, difficulty in a two-player
 * game) are grey. Options entries 2 and 3 are the audio controls, drawn by
 * the audio bank.
 *
 * @param index Entry of the current screen
 */
static void draw_focus(uint8_t index) {
    const char* value;
    uint8_t color = selection == index ? COL_RED : COL_INK;
    uint8_t row;
    if(!setup) {
        if(index == 1 && !resumable) color = COL_GREY;
        video_text(36, 46 + index * 2, index == 0 ? "NEW GAME" : index == 1 ? "CONTINUE" : index == 2 ? "LOAD GAME" : index == 3 ? "OPTIONS" : index == 4 ? "ABOUT" : "EXIT", color);
    } else if(setup == 1) {
        if(index < (player_side == 2 ? 3 : 2)) {
            // a setting with its value between left and right arrows
            row = index == 0 ? 20 : index == 1 ? 29 : 37;
            if(index == 1 && player_side == 3) color = COL_GREY;
            if(index == 0) value = sides[player_side];
            else if(index == 2) value = levels[start_black_difficulty];
            else if(player_side == 3) value = "NOT USED";
            else value = levels[start_difficulty];
            text_field(45, row, 30, value, color, 1);
            video_text(44, row, arrow_left, color);
            video_text(75, row, arrow_right, color);
        } else {
            row = player_side == 2 ? 41 : 39;
            video_text(44, row, "START GAME", color);
            video_text(42, row, selection == index ? arrow_right : blank, COL_RED);
        }
    } else if(setup == 2) {
        if(index < 2) {
            row = index ? 29 : 20;
            text_field(62, row, 16, index ? pieces[start_piece_set] : boards[playfield_theme], color, 1);
            video_text(61, row, arrow_left, color);
            video_text(78, row, arrow_right, color);
        } else if(index < 4) sound_event(SOUND_OPTIONS + selection);
        else video_text_centered(560, index == 4 ? 42 : 46, index == 4 ? "SAVE PREFERENCES" : "DONE", color);
    }
}

/**
 * @brief Move the red focus from the previously drawn entry to selection
 */
static void update_focus(void) {
    if(drawn_selection != selection) {
        draw_focus(drawn_selection);
        draw_focus(selection);
        drawn_selection = selection;
    }
}

/**
 * @brief Draw the initial position on the Options board preview
 *
 * Previews without starting or altering a match. The resident video
 * functions restore bank 21 after consulting square tables.
 *
 * @param background 1 to draw the squares (and, with foreground, labels)
 * @param foreground 1 to draw the pieces
 */
static void draw_preview(uint8_t background, uint8_t foreground) {
    uint8_t f, r, piece;
    char label[2];
    label[1] = 0;
    for(r=0; r<8; r++) {
        label[0] = '8' - r;
        if(background && foreground) {
            video_text(RANK_LABEL_COL_LEFT, 4 + r * 7, label, COL_INK);
            video_tile(6 + r * 7, 58, L1_FILES + r, COL_INK);
        }
        for(f=0; f<8; f++) {
            if(background) video_square(3 + f * 7, 1 + r * 7,
                         ((playfield_theme << 1) + ((f + r) & 1)) * SQ_STATES);
            // piece images 0-5 are white, 6-11 black; 0xFF leaves the square empty
            piece = r == 0 ? back_rank[f] + 6 : r == 1 ? 6 :
                    r == 6 ? 0 : r == 7 ? back_rank[f] : 0xFF;
            if(foreground && piece != 0xFF) video_piece(3 + f * 7, 1 + r * 7, piece);
        }
    }
}

/**
 * @brief Draw all text and controls of the current screen and present it
 */
static void draw_menu(void) {
    uint8_t i;
    drawn_selection = selection;
    if(setup == 3) {
        video_clear_block(40, 17, 40, 43);
        video_text(43, 17, "CX16 CHESS " CHESS_VERSION, COL_RED);
        video_text(43, 22, "AUTHOR", COL_RED);
        video_text(43, 25, "Ivo Filot", COL_INK);
        video_text(43, 30, "COMPILATION", COL_RED);
        video_text(43, 33, "cc65 / 65C02", COL_INK);
        video_text(43, 36, "Built " CHESS_BUILD_DATE, COL_INK);
        video_text(43, 41, "GITHUB REPOSITORY", COL_RED);
        video_text(43, 44, "github.com/ifilot/cx16-chess", COL_INK);
        video_text_centered(480, 51, "BACK", COL_INK);
        video_text_centered(480, 57, "ENTER / ESC BACK", COL_INK);
        video_present();
        return;
    }
    if(setup == 2) {
        video_clear_block(61, 17, 19, 43);
        video_text(61, 17, "BOARD", COL_RED);
        text_field(62, 20, 16, boards[playfield_theme], COL_INK, 1);
        video_text(61, 26, "CHESS SET", COL_RED);
        text_field(62, 29, 16, pieces[start_piece_set], COL_INK, 1);
        for(i = 0; i < 6; i++) draw_focus(i);
        if(preference_message) video_text_centered(560, 49, preference_message, COL_RED);
        video_text_centered(560, 52, "UP/DOWN SELECT", COL_INK);
        video_text_centered(560, 55, "ENTER SELECT", COL_INK);
        video_text_centered(560, 58, "ESC BACK", COL_INK);
        video_present();
        return;
    }
    if(setup == 1) {
        /* Clear the menu area only: layer 1 also holds queen artwork. */
        video_clear_block(40, 17, 40, 43);
        video_text(44, 17, "PLAY AS", COL_RED);
        setup_values();
        for(i = 0; i <= (player_side == 2 ? 3 : 2); i++) draw_focus(i);
        video_text_centered(480, 48, "UP/DOWN SELECT", COL_INK);
        video_text_centered(480, 51, "LEFT/RIGHT CHANGE", COL_INK);
        video_text_centered(480, 54, "ENTER START", COL_INK);
        video_text_centered(480, 57, "ESC BACK", COL_INK);
        video_present();
        return;
    }
    video_clear_block(0, 46, 80, 14);
    for(i=0; i<6; i++) draw_focus(i);
    video_present();
}

/**
 * @brief Load the start screen and draw the main menu
 *
 * @param can_continue 1 when a game in RAM can be continued
 *
 * @return 0 when the artwork could not be loaded
 */
uint8_t start_open(uint8_t can_continue) {
    sound_event(SOUND_MENU);
    resumable = can_continue;
    selection = setup = last_buttons = 0;
    preference_message = 0;
    player_side = start_computer == COMPUTER_WHITE ? 1 : start_computer == COMPUTER_BOTH ? 2 : start_computer == COMPUTER_NONE ? 3 : 0;
    if(!video_show_start()) return 0;
    draw_menu();
    return 1;
}

/**
 * @brief Change the value of the focused setting in New Game or Options
 *
 * Board and piece-set changes update the preview immediately. Switching to
 * or from CPU vs CPU adds or removes the Black CPU rows.
 *
 * @param backward 1 to step to the previous value, 0 for the next
 *
 * @return START_NONE, or START_ERROR when a piece set failed to load
 */
static uint8_t change(uint8_t backward) {
    uint8_t previous_side = player_side, i;
    sound_sfx(SFX_MENU_SELECT);
    update_focus();
    if(setup == 2) {
        if(selection == 0) {
            playfield_theme = backward ? (playfield_theme == 0 ? THEMES - 1 : playfield_theme - 1) : (playfield_theme + 1) % THEMES;
            draw_preview(1, 0);
            text_field(62, 20, 16, boards[playfield_theme], COL_RED, 1);
        } else if(selection == 1) {
            start_piece_set = backward ? (start_piece_set == 0 ? 2 : start_piece_set - 1) : (start_piece_set + 1) % 3;
            if(!video_load_piece_set()) return START_ERROR;
            draw_preview(0, 1);
            text_field(62, 29, 16, pieces[start_piece_set], COL_RED, 1);
            video_present();
        } else if(selection < 4) {
            sound_event(selection == 2 ? SOUND_MUSIC_TOGGLE : SOUND_EFFECTS_TOGGLE);
            sound_event(SOUND_OPTIONS + selection);
        }
        return START_NONE;
    }
    if(selection == 0) {
        player_side = backward ? (player_side == 0 ? 3 : player_side - 1) : (player_side + 1) % 4;
        // blank the rows whose layout differs between one and two CPUs
        if(player_side == 2) {
            text_field(42, 32, 34, "", COL_INK, 0);
            text_field(42, 39, 34, "", COL_INK, 0);
        } else if(previous_side == 2) {
            text_field(42, 34, 34, "", COL_INK, 0);
            text_field(42, 37, 34, "", COL_INK, 0);
            text_field(42, 41, 34, "", COL_INK, 0);
        }
        setup_values();
        for(i = 0; i <= (player_side == 2 ? 3 : 2); i++) draw_focus(i);
    } else if(selection == 1 && player_side != 3) {
        start_difficulty = backward ? previous_level[start_difficulty] : next_level[start_difficulty];
        text_field(45, 29, 30, levels[start_difficulty], COL_RED, 1);
        setup_hint();
    } else if(selection == 2 && player_side == 2) {
        start_black_difficulty = backward ? previous_level[start_black_difficulty] : next_level[start_black_difficulty];
        text_field(45, 37, 30, levels[start_black_difficulty], COL_RED, 1);
        setup_hint();
    }
    return START_NONE;
}

/**
 * @brief Carry out the focused entry: open a screen, change a setting,
 *        save preferences, or leave the menus
 *
 * @return One of the START_* values
 */
static uint8_t activate(void) {
    sound_sfx(SFX_MENU_SELECT);
    if(setup == 3) {
        setup = selection = 0;
        if(!video_show_start()) return START_ERROR;
        draw_menu();
    } else if(setup == 2) {
        if(selection < 4) return change(0);
        if(selection == 4) {
            preference_message = preferences_save() ? "PREFERENCES SAVED" : "SAVE FAILED";
            sound_sfx(preference_message[0] == 'P' ? SFX_SAVE : SFX_ERROR);
            text_field(61, 49, 19, preference_message, COL_RED, 1);
            return START_NONE;
        }
        setup = selection = 0;
        if(!video_show_start()) return START_ERROR;
        draw_menu();
    } else if(setup == 1) {
        if(selection == (player_side == 2 ? 3 : 2)) {
            start_computer = computers[player_side];
            return START_NEW;
        }
        return change(0);
    } else if(selection == 1) {
        if(resumable) return START_CONTINUE;
    } else {
        if(selection == 5) return START_EXIT;
        if(selection == 2) return START_LOAD;
        if(selection == 4) {
            if(!video_show_about()) return START_ERROR;
            setup = 3;
        } else if(selection == 3) {
            preference_message = 0;
            if(!video_show_options()) return START_ERROR;
            setup = 2;
            draw_preview(1, 1);
        } else {
            if(!video_show_setup()) return START_ERROR;
            setup = 1;
        }
        selection = 0;
        draw_menu();
    }
    return START_NONE;
}

/**
 * @brief Handle a key press in the menus
 *
 * Up/Down move the focus (skipping an unavailable Continue), Left/Right
 * change a setting, Return/Space activate and Escape goes back. In the
 * main menu N, C, L, A, O and X are shortcuts; V and S toggle the audio.
 *
 * @param key PETSCII keycode returned by GETIN
 *
 * @return One of the START_* values
 */
uint8_t start_key(uint8_t key) {
    switch(key) {
        case 'V': case 'v': sound_event(SOUND_MUSIC_TOGGLE); if(setup == 2) sound_event(SOUND_OPTIONS + selection); return START_NONE;
        case 'S': case 's': sound_event(SOUND_EFFECTS_TOGGLE); if(setup == 2) sound_event(SOUND_OPTIONS + selection); return START_NONE;
        case KEY_UP:
            sound_sfx(SFX_MENU_MOVE);
            if(setup == 3) return START_NONE;
            selection = selection == 0 ? (setup == 2 ? 5 : setup ? (player_side == 2 ? 3 : 2) : 5) : selection - 1;
            if(!setup && !resumable && selection == 1) selection = 0;
            break;
        case KEY_DOWN:
            sound_sfx(SFX_MENU_MOVE);
            if(setup == 3) return START_NONE;
            selection = selection == (setup == 2 ? 5 : setup ? (player_side == 2 ? 3 : 2) : 5) ? 0 : selection + 1;
            if(!setup && !resumable && selection == 1) selection = 2;
            break;
        case KEY_LEFT: case KEY_RIGHT:
            if(setup && setup != 3) return change(key == KEY_LEFT);
            return START_NONE;
        case KEY_RETURN: case KEY_SPACE:
            // Return in New Game always starts, whichever row has the focus
            if(setup == 1) selection = player_side == 2 ? 3 : 2;
            return activate();
        case KEY_ESCAPE:
            sound_sfx(SFX_MENU_BACK);
            if(setup) {
                setup = selection = 0;
                if(!video_show_start()) return START_ERROR;
                draw_menu();
                return START_NONE;
            } else if(resumable) return START_CONTINUE;
            break;
        case 'N': case 'n':
            if(!setup) { selection = 0; return activate(); }
            return START_NONE;
        case 'C': case 'c':
            if(!setup && resumable) return START_CONTINUE;
            return START_NONE;
        case 'L': case 'l':
            if(!setup) return START_LOAD;
            return START_NONE;
        case 'X': case 'x':
            if(!setup) return START_EXIT;
            return START_NONE;
        case 'A': case 'a':
            if(!setup) { selection = 4; return activate(); }
            return START_NONE;
        case 'O': case 'o':
            if(!setup) { selection = 3; return activate(); }
            return START_NONE;
        default: return START_NONE;
    }
    update_focus();
    return START_NONE;
}

uint8_t gui_mouse_hit(uint16_t x, uint16_t y, uint8_t layout); // resident entry in drag.s

/**
 * @brief Handle the mouse; hovering selects, a new left click activates
 *
 * Clicking a setting changes its value: the left part of the field steps
 * backward, the right part forward.
 *
 * @param x       Pointer position in screen pixels
 * @param y       Pointer position in screen pixels
 * @param buttons KERNAL mouse button bits; bit 0 is the left button
 *
 * @return One of the START_* values
 */
uint8_t start_mouse(uint16_t x, uint16_t y, uint8_t buttons) {
    static uint16_t last_x, last_y;     // pointer position of the previous call
    uint8_t pressed = (buttons & 1) && !(last_buttons & 1), index;
    uint8_t moved = x != last_x || y != last_y;
    last_buttons = buttons;
    last_x = x; last_y = y;
    if(!pressed && !moved) return START_NONE;
    // hit-test layouts: 0 main, 1 setup, 2 setup with two CPUs, 3 options, 4 about
    index = gui_mouse_hit(x, y, setup == 3 ? 4 : setup == 2 ? 3 :
                         setup == 1 ? (player_side == 2 ? 2 : 1) : 0);
    if(setup == 3) {
        video_text_centered(480, 51, "BACK", index == 0 ? COL_RED : COL_INK);
    }
    if(index == 0xFF || (!setup && index == 1 && !resumable) ||
       (setup == 1 && index == 1 && player_side == 3 && !pressed)) return START_NONE;
    selection = index;
    update_focus();
    if(!pressed) return START_NONE;
    if(setup == 2 && selection < 2) return change(x < 512);
    if(setup == 1 && selection < (player_side == 2 ? 3 : 2)) return change(x < 376);
    return activate();
}
