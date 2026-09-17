TOP := tr1um_alu8
.PHONY: all sim clean
all: sim
sim:
	iverilog -g2012 -DSIMULATION -s $(TOP)_tb -o $(TOP)_tb.out $(TOP).v $(TOP)_tb.v
	vvp $(TOP)_tb.out
clean:
	rm -f $(TOP)_tb.out
