IVERILOG ?= iverilog
VVP      ?= vvp

BUILD_DIR := build
SIM       := $(BUILD_DIR)/tr1um_uarttx_tb.vvp
SOURCES   := tr1um_uarttx.v tr1um_uarttx_tb.v

.PHONY: all sim clean

all: sim

sim: $(SIM)
	$(VVP) $(SIM)

$(SIM): $(SOURCES)
	mkdir -p $(BUILD_DIR)
	$(IVERILOG) -g2012 -Wall -DSIMULATION -s tr1um_uarttx_tb -o $@ $(SOURCES)

clean:
	rm -rf $(BUILD_DIR)
