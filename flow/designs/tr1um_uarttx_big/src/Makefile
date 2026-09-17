IVERILOG ?= iverilog
VVP      ?= vvp

BUILD_DIR := build
SIM       := $(BUILD_DIR)/tr1um_uarttx_big_tb.vvp
SOURCES   := tr1um_uarttx_big.v tr1um_uarttx_big_tb.v

.PHONY: all sim clean

all: sim

sim: $(SIM)
	$(VVP) $(SIM)

$(SIM): $(SOURCES)
	mkdir -p $(BUILD_DIR)
	$(IVERILOG) -g2012 -Wall -DSIMULATION -s tr1um_uarttx_big_tb -o $@ $(SOURCES)

clean:
	rm -rf $(BUILD_DIR)
