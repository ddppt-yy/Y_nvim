# Golden AUTO Tests

这些用例定义 Python 版 `verilog-batch-auto` / `verilog-batch-delete-auto` 的目标行为。

运行方式：

```bash
python3 test/golden/run_golden.py
```

每个 case 目录包含：

- `input.sv`: 原始 top 文件
- `expected_auto.sv`: 执行 `verilog-batch-auto` 后应得到的文件
- `expected_delete.sv`: 在 `expected_auto.sv` 上执行 `verilog-batch-delete-auto` 后应得到的文件
- 其他 `.sv/.v` 文件: 子模块或 interface 依赖

当前用例优先覆盖不依赖 Emacs/Elisp 的核心 AUTO 能力。

