EMU ?= $(abspath ../x16-emulator/build/x16emu)
ROM ?= $(abspath $(firstword $(wildcard ../emulator/rom.bin ../emulator-win/rom.bin) ../emulator/rom.bin))
EMU_FLAGS ?= -scale 2
DEMO_GIF ?= docs/cx16-chess-gameplay.gif

.PHONY: all run screenshot demo test test-ui test-dist test-sd test-storage parity fuzz bench wac dist clean

all:
	$(MAKE) -C src

dist: all
	python3 tools/distribute.py

run: all
	cd src && "$(EMU)" -rom "$(ROM)" -prg CHESS.PRG -run $(EMU_FLAGS)

screenshot: all
	python3 tools/screenshot.py --emu "$(EMU)" --rom "$(ROM)"

demo: all
	$(MAKE) -C tests uci
	python3 tools/record_gameplay.py --emulator "$(EMU)" --rom "$(ROM)" --output "$(DEMO_GIF)"

# native tests: perft and SAN of rules.c, engine perft and mates
test:
	$(MAKE) -C tests
	python3 tests/graphics_test.py

test-ui: all
	python3 tools/startup_test.py
	python3 tools/transitions_test.py
	python3 tools/ui_test.py
	python3 tools/scorecard_test.py
	python3 tools/options_test.py
	python3 tools/indicators_test.py
	python3 tools/assets_test.py
	python3 tools/storage_test.py
	python3 tools/demo_test.py

test-dist: dist
	CHESS_FSROOT="$(abspath build/dist/CHESS)" $(MAKE) test-ui

test-storage: all
	python3 tools/storage_test.py
	python3 tools/demo_test.py

# Exercise the ROM's real CMDR-DOS/SD path, including native partial reads.
# Requires mkfs.fat and mcopy; the generated image is confined to build/.
test-sd: dist
	python3 tools/make_sdcard.py
	CHESS_FSROOT="$(abspath build/dist/CHESS)" CHESS_SDCARD="$(abspath build/dist/CHESS.IMG)" python3 tools/startup_test.py --out build/startup-sd.json
	CHESS_FSROOT="$(abspath build/dist/CHESS)" CHESS_SDCARD="$(abspath build/dist/CHESS.IMG)" python3 tools/ui_test.py
	CHESS_FSROOT="$(abspath build/dist/CHESS)" CHESS_SDCARD="$(abspath build/dist/CHESS.IMG)" python3 tools/options_test.py
	python3 tools/storage_sd_test.py

# X16 engine tests in the AgentBridge emulator (see README); fuzz and wac
# need python-chess
parity: all test
	python3 tools/parity_test.py 4

fuzz: all test
	python3 tools/fuzz_test.py 100

bench: all
	python3 tools/depth_bench.py 5 10 30

wac: all
	python3 tools/epd_test.py tests/epd/wac.epd --time 10 --workers 8

clean:
	$(MAKE) -C src clean
	$(MAKE) -C tests clean
	rm -rf build tools/__pycache__ assets/scripts/__pycache__
