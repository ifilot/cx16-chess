# Development notes

This document describes how CX16-CHESS is built and tested, and how the game
and its engine work. For an overview of the game itself, see the
[README](../README.md).

## Build targets

Building requires **cc65**, **Python 3** with **Pillow** and **NumPy**, GNU
make and a native C compiler (for the tests).

```sh
make              # build src/CHESS.PRG (the game) and src/ENGINE.PRG
make run          # build and start the emulator
make test         # native tests: rules perft and SAN, engine perft and mates
make test-ui      # emulator tests: menus, setup, clocks, saves, preferences, palette
make test-storage # isolated save-slot and preference persistence tests
make screenshot   # headless capture via the X16 AgentBridge emulator
make demo         # record docs/cx16-chess-gameplay.gif
make test-dist    # run emulator tests using only the distribution files
make test-sd      # test loading from a FAT32 SD-card image (requires mkfs.fat and mcopy)
make dist         # package the playable game in build/dist/CHESS.ZIP
make site         # build the browser version in build/site
make test-site    # browser checks of the WebAssembly build (requires Playwright)
make clean        # remove everything generated
```

`make run` uses `../x16-emulator/build/x16emu` and the first ROM found in
`../emulator/rom.bin` or `../emulator-win/rom.bin`. Override them with
`make run EMU=... ROM=...`.

The emulator tests require the [AgentBridge](https://github.com/ifilot/x16-emulator)
emulator in `../x16-emulator`. The engine tests below also need python-chess
(`pip install chess`), and matches and game reviews need Stockfish
(`/usr/games/stockfish`):

```sh
make parity     # X16 assembly engine vs the native C reference
make fuzz       # random positions: evaluation, move generation, validation
make bench      # search depth reached within 5, 10 and 30 seconds
make wac        # Win At Chess test suite at 10 s per position
```

### Gameplay recording

`make demo` writes a looping 640×480 GIF of 60 seconds at 10 fps. It visits
About and Options, changes the board and pieces, and then plays a
human-versus-computer game. The human moves are chosen by a native build of the
engine and entered with mouse clicks; the opponent runs on the emulated X16.
The recorder works on temporary copies of the runtime files, so saves and
preferences are not affected. Use `make demo DEMO_GIF=build/demo.gif` to change
the output file. Timing and move details are written to
`build/demo-recording.json`.

## Distribution

`make dist` creates `build/dist/CHESS.ZIP` with six files:

| File | Contents |
| --- | --- |
| `CHESS.PRG` | the game |
| `AUTOBOOT.X16` | a copy of `CHESS.PRG` that starts automatically on boot |
| `CHESS.BIN` | banked code, music and sound effects |
| `CHESS.DAT` | all graphics resources |
| `README.TXT` | short instructions and the ZSMKit license |
| `HASHES.TXT` | checksums of the runtime files |

All filenames follow the 8.3 convention. The headless engine, intermediate
graphics, symbols and test files are not included.

**`CHESS.BIN`** is a headerless 200 KiB image of RAM banks 21–45 with the menu,
dialog, board and sound code, plus all music tracks and sound effects. It is
loaded with a single KERNAL LOAD at startup, so no audio is read from disk
during play.

**`CHESS.DAT`** starts with a 16-byte build identifier and an index of
twenty-four resources (32-bit offset, 16-bit length). The loader checks the
identifier, keeps the file open and seeks to each resource with the CMDR-DOS
POSITION command. Data is streamed into VERA or banked RAM with MACPTR, with
ACPTR as a fallback. Read errors or a truncated file abort loading.

The graphics `.DAT` files are generated from the bitmap artwork, fonts and
Python scripts in `assets/`; they are not tracked by Git.

## Browser version

`make site` builds a static website in `build/site` that runs the real game in
the official WebAssembly emulator (r49). The emulator ZIP is cached in
`build/site-cache` and checked against a pinned SHA-256. All assets are served
locally. Saves in the browser only last for the current page session.

Serve the result over HTTP; opening `index.html` directly cannot load the
WebAssembly files:

```sh
python3 -m http.server 8000 --directory build/site
```

Browser checks:

```sh
npm install --prefix build/browser-tools playwright@1.64.0
build/browser-tools/node_modules/.bin/playwright install chromium
NODE_PATH="$PWD/build/browser-tools/node_modules" make test-site
```

These boot the WebAssembly build, compare canvas pixels against the exported
artwork, and test the menus, a legal move, fullscreen, the mobile layout and
touch input. Screenshots go to `build/site-check`. Set `CHROMIUM_PATH` to use
an existing Chromium binary.

`.github/workflows/pages.yml` builds and checks the site and deploys it to
GitHub Pages on every push to `master`.

## Source layout

The game is split into a core without any graphics and a front end:

| Directory | Contents |
| --- | --- |
| `src/core/` | `rules.c` (move rules, SAN), `match.c` (game controller: moves, clocks, results, which side is played by whom), the engine (`engine*.c`, `engine_asm.s`, `engine_search.s`) |
| `src/gui/` | VERA setup (`video.c`), start and setup menus (`start.c`), the playing field (`playfield.c`), `main.c`, disk persistence (`storage.c`) and dialogs (`dialog.c`) |
| `src/bridge/` | `ENGINE.PRG`: the engine driven through a mailbox at `$0400`, used by the test tools |
| `assets/` | artwork, fonts, sound and the graphics build scripts |
| `tools/` | build helpers and AgentBridge test drivers |
| `tests/` | native tests, test suites and reference images |

The front end only talks to `match.h` and never calls the engine directly. The
engine shares only the 0x88 board encoding with `rules.h` and receives
positions through `engine_set_position()`.

## Returning to BASIC

The main menu's Exit entry (or X) returns from `main()`. All returns, including
loading failures, share the cleanup in `src/gui/runtime.s`. This replaces the
CX16 r37 startup in cc65 2.19, which accesses obsolete bank registers at
`$9F60/$9F61` and does not preserve BASIC's zero page.

Before constructors or C code run, the game saves `$22–$7F`, the RAM bank and
the hardware stack pointer in resident INIT storage. On return it runs library
destructors, stops both ZSMKit priorities and restores the previous IRQ vector,
closes the graphics channels, disables the mouse and calls KERNAL CINT to
restore text mode. It then restores zero page, the RAM bank and hardware stack,
selects BASIC ROM bank 4 and returns to the SYS caller. The game uses the
current `$00/$01` bank registers and does not jump to `$FF47`.

The game still occupies its loaded main RAM, golden RAM, VRAM and working RAM
banks 1–45; exit does not erase these areas or restore a program that was
replaced by loading CHESS.PRG. BASIC can accept commands, create programs and
load another application. `tools/exit_test.py` checks the actual return path,
byte-for-byte zero-page and vector restoration, the bank registers and CPU
stack, system bank 0 outside KERNAL input/audio state, an untouched bank-46
sentinel, silent PSG channels, BASIC execution and reloading the game. It covers
keyboard, mouse, a played game, and missing code/graphics files.

## The engine

* 0x88 board with incrementally updated material, piece-square score,
  32-bit Zobrist hash, pawn structure and check status.
* Iterative deepening, principal variation search, a transposition table
  (16384 entries in banked RAM), null move, late move reductions, futility
  pruning (depth 1–3), late move pruning, check extensions, killer and history
  move ordering, quiescence search with delta pruning, and repetition and
  fifty-move detection.
* Evaluation: material and piece-square tables, king tables for the endgame,
  bishop pair, doubled / isolated / passed pawns (cached), pawn shelter, and
  mop-up against a bare king.
* The per-node code (board, move generation, evaluation, search) is written in
  65C02 assembly. The same algorithm exists in C (`engine_hot.c`, `search()` in
  `engine.c`) for native builds. Both visit exactly the same nodes, which
  `tools/parity_test.py` verifies.
* The engine tables use RAM banks 1–18; bank 19 holds the game's move list.

On the 8 MHz X16 the engine searches 400–1200 nodes per second. Beginner and
Easy add seeded random errors to a 1-ply search; all other levels search to a
fixed depth without a time limit. Mate and forced-move searches can stop early.

### Strength

The difficulty levels were rated in matches against Stockfish 16 with limited
strength (`UCI_Elo`), using 1,200 games per depth over 300 distinct openings.
These are benchmark ratings, not human ratings.

| Depth | Estimated Elo (95% interval) |
| --- | --- |
| 1 ply | 1184 (1163–1205) |
| 2 ply | 1355 (1335–1374) |
| 3 ply | 1405 (1386–1424) |
| 4 ply | 1432 (1413–1452) |
| 5 ply | 1406 (1387–1425) |
| 6 ply | 1464 (1446–1482) |
| 7 ply | 1617 (1595–1640) |
| 8 ply | 1729 (1703–1758) |

Because 5 ply measured no stronger than 3 or 4 ply, it is not offered in the
game. The Beginner and Easy settings are described in the
[weak-engine calibration](engine/weak-calibration-2026-10-11/RESULTS.md).
All results, raw games and search records are indexed in
[engine/RESULTS.md](engine/RESULTS.md); [engine/ARCHIVES.md](engine/ARCHIVES.md)
explains how to restore the archived data.

### Engine tools

All engine tests run the real X16 binary in the AgentBridge emulator, which runs
about seven times faster than a real X16. Reported times are emulated X16 time.

| Tool | Purpose |
| --- | --- |
| `tools/engine_bridge.py` | drives `ENGINE.PRG` through its mailbox (used by all tools below) |
| `tools/parity_test.py` | X16 assembly engine vs native C reference: perft, evaluation, full searches |
| `tools/native_replay_test.py` | replays every recorded search of complete X16 games in native C |
| `tools/compare_depth_runs.py` | paired comparisons between rating runs |
| `tools/fuzz_test.py` | random positions: evaluation, move generation, move validation |
| `tools/depth_bench.py` | depth reached within a time limit |
| `tools/fixed_depth_bench.py` | time needed for fixed depths 2–6 |
| `tools/weakness_parity_test.py` | weakened searches compared between native C and X16 |
| `tools/weakness_ui_test.py` | weak levels in the menus, saves and analysis |
| `tools/epd_test.py` | test suites, e.g. `tests/epd/wac.epd` (Win At Chess) |
| `tools/match.py --x16` | games against Stockfish with limited strength |
| `tools/rate_difficulties.py` | difficulty ratings against Stockfish |
| `tools/depth_run_status.py` | provisional results of a running rating run |
| `tools/generate_openings.py` | sets of distinct, balanced openings for rating runs |
| `tools/benchmark_emulator.py` | emulator throughput and engine-result comparisons |
| `tools/benchmark_workers.py` | emulator throughput at different worker counts |
| `tools/review_games.py` | centipawn loss per move, by local Stockfish or (`--online`) cloud evaluation |
| `tools/selfplay.py` | native self-play between engine variants, for tuning |
| `tools/profile_engine.py` | statistical profiler that samples the emulated program counter |
| `tools/x16uci.py` | the emulated X16 engine as a UCI engine |
| `tools/screenshot.py` | boots the game, clicks and types, captures screenshots |

A typical rating run:

```sh
python3 tools/generate_openings.py --count 100 --out build/rating-openings.json
python3 tools/rate_difficulties.py --depths 2 3 --games-per-opponent 200 --workers 16 \
  --emulator ../x16-emulator/build/x16emu \
  --openings build/rating-openings.json --out build/difficulty-extended
```

For faster runs, replace `--emulator ...` with `--native-engine tests/uci`
(build it with `make -C tests uci`). Native runs use host time and do not
simulate the X16 clock. Keep native and emulator runs in separate output
folders.

[tools/emulator-fast.patch](../tools/emulator-fast.patch) speeds up the
AgentBridge emulator (commit `464e447f`) by about 12% for these runs, without
changing CPU, raster, IRQ or audio timing. Apply it in the emulator checkout
with `git apply`, then rebuild and run `ctest --test-dir build --output-on-failure`.
See the [performance report](engine/emulator-performance-2026-10-11/RESULTS.md).

## Graphics and memory

* **Layer 0** holds the background as deduplicated 8×8 4bpp tiles. Two
  complete tilemaps are kept in VRAM, with and without the move sheet;
  toggling the sheet only changes the map base. Highlighted board squares use
  pre-rendered tile variants.
* **Layer 1** holds the pieces (7×7 tiles of 8×8) and text. Its 16 palette
  rows repeat the base palette with different ink colours, so the text colour
  is set by the tilemap palette offset.
* **Sprites** are used for the mouse pointer, keyboard cursor and dragged
  piece.
* The C stack lives in golden RAM (`$0400`–`$07FF`) to leave main RAM for code
  and engine tables.
* Banked RAM: engine tables in banks 1–18, the move list in bank 19, menu code
  and SAN formatting in bank 21, dialogs and persistence in bank 22, board
  drawing and input in bank 23, move coordinates in bank 24, and audio in
  banks 25–45.
* `assets/scripts/build_graphics.py` renders the screens from
  `assets/scripts/layout.py` and `palette.py` into `build/graphics/`.
  `tools/package_graphics.py` packs the result into `src/CHESS.DAT` and
  generates `src/gfx.h`. The build decodes the exported tiles again and fails
  on any changed pixel, invalid palette or exceeded tile budget.
* `make test-ui` compares emulator screenshots with the reference images in
  `tests/fixtures/graphics/` at zero pixel tolerance.

More detail on the assets is in [assets/font/README.md](../assets/font/README.md),
[assets/pieces/README.md](../assets/pieces/README.md) and
[assets/sound/README.md](../assets/sound/README.md).
