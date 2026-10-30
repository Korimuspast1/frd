#!/bin/bash
set -e
echo "=== Beepnook Gadget Shop — native build ==="
g++ -std=c++17 -O2 -Wall -o beepnook src/main.cpp
echo "Build OK: ./beepnook"
