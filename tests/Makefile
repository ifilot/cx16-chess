CC ?= cc
CORE = ../src/core/rules.c ../src/core/engine.c ../src/core/engine_board.c ../src/core/engine_hot.c

# native builds of the core: perft/SAN tests of rules.c, and the engine as
# a UCI program (used by the tools for matches and as the C reference)
test: perft uci
	./perft
	./engine_test.sh

perft: perft.c ../src/core/rules.c ../src/core/rules.h
	$(CC) -O2 -Wall -o perft perft.c ../src/core/rules.c

uci: uci.c $(CORE) ../src/core/*.h
	$(CC) -O2 -Wall -o uci uci.c $(CORE)

# variant builds for tuning with tools/selfplay.py: make uci_NAME compiles
# with -DNAME, so experimental code can be guarded by #ifdef NAME
uci_%: uci.c $(CORE) ../src/core/*.h
	$(CC) -O2 -Wall -D$* -o $@ uci.c $(CORE)

clean:
	rm -f perft uci uci_*

.PHONY: test clean
