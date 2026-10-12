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
#include <cbm.h>
#include <string.h>
#include "storage.h"
#include "gfx.h"
#include "match.h"
#include "playfield.h"
#include "start.h"
#include "sound.h"
void asset_close(void);                 // frees the CHESS.DAT channels (assets.s)

/* Storage calls are nonrecursive and run only in the main loop. */
#pragma static-locals (on)
#pragma code-name ("UICODE")
#pragma rodata-name ("UICODE")
#pragma bss-name ("UIBSS")

/*
 * Saved games and preferences. Records are versioned and little-endian,
 * independent of C struct padding. Each slot alternates two generations: a
 * failed write leaves the other generation intact, and a checksum rejects
 * interrupted or damaged records.
 *
 * Save file (version 4): a 28-byte header followed by three bytes (from,
 * to, promotion) per half move.
 *
 *   0..7   "X16SAVE4"                  18  match_state
 *   8..9   generation counter          19  match_result
 *  10..11  number of half moves        20  board theme
 *  12..13  White's clock (seconds)     21  piece set
 *  14..15  Black's clock (seconds)     22  board flipped
 *  16      match_computer              23  move sheet shown
 *  17      match_difficulty            24  clock fraction (jiffies)
 *                                      25  Black's difficulty (CPU vs CPU)
 *                                  26..27  checksum of header and moves
 *
 * Preferences (version 5, CHESSOPT.DAT): "X16P5", board theme, piece set,
 * opponent with mute bits, difficulty, and a checksum byte.
 */
#define HEADER 28
/* Small metadata buffers stay in main RAM; the large replay buffer is banked. */
#pragma bss-name (push, "BSS")
static uint8_t header[HEADER];          // header of the save being read or written
static uint8_t prefs[10];               // preference record
#pragma bss-name (pop)
static uint8_t moves[MAX_HISTORY * 3];  // from, to, promotion of every half move
static rules_position_t previous;       // position kept while validating a save
static char filename[24];               // CMDR-DOS file name with type and mode
static uint16_t count;                  // half moves in moves[]
static uint16_t generation;             // generation of the newest valid copy
static uint8_t chosen;                  // copy (0 = A, 1 = B) picked by latest()
static move_t move;                     // scratch move for replay

/**
 * @brief Number of valid difficulty IDs in a record of the given version
 *
 * Legacy time-based levels map to depths 2, 4 and 6. Keep their bytes
 * intact until after checksum verification, including latest-generation
 * selection.
 *
 * @param version Version character of the record, '1'..'5'
 */
static uint8_t level_count(uint8_t version) {
    return version == '1' ? 3 : version == '2' ? 5 : version == '3' ? 8 : DIFFICULTY_COUNT;
}

/**
 * @brief Convert a stored difficulty to a current DIFFICULTY_* value
 *
 * Version 1 stored Easy/Normal/Hard as 0/1/2; they become 2, 4 and 6 ply.
 */
static uint8_t saved_level(uint8_t level) {
    return header[7] == '1' ? level * 2 : level;
}

/**
 * @brief Read a little-endian word of the header
 */
static uint16_t word(uint8_t offset) {
    return header[offset] | ((uint16_t)header[offset + 1] << 8);
}

/**
 * @brief Store a little-endian word in the header
 */
static void put_word(uint8_t offset, uint16_t value) {
    header[offset] = value;
    header[offset + 1] = value >> 8;
}

/**
 * @brief Rotate-and-xor checksum over a buffer
 *
 * @param data   Bytes to include
 * @param length Number of bytes
 * @param value  Starting value, or the result of a previous call
 *
 * @return Updated checksum
 */
static uint16_t checksum(const uint8_t* data, uint16_t length, uint16_t value) {
    while(length--) value = (value << 5) ^ (value >> 11) ^ *data++;
    return value;
}

/**
 * @brief Checksum of the header (without its checksum field) and the moves
 */
static uint16_t digest(void) {
    return checksum(moves, count * 3, checksum(header, HEADER - 2, 0xA761));
}

/**
 * @brief Build the file name of a slot copy, e.g. "@:CHESS3B.SAV,S,W"
 *
 * @param slot  Slot number, 0..SAVE_SLOTS-1
 * @param copy  Generation copy, 0 (A) or 1 (B)
 * @param write 1 to open for (over)writing, 0 to open for reading
 */
static void name(uint8_t slot, uint8_t copy, uint8_t write) {
    strcpy(filename, write ? "@:CHESS1A.SAV,S,W" : "CHESS1A.SAV,S,R");
    filename[write ? 7 : 5] = '1' + slot;
    filename[write ? 8 : 6] = 'A' + copy;
}

/**
 * @brief Read exactly size bytes from logical file 3, across short reads
 *
 * @return 1 on success, 0 on an error or premature end of file
 */
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

/**
 * @brief Read and validate one copy of a slot into header[] and moves[]
 *
 * Every header field is range checked, the checksum must match and the
 * file must end right after the last move.
 *
 * @return 1 when the copy is valid
 */
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

/**
 * @brief Load the newest valid copy of a slot into header[] and moves[]
 *
 * Sets chosen and generation. The generation comparison is done modulo
 * 65536, so the counter may wrap.
 *
 * @return 1 when at least one copy is valid
 */
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

/**
 * @brief Read the summary of a slot for the save and load tables
 *
 * @param slot Slot number, 0..SAVE_SLOTS-1
 * @param info Receives the summary when the slot holds a valid save
 *
 * @return 1 when the slot holds a valid save, 0 when it is empty or damaged
 */
uint8_t storage_probe(uint8_t slot, save_info_t* info) {
    asset_close();
    if(!latest(slot)) return 0;
    info->moves = count;
    info->computer = header[16];
    info->difficulty = saved_level(header[17]);
    info->black_difficulty = saved_level(header[25]);
    return 1;
}

/**
 * @brief Check the drive status after a write
 *
 * Read the DOS status after close as well: write APIs alone cannot detect
 * disk-full and write-protection errors reported by the drive. Channel 14
 * is separate from the graphics loader's logical command channel 15.
 *
 * @return 1 when the drive reports "00" (OK)
 */
static uint8_t drive_ok(void) {
    uint8_t status[2], ok;
    if(cbm_open(14, 8, 15, "")) { cbm_close(14); return 0; }
    ok = cbm_read(14, status, 2) == 2 && status[0] == '0' && status[1] == '0';
    /* Drain the status line so later graphics seeks do not inherit errors. */
    while(cbm_read(14, status, 1) == 1 && status[0] != 13);
    cbm_close(14);
    return ok;
}

/**
 * @brief Save the current game over the older generation of a slot
 *
 * The written file is read back and verified before reporting success.
 *
 * @param slot Slot number, 0..SAVE_SLOTS-1
 *
 * @return 1 when the save was written and verified
 */
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

/**
 * @brief Replay moves[] from the initial position on a scratch copy
 *
 * The current position is captured first and restored afterwards, so the
 * game in RAM is untouched.
 *
 * @return 1 when every move is legal and the game had not already ended
 */
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

/**
 * @brief Replace the current game with the newest valid save of a slot
 *
 * Every move is replayed and checked for legality first; a damaged or
 * invalid save leaves the current game intact.
 *
 * @param slot Slot number, 0..SAVE_SLOTS-1
 *
 * @return 1 when the game was loaded
 */
uint8_t storage_load(uint8_t slot) {
    uint16_t index;
    const move_t* legal;
    asset_close();
    if(slot >= SAVE_SLOTS || !latest(slot) || !validate_moves()) return 0;
    // replaying through match_play() rebuilds the SAN list and repetition history
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

/**
 * @brief Apply the saved preferences, if CHESSOPT.DAT exists and is valid
 *
 * Versions 1..5 are accepted. In version 5, bits 2 and 3 of the opponent
 * byte mute music and effects. In CPU vs CPU the difficulty byte holds
 * White's level plus Black's level times the number of levels.
 */
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

/**
 * @brief Write board, piece set, opponent, difficulties and audio switches
 *
 * @return 1 when the file was written without a drive error
 */
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
/**
 * @brief Resident trampoline to storage_preferences_save(), callable from
 *        menu bank 21; selects bank 22 and restores the caller's bank
 *
 * @return 1 when the file was written without a drive error
 */
uint8_t preferences_save(void) {
    uint8_t saved = *(uint8_t*)0, ok;
    *(uint8_t*)0 = 22;
    ok = storage_preferences_save();
    *(uint8_t*)0 = saved;
    return ok;
}
