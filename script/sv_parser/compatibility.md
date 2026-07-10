# Python AUTO Compatibility Plan

## Goal

实现一个不依赖 Emacs/Elisp 的 Python 版 batch AUTO 工具：

```bash
python3 verilog-mode.py verilog-batch-auto <top_file>
python3 verilog-mode.py verilog-batch-delete-auto <top_file>
```

解析 SystemVerilog/Verilog 主语法时优先复用 `sv_parser.py`，由 `verible-verilog-syntax` 提供 AST。Python 侧负责 AUTO 业务逻辑、文本替换、delete/re-expand 稳定性和兼容测试。

## Non-goals

- 不调用 Emacs。
- 不执行 Elisp。
- 不支持 Emacs hook、buffer-local eval、syntax-table 运行时行为。
- 不承诺初期与 `verilog-mode.el` 逐字符一致；目标是分阶段实现可验证兼容。

## Key Design

1. `verible` 负责合法 SV/V 文件的结构化解析。
2. AUTO 中间态可能不是合法 SV，例如 `/*AUTOSENSE*/`、`.*` 展开混合状态；进入 `sv_parser.py` 前需要临时 sanitize。
3. `verilog-batch-auto` 必须先执行 delete，再按固定顺序重新展开。
4. `verilog-batch-delete-auto` 必须能恢复 AUTO marker，保证：

```text
auto -> delete -> auto
```

结果稳定。

## Compatibility Matrix

| Feature | Target Status | Parser Basis | Difficulty | Notes |
|---|---:|---|---:|---|
| `verilog-batch-auto` | Full | Text driver | Low | 单 top 文件输入，写回文件 |
| `verilog-batch-delete-auto` | Full | Text driver | Medium | 必须覆盖所有已支持 AUTO |
| Module lookup | Full | Local Variables + path | Medium | 支持 top 同目录、`verilog-library-directories`、`+libext+` |
| `AUTOARG` | Full | `SvParser` current module ports | Medium | 从最终端口声明回填 module header |
| `AUTOINST` | Full first | child module ports | Medium | 支持手写端口跳过 |
| `AUTOINSTPARAM` | Full first | child module params | Medium | 支持参数连接；参数值替换后续再细化 |
| `.*` | Full first | child module ports | Medium | 展开成显式连接；delete 恢复 `.*` |
| `AUTOINPUT` | Full first | submodule connections | Medium | 依赖 `AUTOINST` 连接结果 |
| `AUTOOUTPUT` | Full first | submodule connections | Medium | 依赖 `AUTOINST` 连接结果 |
| `AUTOINOUT` | Full first | submodule connections | Medium | 依赖 `AUTOINST` 连接结果 |
| `AUTOWIRE` | Full first | current decls + submodule outputs | Medium | 避免重复声明已生成 output/inout |
| `AUTOLOGIC` | Full first | same as `AUTOWIRE` | Medium | 以 logic 生成 |
| `AUTOREG` | Partial first | current outputs | Medium | 复杂 always 赋值分析后续补 |
| `AUTOREGINPUT` | Partial first | submodule inputs | Medium | assignment 排除逻辑后续补 |
| `AUTOOUTPUTEVERY` | Partial first | current signals | Medium | 当前基于顶层 signal 声明 |
| `AUTOINOUTMODULE` | Full first | target module ports | Medium | 从指定模块复制 IO |
| `AUTOINOUTCOMP` | Full first | target module ports | Medium | input/output 方向反转 |
| `AUTOINOUTIN` | Full first | target module ports | Medium | 全部生成为 input |
| `AUTOINOUTPARAM` | Full first | target module params | Medium | 复制参数名，不复制默认值 |
| `AUTOINOUTMODPORT` | Full first | interface/modport info | Medium-high | 依赖 `sv_parser.py` 的 interface 支持 |
| `AUTOASSIGNMODPORT` | Full first | interface/modport info | Medium-high | 生成 modport assign |
| `AUTOTIEOFF` | Partial first | current outputs + submodule outputs | Medium | 宽度常量、active-low 后续补 |
| `AUTOUNUSED` | Partial first | current inputs/inouts + submodule use | Medium | 表达式真实使用分析后续补 |
| `AUTOUNDEF` | Full first | text scan | Low | 扫描 `define/undef` |
| `AUTOSENSE` / `AS` | Partial | process block scan | High | 后续应改为 verible AST 读写分析 |
| `AUTORESET` | Planned | process block AST | High | reset 值、宽度、blocking/nonblocking 复杂 |
| `AUTO_TEMPLATE` exact names | Planned | template parser | High | P3 |
| `AUTO_TEMPLATE` regexp | Planned | template parser | High | P3 |
| `AUTO_TEMPLATE` `@` and `[]` | Planned | template engine | High | P3 |
| Template Lisp `@"(...)"` | Unsupported by default | Elisp runtime | Very High | 不执行 Elisp；可考虑小型表达式子集 |
| `AUTOINSERTLISP` / `AUTOINSERTLAST` | Unsupported | Elisp runtime | Very High | 不执行 Elisp |

Status meaning:

- `Full first`: 先实现工程常用语义，后续用 golden tests 收敛细节。
- `Partial first`: 有基础实现，但需要更多真实用例完善。
- `Planned`: 需要单独阶段实现。
- `Unsupported`: 和“不调用 Emacs/不执行 Elisp”的目标冲突。

## AUTO Expansion Order

目标顺序参考 `verilog-mode.el`：

1. delete existing generated blocks
2. `AUTOINSERTLISP` skipped
3. `AUTOINSTPARAM`
4. `AUTOINST`
5. `.*`
6. `AUTOINOUTMODPORT`
7. `AUTOINOUTMODULE`
8. `AUTOINOUTCOMP`
9. `AUTOINOUTIN`
10. `AUTOINOUTPARAM`
11. `AUTOOUTPUT`
12. `AUTOINPUT`
13. `AUTOINOUT`
14. `AUTOTIEOFF`
15. `AUTOUNDEF`
16. `AUTOASSIGNMODPORT`
17. `AUTOLOGIC`
18. `AUTOWIRE`
19. `AUTOREG`
20. `AUTOREGINPUT`
21. `AUTOOUTPUTEVERY`
22. `AUTOSENSE` / `AS`
23. `AUTORESET`
24. `AUTOUNUSED`
25. `AUTOARG`
26. `AUTOINSERTLAST` skipped

## Test Assets

当前可作为 golden tests 的目录：

```text
test/emacs/
test/emacs_verilog/
```

`test/emacs/template.sv` 覆盖：

- `AUTOINST`
- `AUTOWIRE`
- `AUTOREG`
- instance formatting
- `AUTO_TEMPLATE` 注释形态

`test/emacs_verilog/src/top_ori*.v` 覆盖：

- lowercase auto marker，例如 `/*autoarg*/`
- `AUTOINPUT`
- `AUTOOUTPUT`
- `AUTOWIRE`
- `AUTOINST`
- `AUTOINSTPARAM`
- `AUTO_TEMPLATE`
- regexp template
- instance-number template
- template Lisp-like expression
- `verilog-library-directories`
- `verilog-auto-inst-param-value`

已新增测试结构：

```text
test/golden/<case_name>/input.sv
test/golden/<case_name>/expected_auto.sv
test/golden/<case_name>/expected_delete.sv
```

每个 case 验证：

```bash
python3 verilog-mode.py verilog-batch-auto input.sv
diff input.sv expected_auto.sv
python3 verilog-mode.py verilog-batch-delete-auto input.sv
diff input.sv expected_delete.sv
```

当前已生成 `test/golden/run_golden.py`，可执行：

```bash
python3 test/golden/run_golden.py
```

已生成的首批 golden cases：

| Case | Coverage |
|---|---|
| `autoinst_basic` | 基础 `AUTOINST`、端口方向分组、delete 恢复 marker |
| `star_autosense` | `.*` 显式展开、`AUTOSENSE` 基础 always 敏感列表、delete 恢复 |
| `auto_declarations` | `AUTOARG`、`AUTOINPUT`、`AUTOOUTPUT`、`AUTOINOUT`、`AUTOWIRE`、`AUTOINST` |
| `inout_stub` | `AUTOINOUTPARAM`、`AUTOINOUTMODULE`、`AUTOTIEOFF`、`AUTOUNUSED`、`AUTOUNDEF` |
| `modport_assign` | `AUTOINOUTMODPORT`、`AUTOASSIGNMODPORT` interface/modport 行为 |

## Roadmap

### Phase 0: Freeze Scope

Deliverables:

- This compatibility matrix.
- Explicit unsupported list.
- Batch CLI fixed to only two commands.

Acceptance:

- Any new AUTO support must update this file and golden tests.

### Phase 1: Test Harness

Deliverables:

- A Python or Makefile runner for golden tests.
- Cases copied from `test/emacs` and `test/emacs_verilog`.
- Auto/delete/auto stability checks.

Acceptance:

- `auto -> delete -> auto` is deterministic.
- No generated block duplicates.

### Phase 2: Core Instance Connectivity

Features:

- `AUTOINST`
- `AUTOINSTPARAM`
- `.*`
- module lookup
- manual connection skip
- vector preservation

Acceptance:

- `test/emacs/template.sv` passes non-template baseline.
- `test/emacs_verilog/src/top_ori.v` passes once basic template support is available.

### Phase 3: Declaration Generation

Features:

- `AUTOARG`
- `AUTOINPUT`
- `AUTOOUTPUT`
- `AUTOINOUT`
- `AUTOWIRE`
- `AUTOLOGIC`
- `AUTOREG`
- `AUTOREGINPUT`
- `AUTOOUTPUTEVERY`

Acceptance:

- Generated declarations do not duplicate existing ports/signals.
- Re-running batch-auto produces no diff.

### Phase 4: Module and Interface Copy Helpers

Features:

- `AUTOINOUTMODULE`
- `AUTOINOUTCOMP`
- `AUTOINOUTIN`
- `AUTOINOUTPARAM`
- `AUTOINOUTMODPORT`
- `AUTOASSIGNMODPORT`
- `AUTOTIEOFF`
- `AUTOUNUSED`
- `AUTOUNDEF`

Acceptance:

- Stub/shell module cases pass.
- Interface modport cases pass.

### Phase 5: Template Engine

Features:

- exact `AUTO_TEMPLATE`
- regexp `AUTO_TEMPLATE`
- `@` instance-number replacement
- `[]` / `[][]` bus replacement
- `AUTONOHOOKUP` recognition

Acceptance:

- `test/emacs_verilog/src/top_ori2.v`
- `test/emacs_verilog/src/top_ori3.v`
- `test/emacs_verilog/src/top_ori4.v`
- `test/emacs_verilog/src/top_ori5.v`

pass expected outputs.

### Phase 6: Process Block Analysis

Features:

- robust `AUTOSENSE` / `AS`
- `AUTORESET`

Implementation note:

- Prefer verible AST traversal over regex.
- Track RHS reads, LHS writes, temps, params, localparams, memories.

Acceptance:

- always block test cases with if/case/for/function-call/nested begin/end pass.

### Phase 7: Explicitly Decide Elisp Features

Features:

- `AUTOINSERTLISP`
- `AUTOINSERTLAST`
- template Lisp expression `@"(...)"`
- hooks/local eval

Recommendation:

- Keep unsupported by default.
- If needed, implement a restricted Python expression subset, not arbitrary Elisp.

## Immediate Next Steps

1. Implement `verilog-mode.py` from the simplest passing target: `test/golden/autoinst_basic`.
2. Add parser/text sanitizer so AUTO intermediate states such as `/*AUTOSENSE*/` and `.*` can be analyzed without calling Emacs.
3. Bring up declaration generation against `test/golden/auto_declarations`.
4. Bring up interface/stub helpers against `test/golden/inout_stub` and `test/golden/modport_assign`.
5. Convert `test/emacs/template.sv` and `test/emacs_verilog/src/top_ori*.v` into stricter golden cases after the Phase 5 template engine exists.
6. Only after template tests pass, refine process-block features like `AUTOSENSE` and `AUTORESET`.
