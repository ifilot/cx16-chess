# CX16-CHESS

![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/ifilot/cx16-chess?label=version)
[![GitHub Pages](https://github.com/ifilot/cx16-chess/actions/workflows/pages.yml/badge.svg)](https://github.com/ifilot/cx16-chess/actions/workflows/pages.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

[Play in your browser](https://ifilot.github.io/cx16-chess/)

![One-minute gameplay walkthrough](docs/cx16-chess-gameplay.gif)

## Description

CX16-CHESS is a complete chess game for the
[Commander X16](https://www.commanderx16.com/), styled after the chess column
of an old newspaper: warm paper, serif mastheads, engraved pieces and dark red
ink. Play against the computer at nine difficulty levels, against a friend on
the same machine, or sit back and watch the computer play itself.

The opponent is a chess engine written in 65C02 assembly that runs on the real
8 MHz machine. It plays at roughly 800 to 1750 Elo, depending on the selected
level.

| Start screen | Game setup |
| --- | --- |
| ![Start screen](docs/start-screen.png) | ![Game setup](docs/game-setup.png) |

![Playing field](docs/playfield.png)

## Features

* **Full chess rules**: castling, en passant, promotion with an on-board piece
  picker, check, checkmate, stalemate, threefold repetition, the fifty-move
  rule and insufficient material.
* **Four game modes**: play White or Black against the computer, two players
  on one machine, or CPU vs CPU with a separate difficulty for each side.
* **Nine difficulty levels**, from Beginner to Analysis (see below).
* **Newspaper-style board**: a large 448x448 board with a scorecard showing
  both clocks, an evaluation bar and the move list in figurine algebraic
  notation. Choose from three piece sets (Victorian Diagram, Continental
  Engraving, Daily Letterpress) and four board styles.
* **Mouse and keyboard**: drag and drop or click to move, or use the arrow
  keys. Legal moves and captures are marked on the board, and the board can
  be flipped.
* **Analysis**: press **A** during a game to let the engine evaluate the
  current position.
* **Nine save slots**: each save holds the full game, including move history,
  clocks and settings. Saves are stored twice, so a damaged file falls back to
  the previous copy.
* **Music and sound**: a title theme, four chamber-music tracks that rotate
  between games, result jingles and sound effects. Music and effects can be
  switched off separately.

## Difficulty levels

| Level | Search depth | Approximate Elo | Average time per move |
| --- | --- | ---: | ---: |
| Beginner | 1 ply, with deliberate mistakes | 800 | 0.4 s |
| Easy | 1 ply, with deliberate mistakes | 1100 | 0.4 s |
| Casual | 1 ply | 1200 | 0.4 s |
| Medium | 2 ply | 1350 | 0.7 s |
| Challenging | 3 ply | 1400 | 1.5 s |
| **Strong** (default) | 4 ply | 1450 | 4 s |
| Deep | 6 ply | 1450 | 26 s |
| Very Hard | 7 ply | 1600 | 60 s |
| Analysis | 8 ply | 1750 | 204 s |

The Elo values are estimates from matches against Stockfish, not official
ratings. The times are averages on an 8 MHz X16, and complicated positions can
take much longer. Levels above Strong can need several minutes for a single
move, and the game shows a warning when you select one of them.

## Controls

| Action | Mouse | Keyboard |
| --- | --- | --- |
| Select and move a piece | Click, or drag and drop | Arrow keys + Return or Space |
| Cancel a selection | Click an empty square | |
| Pause, save or return to the menu | | Escape |
| Open the menu | | M |
| Analyse the position | | A |
| Show or hide the move sheet | | I or Tab |
| Flip the board | | F |
| Change the board style | Options | T |
| Change which side the computer plays | | C |
| Music on / off | Options or pause menu | V |
| Sound effects on / off | Options or pause menu | S |

In the menus, use Up/Down to select an entry and Left/Right to change a
setting, or click on it. Return or Space confirms and Escape goes back. The
game clocks stop while a menu or dialog is open.

## Installation

Download `CHESS.ZIP` from the
[releases page](https://github.com/ifilot/cx16-chess/releases) and copy the
files inside its `CHESS` folder to the root of your SD card, or to the folder
you use with the emulator. `AUTOBOOT.X16` is a copy of `CHESS.PRG`; the X16
runs it automatically when it starts up with that file in the root of the SD
card. You can also load the game yourself:

```
LOAD "CHESS.PRG"
RUN
```

Keep `CHESS.PRG`, `CHESS.BIN` and `CHESS.DAT` in the same folder. Saved games
(`CHESS1A.SAV` to `CHESS9B.SAV`) and preferences (`CHESSOPT.DAT`) are written
to that folder as well.

## Compilation

Install the required dependencies:

```bash
sudo apt-get install -y build-essential cc65 python3 python3-numpy python3-pil
```

Then build the game from the repository root:

```bash
make            # build the game
make run        # build and start the emulator
make dist       # package the game as build/dist/CHESS.ZIP
```

`make run` uses the emulator in `../x16-emulator/build/x16emu` by default.
Use `make run EMU=/path/to/x16emu ROM=/path/to/rom.bin` to select a different
emulator or ROM.

Testing, the browser build, the engine and the internals of the game are
described in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Dependencies

CX16-CHESS uses [ZSMKit](https://github.com/mooinglemur/zsmkit) for music and
sound effects. ZSMKit is available under the MIT license; a copy is included in
[src/vendor/zsmkit](src/vendor/zsmkit).

## Credits

* Chess pieces and portraits were generated with an image generator and
  adapted to the game's palette. See [assets/pieces/README.md](assets/pieces/README.md).
* The 8×8 bitmap font comes from
  [CX16-Kakuro](https://github.com/ifilot/cx16-kakuro) (GPL-3.0-or-later).
* Mastheads and headings use PT Serif by ParaType (SIL Open Font License 1.1).
* Music and sound effects were made with chipscore. See
  [assets/sound/README.md](assets/sound/README.md).

## Community guidelines

* To report a bug, please open a
  [new issue with the bug label](https://github.com/ifilot/cx16-chess/issues/new?labels=bug).
* For questions, please open an
  [issue with the question label](https://github.com/ifilot/cx16-chess/issues/new?labels=question).

## License

Unless otherwise stated, all code in this repository is provided under the GNU
General Public License version 3.
