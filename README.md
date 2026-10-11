# CX16-CHESS

A chess program for the **Commander X16** with a clean newspaper layout:
640x480, a sixteen-colour base palette, warm paper, bitmap lettering, serif
mastheads and dark red accents. The start-screen masthead, menu titles, and
in-game masthead use four additional shades in a separate tile palette to smooth
their red ink edges.

The start screen uses a dithered bishop portrait against solid paper:

![Start screen](docs/start-screen.png)

**New Game** opens a setup screen beside a queen portrait. Choose White,
Black, CPU vs CPU, or Two Players, then select a named difficulty (default
**Strong**). The selector shows approximate local benchmark Elo rounded to 50
and the measured average calculation time per move at 8 MHz. CPU vs CPU shows
White and Black averages together. These are estimates, not move time limits.

| Level | Search | Approximate Elo | Average move time on X16 |
| --- | --- | ---: | ---: |
| Beginner | Weakened 1 ply | 800 | 0.4 s |
| Easy | Weakened 1 ply | 1100 | 0.4 s |
| Casual | 1 ply | 1200 | 0.4 s |
| Medium | 2 ply | 1350 | 0.7 s |
| Challenging | 3 ply | 1400 | 1.5 s |
| Strong | 4 ply | 1450 | 4 s |
| Deep | 6 ply | 1450 | 26 s |
| Very Hard | 7 ply | 1600 | 60 s |
| Analysis | 8 ply | 1750 | 204 s |

Beginner and Easy use calibrated random move-selection errors; the other levels
use the regular engine. Elo estimates are relative to the local Stockfish
benchmark, rather than certified human ratings. Times are sample averages at
8 MHz: complex positions can take much longer, with observed 7/8-ply searches
lasting 18/34 minutes. **Every level above Strong shows a red warning about very
high calculation times**, including when either computer uses one in CPU vs CPU.
Searches finish the selected nominal depth without a move time cap;
mate and forced-move searches can stop early. Game clocks still run while thinking.
Legacy 5-ply saves retain their search depth, but 5 ply is omitted from the new
selector because it offered no measured improvement over 3 ply. Older saved
settings remain readable; new saves use format version 4 and preferences use version 5.
Use Up/Down to select, Left/Right to change, and Return to start.
Click a setting to cycle it, or click Start Game. Escape returns to the menu.
Moving the mouse over menu entries, settings, or dialog choices highlights
them in red. Hovering only selects a control; click to activate it or change its value.
Menu focus and setting changes update their controls in place. Options updates
only the board background or pieces when the corresponding setting changes.
Startup and scene changes show a paper background sprinkled with small chess silhouettes
and a native-font Loading label while
the next artwork loads. The cover stays in VRAM and needs no extra disk reads.
Startup draws the paper and Loading label before reading any runtime files,
then adds the silhouettes once the shared font is ready.

![Loading screen](docs/transition-screen.png)
About (or **A** in the menu) shows the version from `VERSION`, compilation
date and toolchain, author, and GitHub repository beside a matching knight portrait.
Return, Space, Escape, or the Back button returns to the menu.

![Game setup](docs/game-setup.png)

![About screen](docs/about-screen.png)

The playing screen follows the Right Scorecard design: a large board on the
left, clocks and paired white/black moves on the right. The default board uses
fine diagonal ink hatching and the Victorian Diagram newspaper pieces, with
mitred bishops, masonry rooks, and crowned kings. **M** opens the menu
and pauses the clocks. Options previews appearance on a full-size board, with
independent board and piece-set selectors. It offers Victorian Diagram,
Continental Engraving, and Daily Letterpress pieces, plus fine hatching,
crosshatching, coarse hatching, and wood boards. Selections apply immediately
to the preview and are used when starting or resuming a game. Continue (or Escape from the main menu) resumes the
same game; it is disabled until a game has been started or loaded. Continue
resumes the game held in RAM during this session. **Load Game** (or **L** in
the menu) restores one of nine numbered disk slots, including after restarting.

**CPU vs CPU** in New Game runs a demo with separate White CPU and Black CPU
difficulty settings. Both computers move automatically. Escape pauses the demo
(including during thinking), so you can save it or return to the main menu.
Demo saves retain both difficulties; their Level column shows White/Black,
for example `2/6` or `B/E` for Beginner/Easy. Legacy Easy/Normal/Hard saves and
preferences load as 2/4/6 ply. Current saves use version 4 and preferences use version 5; both
continue to read versions 1–3.

![Computer versus computer setup](docs/demo-setup.png)

**Escape** on the board opens a pause dialog with Resume Game, Save Game,
Main Menu, Music, and Sounds. Choose Save Game, select slot 1–9 with arrows, a number key,
or a click, then confirm. Replacing an occupied slot asks for confirmation.
Escape backs out or resumes play. Both clocks pause while any dialog or menu
is open. Main Menu keeps the current game available through Continue.

![Pause dialog](docs/pause-dialog.png)

The save and load tables show each slot’s difficulty, your playing side, and
number of moves played (one per player turn). Local games show **Local** and
**Both**. These details are also available for existing saves.

![Save slots](docs/save-slots.png)

Saves retain the entire move history, clocks, opponent, difficulty, board style,
piece set, board orientation, and move-sheet visibility. Replay rebuilds legal
moves, castling, en passant, promotions, and repetition history. Each slot keeps
two alternating generations (`CHESS1A.SAV` / `CHESS1B.SAV` through slot 9),
with checksums and read-back verification; a damaged newest copy falls back
to its previous valid copy. Missing or invalid saves leave the current game intact.
Files use device 8 in the game directory on the SD card or emulator filesystem.

Options includes **Save Preferences**, which persists the board and piece set,
plus the default opponent and difficulty from New Game, in `CHESSOPT.DAT`.
These defaults load at startup; loading a game restores that game's own appearance.
Done or Escape keeps changes for this session without saving them to disk.

![Playing field](docs/playfield.png)

**I** toggles the move sheet, **T** changes between solid brown squares and
a hatched printed diagram, and **F** flips the board.

## Features so far

* Full rules: castling, en passant, promotion (with a piece picker on the
  board), check, checkmate, stalemate, fifty-move rule and insufficient
  material.
* A 448x448 board (56-pixel squares), compact clocks beside WHITE / BLACK, a signed
  evaluation bar, and animated figurines while the engine thinks. CPU searches
  show the selected PLY depth; analysis shows a TIME percentage against its
  time budget. A forced move or mate may finish early.
* Analysis remains available with **A**: the engine searches for up to
  10 seconds and updates the evaluation bar.
* A scrolling score sheet with 19 numbered white/black move pairs in figurine
  algebraic notation.
* Newspaper styling: serif headings, thin rules, warm flat paper, dithered
  chess portraits, and four board styles with three newspaper piece sets.
* Selected pieces use heavy red brackets, legal destinations use hollow
  rings, and captures use corner wedges. The brackets, rings and wedges use
  the masthead red (#991111) with paper keylines. Selection preserves the
  original board colors. The last move and check are highlighted separately.
* Mouse and keyboard control, including sprite-based piece dragging; the board can be flipped.
* A chess engine in 65C02 assembly that searches 4-6 plies within 10-30
  seconds on the 8 MHz X16 (see [The engine](#the-engine)).

Hold the left mouse button on your piece to drag it, then release over a legal
destination. The sprite keeps the point where you grabbed it beneath the mouse
pointer. An illegal or off-board drop returns the piece. A short click still
selects it for click-to-move. Promotion opens the usual piece picker; Escape or
a keyboard action cancels an active drag.

## Controls

| Action | Mouse | Keyboard |
| --- | --- | --- |
| Select piece / move | Left click or drag and drop | Arrows + Return or Space |
| Cancel selection | Click an empty square | |
| Pause / save / main menu | Click a dialog option | Escape |
| Analyse the position | | A |
| Move sheet on / off | | I or Tab |
| Flip board | | F |
| Board style | Options selectors | T |
| Computer plays black / white / nobody | | C |
| New game setup | Main menu | N |
| Menu / pause | | M |
| Appearance and audio options | OPTIONS on opening screen | O in menu |
| Load a saved game | LOAD GAME on opening screen | L in menu |
| Save preferences | SAVE PREFERENCES in Options | Select with arrows + Return |
| About / version and credits | ABOUT on opening screen | A in menu |
| Menu selection / setup field | Click a row | Up / Down |
| Change setup choice | Click the value | Left / Right |
| Start / confirm | Click Start Game | Return or Space |
| Back / continue from menu | | Escape |
| Music on / off | MUSIC in Options or Escape menu | V |
| Sound effects on / off | SOUNDS in Options or Escape menu | S |

## Music and sound

The chipscore Chess assets provide the title minuet *The Gambit*, four calm
chamber-music loops, win/lose/draw jingles, and sixteen menu and board effects.
New games rotate through *Opening Theory*, *Sarabande*, *Café de la Régence*,
and *Nocturne*. Pausing keeps the music playing; returning to the main menu
switches to the title theme. Continuing restores the current game's track.
A completed game plays its result jingle once, then leaves the final position
quiet. In a human-versus-computer match, the jingle reflects the human's result.

Moves play one effect with priority check, promotion, castle, capture, then
normal move; the computer has a distinct normal-move knock. Selecting pieces,
illegal drops, menus, saves, errors, and a human clock below ten seconds have
their own effects. Mouse hover remains silent. **V** and **S** independently
toggle music and effects in menus, dialogs, and play. Options and the midgame
Escape menu also offer separate **MUSIC** and **SOUNDS** controls: click them,
or select with Up/Down and toggle with Left/Right or Return. Changes apply
immediately. **SAVE PREFERENCES** in Options remembers both switches for the
next launch; older preference files enable both by default.

All audio loads into RAM at startup and ZSMKit services it in interrupts,
including during long engine searches. The startup bundle `CHESS.BIN`
contains the sound controller, eight music tracks, and sixteen effects. Source assets and provenance
are documented in [assets/sound/README.md](assets/sound/README.md); ZSMKit's
MIT license is included in [src/vendor/zsmkit/LICENSE](src/vendor/zsmkit/LICENSE).

## Building

Requires **cc65**, **Python 3** with **Pillow** and **NumPy**, GNU make
and a C compiler (for the native tests).

```sh
make            # build src/CHESS.PRG (the game) and src/ENGINE.PRG
make run        # build and start the emulator
make test       # native tests: rules perft and SAN, engine perft and mates
make test-ui    # emulator tests: menus, setup, clocks, saves, preferences, palette
make test-storage # isolated nine-slot and preference persistence tests
make screenshot # headless capture via the X16 AgentBridge emulator
make demo       # record a one-minute menu walkthrough and human-vs-CPU battle
make test-dist  # run emulator tests using only the distribution files
make test-sd    # test the ROM SD-card loader (requires mkfs.fat and mcopy)
make dist       # package only the playable game in build/dist/CHESS.ZIP
make site       # build the browser game in build/site (downloads pinned r49 once)
make test-site  # run real WebAssembly browser checks (requires Playwright)
make clean      # remove everything generated
```



`make demo` writes `docs/cx16-chess-gameplay.gif`: a looping, 640×480 GIF
with exactly 60 seconds of playback at 10 fps. It visits About and Options,
changes the board and pieces, then starts a human-versus-computer game. The
first three human moves and computer replies run at normal speed; later turns
run at 4× speed. Mouse motion, piece selection, legal targets, CPU thinking,
and the growing move sheet are recorded from the running emulator. The final
position stays visible for the closing seconds.

The recorder uses temporary runtime copies, so it cannot change your saves or
preferences. A native build of the same chess engine chooses the scripted
human-side moves, which are entered through mouse clicks; the opponent runs
on the emulated X16. It requires an AgentBridge-enabled emulator and its
Python client, plus the build dependencies above. Override the output with
`make demo DEMO_GIF=build/demo.gif`; `EMU` and `ROM` work as for `make run`.
Timing and move details are saved to `build/demo-recording.json`.

![One-minute gameplay walkthrough](docs/cx16-chess-gameplay.gif)


The X16 engine tests need the [AgentBridge](https://github.com/ifilot/x16-emulator)
emulator in `../x16-emulator`; `make fuzz`, `make wac` and the match and
review tools also need python-chess (`pip install chess`) and, for matches
and reviews, Stockfish (`/usr/games/stockfish`):

```sh
make parity     # X16 assembly engine vs the native C reference
make fuzz       # random positions: evaluation, move generation, validation
make bench      # search depth within 5, 10 and 30 seconds
make wac        # Win At Chess test suite at 10 s per position
```

`make run` uses `../x16-emulator/build/x16emu` and the first ROM found in
`../emulator/rom.bin` or `../emulator-win/rom.bin`; override with
`make run EMU=... ROM=...`. For distribution, run `make dist` and extract `build/dist/CHESS.ZIP`.
Keep the four game files together: `CHESS.PRG`, `AUTOBOOT.X16`, `CHESS.BIN`,
and `CHESS.DAT`. The release has six files in total, including `README.TXT`
(with the audio library license) and `HASHES.TXT`.
All distribution filenames follow 8.3. The ZIP excludes the
headless engine, intermediate graphics, previews, symbols and test files.
The build and ZIP also include `AUTOBOOT.X16`, a copy of the game with its
BASIC startup stub. Startup discards queued launch-command keystrokes and waits
for a held mouse button to be released, so automatic boot and explicit emulator
launches both stop at the main menu. Copy the distribution folder's contents to the SD card
root to start Chess automatically on power-up or reset.
All graphics `.DAT` files are generated from the checked-in bitmap artwork, fonts and
Python generators; none are tracked by Git. Intermediate tiles and maps live
in `build/graphics/`; `src/` contains just one runtime graphics container.

`CHESS.BIN` is a headerless 200 KiB image of RAM banks 21–45: menu, dialog,
board and sound code, plus every music track and sound effect. The packer
checks bank boundaries and verifies every source byte; zero padding initializes
banked state. One KERNAL LOAD fills the banks at startup, with no audio disk
reads during play. The individual `.BIN` and `.ZSM` files remain development
inputs and intermediate outputs and are excluded from the release.

`CHESS.DAT` contains a 16-byte build identifier, twenty-four index entries (32-bit
file offset and 16-bit length), and the original graphics bytes without VRAM
padding. The packer verifies every resource against its generated source.
The loader validates the identifier against the compiled index, keeps a data
channel open and seeks to each resource using CMDR-DOS POSITION. KERNAL MACPTR
streams data directly into VERA or banked RAM, handling partial reads; ACPTR
provides a fallback when bulk reads are unavailable. Read errors and premature
EOF abort loading while the Loading cover stays visible. Screen changes load only the
required resources; font, sprites and game state stay resident.

The distribution includes `HASHES.TXT` for verifying the runtime files.
`make test-dist` exercises the menus, all piece sets and board styles, gameplay,
saves, preferences, and indicators using the distribution directory as the emulator filesystem.
It also checks missing, mismatched and truncated containers, partial reads and
byte-at-a-time fallback. `make test-sd` creates `build/dist/CHESS.IMG`, a FAT32
SD image, and tests the actual ROM CMDR-DOS path, including all twelve board/set
combinations and save/preference writes to an isolated SD image. It requires dosfstools and mtools; it never accesses a physical disk.
`make` also builds `src/ENGINE.PRG`, a headless engine harness for the test tools
below; its separate linker configuration cannot overwrite the banked UI files.

## Browser site

`make site` builds a static website in `build/site`, following the same
WebAssembly emulator setup as CX16 Kakuro. It keeps the game's warm paper,
dark red PT Serif headings, and engraved artwork. The page includes controls,
an explanation of the native 65C02 engine, the measured difficulty estimates
and their uncertainty, and a download of the latest local game build.
The Elo table is generated directly from the recorded strength-test summary.

Serve the output over HTTP (opening `index.html` as a local file cannot load
WebAssembly resources):

```sh
python3 -m http.server 8000 --directory build/site
```

Open `http://localhost:8000`. The emulator downloads only after Play Chess is
pressed. It runs the real game, banked UI, graphics, and audio runtime files,
with native 640×480 pixels, integer fullscreen scaling, and touch controls.
No developer preferences or saved games are bundled. Browser saves live in
the emulator's memory filesystem for this page session; reloading or
restarting clears them. The downloadable game keeps its normal disk saves.

The official emulator r49 ZIP is cached in `build/site-cache` and checked
against a pinned SHA-256 before unpacking. All website assets, including
PT Serif and runtime files, are served locally; no CDN is needed.
Emulator, ROM, and font notices are included with the site.

For browser checks:

```sh
npm install --prefix build/browser-tools playwright@1.64.0
build/browser-tools/node_modules/.bin/playwright install chromium
NODE_PATH="$PWD/build/browser-tools/node_modules" make test-site
```

Checks boot the shipped WASM and compare actual canvas pixels with the
exported artwork under a `/cx16-chess/` URL, then exercise menus, a legal
move, fullscreen, mobile layout, and touch input. Captures go to
`build/site-check`. `CHROMIUM_PATH` can select an existing Chromium binary.

`.github/workflows/pages.yml` builds and checks the site before deploying
from `master`. In the repository's Pages settings, select **GitHub Actions**
as the source. The workflow publishes `build/site` using the repository's
normal GitHub Pages address.

## Source layout

The game is split into a core without any graphics and a front end:

| Directory | Contents |
| --- | --- |
| `src/core/` | `rules.c` (move rules, SAN), `match.c` (game controller: moves, clocks, results, who plays which side), the engine (`engine*.c`, `engine_asm.s`, `engine_search.s`) |
| `src/gui/` | VERA set-up (`video.c`), start/setup menus (`start.c`), the playing field (`playfield.c`, drawing and input only), `main.c`, disk persistence (`storage.c`) and pause/slot dialogs (`dialog.c`) |
| `src/bridge/` | `ENGINE.PRG`: the engine driven through a mailbox at `$0400` |
| `tools/` | AgentBridge drivers: screenshots, engine bridge, tests, matches |

The front end only talks to `match.h`; it never calls the engine. The
engine only shares the 0x88 board encoding with `rules.h` and receives
positions through `engine_set_position()`.

## The engine

* 0x88 board with incrementally updated material, piece-square score,
  32-bit Zobrist hash, pawn structure and check status.
* Iterative deepening, principal variation search, transposition table
  (16384 entries in banked RAM), hash move tried before move generation,
  null move, late move reductions, futility pruning (depth 1-3), late move
  pruning, check extensions, killer and history move ordering, capture
  search with delta pruning, repetition and fifty-move detection.
* Evaluation: material and piece-square tables, king tables for the
  endgame, bishop pair, doubled / isolated / passed pawns (cached), pawn
  shelter, and mop-up of a bare king.
* The per-node code (board, move generation, evaluation, search) is 65C02
  assembly. The same algorithm exists in C (`engine_hot.c`, `search()` in
  `engine.c`) for native builds; both visit exactly the same nodes, which
  `tools/parity_test.py` checks.
* Memory: the engine's tables use RAM banks 1-18 (bank 19 holds the move
  list of the game).

Speed on the 8 MHz X16 is 400-1200 nodes per second (each node includes
move generation and evaluation). Depth reached (plies, plus captures and
check extensions):

| Position | 5 s | 10 s | 30 s |
| --- | --- | --- | --- |
| Opening / middlegame | 3-4 | 4-5 | 5-6 |
| Endgame | 4-9 | 5-11 | 7-15 |

### Testing

All engine tests run the real X16 binary in the
[AgentBridge](https://github.com/ifilot/x16-emulator) emulator, which runs
about 7 times faster than a real X16; times below are emulated X16 time.

| Tool | Purpose |
| --- | --- |
| `tools/engine_bridge.py` | drives `ENGINE.PRG` through its mailbox (used by all tools below) |
| `tools/parity_test.py` | X16 assembly engine vs native C reference: perft, evaluation, full searches |
| `tools/native_replay_test.py` | compare every recorded search in complete X16 games with native C, retaining warm tables |
| `tools/compare_depth_runs.py` | paired depth comparisons across validated runs with identical engines, opponents and openings |
| `tools/fuzz_test.py` | random positions: evaluation, move generation, move validation |
| `tools/depth_bench.py` | depth reached within a time limit |
| `tools/fixed_depth_bench.py` | waiting times for depths 2–6 on sampled tournament and reference positions |
| `tools/weakness_parity_test.py` | reproducible weak-search comparisons between native C and X16, including complete game replays |
| `tools/weakness_ui_test.py` | weak menu order, selected noise/depth, full-strength analysis, saving and stack safety |
| `tools/epd_test.py` | test suites, e.g. `tests/epd/wac.epd` (Win At Chess) |
| `tools/match.py --x16` | games against Stockfish with limited strength |
| `tools/rate_difficulties.py` | paired depth ratings (`--depths 2 3`), seeded weakening (`--depths 1 --noises 50 300`), or legacy time caps, against local Stockfish |
| `tools/generate_openings.py` | recorded suites of distinct, balanced openings for extended difficulty tests |
| `tools/benchmark_emulator.py` | baseline/candidate throughput and engine-result comparisons |
| `tools/benchmark_workers.py` | aggregate emulator throughput at different worker counts |
| `tools/review_games.py` | centipawn loss of every move, by local Stockfish or (`--online`) Lichess cloud evaluation and chess-api.com |
| `tools/selfplay.py` | native self-play between engine variants, for tuning |
| `tools/profile_engine.py` | statistical profiler: samples the emulated program counter |
| `tools/x16uci.py` | the emulated X16 engine as a UCI engine |
| `tools/screenshot.py` | boots the game, clicks and types, captures screenshots |

Completed engine-test evidence is [indexed here](docs/engine/RESULTS.md).
Raw games and search records are consolidated into verified per-run archives;
[analysis and restoration instructions](docs/engine/ARCHIVES.md) preserve the
original tool paths. New rating runs default to ignored `build/engine/` output.

The [legacy time-capped difficulty test](docs/engine/difficulty-2026-10-11/RESULTS.md)
played 400 games per level against local Stockfish 16 across 100 distinct opening
positions. Estimates on Stockfish's UCI_Elo scale: Easy **1357**, Medium (Normal)
**1390**, Hard **1381**. Normal minus Easy is **+33 Elo**, with a paired 95%
interval of **−11 to +77**. All three pair comparisons still include zero;
the levels are close in this benchmark. The [earlier 48-game sample](docs/engine/difficulty-2026-10-10/RESULTS.md)
scored Easy above Normal; that ordering does not persist in the larger run.
These ratings describe the former time caps, not the new fixed-depth settings.
See the [fixed-depth waiting-time measurements](docs/engine/fixed-depth-2026-10-11/RESULTS.md).
The [initial fixed-depth probe](docs/engine/fixed-depth-elo-2026-10-11/RESULTS.md)
completed 96 games each at 2 and 3 ply: estimates **1406** (1344–1472) and
**1410** (1340–1480). The paired difference is **+4 Elo** (−94 to +103), so this
initial sample does not establish a strength difference.
The [extended native run](docs/engine/native-depth-elo-2026-10-11/RESULTS.md)
completed 1,200 games per depth across 300 openings: **2 ply 1355** (1335–1374),
**3 ply 1405** (1386–1424). The paired difference is **+50 Elo** (+24 to +77),
supporting stronger play at 3 ply under these benchmark conditions. Native C
matched all 8,339 recorded searches from the earlier X16 probe before launch.
The [4-ply extension](docs/engine/native-depth4-elo-2026-10-11/RESULTS.md)
completed another 1,200 games under identical conditions: **1432 Elo**
(1413–1452). Its paired advantage over 3 ply is **+27 Elo** (+1 to +54),
providing modest evidence of improvement.
The [5-ply extension](docs/engine/native-depth5-elo-2026-10-11/RESULTS.md)
completed another 1,200 games: **1406 Elo** (1387–1425). The paired difference
from 4 ply is **−26 Elo** (−54 to +2), so this sample does not establish a
strength difference. All 108 depth-5 native/X16 parity searches matched, and
the current binary reproduced all 51,739 searches from the previous 4-ply run.
The [6-ply extension](docs/engine/native-depth6-elo-2026-10-11/RESULTS.md)
completed another 1,200 games: **1464 Elo** (1446–1482). Its paired advantage
is **+58 Elo** (+30 to +86) over 5 ply and **+32 Elo** (+7 to +57) over 4 ply.
All 108 depth-6 native/X16 parity searches matched.
The [experimental 7/8-ply exploration](docs/engine/native-depth78-elo-2026-10-11/RESULTS.md)
completed 1,200 games per depth: **7 ply 1617** (1595–1640),
**8 ply 1729** (1703–1758). All 72 native/X16 checks at these depths matched.
On the same 24 recorded positions, mean X16 waits were 25 seconds at 6 ply,
60 seconds at 7 ply and 204 seconds at 8 ply. Separate early middlegame sequences
included an 8-ply search lasting 34 minutes. These untimed benchmark results
do not describe strength under the game clock; depths 7/8 remain experimental
and are accessible through the test harness.
For interim results during a tournament, `tools/depth_run_status.py --run PATH`
reports provisional ratings. Add `--reference OTHER_RUN` to compare completed
shared opening groups with a compatible earlier run.
The [1-ply probe](docs/engine/native-depth1-elo-2026-10-11/RESULTS.md) completed
1,200 games under the same conditions: **1184 Elo** (1163–1205), substantially
below 2 ply. The rating harness accepts depths 1–8 for these tests.

The [weak-engine calibration](docs/engine/weak-calibration-2026-10-11/RESULTS.md)
records the Beginner/Easy tuning, fresh opening tests, confidence intervals and
native/X16 parity. These estimates are local benchmark ratings, rather than
certified human Elo ratings.

For an extended test, generate a larger opening suite rather than repeating the
small built-in list. The runner records the engine, emulator and opening-suite
hashes and checkpoints each game, including the engine's per-move search data:

For faster fixed-depth runs, add `--native-engine tests/uci` instead of
`--emulator`. Build it with `make -C tests uci`. Native runs record host time
and do not simulate the X16 clock; finished runs automatically validate their
PGNs and search traces. Keep native and emulator runs in separate output folders.

```sh
python3 tools/generate_openings.py --count 100 --out build/rating-openings.json
python3 tools/rate_difficulties.py --depths 2 3 --games-per-opponent 200 --workers 16 \
  --emulator ../x16-emulator/build/x16emu \
  --openings build/rating-openings.json --out build/difficulty-extended
```

The tested emulator changes are also stored in [tools/emulator-fast.patch](tools/emulator-fast.patch),
against AgentBridge commit `464e447f4fba9151d1446f07750635812f40adfc`.
They reduce request checks and repeated I²C sampling and accelerate disabled PSG
channels while retaining oscillator/noise state. CPU, raster, IRQ, PCM and Yamaha
timing remain emulated. Apply the patch in the emulator checkout with
`git apply /path/to/cx16-chess/tools/emulator-fast.patch`, then rebuild and run
`ctest --test-dir build --output-on-failure`. The [benchmark artifacts](docs/engine/emulator-performance-2026-10-11/benchmark.json)
include fixed-depth, timed and repetition-history comparisons; [worker measurements](docs/engine/emulator-performance-2026-10-11/workers.json)
record how throughput scales on the test host.
The [performance report](docs/engine/emulator-performance-2026-10-11/RESULTS.md)
measured **12.4% higher emulator throughput** with identical engine results and
clock ticks in 34 search comparisons. The extended tournament took about
**2 hours 40 minutes**, and all 1,200 PGNs and recorded search traces passed
validation.

Earlier results with 10 s per move (October 2026, details and games in
[docs/engine](docs/engine/RESULTS.md)):

| Test | Result |
| --- | --- |
| vs Stockfish 16, UCI_Elo 1320 (48 games) | 31/48 = 65% |
| vs Stockfish 16, UCI_Elo 1500 (48 games) | 15.5/48 = 32% |
| Estimated rating | about 1400 (Stockfish UCI_Elo scale) |
| Win At Chess (300 positions) | 187 solved |
| Average centipawn loss (Stockfish 16 review) | 45-53 |

## How it is built

* **Layer 0** shows the background: 8x8 tiles at 4 bpp, deduplicated
  (488 tiles). There are two complete tilemaps in VRAM, with and
  without the move sheet; switching the view only changes the map base.
  Board squares switch between pre-rendered 7x7-tile variants for their
  highlighted states (`SQTILES` resource, kept in banked RAM). The active clock is drawn in red ink.
* **Layer 1** shows pieces (7x7 tiles) and text with transparent index 0.
  The 16 palette rows repeat the base palette with a different ink colour,
  so text colour is just the tilemap palette offset.
* The game keeps its C stack in golden RAM ($0400-$07FF) to leave main RAM
  for code and engine tables.
* **Sprites** are used for the mouse pointer, keyboard cursor and dragged piece.
  Dragging streams the selected set’s 56×56 piece tiles into a padded 64×64
  sprite at $1C000; the board layer hides its source until release.
* `assets/scripts/build_graphics.py` renders the whole screen from
  `assets/scripts/layout.py` and `palette.py` and writes intermediate VRAM data into `build/graphics/`.
  `tools/package_graphics.py` packs it into `src/CHESS.DAT` and generates the
  resource index and `src/gfx.h`.
* `assets/scripts/bitmap_font.py` regenerates the native ASCII font sheet
  automatically when its source changes. Active portraits, newspaper pieces,
  and serif masthead artwork are kept as approved PNG sources.
* Start/setup artwork is split between both tile layers at native 640x480;
  each layer stays within its tile and VRAM budget. Menu code lives in RAM
  bank 21, along with SAN formatting; dialogs and persistence
  live in bank 22; board drawing, input and sprite copying use bank 23
  from the shared startup bundle, leaving main RAM for the engine and ZSMKit. Coordinate history
  uses bank 24; SAN still uses bank 19. Returning to
  play reloads the playing-field graphics without resetting the match.
  Startup loads only opening-screen assets; engine and board data wait until
  the first game. Scene artwork becomes visible after artwork and controls are drawn; a separate
  paper tilemap and Loading sprite cover scene and piece-set loading.
  The bitmap font and scorecard background map stay resident, avoiding repeated
  disk transfers. Layer-1 map clears use a direct VERA write loop.
  Startup graphics loading is roughly halved; retaining the font and scorecard
  map avoids repeated transfers. The original optimization measurements are
  recorded in `docs/startup-performance.json`; HostFS timings exclude physical
  disk transfer time.
* UI text uses Kakuro’s native 8×8 bitmap glyphs, with integer pixel
  scaling for headings. Game clocks use the native font. The opening masthead retains its original
  serif artwork; menu titles and the in-game masthead use matching PT Serif Bold coverage masks.
  The board margins show only coordinates;
  evaluation appears as a bar in the scorecard. Scorecard figurines use supplied native
  pixel art in 16×16 cells, assembled from four 8×8 tiles; text retains its
  8-pixel advance. The foreground uses 833 of VERA’s 1024 tiles, including smooth bar fills.
* Blank paper uses one solid palette color. Dithering is confined to the
  portraits; the runtime labels and controls remain crisp.
* The opening screen uses the approved Black + paper only portrait,
  black dithering and solid `#EEDDBB` paper. Its shared `PALETTE` resource
  preserves the original portrait colors; a reserved palette row provides the masthead edge shades. Setup loads the `SETPAL` resource for a four-tone
  black/gray/white queen that extends through the bottom edge; play restores
  `PALETTE` resource. Red setup headings and clickable left/right triangles use
  the native bitmap font slots. Keyboard arrows still select and change values.
* Portrait tiles on layer 1 have an underlay matching palette index zero:
  black on both the opening screen and setup. Index zero is
  transparent on that layer but opaque in the source artwork.
  Palette row zero preserves all sixteen source colors. The graphics build
  decodes the exported 4bpp tiles and maps and rejects any changed pixel,
  invalid palette, missing tile, or exceeded tile budget. Its previews come
  from that verified reconstruction.
* `make test` includes transparency/palette regression tests. `make test-ui`
  checks that no board or unfinished artwork appears during startup, then
  compares the actual emulator screenshots against the verified portraits
  with zero pixel tolerance, including after menu transitions. The mouse
  pointer is moved outside the artwork before comparison.

The approved splash, Victorian board, and selector pixel references live in
`tests/fixtures/graphics/`. Tests have no dependency on historical galleries.
The design explorations, old screenshots, and obsolete assets are preserved
in an external archive listed in `docs/cleanup-manifest.json`; every archived
file was read back and SHA256 verified before removal. The compact font layout
and removed slots are documented in `assets/font/README.md`.

## Credits

* Active chess pieces: Victorian Diagram, Continental Engraving, and Daily
  Letterpress, generated with imagegen from the supplied newspaper reference.
  Cburnett’s older unused artwork is archived; attribution remains in
  `assets/pieces/README.md`.
* Fonts: native 8×8 bitmap UI font from Ivo Filot's CX16 Kakuro (GPL-3.0-or-later), see `assets/font/README.md`.
* Serif masthead lettering: PT Serif (ParaType, SIL Open Font License 1.1).
* Start/setup/about portraits generated with imagegen and constrained to the
  project palette; source artwork lives in `assets/art/splash.png`,
  `assets/art/setup.png`, and `assets/art/about.png`.

## License

Unless otherwise stated, the code in this repository is provided under the
GNU General Public License version 3.
