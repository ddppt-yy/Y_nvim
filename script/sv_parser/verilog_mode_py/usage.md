# ex.el Usage

`ex.el` 是基于 `verilog-mode.el` 的 batch 报告脚本，用来输出输入 Verilog/SystemVerilog 文件中的模块、实例、自动连接、普通实例连接以及未连接端口信息。

## 基本用法

```sh
emacs -Q --batch -l ./ex.el -f vm-dump-auto-cli -- top.sv auto_report.json
```

带 library path / libext：

```sh
emacs -Q --batch -l ./ex.el -f vm-dump-auto-cli -- top.sv auto_report.json -y rtl +libext+.v+.sv
```

剩余参数会追加到 `verilog-library-flags`，用于解析 submodule 的 file path 和端口定义。

## 输出文件

执行 `vm-dump-auto` / `vm-dump-auto-cli` 时默认会生成四份报告：

| 文件            | 位置                                      | 含义                                                    |
| --------------- | ----------------------------------------- | ------------------------------------------------------- |
| JSON 输出文件   | 命令行第二个参数指定的位置                | 机器可读的完整连接报告。                                |
| `signal_inner.txt` | 与 JSON 输出文件同目录                | 内部 submodule 之间的互联 `logic` 和 interface 声明。   |
| `signal_ex.txt` | 与 JSON 输出文件同目录                    | 对外/单端点的 `logic` 和 interface 声明。                |
| `unconnect.txt` | 与 JSON 输出文件同目录                    | 按具体 instance 列出的未连接 port/interface。           |

当 JSON 输出参数为 `-` 或省略时，`signal_inner.txt`、`signal_ex.txt` 和 `unconnect.txt` 会写到当前 `default-directory`。

如只需要 JSON，可在调用前关闭：

```elisp
(setq vm-auto-report-write-text-files nil)
```

## `signal_inner.txt` / `signal_ex.txt`

两个文件都按当前输入文件中的每个 design unit 分组，结构一致，但内容按信号范围拆开：

| 段落                                            | 含义                                                                                 |
| ----------------------------------------------- | ------------------------------------------------------------------------------------ |
| `Internal logic interconnect declarations` / `External logic interconnect declarations` | 从 `instances[].connections` 汇总出的普通端口互联信号声明。多端点互联进 `signal_inner.txt`，单端点/对外信号进 `signal_ex.txt`。 |
| `Internal interface interconnect declarations` / `External interface interconnect declarations` | 从 interface port 连接汇总出的 interface 实例声明。多端点 interface 进 `signal_inner.txt`，单端点/对外 interface 进 `signal_ex.txt`。 |
| `Connections that were not converted to declarations` | 不能安全转成声明的连接表达式，例如拼接、常量、函数调用或找不到定义的 `.*`。          |

声明宽度、`signed`、interface type 等信息来自被例化 submodule 的端口定义；同名信号会合并，注释里会标出 instance port 之间的连接关系。`logic` 会尽量按方向输出 `from ... to ...`，interface 会输出 `connect ... with ...`。多端点信号写入 `signal_inner.txt`，单端点信号和难以稳定归类的复杂表达式默认写入 `signal_ex.txt`。`.*` 会尽量按 submodule 端口定义展开为同名连接后再进入声明列表。

示例：

```systemverilog
// Internal logic interconnect declarations
logic data;                                      // from u_prod.data_o to u_cons.data_i

// Internal interface interconnect declarations
axi_if m_axi ();                                 // connect u_master.m_axi with u_slave.m_axi
```

`signal_ex.txt` 里通常会看到这种单端点形式：

```systemverilog
// External logic interconnect declarations
logic clk;                                       // to u_child.clk

// External interface interconnect declarations
link_if bus ();                                  // connect u_child.bus
```

## `unconnect.txt`

`unconnect.txt` 只列出存在未连接 port/interface 的 instance。每个条目包含父 module、具体 instance、submodule file path、连接来源和未连接列表。

| 字段       | 含义                                                         |
| ---------- | ------------------------------------------------------------ |
| `Module`   | 当前父级 design unit。                                       |
| `Instance` | 被例化的 submodule 名称和 instance 名称。                    |
| `File`     | 被例化 submodule 的定义文件；解析失败时为 `UNRESOLVED`。     |
| `Source`   | 当前实例来源：`manual`、`autoinst` 或 `dot-star`。           |
| 列表列 1   | 未连接端口方向，例如 `input`、`output`、`inout`、`interface`。 |
| 列表列 2   | 未连接 port/interface 名称。                                 |
| 列表列 3   | 未连接原因：`empty` 表示 `.port()`，`omitted` 表示完全没写。 |
| 列表列 4   | 端口类型摘要，包括 type、signed、位宽、array、modport。      |

示例：

```text
Module   : top
Instance : child u_child
File     : /path/to/child.sv
Source   : manual
Unconnected ports:
  input      b                        empty    logic
  interface  bus                      omitted  ifc
```

## 顶层 JSON

```json
{
  "source_file": "...",
  "ran_verilog_auto": true,
  "library_flags": [],
  "modules": []
}
```

| Key                | Type          | 含义                                                                                 |
| ------------------ | ------------- | ------------------------------------------------------------------------------------ |
| `source_file`      | string        | 输入文件的绝对路径。                                                                 |
| `ran_verilog_auto` | boolean       | 是否在生成报告前运行了 `verilog-auto`。当前默认是 `true`。                           |
| `library_flags`    | array[string] | 实际使用的 `verilog-library-flags`。影响 submodule 查找、`-y`、`-v`、`+libext+` 等。 |
| `modules`          | array[object] | 输入文件中识别到的 `module/interface/program/connectmodule` 列表。                   |

## `modules[]`

```json
{
  "name": "top",
  "type": "module",
  "location": {},
  "auto_signals": {},
  "submodules": [],
  "instances": []
}
```

| Key            | Type          | 含义                                                                                   |
| -------------- | ------------- | -------------------------------------------------------------------------------------- |
| `name`         | string        | 当前 design unit 名称。                                                                |
| `type`         | string        | design unit 类型，例如 `module`、`interface`、`program`、`connectmodule`。             |
| `location`     | object        | 当前 design unit 在输入文件中的位置。                                                  |
| `auto_signals` | object        | 从 AUTOINST 自动连接中聚合得到的信号集合。                                             |
| `submodules`   | array[object] | 只包含 `/*AUTOINST*/` 或 `.*` 自动连接实例的报告。                                     |
| `instances`    | array[object] | 普通实例扫描结果，包含手写实例和自动实例。通常这是看完整实例连接关系时优先使用的字段。 |

## `location`

```json
{
  "line": 10,
  "column": 3
}
```

| Key      | Type   | 含义           |
| -------- | ------ | -------------- |
| `line`   | number | 1-based 行号。 |
| `column` | number | 0-based 列号。 |

## `auto_signals`

```json
{
  "outputs": [],
  "inputs": [],
  "inouts": [],
  "interfaces": [],
  "interfaced": []
}
```

| Key          | Type          | 含义                                               |
| ------------ | ------------- | -------------------------------------------------- |
| `outputs`    | array[signal] | AUTOINST 子实例输出驱动到当前 module 的信号。      |
| `inputs`     | array[signal] | 当前 module 驱动到 AUTOINST 子实例输入的信号。     |
| `inouts`     | array[signal] | AUTOINST 子实例 inout 相关信号。                   |
| `interfaces` | array[signal] | AUTOINST 子实例 interface port 连接信号。          |
| `interfaced` | array[signal] | interface 内部被 `Interfaced` 段识别到的连接信号。 |

这些列表来自 `verilog-read-sub-decls`，主要反映 verilog-mode 能从 AUTOINST 展开结果中识别到的自动连接。

## `signal`

`auto_signals` 中的元素使用 signal 结构：

```json
{
  "direction": "input",
  "name": "clk",
  "bits": null,
  "multidim": null,
  "memory": null,
  "signed": null,
  "type": "logic",
  "modport": null,
  "comment": "To u_sub of sub.v"
}
```

| Key         | Type         | 含义                                                                         |
| ----------- | ------------ | ---------------------------------------------------------------------------- |
| `direction` | string       | 信号方向：`input`、`output`、`inout`、`interface`、`interfaced`。            |
| `name`      | string       | 信号名。                                                                     |
| `bits`      | string/null  | packed 位宽，例如 `[7:0]`。没有位宽时为 `null`。                             |
| `multidim`  | string/null  | 多维 packed 维度补充信息。                                                   |
| `memory`    | string/null  | unpacked array / memory 维度。                                               |
| `signed`    | boolean/null | 是否 signed。不是 signed 时通常为 `null`。                                   |
| `type`      | string/null  | 数据类型或 interface 类型，例如 `logic`、`wire`、`my_if`。                   |
| `modport`   | string/null  | interface modport 名，例如 `master`。非 interface 或无 modport 时为 `null`。 |
| `comment`   | string/null  | verilog-mode 生成的来源说明，例如 `From u_sub of sub.v`。                    |

## `submodules[]`

`submodules` 只记录 AUTOINST / `.*` 相关实例，适合看 verilog-mode 自动连接结果。

```json
{
  "module": "child",
  "instance": "u_child",
  "file": "/abs/path/child.sv",
  "definition_type": "module",
  "marker": "AUTOINST",
  "location": {},
  "connections": []
}
```

| Key               | Type              | 含义                                                        |
| ----------------- | ----------------- | ----------------------------------------------------------- |
| `module`          | string            | 被例化的 submodule/interface 名。                           |
| `instance`        | string            | 实例名。                                                    |
| `file`            | string/null       | submodule 定义所在文件路径。查找失败时为 `null`。           |
| `definition_type` | string/null       | 定义类型，例如 `module`、`interface`。查找失败时为 `null`。 |
| `marker`          | string            | 自动连接标记类型：`AUTOINST` 或 `dot-star`。                |
| `location`        | object            | AUTOINST / `.*` 标记所在位置。                              |
| `connections`     | array[connection] | AUTOINST 展开出来的端口连接。                               |

## `instances[]`

`instances` 是普通实例扫描结果，包含手写实例和自动实例。完整连接关系建议看这个字段。

```json
{
  "module": "child",
  "instance": "u_child",
  "file": "/abs/path/child.sv",
  "definition_type": "module",
  "source": "manual",
  "location": {},
  "connections": [],
  "unconnected_ports": []
}
```

| Key                 | Type                    | 含义                                                   |
| ------------------- | ----------------------- | ------------------------------------------------------ |
| `module`            | string                  | 被例化的 cell/module/interface 名。                    |
| `instance`          | string                  | 实例名。                                               |
| `file`              | string/null             | 被例化对象的定义文件路径。查找失败时为 `null`。        |
| `definition_type`   | string/null             | 定义类型，例如 `module`、`interface`。                 |
| `source`            | string                  | 实例连接来源：`manual`、`autoinst`、`dot-star`。       |
| `location`          | object                  | 实例名所在位置。                                       |
| `connections`       | array[connection]       | 当前实例中实际写出的端口连接。                         |
| `unconnected_ports` | array[unconnected_port] | submodule 定义中存在、但当前实例未连接或空连接的端口。 |

### `source`

| Value      | 含义                                      |
| ---------- | ----------------------------------------- |
| `manual`   | 手写实例连接，没有 AUTOINST / `.*` 标记。 |
| `autoinst` | 实例端口列表中包含 `/*AUTOINST*/`。       |
| `dot-star` | 实例端口列表中包含 `.*`。                 |

## `connection`

`connections` 表示实例中已经写出的连接。

```json
{
  "style": "named",
  "direction": "input",
  "port": "clk",
  "expr": "clk_i",
  "bits": null,
  "multidim": null,
  "memory": null,
  "signed": null,
  "type": "logic",
  "modport": null
}
```

| Key         | Type         | 含义                                                                                  |
| ----------- | ------------ | ------------------------------------------------------------------------------------- |
| `style`     | string/null  | 连接风格。`instances[].connections` 中一定有；`submodules[].connections` 中通常没有。 |
| `index`     | number       | ordered port 连接的序号，仅 `style: "ordered"` 时出现。                               |
| `direction` | string/null  | submodule 端口方向。需要能解析到 submodule 定义。                                     |
| `port`      | string/null  | submodule 端口名。ordered 且无法推断端口名时可能为 `null`。未展开的原始 `.*` 为 `"*"`。 |
| `expr`      | string       | 连接表达式。空连接 `.foo()` 会是空字符串 `""`。                                       |
| `bits`      | string/null  | submodule 端口 packed 位宽。                                                          |
| `multidim`  | string/null  | submodule 端口多维 packed 维度。                                                      |
| `memory`    | string/null  | submodule 端口 unpacked 维度。                                                        |
| `signed`    | boolean/null | submodule 端口是否 signed。                                                           |
| `type`      | string/null  | submodule 端口类型或 interface 类型。                                                 |
| `modport`   | string/null  | submodule interface port 的 modport。                                                 |

### `style`

| Value      | 示例          | 含义                                                            |
| ---------- | ------------- | --------------------------------------------------------------- |
| `named`    | `.clk(clk_i)` | 显式 named port 连接。                                          |
| `dot-name` | `.clk`        | SystemVerilog dot-name 连接，等价于 `.clk(clk)`。               |
| `ordered`  | `(a, b, y)`   | ordered port 连接。脚本会尽量按 submodule 端口顺序补出 `port`。 |
| `dot-star` | `.*`          | SystemVerilog implicit all connection；能解析 submodule 时会展开成逐 port 的同名连接。 |

## `unconnected_ports`

`unconnected_ports` 表示 submodule 定义里有，但当前实例没有有效连接的端口，包括普通 port 和 interface port。

```json
{
  "direction": "interface",
  "port": "bus",
  "name": "bus",
  "reason": "omitted",
  "bits": null,
  "multidim": null,
  "memory": null,
  "signed": null,
  "type": "ifc",
  "modport": null
}
```

| Key         | Type         | 含义                                                      |
| ----------- | ------------ | --------------------------------------------------------- |
| `direction` | string       | 未连接端口方向：`input`、`output`、`inout`、`interface`。 |
| `port`      | string       | submodule 端口名。                                        |
| `name`      | string       | 与 `port` 相同，保留为 signal 结构兼容字段。              |
| `reason`    | string       | 未连接原因：`empty` 或 `omitted`。                        |
| `bits`      | string/null  | submodule 端口 packed 位宽。                              |
| `multidim`  | string/null  | submodule 端口多维 packed 维度。                          |
| `memory`    | string/null  | submodule 端口 unpacked 维度。                            |
| `signed`    | boolean/null | submodule 端口是否 signed。                               |
| `type`      | string/null  | submodule 端口类型或 interface 类型。                     |
| `modport`   | string/null  | submodule interface port 的 modport。                     |

### `reason`

| Value     | 示例                                           | 含义                                   |
| --------- | ---------------------------------------------- | -------------------------------------- |
| `empty`   | `.b()` 或 ordered 里的空项 `(a, , y)`          | 端口被写出，但连接表达式为空。         |
| `omitted` | submodule 有 `ifc bus`，实例里没有 `.bus(...)` | 端口完全没有在当前实例连接列表里出现。 |

## `null` 和空数组

| 表示   | 含义                                                                            |
| ------ | ------------------------------------------------------------------------------- |
| `null` | 当前字段无法解析、不存在，或 submodule 定义未找到。                             |
| `[]`   | 成功解析，但没有对应条目。例如 `unconnected_ports: []` 表示没有发现未连接端口。 |

## 重要限制

- 这不是 elaborator，不会展开 generate、宏条件、参数化层级后的真实硬件层次。
- `file` 和方向/type 信息依赖 `verilog-library-flags` 能找到 submodule 定义。
- `.*` 会尽量根据 submodule 端口定义展开为同名连接；但脚本不会做完整 elaboration，也不会严格验证父级作用域里是否已有同名声明。
- ordered port 的 `port` 名是 best-effort，由 submodule header 端口顺序推断；复杂 header 可能不完全准确。
- `submodules` 只看 AUTOINST / `.*`；完整实例列表请看 `instances`。
