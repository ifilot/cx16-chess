EMU ?= $(abspath ../x16-emulator/build/x16emu)
ROM ?= $(abspath $(firstword $(wildcard ../emulator/rom.bin ../emulator-win/rom.bin) ../emulator/rom.bin))
EMU_FLAGS ?= -scale 2

.PHONY: all run screenshot test parity fuzz bench wac clean

all:
	$(MAKE) -C src

run: all
	cd src && "$(EMU)" -rom "$(ROM)" -prg CHESS.PRG -run $(EMU_FLAGS)

screenshot: all
	python3 tools/screenshot.py --emu "$(EMU)" --rom "$(ROM)"

# native tests: perft and SAN of rules.c, engine perft and mates
test:
	$(MAKE) -C tests

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
