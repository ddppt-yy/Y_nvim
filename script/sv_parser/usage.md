# verilog-mode.py usage

只支持两个 batch 命令，输入参数只有一个 top module 文件，命令会直接写回该文件：

```bash
python3 verilog-mode.py verilog-batch-auto <top_file>
python3 verilog-mode.py verilog-batch-delete-auto <top_file>
```

示例：

```bash
python3 verilog-mode.py verilog-batch-auto test/emacs/template.sv
python3 verilog-mode.py verilog-batch-delete-auto test/emacs/template.sv
```

模块查找会使用 top 文件所在目录，并读取文件尾部 `Local Variables` 中的
`verilog-library-directories` 和 `+libext+` 设置。
