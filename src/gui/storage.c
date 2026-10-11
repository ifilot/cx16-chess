#include <ascii_charmap.h>
#include <cbm.h>
#include <string.h>
#include "storage.h"
#include "gfx.h"
#include "match.h"
#include "playfield.h"
#include "start.h"
#include "sound.h"
void asset_close(void);
#pragma static-locals (on)
#pragma code-name ("UICODE")
#pragma rodata-name ("UICODE")
#pragma bss-name ("UIBSS")

/* Versioned, little-endian records, independent of C struct padding.
 * Each slot alternates two generations. A failed write leaves the other
 * generation intact; a checksum rejects interrupted or damaged records. */
#define HEADER 28
/* Small metadata buffers stay in main RAM; the large replay buffer is banked. */
#pragma bss-name (push, "BSS")
static uint8_t header[HEADER], prefs[10];
#pragma bss-name (pop)
static uint8_t moves[MAX_HISTORY * 3];
static rules_position_t previous;
static char filename[24];
static uint16_t count, generation;
static uint8_t chosen;
static move_t move;

/* Legacy time-based levels map to depths 2, 4 and 6. Keep their bytes intact
 * until after checksum verification, including latest-generation selection. */
static uint8_t level_count(uint8_t version) {
    return version == '1' ? 3 : version == '2' ? 5 : version == '3' ? 8 : DIFFICULTY_COUNT;
}

static uint8_t saved_level(uint8_t level) {
    return header[7] == '1' ? level * 2 : level;
}

static uint16_t word(uint8_t offset) {
    return header[offset] | ((uint16_t)header[offset + 1] << 8);
}
static void put_word(uint8_t offset, uint16_t value) {
    header[offset] = value;
    header[offset + 1] = value >> 8;
}
static uint16_t checksum(const uint8_t* data, uint16_t length, uint16_t value) {
    while(length--) value = (value << 5) ^ (value >> 11) ^ *data++;
    return value;
}
static uint16_t digest(void) {
    return checksum(moves, count * 3, checksum(header, HEADER - 2, 0xA761));
}
static void name(uint8_t slot, uint8_t copy, uint8_t write) {
    strcpy(filename, write ? "@:CHESS1A.SAV,S,W" : "CHESS1A.SAV,S,R");
    filename[write ? 7 : 5] = '1' + slot;
    filename[write ? 8 : 6] = 'A' + copy;
}
static uint8_t read_exact(void* data, uint16_t size) {
    int got;
    uint8_t* target = data;
    while(size) {
        got = cbm_read(3, target, size);
        if(got <= 0) return 0;
        target += got;
        size -= got;
    }
    return 1;
}
static uint8_t read_copy(uint8_t slot, uint8_t copy) {
    uint8_t ok, extra;
    name(slot, copy, 0);
    if(cbm_open(3, 8, 3, filename)) { cbm_close(3); return 0; }
    ok = read_exact(header, HEADER);
    if(ok) {
        count = word(10);
        ok = !memcmp(header, "X16SAVE", 7) && (header[7] >= '1' && header[7] <= '4') && count < MAX_HISTORY &&
             header[16] <= COMPUTER_BOTH && header[17] < level_count(header[7]) &&
             header[18] <= MATCH_OVER && header[19] <= RESULT_LENGTH &&
             header[20] < THEMES && header[21] < 3 && header[22] < 2 &&
             header[23] < 2 && header[24] < 60 && header[25] < level_count(header[7]) &&
             ((header[18] == MATCH_PLAYING) == (header[19] == RESULT_NONE));
    }
    if(ok) ok = read_exact(moves, count * 3) && digest() == word(26);
    if(ok) ok = cbm_read(3, &extra, 1) == 0;
    cbm_close(3);
    return ok;
}
static uint8_t latest(uint8_t slot) {
    uint8_t a, b;
    uint16_t first;
    a = read_copy(slot, 0);
    first = word(8);
    b = read_copy(slot, 1);
    if(!a && !b) return 0;
    chosen = b && (!a || (int16_t)(word(8) - first) > 0);
    if(!read_copy(slot, chosen)) return 0;
    generation = word(8);
    return 1;
}
uint8_t storage_probe(uint8_t slot, save_info_t* info) {
    asset_close();
    if(!latest(slot)) return 0;
    info->moves = count;
    info->computer = header[16];
    info->difficulty = saved_level(header[17]);
    info->black_difficulty = saved_level(header[25]);
    return 1;
}

/* Read the DOS status after close as well: write APIs alone cannot detect
 * disk-full and write-protection errors reported by the drive. Channel 14
 * is separate from the graphics loader's logical command channel 15. */
static uint8_t drive_ok(void) {
    uint8_t status[2], ok;
    if(cbm_open(14, 8, 15, "")) { cbm_close(14); return 0; }
    ok = cbm_read(14, status, 2) == 2 && status[0] == '0' && status[1] == '0';
    /* Drain the status line so later graphics seeks do not inherit errors. */
    while(cbm_read(14, status, 1) == 1 && status[0] != 13);
    cbm_close(14);
    return ok;
}
uint8_t storage_save(uint8_t slot) {
    uint16_t index, expected;
    uint8_t copy, ok;
    if(slot >= SAVE_SLOTS) return 0;
    asset_close();
    ok = latest(slot);
    copy = ok ? !chosen : 0;
    generation = ok ? generation + 1 : 1;
    /* latest() uses the candidate buffer; fill it only after choosing a copy. */
    memset(header, 0, HEADER);
    memcpy(header, "X16SAVE4", 8);
    put_word(8, generation);
    count = ply;
    put_word(10, count);
    put_word(12, match_clock[0]);
    put_word(14, match_clock[1]);
    header[16] = match_computer;
    header[17] = match_difficulty;
    header[18] = match_state;
    header[19] = match_result;
    header[20] = playfield_theme;
    header[21] = start_piece_set;
    header[22] = playfield_flipped;
    header[23] = playfield_info;
    header[24] = match_clock_fraction();
    header[25] = match_computer == COMPUTER_BOTH ? match_black_difficulty : 0;
    for(index = 0; index < count; index++) {
        match_move_at(index, &move);
        moves[index * 3] = move.from;
        moves[index * 3 + 1] = move.to;
        moves[index * 3 + 2] = move.promo;
    }
    expected = digest();
    put_word(26, expected);
    name(slot, copy, 1);
    if(cbm_open(3, 8, 3, filename)) { cbm_close(3); return 0; }
    ok = cbm_write(3, header, HEADER) == HEADER &&
         cbm_write(3, moves, count * 3) == count * 3;
    cbm_close(3);
    if(!ok || !drive_ok()) return 0;
    /* Verify the actual persisted bytes before reporting success. */
    return read_copy(slot, copy) && word(8) == generation && word(26) == expected;
}
static uint8_t validate_moves(void) {
    uint16_t index;
    uint8_t legal, found;
    rules_capture(&previous);
    rules_new_game();
    found = 1;
    for(index = 0; index < count; index++) {
        if(halfmove_clock >= 100 || rules_insufficient_material()) { found = 0; break; }
        rules_generate_legal();
        found = 0;
        for(legal = 0; legal < legal_count; legal++) {
            if(legal_moves[legal].from == moves[index * 3] &&
               legal_moves[legal].to == moves[index * 3 + 1] &&
               legal_moves[legal].promo == moves[index * 3 + 2]) {
                move = legal_moves[legal];
                found = rules_make(&move);
                rules_commit();
                break;
            }
        }
        if(!found) break;
    }
    rules_restore(&previous);
    return found;
}
uint8_t storage_load(uint8_t slot) {
    uint16_t index;
    const move_t* legal;
    asset_close();
    if(slot >= SAVE_SLOTS || !latest(slot) || !validate_moves()) return 0;
    match_new(1800, header[16]);
    for(index = 0; index < count; index++) {
        legal = match_find_move(moves[index * 3], moves[index * 3 + 1], moves[index * 3 + 2]);
        match_play(legal);
    }
    match_clock[0] = word(12);
    match_clock[1] = word(14);
    match_difficulty = saved_level(header[17]);
    match_black_difficulty = saved_level(header[25]);
    match_state = header[18];
    match_result = header[19];
    match_restore_fraction(header[24]);
    playfield_theme = header[20];
    start_piece_set = header[21];
    playfield_flipped = header[22];
    playfield_info = header[23];
    return 1;
}
void storage_preferences_load(void) {
    uint8_t ok, levels;
    asset_close();
    if(cbm_open(3, 8, 3, "CHESSOPT.DAT,S,R")) { cbm_close(3); return; }
    ok = read_exact(prefs, sizeof(prefs));
    cbm_close(3);
    levels = level_count(prefs[4]);
    if(!ok || memcmp(prefs, "X16P", 4) || (prefs[4] < '1' || prefs[4] > '5') || prefs[5] >= THEMES || prefs[6] >= 3 ||
       prefs[7] > (prefs[4] == '5' ? 15 : COMPUTER_BOTH) || prefs[8] >= ((prefs[7] & 3) == COMPUTER_BOTH ? levels * levels : levels) ||
       prefs[9] != (uint8_t)checksum(prefs, 9, 0xA761)) return;
    playfield_theme = prefs[5];
    start_piece_set = prefs[6];
    start_computer = prefs[7] & 3;
    start_difficulty = prefs[8] % levels;
    start_black_difficulty = start_computer == COMPUTER_BOTH ? prefs[8] / levels : DEFAULT_DIFFICULTY;
    sound_music_enabled = !(prefs[7] & 4);
    sound_effects_enabled = !(prefs[7] & 8);
    sound_event(SOUND_APPLY);
    if(prefs[4] == '1') {
        start_difficulty *= 2;
        if(prefs[7] == COMPUTER_BOTH) start_black_difficulty *= 2;
    }
}
uint8_t storage_preferences_save(void) {
    uint8_t ok;
    asset_close();
    memcpy(prefs, "X16P5", 5);
    prefs[5] = playfield_theme;
    prefs[6] = start_piece_set;
    /* Version 5 keeps the ten-byte record: bits 2/3 mute music/effects. */
    prefs[7] = start_computer | (sound_music_enabled ? 0 : 4) | (sound_effects_enabled ? 0 : 8);
    prefs[8] = start_difficulty + (start_computer == COMPUTER_BOTH ? start_black_difficulty * DIFFICULTY_COUNT : 0);
    prefs[9] = checksum(prefs, 9, 0xA761);
    if(cbm_open(3, 8, 3, "@:CHESSOPT.DAT,S,W")) { cbm_close(3); return 0; }
    ok = cbm_write(3, prefs, sizeof(prefs)) == sizeof(prefs);
    cbm_close(3);
    return ok && drive_ok();
}

#pragma code-name ("CODE")
#pragma bss-name ("BSS")
uint8_t preferences_save(void) {
    uint8_t saved = *(uint8_t*)0, ok;
    *(uint8_t*)0 = 22;
    ok = storage_preferences_save();
    *(uint8_t*)0 = saved;
    return ok;
}
