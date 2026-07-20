

  用法示例：

  emacs -Q --batch -l ./ex.el -f vm-dump-auto-cli -- top.sv auto_report.json

  带 library path / libext：

  emacs -Q --batch -l ./ex.el -f vm-dump-auto-cli -- top.sv auto_report.json -y rtl +libext+.v+.sv

  输出 JSON 里包含每个 module 的：

  - auto_signals: AUTOINST 推导出的 input/output/inout/interface 信号
  - submodules: AUTOINST / .* 实例的 module、instance、file path、连接端口列表
