# Makefile - 用于 Verilator + GTKWave 仿真

# 项目变量
TOP_MODULE = tb_adder8          # 顶层模块名（测试台）
DESIGN_FILES = adder8.sv tb_adder8.sv
SIM_EXE = ./obj_dir/V$(TOP_MODULE)
WAVEFORM = waveform.vcd

# 默认目标：编译并运行仿真
all: sim

# 编译 + 仿真（使用 --timing 支持 # 延时）
sim:
	verilator --timing --trace --main --top-module $(TOP_MODULE) \
		-Wno-WIDTHTRUNC -cc --exe --build $(DESIGN_FILES)
	$(SIM_EXE)

# 查看波形（用 GTKWave）
wave:
	gtkwave $(WAVEFORM)

# 仅编译（不运行）
compile:
	verilator --timing --trace --main --top-module $(TOP_MODULE) \
		-Wno-WIDTHTRUNC -cc --exe --build $(DESIGN_FILES)

# 运行已编译的仿真
run:
	$(SIM_EXE)

# 清理生成的文件
clean:
	rm -rf obj_dir $(WAVEFORM)

# 清理后重新编译并仿真
rebuild: clean sim

# 声明伪目标
.PHONY: all sim wave compile run clean rebuild
