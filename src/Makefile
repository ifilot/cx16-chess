CC=cl65
CFLAGS?=-O -I core -I gui -I bridge -I .
LDFLAGS?=-t cx16 -C chess.cfg
ENGINE_LDFLAGS?=-t cx16 -C engine.cfg
PYTHON=python3
SCRIPTS=../assets/scripts
GFX_ASSETS=CHESS.DAT gfx.h assets.h assets.inc
SOUND_FILES=TITLE.ZSM GAME.ZSM GAME2.ZSM GAME3.ZSM GAME4.ZSM WIN.ZSM LOSE.ZSM DRAW.ZSM SFX.BIN
SOUND_ASSETS=$(SOUND_FILES) music.h sfx.h

CORE_SRC=$(wildcard core/*.c core/*.s)
GUI_SRC=$(wildcard gui/*.c gui/*.s)
BRIDGE_SRC=$(wildcard bridge/*.c)
CORE_HDR=$(wildcard core/*.h)
ENGINE_SRC=$(filter-out core/match.c,$(CORE_SRC))

all: CHESS.PRG MENU.BIN UI.BIN DRAG.BIN AUDIO.BIN ENGINE.PRG AUTOBOOT.X16 $(SOUND_ASSETS)

$(SOUND_ASSETS): %: ../assets/sound/%
	cp $< $@

# Memory playback needs no streaming buffers or disk work during search.
vendor/zsmkit/zsmkit.o: $(wildcard vendor/zsmkit/*.s vendor/zsmkit/*.inc)
	ca65 --cpu 65C02 -I vendor/zsmkit vendor/zsmkit/zsmkit.s -o $@

# The game already has a BASIC SYS stub, so it can boot directly under this name.
AUTOBOOT.X16: CHESS.PRG
	cp CHESS.PRG $@

# the game: core + graphical front end (C stack in golden RAM, gui/stack.s)
CHESS.PRG MENU.BIN UI.BIN DRAG.BIN AUDIO.BIN &: $(CORE_SRC) $(GUI_SRC) $(CORE_HDR) $(wildcard gui/*.h) chess.cfg $(GFX_ASSETS) $(SOUND_ASSETS) vendor/zsmkit/zsmkit.o strings.h build_info.h
	$(CC) $(CFLAGS) --asm-include-dir . -DNO_TEST_HOOKS -o CHESS.PRG -m CHESS.map -Ln CHESS.sym $(LDFLAGS) -Wl -D,__STACKSIZE__=0 \
		$(CORE_SRC) $(GUI_SRC) vendor/zsmkit/zsmkit.o

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

build_info.h: ../VERSION ../tools/build_info.py Makefile chess.cfg $(GFX_ASSETS) strings.h $(CORE_SRC) $(GUI_SRC) $(CORE_HDR) $(wildcard gui/*.h)
	$(PYTHON) ../tools/build_info.py $@

strings.h: $(SCRIPTS)/build_strings.py
	$(PYTHON) $(SCRIPTS)/build_strings.py strings.h

clean:
	rm -f $(SOUND_ASSETS) vendor/zsmkit/*.o
	rm -f core/*.o gui/*.o bridge/*.o CHESS.DAT AUTOBOOT.X16 *.PRG *.BIN *.menu *.map *.sym gfx.h assets.h assets.inc strings.h build_info.h playfield*.png splash.png setup.png

.PHONY: all clean
