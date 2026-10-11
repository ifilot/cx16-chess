#include <ascii_charmap.h>
#include <cx16.h>
#include <stdlib.h>
#include "match.h"
#include "dialog.h"
#include "storage.h"
#include "video.h"
#include "playfield.h"
#include "sound.h"
#pragma static-locals (on)
#pragma code-name ("UICODE")
#pragma rodata-name ("UICODE")
#pragma bss-name ("UIBSS")

static uint8_t mode, selection, last_buttons, occupied[SAVE_SLOTS], confirm, back_hover;
static save_info_t info[SAVE_SLOTS];
static const char* const levels[] = {"2", "3", "4", "5", "6", "1", "EASY", "BEGIN.", "7", "8"};
static const char* const players[] = {"BOTH", "BLACK", "WHITE", "CPU/CPU"};
static const char* message;
static char label[24];
static const char* const choices[] = {"RESUME GAME", "SAVE GAME", "MAIN MENU"};

/* Sixteen connected line tiles, reserved beyond all game/splash artwork.
 * Bits select left, right, up and down arms of a one-pixel ink rule. */
#define RULE_TILES 1008
#define LINE_LEFT 1
#define LINE_RIGHT 2
#define LINE_UP 4
#define LINE_DOWN 8

#pragma code-name ("DRAGCODE")
#pragma bss-name ("DRAGBSS")
void dialog_build_rules_banked(void) {
    uint8_t mask, x, y, pair, pixel;
    uint32_t address = VRAM_L1_TILES + RULE_TILES * 32UL;
    VERA.control = 0;
    VERA.address = address;
    VERA.address_hi = 0x10 | (uint8_t)(address >> 16);
    for(mask = 0; mask < 16; mask++) {
        for(y = 0; y < 8; y++) {
            pair = 0;
            for(x = 0; x < 8; x++) {
                pixel = (y == 3 && ((x <= 3 && (mask & LINE_LEFT)) ||
                                   (x >= 3 && (mask & LINE_RIGHT)))) ||
                        (x == 3 && ((y <= 3 && (mask & LINE_UP)) ||
                                   (y >= 3 && (mask & LINE_DOWN))));
                pair = (pair << 4) | pixel;
                if(x & 1) VERA.data0 = pair;
            }
        }
    }
}
#pragma code-name ("UICODE")
#pragma bss-name ("UIBSS")
void dialog_build_rules(void);
static void rule(uint8_t col, uint8_t row, uint8_t mask) {
    video_tile(col, row, RULE_TILES + mask, COL_INK);
}
static void frame(uint8_t left, uint8_t top, uint8_t right, uint8_t bottom) {
    uint8_t col, row;
    for(col = left + 1; col < right; col++) {
        rule(col, top, LINE_LEFT | LINE_RIGHT);
        rule(col, bottom, LINE_LEFT | LINE_RIGHT);
    }
    for(row = top + 1; row < bottom; row++) {
        rule(left, row, LINE_UP | LINE_DOWN);
        rule(right, row, LINE_UP | LINE_DOWN);
    }
    rule(left, top, LINE_RIGHT | LINE_DOWN);
    rule(right, top, LINE_LEFT | LINE_DOWN);
    rule(left, bottom, LINE_RIGHT | LINE_UP);
    rule(right, bottom, LINE_LEFT | LINE_UP);
}
static void separator(uint8_t left, uint8_t right, uint8_t row) {
    uint8_t col;
    for(col = left + 1; col < right; col++) rule(col, row, LINE_LEFT | LINE_RIGHT);
    rule(left, row, LINE_UP | LINE_DOWN | LINE_RIGHT);
    rule(right, row, LINE_UP | LINE_DOWN | LINE_LEFT);
}

/* Opaque paper panel inside the board. Resume invalidates every board tile
 * and restores both background maps, as well as pieces and selection. */
static void paper(void) {
    uint8_t row, col, map;
    uint32_t address;
    VERA.control = 0;
    for(map = 0; map < 2; map++) {
        for(row = 10; row < 51; row++) {
            address = (map ? VRAM_L0_MAP_INFO : VRAM_L0_MAP_PLAIN) + (row * 128UL + 18) * 2;
            VERA.address = address;
            VERA.address_hi = 0x10 | (uint8_t)(address >> 16);
            for(col = 0; col < 40; col++) { VERA.data0 = 0; VERA.data0 = 0; }
        }
    }
    video_clear_block(18, 10, 40, 41);
    frame(18, 10, 57, 50);
}
static void column(uint8_t col) {
    uint8_t row;
    for(row = 14; row < 43; row++)
        rule(col, row, LINE_UP | LINE_DOWN | ((row >= 16 && (row - 16) % 3 == 0) ? LINE_LEFT | LINE_RIGHT : 0));
    rule(col, 13, LINE_LEFT | LINE_RIGHT | LINE_DOWN);
    rule(col, 43, LINE_LEFT | LINE_RIGHT | LINE_UP);
}
/* Selection changes overwrite only the labels; the paper and rules stay put. */
static void draw_choice(uint8_t index) {
    uint8_t color = selection == index ? COL_RED : COL_INK;
    uint8_t row = 17 + index * 3;
    if(confirm) {
        video_text_centered(304, index ? 28 : 23, index ? "REPLACE" : "CANCEL", color);
    } else if(!mode) {
        if(index < 3) video_text_centered(304, 22 + index * 5, choices[index], color);
        else sound_event(SOUND_PAUSE + selection);
    } else {
        label[0] = '1' + index;
        label[1] = 0;
        video_text(21, row, label, color);
        if(occupied[index]) {
            if(info[index].computer == COMPUTER_BOTH) {
                label[0] = levels[info[index].difficulty][0];
                label[1] = '/';
                label[2] = levels[info[index].black_difficulty][0];
                label[3] = 0;
                video_text(26, row, label, color);
            } else if(info[index].computer) video_text(26, row, levels[info[index].difficulty], color);
            else video_text(26, row, "LOCAL", color);
            video_text(35, row, players[info[index].computer], color);
            utoa(info[index].moves, label, 10);
            video_text(45, row, label, color);
        } else video_text(26, row, "EMPTY", color);
    }
}

static void draw(void) {
    uint8_t index;
    back_hover = 0;
    paper();
    if(confirm) {
        frame(23, 21, 53, 31);
        separator(23, 53, 26);
        video_text_centered(304, 15, "REPLACE SAVED GAME?", COL_RED);
        draw_choice(0);
        draw_choice(1);
        video_text_centered(304, 44, "ENTER SELECT / ESC CANCEL", COL_INK);
    } else if(!mode) {
        frame(23, 20, 53, 45);
        separator(23, 53, 35);
        separator(23, 53, 40);
        separator(23, 53, 25);
        separator(23, 53, 30);
        video_text_centered(304, 14, "GAME PAUSED", COL_RED);
        for(index = 0; index < 5; index++)
            draw_choice(index);
        video_text_centered(304, 48, "ESC RESUME", COL_INK);
    } else {
        video_text_centered(304, 11, mode == 1 ? "SAVE GAME" : "LOAD GAME", COL_RED);
        frame(19, 13, 56, 43);
        separator(19, 56, 16);
        for(index = 1; index < SAVE_SLOTS; index++) separator(19, 56, 16 + index * 3);
        column(24);
        column(33);
        column(43);
        video_text(20, 14, "SLOT", COL_INK);
        video_text(26, 14, "LEVEL", COL_INK);
        video_text(35, 14, "PLAYER", COL_INK);
        video_text(45, 14, "MOVES", COL_INK);
        for(index = 0; index < SAVE_SLOTS; index++) draw_choice(index);
        if(!message) video_text_centered(304, 44, "W/B: PLY OR B/E", COL_INK);
        video_text_centered(304, 46, "1-9 SELECT / ESC BACK", COL_INK);
        video_text_centered(304, 48, "BACK", COL_INK);
    }
    if(message) video_text_centered(304, 44, message, COL_RED);
    video_present();
}
static void slots(uint8_t load) {
    uint8_t index;
    sound_sfx(SFX_DIALOG);
    mode = load ? 2 : 1;
    selection = 0;
    message = 0;
    for(index = 0; index < SAVE_SLOTS; index++) occupied[index] = storage_probe(index, &info[index]);
    draw();
}
void dialog_open(uint8_t load) {
    sound_sfx(SFX_DIALOG);
    mode = selection = last_buttons = confirm = back_hover = 0;
    message = 0;
    video_cursor(0, 0, 0);
    dialog_build_rules();
    if(load) slots(1);
    else draw();
}
static uint8_t activate(void) {
    static uint8_t slot;
    sound_sfx(SFX_MENU_SELECT);
    if(confirm) {
        confirm = 0;
        if(selection == 0) { selection = slot; draw(); return DIALOG_NONE; }
        selection = slot;
    } else if(!mode) {
        if(selection == 0) return DIALOG_RESUME;
        if(selection == 2) return DIALOG_MENU;
        if(selection > 2) {
            sound_event(selection == 3 ? SOUND_MUSIC_TOGGLE : SOUND_EFFECTS_TOGGLE);
            sound_event(SOUND_PAUSE + selection);
        } else slots(0);
        return DIALOG_NONE;
    } else if(mode == 1 && occupied[selection]) {
        slot = selection;
        confirm = 1;
        selection = 0;
        message = 0;
        draw();
        return DIALOG_NONE;
    }
    if(mode == 2) {
        if(!occupied[selection]) message = "EMPTY SLOT";
        else if(storage_load(selection)) { sound_sfx(SFX_MENU_SELECT); return DIALOG_LOADED; }
        else message = "CANNOT LOAD THIS SAVE";
    } else {
        if(storage_save(selection)) {
            occupied[selection] = storage_probe(selection, &info[selection]);
            message = "GAME SAVED";
        } else message = "SAVE FAILED - TRY AGAIN";
    }
    sound_sfx(message[0] == 'G' ? SFX_SAVE : SFX_ERROR);
    draw();
    return DIALOG_NONE;
}
uint8_t dialog_key(uint8_t key) {
    uint8_t limit = confirm ? 1 : mode ? SAVE_SLOTS - 1 : 4;
    uint8_t previous = selection;
    switch(key) {
        case 'V': case 'v': sound_event(SOUND_MUSIC_TOGGLE); if(!mode && !confirm) sound_event(SOUND_PAUSE + selection); return DIALOG_NONE;
        case 'S': case 's': sound_event(SOUND_EFFECTS_TOGGLE); if(!mode && !confirm) sound_event(SOUND_PAUSE + selection); return DIALOG_NONE;
        case KEY_ESCAPE:
            sound_sfx(SFX_MENU_BACK);
            if(confirm) { confirm = 0; message = 0; selection = 0; }
            else if(mode == 2) return DIALOG_MENU;
            else if(mode == 1) { mode = selection = 0; message = 0; }
            else return DIALOG_RESUME;
            draw();
            return DIALOG_NONE;
        case KEY_UP: sound_sfx(SFX_MENU_MOVE); selection = selection ? selection - 1 : limit; break;
        case KEY_DOWN: sound_sfx(SFX_MENU_MOVE); selection = selection == limit ? 0 : selection + 1; break;
        case KEY_LEFT: case KEY_RIGHT:
            return !mode && !confirm && selection > 2 ? activate() : DIALOG_NONE;
        case KEY_RETURN: case KEY_SPACE: return activate();
        default:
            if(mode && !confirm && key >= '1' && key <= '9') selection = key - '1';
            else return DIALOG_NONE;
    }
    if(previous != selection) {
        draw_choice(previous);
        draw_choice(selection);
    }
    if(message) {
        message = 0;
        video_text_clear(19, 44, 38);
        if(mode && !confirm)
            video_text_centered(304, 44, "W/B: PLY OR B/E", COL_INK);
    }
    return DIALOG_NONE;
}
uint8_t gui_mouse_hit(uint16_t x, uint16_t y, uint8_t layout);
uint8_t dialog_mouse(uint16_t x, uint16_t y, uint8_t buttons) {
    static uint16_t last_x, last_y;
    uint8_t pressed = (buttons & 1) && !(last_buttons & 1), index, previous;
    uint8_t moved = x != last_x || y != last_y;
    last_buttons = buttons;
    last_x = x; last_y = y;
    if(!pressed && !moved) return DIALOG_NONE;
    index = gui_mouse_hit(x, y, confirm ? 7 : mode ? 6 : 5);
    if(mode && !confirm && back_hover != (index == SAVE_SLOTS)) {
        back_hover = index == SAVE_SLOTS;
        video_text_centered(304, 48, "BACK", back_hover ? COL_RED : COL_INK);
    }
    if(index == 0xFF) return DIALOG_NONE;
    if(index == SAVE_SLOTS) return pressed ? dialog_key(KEY_ESCAPE) : DIALOG_NONE;
    previous = selection;
    selection = index;
    if(selection != previous) {
        draw_choice(previous);
        draw_choice(selection);
    }
    return pressed ? activate() : DIALOG_NONE;
}
