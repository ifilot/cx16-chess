CC=cl65
CFLAGS?=-O -I core -I gui -I bridge -I .
LDFLAGS?=-t cx16 -C chess.cfg
ENGINE_LDFLAGS?=-t cx16 -C engine.cfg
PYTHON=python3
SCRIPTS=../assets/scripts
GFX_ASSETS=CHESS.DAT gfx.h assets.h assets.inc

CORE_SRC=$(wildcard core/*.c core/*.s)
GUI_SRC=$(wildcard gui/*.c gui/*.s)
BRIDGE_SRC=$(wildcard bridge/*.c)
CORE_HDR=$(wildcard core/*.h)
ENGINE_SRC=$(filter-out core/match.c,$(CORE_SRC))

all: CHESS.PRG MENU.BIN ENGINE.PRG

# the game: core + graphical front end (C stack in golden RAM, gui/stack.s)
CHESS.PRG MENU.BIN &: $(CORE_SRC) $(GUI_SRC) $(CORE_HDR) $(wildcard gui/*.h) chess.cfg $(GFX_ASSETS) strings.h
	$(CC) $(CFLAGS) --asm-include-dir . -DNO_TEST_HOOKS -o CHESS.PRG -m CHESS.map -Ln CHESS.sym $(LDFLAGS) -Wl -D,__STACKSIZE__=0 \
		$(CORE_SRC) $(GUI_SRC)

# headless engine harness driven through the $0400 mailbox (tools/engine_bridge.py)
ENGINE.PRG: $(ENGINE_SRC) $(BRIDGE_SRC) $(CORE_HDR) bridge/bridge.h engine.cfg
	$(CC) $(CFLAGS) -o $@ -m ENGINE.map -Ln ENGINE.sym $(ENGINE_LDFLAGS) $(ENGINE_SRC) $(BRIDGE_SRC)

# Runtime sheets derive directly from the checked-in native bitmap font.
../assets/font/font8x16.png: $(SCRIPTS)/bitmap_font.py $(SCRIPTS)/palette.py ../assets/font/kakuro-ui.png
	$(PYTHON) $(SCRIPTS)/bitmap_font.py

$(GFX_ASSETS) &: ../tools/package_graphics.py $(SCRIPTS)/build_graphics.py $(SCRIPTS)/bitmap_font.py $(SCRIPTS)/verify_graphics.py $(SCRIPTS)/indicators.py $(SCRIPTS)/layout.py $(SCRIPTS)/palette.py \
		$(wildcard ../assets/font/*) $(wildcard ../assets/pieces/*.png) $(wildcard ../assets/art/*.png)
	mkdir -p ../build/graphics
	$(PYTHON) $(SCRIPTS)/build_graphics.py ../build/graphics
	$(PYTHON) ../tools/package_graphics.py ../build/graphics .

strings.h: $(SCRIPTS)/build_strings.py
	$(PYTHON) $(SCRIPTS)/build_strings.py strings.h

clean:
	rm -f core/*.o gui/*.o bridge/*.o *.DAT *.PRG *.BIN *.menu *.map *.sym gfx.h assets.h assets.inc strings.h playfield*.png splash.png setup.png

.PHONY: all clean
