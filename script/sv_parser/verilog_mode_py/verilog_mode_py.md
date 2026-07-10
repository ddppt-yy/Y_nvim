# verilog_mode_py Implementation Guide

## Goal

实现一个不调用原始 `verilog-mode.el` 的纯 Python Verilog/SystemVerilog AUTO 生成工具，重点覆盖例化和声明生成相关功能。

目标不是复刻 Emacs 编辑器，也不是完整翻译 Elisp。目标是实现下面这类 batch 行为：

```bash
python3 -m verilog_mode_py verilog-batch-auto <top_file>
python3 -m verilog_mode_py verilog-batch-delete-auto <top_file>
```

核心判断标准：

```text
input.sv -> python auto -> output.sv
```

在目标功能范围内，应尽量等价于：

```text
input.sv -> verilog-mode.el batch auto -> output.sv
```

## Scope

优先实现和例化/AUTO 生成直接相关的功能：

- `AUTOINST`
- `AUTOINSTPARAM`
- `AUTOARG`
- `AUTOWIRE`
- `AUTOLOGIC`
- `AUTOINPUT`
- `AUTOOUTPUT`
- `AUTOINOUT`
- `.*` 显式展开
- module/interface lookup
- 基础 `AUTO_TEMPLATE`
- `AUTOINOUTMODULE`
- `AUTOINOUTCOMP`
- `AUTOINOUTIN`
- `AUTOINOUTPARAM`
- `AUTOINOUTMODPORT`
- `AUTOASSIGNMODPORT`

明确不做 Emacs UI 功能：

- font/font-lock
- indent engine
- interactive menu
- mouse/keyboard command
- completion
- editor window/buffer display

复杂功能后置：

- `AUTOSENSE`
- `AUTORESET`
- `AUTOREG`
- `AUTOREGINPUT`
- `AUTOUNUSED`
- 任意 `AUTO_LISP`
- `AUTOINSERTLISP`
- `AUTOINSERTLAST`

## Key Principle

不要尝试把 `verilog-mode.el` 逐行翻译成 Python。

正确路线是：

1. 把 `verilog-mode.el` 当作行为规格和测试 oracle。
2. 用 Python 重新实现 AUTO 所需的数据结构和文本重写逻辑。
3. 用 upstream tests 和本项目 golden tests 做差分收敛。

也就是说，实现目标是行为等价，不是源码结构等价。

## Architecture

建议拆成以下模块，而不是继续堆一个巨大的单文件：

```text
verilog_mode_py/
  __init__.py
  __main__.py
  cli.py
  buffer.py
  syntax.py
  config.py
  sv_lexer.py
  sv_parse.py
  library.py
  model.py
  formatter.py
  auto/
    __init__.py
    delete.py
    inst.py
    arg.py
    declarations.py
    template.py
    modport.py
    sense.py
    reset.py
  tests/
    upstream_runner.py
```

### `model.py`

定义内部统一数据模型。AUTO 逻辑只依赖这些数据结构，不直接依赖 Verilator AST 或正则 match。

建议模型：

```python
@dataclass(frozen=True)
class Port:
    name: str
    direction: str
    data_type: str = ""
    packed: str = ""
    unpacked: str = ""
    interface_type: tuple[str, ...] = ()

@dataclass(frozen=True)
class Param:
    name: str
    value: str = ""
    data_type: str = ""
    packed: str = ""

@dataclass
class ModuleInfo:
    name: str
    ports: list[Port]
    params: list[Param]
    signals: list[Port]
    interface_ports: dict[str, Port]
    modports: dict[str, list[tuple[str, str]]]
    source_path: Path | None = None

@dataclass(frozen=True)
class Instance:
    module: str
    name: str
    start: int
    port_open: int
    port_close: int
    param_open: int | None = None
    param_close: int | None = None
```

### `buffer.py`

实现一个小型文本编辑内核，替代 AUTO 需要的 Emacs buffer primitives。

需要能力：

- 当前扫描位置 `pos`
- `goto(pos)`
- `looking_at(pattern)`
- `search_forward(pattern)`
- `insert(pos, text)`
- `delete(start, end)`
- `replace(start, end, text)`
- `line_bounds(pos)`
- `line_indent(pos)`
- `column(pos)`
- `save_pos()` context manager
- 维护最近一次正则匹配结果 `last_match`

不需要实现完整 Emacs buffer，只实现 AUTO 所需子集。

### `syntax.py`

负责源码语法状态扫描。

必须支持：

- 跳过 `// ...`
- 跳过 `/* ... */`
- 跳过字符串
- 跳过 attributes `(* ... *)`
- 找 matching `()`, `[]`, `{}`
- 判断 offset 是否在 comment/string 内

这是 `syntax-ppss` / `parse-partial-sexp` 的 Python 替代层。

### `sv_lexer.py`

实现轻量 tokenizer，不追求完整 SystemVerilog 编译器。

需要 token：

- identifier
- escaped identifier
- keyword
- number
- string
- operator/punctuation
- preprocessor directive
- comment
- attribute

lexer 的目标是服务 AUTO，不是做完整语义分析。

### `sv_parse.py`

从源码中解析 AUTO 需要的信息：

- module/interface 边界
- parameter/localparam
- ANSI and non-ANSI ports
- signal declarations
- module instances
- named connections
- interface declarations
- modport declarations

关键要求：

- 保留源码形态，例如 `[WIDTH-1:0]` 不能被归一化成 `[7:0]`。
- 支持 AUTO 中间态，例如 `/*AUTOINST*/`、`/*AUTOARG*/`。
- 能处理文件中多个 module/interface。

Verilator 可以作为辅助校验或 fallback，但不能作为唯一 parser，因为 Verilator 会归一化源码并且不适合处理中间态 AUTO 文本。

### `library.py`

负责模块查找。

支持：

- 当前 top 文件
- top 同目录
- `verilog-library-directories`
- `verilog-library-flags`
- `+libext+`
- `-I`
- `-y`
- `verilog-library-files`

输出统一为 `ModuleInfo`。

注意：库查找逻辑必须独立，不能散落在 `AUTOINST` 或 `AUTOARG` 代码里。

### `config.py`

解析每个文件的配置。

支持常用 file-local variables：

```verilog
// Local Variables:
// verilog-library-directories:("." "rtl" "ip")
// verilog-library-flags:("-Iinc +libext+.sv+.v")
// verilog-auto-inst-sort:t
// verilog-auto-arg-sort:t
// verilog-auto-inst-param-value:t
// End:
```

Python 内部使用 per-file config object，不需要实现完整 Emacs buffer-local variable 系统。

## AUTO Expansion Pipeline

`verilog-batch-auto` 的推荐流程：

1. 读取 top file。
2. 解析 file-local config。
3. 构建 `ModuleLibrary`。
4. 执行 delete pass，删除已有 automatic block。
5. 重新解析当前文本和 library。
6. 解析 `AUTO_TEMPLATE`。
7. 按固定顺序展开 AUTO。
8. 写回文件。

推荐顺序：

```text
1. delete existing generated blocks
2. AUTOINSTPARAM
3. AUTOINST
4. .*
5. AUTOINOUTMODPORT
6. AUTOINOUTMODULE
7. AUTOINOUTCOMP
8. AUTOINOUTIN
9. AUTOINOUTPARAM
10. AUTOOUTPUT
11. AUTOINPUT
12. AUTOINOUT
13. AUTOLOGIC
14. AUTOWIRE
15. AUTOARG
```

后续再加入：

```text
AUTOREG
AUTOREGINPUT
AUTOOUTPUTEVERY
AUTOSENSE
AUTORESET
AUTOUNUSED
AUTOTIEOFF
AUTOUNDEF
```

## Delete Pass

delete pass 是稳定性的关键。

必须满足：

```text
auto -> delete -> auto
```

结果 deterministic。

需要删除：

- `// Beginning of automatic ...`
- `// End of automatics`
- automatic block 中间内容
- `AUTOINST` marker 后生成的连接
- `AUTOINSTPARAM` marker 后生成的参数连接
- `.*` 展开出来的 explicit connection
- `AUTOARG` header 中插入的端口列表
- `AUTOSENSE` 中插入的敏感信号

不要删除用户手写连接和用户手写声明。

## `AUTOINST`

输入：

- 当前 instance
- 子模块 `ModuleInfo`
- 已存在的手写 port connection
- template resolver

输出：

```verilog
// Outputs
.dout                           (dout),
// Inputs
.clk                            (clk),
.din                            (din)
```

规则：

- 按 direction 分组，通常 `output`, `inout`, `input`。
- 跳过用户已手写连接的端口。
- 保留 vector 连接，例如 `din[3:0]`。
- 支持 `verilog-auto-inst-sort`。
- 支持 `AUTO_TEMPLATE` 改名。

## `AUTOINSTPARAM`

输入：

- 子模块 params
- 已存在手写 parameter override

输出：

```verilog
// Parameters
.WIDTH                          (WIDTH),
.DEPTH                          (DEPTH)
```

规则：

- 跳过用户已手写参数。
- 后续支持 `verilog-auto-inst-param-value`。

## `AUTOARG`

目标：根据当前 module 内声明的 ports 生成 module header。

输入：

- 当前 module scope
- input/output/inout declarations

输出：

```verilog
/*AUTOARG*/
// Outputs
dout,
// Inouts
pad,
// Inputs
din, clk
```

规则：

- 支持 `verilog-auto-arg-sort`。
- 保持和 delete/auto 稳定。
- 需要处理 header 内 marker 位置。

## Declaration AUTO

包括：

- `AUTOINPUT`
- `AUTOOUTPUT`
- `AUTOINOUT`
- `AUTOWIRE`
- `AUTOLOGIC`

基本思路：

1. 先完成 `AUTOINST`，得到所有子模块 connection use。
2. 收集当前 module 已声明 names。
3. 找出未声明的 input/output/inout/wire。
4. 生成声明。

关键点：

- 不重复声明已有 signal。
- `AUTOWIRE` 通常只声明子模块 output/inout 驱动出的未声明信号。
- `AUTOINPUT` 只声明仅被子模块 input 使用的未声明信号。
- `AUTOOUTPUT` 只声明仅被子模块 output 使用的未声明信号。
- template 生成的表达式如果不是简单 signal，不应盲目声明。

## `AUTO_TEMPLATE`

这是例化兼容性的最大难点，单独实现。

分阶段支持：

### Stage 1

- 精确 port name
- 简单 signal rename

```verilog
/* leaf AUTO_TEMPLATE (
   .din (foo_din[]),
); */
```

### Stage 2

- `@` instance number
- `[]` vector substitution
- `vl-name`
- `vl-cell-name`
- `vl-width`

### Stage 3

- regexp port pattern
- instance regexp
- backreference `\1`, `\2`

### Stage 4

支持白名单 Lisp-like expression，不支持任意 Elisp。

建议白名单：

- `downcase`
- `upcase`
- `concat`
- `substring`
- `format`
- `replace-regexp-in-string`
- `verilog-string-replace-matches`

任意 `eval`、`AUTOINSERTLISP`、复杂 `AUTO_LISP` 默认 unsupported。

## Test Strategy

测试是这个项目的核心。

### Local Golden Tests

继续使用本项目结构：

```text
test/golden/<case_name>/input.sv
test/golden/<case_name>/expected_auto.sv
test/golden/<case_name>/expected_delete.sv
```

每个 case 验证：

```text
input -> auto == expected_auto
expected_auto -> delete == expected_delete
expected_delete -> auto == expected_auto
```

### Upstream Tests

不要简单遍历 `test/verilog-mode/tests/*.v`。

需要复刻 upstream harness 的语义：

- `tests_batch_ok`
- `tests`
- `tests_ok`
- include path
- file-local variables
- batch delete/auto/diff/indent 中与 AUTO 相关的部分

本项目只关注 AUTO/例化功能，所以先筛选 AUTO 相关用例：

- 文件名包含 `autoinst`
- 文件名包含 `autoarg`
- 文件名包含 `autowire`
- 文件名包含 `autoinput`
- 文件名包含 `autooutput`
- 文件名包含 `autoinout`
- 文件名包含 `template`
- 文件名包含 `modport`

### Differential Testing

对于未确认行为，可以临时用原版 `verilog-mode.el` 生成 expected output，但最终 Python 实现本身不调用 el 文件。

流程：

```text
fixture -> emacs/verilog-mode.el -> golden
fixture -> python implementation -> actual
diff golden actual
```

golden 一旦生成，提交进测试目录，后续不再运行 Emacs。

## Implementation Phases

### Phase 0: Refactor Skeleton

- 建包 `verilog_mode_py`
- 加 `cli.py`
- 加 `model.py`
- 加 `buffer.py`
- 加 `syntax.py`
- 保持现有 golden tests 可运行

Acceptance:

- CLI 可执行
- delete-auto 不破坏 marker
- py_compile 通过

### Phase 1: Parser and Library

- 实现 module/interface parser
- 实现 port/param/signal parser
- 实现 instance parser
- 实现 module lookup

Acceptance:

- 能正确读取多 module 文件
- 能正确保留 `[WIDTH-1:0]`
- 能处理 AUTO 中间态

### Phase 2: Core Instantiation

- `AUTOINST`
- `AUTOINSTPARAM`
- `.*`
- manual connection skip

Acceptance:

- basic AUTOINST golden 通过
- auto/delete/auto 稳定

### Phase 3: Declaration Generation

- `AUTOARG`
- `AUTOINPUT`
- `AUTOOUTPUT`
- `AUTOINOUT`
- `AUTOWIRE`
- `AUTOLOGIC`

Acceptance:

- 不重复声明
- declaration order 与目标 tests 对齐

### Phase 4: Templates

- exact template
- regexp template
- `@`
- `[]`
- common Lisp-like whitelist

Acceptance:

- upstream AUTO_TEMPLATE 常见用例通过

### Phase 5: Interface Helpers

- `AUTOINOUTMODULE`
- `AUTOINOUTCOMP`
- `AUTOINOUTIN`
- `AUTOINOUTPARAM`
- `AUTOINOUTMODPORT`
- `AUTOASSIGNMODPORT`

Acceptance:

- interface/modport golden 通过

### Phase 6: Advanced Analysis

- `AUTOSENSE`
- `AUTOREG`
- `AUTOREGINPUT`
- `AUTORESET`
- `AUTOUNUSED`

Acceptance:

- 先 partial support
- 每个 feature 必须有独立 golden

## Unsupported Policy

默认不支持会执行任意代码的 Elisp 功能：

- arbitrary `AUTO_LISP`
- arbitrary template Lisp expression
- `AUTOINSERTLISP`
- `AUTOINSERTLAST`
- file-local `eval`
- user hooks

遇到 unsupported feature 时，CLI 应该：

1. 给出明确错误或 warning。
2. 不产生半错误 output。
3. 保留原文件不变，除非用户显式允许 partial output。

## Verification Commands

建议每次改动至少运行：

```bash
python3 -m py_compile verilog-mode_v1.py
python3 test/golden/run_golden.py
```

重构成包以后改为：

```bash
python3 -m py_compile verilog_mode_py/*.py verilog_mode_py/auto/*.py
python3 -m pytest
python3 test/golden/run_golden.py --script python3 -m verilog_mode_py
```

## Quality Rules

- AUTO 输出必须 deterministic。
- 不要依赖 dict insertion order 以外的隐式行为；需要排序时显式排序。
- 任何新增 feature 必须有 auto/delete/re-auto 测试。
- parser 应保留源码文本形态，不能只保留 elaborated 语义。
- Verilator 只能作为辅助，不能作为唯一 parser。
- 不要为了一个特殊 case 破坏通用 tokenizer/parser。

## Summary

这个项目的可行路线是：

```text
纯 Python source-to-source AUTO engine
+ 轻量 SV tokenizer/parser
+ 独立 module library
+ 分阶段 AUTO feature 实现
+ upstream/golden differential tests
```

不需要复刻 Emacs UI，也不需要完整翻译 `verilog-mode.el`。

后续实现应优先保证：

```text
AUTOINST/AUTOINSTPARAM/AUTOARG/AUTOWIRE/AUTOINPUT/AUTOOUTPUT/AUTOINOUT
```

这些例化相关功能稳定后，再扩展 template 和高级分析功能。
