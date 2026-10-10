CC=cl65
CFLAGS?=-O -I core -I gui -I bridge -I .
LDFLAGS?=-t cx16 -C chess.cfg
PYTHON=python3
SCRIPTS=../assets/scripts
GFX_ASSETS=L0TILES.DAT L0MAP.DAT L1TILES.DAT SPRITES.DAT PALETTE.DAT gfx.h

CORE_SRC=$(wildcard core/*.c core/*.s)
GUI_SRC=$(wildcard gui/*.c gui/*.s)
BRIDGE_SRC=$(wildcard bridge/*.c)
CORE_HDR=$(wildcard core/*.h)
ENGINE_SRC=$(filter-out core/match.c,$(CORE_SRC))

all: CHESS.PRG ENGINE.PRG

# the game: core + graphical front end
CHESS.PRG: $(CORE_SRC) $(GUI_SRC) $(CORE_HDR) $(wildcard gui/*.h) chess.cfg $(GFX_ASSETS) strings.h
	$(CC) $(CFLAGS) -DNO_TEST_HOOKS -o $@ -m CHESS.map -Ln CHESS.sym $(LDFLAGS) $(CORE_SRC) $(GUI_SRC)

# headless engine harness driven through the $0400 mailbox (tools/engine_bridge.py)
ENGINE.PRG: $(ENGINE_SRC) $(BRIDGE_SRC) $(CORE_HDR) bridge/bridge.h chess.cfg
	$(CC) $(CFLAGS) -o $@ -m ENGINE.map -Ln ENGINE.sym $(LDFLAGS) $(ENGINE_SRC) $(BRIDGE_SRC)

$(GFX_ASSETS) &: $(SCRIPTS)/build_graphics.py $(SCRIPTS)/layout.py $(SCRIPTS)/palette.py \
		$(wildcard ../assets/font/*) ../assets/pieces/pieces.png $(wildcard ../assets/art/*.png)
	$(PYTHON) $(SCRIPTS)/build_graphics.py .

strings.h: $(SCRIPTS)/build_strings.py
	$(PYTHON) $(SCRIPTS)/build_strings.py strings.h

clean:
	rm -f core/*.o gui/*.o bridge/*.o *.DAT *.PRG *.map *.sym gfx.h strings.h playfield.png

.PHONY: all clean
