# Local builds. The submission itself is produced by tools/pack.py (see README).
CXX      ?= c++
CXXFLAGS ?= -O3 -std=c++17 -march=native
NET      ?= tools/nets/n10b.bin
HIDDEN   ?= 384
BUCKETS  ?= 4

all: build/bot build/referee

build/bot: bot.cpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) -DLOCAL -DNN_H=$(HIDDEN) -DNN_B=$(BUCKETS) -o $@ $<

build/referee: tools/referee.cpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) -pthread -o $@ $<

# single-file submission with the net embedded
pack:
	python3 tools/pack.py -n $(NET) -H $(HIDDEN) -B $(BUCKETS) -o out/submission.cpp

# move generator check: must print 6182818
perft: build/bot
	BT_PERFT=5 ./build/bot

clean:
	rm -rf build out

.PHONY: all pack perft clean
