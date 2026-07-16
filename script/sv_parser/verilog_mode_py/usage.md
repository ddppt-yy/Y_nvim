# verilog_mode_py.py 使用说明

## 主功能

```bash
# 进入目录
cd /home/yh/my_script/Y_nvim/script/sv_parser/verilog_mode_py

# AUTO 展开（核心功能，会原地修改文件）
python3 verilog_mode_py.py verilog-batch-auto <文件.sv>

# 删除所有 AUTO 生成的块（会原地修改文件）
python3 verilog_mode_py.py verilog-batch-delete-auto <文件.sv>
```

**注意**：被处理的文件会原地修改，建议先备份或用版本控制。

## 修改后自动跑测试

```bash
# 1. 快速检查编译是否通过
python3 -m py_compile verilog_mode_py.py

# 2. 跑全部 187 个 AUTO 相关测试用例（包版本）
python3 tests/upstream_runner.py

# 3. 也可以只列出用例不运行
python3 tests/upstream_runner.py --list
```

## 对比单文件版与包版本

```bash
# 快速对比：用同一个文件分别跑两个版本，diff 输出
cp tests/autoinst_star.v /tmp/a.v && cp tests/autoinst_star.v /tmp/b.v
python3 verilog_mode_py.py verilog-batch-auto /tmp/a.v
python3 -m verilog_mode_py verilog-batch-auto /tmp/b.v
diff /tmp/a.v /tmp/b.v && echo "输出一致"
```

## 典型修改工作流

```bash
# 1. 改代码
vim verilog_mode_py.py

# 2. 编译检查
python3 -m py_compile verilog_mode_py.py

# 3. 跑测试
python3 tests/upstream_runner.py

# 4. 如果 upstream_runner 通过，再确认单文件版和包版一致
cp tests/autoinst_star.v /tmp/a.v && python3 verilog_mode_py.py verilog-batch-auto /tmp/a.v
cp tests/autoinst_star.v /tmp/b.v && python3 -m verilog_mode_py verilog-batch-auto /tmp/b.v
diff /tmp/a.v /tmp/b.v && echo "PASS"
```

## 测试覆盖范围

共 187 个 AUTO 相关测试用例，覆盖功能：

- AUTOINST / AUTOINSTPARAM — 例化与参数例化
- AUTOARG — 模块端口声明
- AUTOWIRE / AUTOLOGIC — 信号声明
- AUTOINPUT / AUTOOUTPUT / AUTOINOUT — 端口声明
- AUTOINOUTMODULE / AUTOINOUTCOMP / AUTOINOUTIN / AUTOINOUTPARAM — 接口辅助
- AUTOINOUTMODPORT / AUTOASSIGNMODPORT — modport 生成
- AUTOSENSE — 敏感信号列表
- AUTO_TEMPLATE — 模板展开
- AUTOTIEOFF / AUTOUNUSED / AUTOUNDEF — 辅助功能

不支持的特性（AUTO_LISP、AUTOREG、AUTORESET 等）已在测试中自动跳过。