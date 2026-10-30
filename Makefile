CXX = g++
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra
SRC = src/main.cpp
OUT = beepnook

all: $(OUT)

$(OUT): $(SRC)
	$(CXX) $(CXXFLAGS) -o $(OUT) $(SRC)

run: $(OUT)
	./$(OUT)

clean:
	rm -f $(OUT)

.PHONY: all run clean
