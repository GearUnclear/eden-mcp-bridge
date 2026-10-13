# Makefile for arma3_mcp_bridge.dll
# Cross-compiles a Windows x64 DLL from WSL using MinGW-w64.
#
# Usage (from WSL):
#   cd /mnt/c/path/to/eden-mcp-bridge/bridge_dll
#   make
#   make install        # also copies DLL to the addon folder
#   make clean

CXX      := x86_64-w64-mingw32-g++-posix
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra \
            -DWIN32_LEAN_AND_MEAN -D_WIN32_WINNT=0x0600 \
            -Isrc
LDFLAGS  := -shared \
            -static -static-libgcc -static-libstdc++ \
            -Wl,--subsystem,windows \
            -Wl,--kill-at
LIBS     := -lkernel32 -luser32 -ladvapi32

OUT_DIR  := build/wsl
TARGET   := $(OUT_DIR)/arma3_mcp_bridge.dll

ADDON_DIR := ../arma3_addon/addons/bridge

SRCS := src/dllmain.cpp \
        src/pipe_server.cpp \
        src/message_queue.cpp

OBJS := $(patsubst src/%.cpp, $(OUT_DIR)/%.o, $(SRCS))

# ---------------------------------------------------------------------------

.PHONY: all install clean

all: $(TARGET)

$(OUT_DIR):
	mkdir -p $(OUT_DIR)

$(OUT_DIR)/%.o: src/%.cpp $(wildcard src/*.h) | $(OUT_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(TARGET): $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^ $(LIBS)
	@echo ""
	@echo "Built: $(TARGET)"

install: $(TARGET)
	cp $(TARGET) $(ADDON_DIR)/arma3_mcp_bridge.dll
	@echo "Installed to: $(ADDON_DIR)/arma3_mcp_bridge.dll"

clean:
	rm -rf $(OUT_DIR)
