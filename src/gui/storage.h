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

#ifndef STORAGE_H
#define STORAGE_H

#include <stdint.h>

/*
 * Saved games and preferences on device 8. Each of the nine slots keeps two
 * alternating generations (CHESS1A.SAV / CHESS1B.SAV), so a failed write
 * never destroys the previous copy. Preferences live in CHESSOPT.DAT.
 *
 * Except for preferences_save(), these calls run with UI bank 22 selected.
 * Slot numbers are zero based.
 */

#define SAVE_SLOTS 9

/* Summary of a slot, taken from its newest checksum-valid generation. */
typedef struct {
    uint16_t moves;                     // half moves (plies) played
    uint8_t computer;                   // COMPUTER_* sides played by the engine
    uint8_t difficulty;                 // DIFFICULTY_* of the engine (White's in CPU vs CPU)
    uint8_t black_difficulty;           // DIFFICULTY_* of Black in CPU vs CPU
} save_info_t;

/**
 * @brief Read the summary of a slot for the save and load tables
 *
 * @param slot Slot number, 0..SAVE_SLOTS-1
 * @param info Receives the summary when the slot holds a valid save
 *
 * @return 1 when the slot holds a valid save, 0 when it is empty or damaged
 */
uint8_t storage_probe(uint8_t slot, save_info_t* info);

/**
 * @brief Save the current game over the older generation of a slot
 *
 * The written file is read back and verified before reporting success.
 *
 * @param slot Slot number, 0..SAVE_SLOTS-1
 *
 * @return 1 when the save was written and verified
 */
uint8_t storage_save(uint8_t slot);

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
uint8_t storage_load(uint8_t slot);

/**
 * @brief Apply the saved preferences, if CHESSOPT.DAT exists and is valid
 */
void storage_preferences_load(void);

/**
 * @brief Write board, piece set, opponent, difficulties and audio switches
 *
 * @return 1 when the file was written without a drive error
 */
uint8_t storage_preferences_save(void);

/**
 * @brief Resident trampoline to storage_preferences_save(), callable from
 *        menu bank 21; selects bank 22 and restores the caller's bank
 *
 * @return 1 when the file was written without a drive error
 */
uint8_t preferences_save(void);

#endif // STORAGE_H
