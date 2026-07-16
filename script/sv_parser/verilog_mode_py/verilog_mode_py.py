#!/usr/bin/env python3
"""Pure Python Verilog/SystemVerilog AUTO expansion tool.

Single-file version of verilog_mode_py package.

Usage:
    python3 verilog_mode_py.py verilog-batch-auto <file.sv>
    python3 verilog_mode_py.py verilog-batch-delete-auto <file.sv>
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from re import Match, Pattern

# -- Gate Primitives Data --------------------------------------------------

GATE_IOS: dict[str, tuple[str, ...]] = {
    # Remaining positional arguments default to input.
    "and": ("output",),
    "buf": ("output",),
    "bufif0": ("output",),
    "bufif1": ("output",),
    "cmos": ("output",),
    "nand": ("output",),
    "nmos": ("output",),
    "nor": ("output",),
    "not": ("output",),
    "notif0": ("output",),
    "notif1": ("output",),
    "or": ("output",),
    "pmos": ("output",),
    "pulldown": ("output",),
    "pullup": ("output",),
    "rcmos": ("output",),
    "rnmos": ("output",),
    "rpmos": ("output",),
    "rtran": ("inout", "inout"),
    "rtranif0": ("inout", "inout"),
    "rtranif1": ("inout", "inout"),
    "tran": ("inout", "inout"),
    "tranif0": ("inout", "inout"),
    "tranif1": ("inout", "inout"),
    "xnor": ("output",),
    "xor": ("output",),
}

GATE_PRIMITIVES = frozenset(GATE_IOS)

# -- Data Models --------------------------------------------------

from dataclasses import dataclass, field

@dataclass(frozen=True)
class Port:
    name: str
    direction: str = ""
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
    unpacked: str = ""
    kind: str = "parameter"

@dataclass(frozen=True)
class Instance:
    module: str
    name: str
    start: int
    end: int
    port_open: int
    port_close: int
    param_open: int | None = None
    param_close: int | None = None

@dataclass
class ModuleInfo:
    name: str
    kind: str = "module"
    ports: list[Port] = field(default_factory=list)
    params: list[Param] = field(default_factory=list)
    signals: list[Port] = field(default_factory=list)
    interface_ports: dict[str, Port] = field(default_factory=dict)
    modports: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    instances: list[Instance] = field(default_factory=list)
    source_path: Path | None = None
    start: int = 0
    end: int = 0
    header_end: int = 0
    header_port_open: int | None = None
    header_port_close: int | None = None

    def declared_names(self) -> set[str]:
        return (
            {port.name for port in self.ports}
            | {signal.name for signal in self.signals}
            | {param.name for param in self.params}
        )

# -- Syntax Utilities --------------------------------------------------

from collections.abc import Iterator
from contextlib import contextmanager

IDENT_RE = re.compile(r"\\\S+|`[A-Za-z_][$A-Za-z0-9_]*|[A-Za-z_][$A-Za-z0-9_]*")

def mask_syntax(text: str, *, keep_newlines: bool = True) -> str:
    """Replace comments, strings, and attributes with spaces, preserving offsets."""
    chars = list(text)
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = i
            while j < n and text[j] != "\n":
                chars[j] = " "
                j += 1
            i = j
            continue
        if ch == "/" and nxt == "*":
            j = i
            while j + 1 < n and not (text[j] == "*" and text[j + 1] == "/"):
                if not (keep_newlines and text[j] == "\n"):
                    chars[j] = " "
                j += 1
            if j + 1 < n:
                chars[j] = " "
                chars[j + 1] = " "
                j += 2
            i = j
            continue
        if ch == '"':
            quote = ch
            j = i
            chars[j] = " "
            j += 1
            while j < n:
                if not (keep_newlines and text[j] == "\n"):
                    chars[j] = " "
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            i = j
            continue
        if ch == "(" and nxt == "*" and previous_nonspace(text, i) != "@":
            j = i
            while j + 1 < n and not (text[j] == "*" and text[j + 1] == ")"):
                if not (keep_newlines and text[j] == "\n"):
                    chars[j] = " "
                j += 1
            if j + 1 < n:
                chars[j] = " "
                chars[j + 1] = " "
                j += 2
            i = j
            continue
        i += 1
    return "".join(chars)

def skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos

def previous_nonspace(text: str, pos: int) -> str:
    pos -= 1
    while pos >= 0 and text[pos].isspace():
        pos -= 1
    return text[pos] if pos >= 0 else ""

def find_matching(text: str, open_pos: int) -> int | None:
    pairs = {"(": ")", "[": "]", "{": "}"}
    open_ch = text[open_pos]
    close_ch = pairs.get(open_ch)
    if close_ch is None:
        return None
    masked = mask_syntax(text)
    depth = 0
    for pos in range(open_pos, len(text)):
        ch = masked[pos]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return pos
    return None

def find_matching_before(text: str, close_pos: int) -> int | None:
    pairs = {")": "(", "]": "[", "}": "{"}
    close_ch = text[close_pos]
    open_ch = pairs.get(close_ch)
    if open_ch is None:
        return None
    masked = mask_syntax(text)
    depth = 0
    for pos in range(close_pos, -1, -1):
        ch = masked[pos]
        if ch == close_ch:
            depth += 1
        elif ch == open_ch:
            depth -= 1
            if depth == 0:
                return pos
    return None

def find_top_level_semicolon(text: str, start: int) -> int | None:
    masked = mask_syntax(text)
    paren = bracket = brace = 0
    for pos in range(start, len(text)):
        ch = masked[pos]
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == ";" and paren == 0 and bracket == 0 and brace == 0:
            return pos
    return None

def split_top_level(text: str, sep: str = ",") -> list[str]:
    masked = mask_syntax(text)
    parts: list[str] = []
    start = 0
    paren = bracket = brace = 0
    for pos, ch in enumerate(masked):
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == sep and paren == 0 and bracket == 0 and brace == 0:
            parts.append(text[start:pos])
            start = pos + 1
    parts.append(text[start:])
    return parts

def iter_bracketed_ranges(text: str) -> list[tuple[int, int, str]]:
    masked = mask_syntax(text, keep_newlines=False)
    ranges: list[tuple[int, int, str]] = []
    pos = 0
    while pos < len(masked):
        if masked[pos] != "[":
            pos += 1
            continue
        close = find_matching(text, pos)
        if close is None:
            pos += 1
            continue
        ranges.append((pos, close + 1, text[pos : close + 1].strip()))
        pos = close + 1
    return ranges

def split_bracketed_dims(text: str) -> list[str]:
    return [dim for _, _, dim in iter_bracketed_ranges(text)]

def is_only_bracketed_dims(text: str) -> bool:
    if not text.strip():
        return False
    chars = list(mask_syntax(text, keep_newlines=False))
    for start, end, _ in iter_bracketed_ranges(text):
        chars[start:end] = " " * (end - start)
    return not "".join(chars).strip()

def split_statements(text: str) -> list[tuple[int, int, str]]:
    masked = mask_syntax(text)
    result: list[tuple[int, int, str]] = []
    start = 0
    paren = bracket = brace = 0
    for pos, ch in enumerate(masked):
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == ";" and paren == 0 and bracket == 0 and brace == 0:
            result.append((start, pos + 1, text[start : pos + 1]))
            start = pos + 1
    return result

def strip_top_level_assignment(text: str) -> tuple[str, str]:
    masked = mask_syntax(text)
    paren = bracket = brace = 0
    for pos, ch in enumerate(masked):
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == "=" and paren == 0 and bracket == 0 and brace == 0:
            return text[:pos].strip(), text[pos + 1 :].strip()
    return text.strip(), ""

def line_start(text: str, pos: int) -> int:
    return text.rfind("\n", 0, pos) + 1

def line_end(text: str, pos: int) -> int:
    end = text.find("\n", pos)
    return len(text) if end == -1 else end

def line_indent_at(text: str, pos: int) -> str:
    start = line_start(text, pos)
    end = start
    while end < len(text) and text[end] in " \t":
        end += 1
    return text[start:end]

def find_port_close_after_marker(text: str, marker_end: int) -> int | None:
    masked = mask_syntax(text)
    depth = 0
    for pos in range(marker_end, len(text)):
        ch = masked[pos]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return pos
            depth -= 1
    return None

@contextmanager
def saved_match_data() -> Iterator[None]:
    """Compatibility placeholder for code that mirrors Emacs-style scanners."""
    yield

def normalize_space(text: str) -> str:
    return " ".join(text.strip().split())

def iter_identifiers(text: str) -> Iterator[str]:
    masked = mask_syntax(text)
    for match in IDENT_RE.finditer(masked):
        yield text[match.start() : match.end()]

# -- Text Buffer --------------------------------------------------

from contextlib import contextmanager
from dataclasses import dataclass
from re import Match, Pattern
from typing import Iterator

@dataclass
class TextBuffer:
    text: str
    pos: int = 0
    last_match: Match[str] | None = None

    def goto(self, pos: int) -> None:
        self.pos = max(0, min(len(self.text), pos))

    @contextmanager
    def save_pos(self) -> Iterator[None]:
        old_pos = self.pos
        old_match = self.last_match
        try:
            yield
        finally:
            self.pos = old_pos
            self.last_match = old_match

    def looking_at(self, pattern: str | Pattern[str]) -> bool:
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.last_match = regex.match(self.text, self.pos)
        return self.last_match is not None

    def search_forward(self, pattern: str | Pattern[str]) -> int | None:
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.last_match = regex.search(self.text, self.pos)
        if self.last_match is None:
            return None
        self.pos = self.last_match.end()
        return self.last_match.start()

    def insert(self, pos: int, value: str) -> None:
        self.text = self.text[:pos] + value + self.text[pos:]
        if self.pos >= pos:
            self.pos += len(value)

    def delete(self, start: int, end: int) -> None:
        self.text = self.text[:start] + self.text[end:]
        if self.pos > end:
            self.pos -= end - start
        elif self.pos > start:
            self.pos = start

    def replace(self, start: int, end: int, value: str) -> None:
        self.delete(start, end)
        self.insert(start, value)

    def line_bounds(self, pos: int) -> tuple[int, int]:
        return line_start(self.text, pos), line_end(self.text, pos)

    def line_indent(self, pos: int) -> str:
        return line_indent_at(self.text, pos)

    def column(self, pos: int) -> int:
        return pos - line_start(self.text, pos)

# -- Formatter --------------------------------------------------

GROUP_TITLES = {
    "output": "Outputs",
    "inout": "Inouts",
    "input": "Inputs",
    "interface": "Interfaces",
}

def direction_groups(ports: list[Port]) -> list[tuple[str, list[Port]]]:
    return [
        (
            "interface",
            [port for port in ports if not port.direction and port.interface_type],
        )
    ] + [
        (direction, [port for port in ports if port.direction == direction])
        for direction in ("output", "inout", "input")
    ]

def declaration_prefix(port: Port) -> str:
    pieces = [port.direction]
    data_type = port.data_type.strip()
    if data_type and not (port.direction == "inout" and data_type == "wire"):
        pieces.append(data_type)
    if port.packed:
        pieces.append(port.packed)
    return " ".join(piece for piece in pieces if piece)

def format_identifier(name: str, *, terminator: str = "") -> str:
    if name.startswith("\\") and terminator:
        return f"{name} {terminator}"
    return f"{name}{terminator}"

def format_declaration(indent: str, port: Port, comment: str = "") -> str:
    prefix = declaration_prefix(port)
    suffix = f" {comment}" if comment else ""
    name = format_identifier(port.name, terminator="")
    terminator = format_identifier(port.name, terminator=";")[len(name) :]
    return f"{indent}{prefix:<28}{name}{port.unpacked}{terminator}{suffix}"

def format_parameter(indent: str, param: Param) -> str:
    prefix = "parameter"
    return f"{indent}{prefix:<28}{param.name};"

def port_actual(port: Port) -> str:
    if port.interface_type:
        return port.name
    if port.packed:
        return f"{port.name}{port.packed}"
    return port.name

def format_connection(indent: str, port: Port, actual: str, terminator: str) -> str:
    return f"{indent}.{port.name:<31}({actual}){terminator}"

# -- SV Parse --------------------------------------------------

DIRECTIONS = {"input", "output", "inout"}
DIRECTION_RE = re.compile(r"\b(?:input|output|inout)\b")
DATA_KEYWORDS = {
    "wire",
    "tri",
    "supply0",
    "supply1",
    "wand",
    "wor",
    "triand",
    "trior",
    "tri0",
    "tri1",
    "uwire",
    "reg",
    "logic",
    "bit",
    "byte",
    "shortint",
    "int",
    "longint",
    "integer",
    "time",
    "real",
    "realtime",
    "shortreal",
    "signed",
    "unsigned",
}
DIRECTIVE_LINE_RE = re.compile(
    r"(?m)^[ \t]*`(?:ifdef|ifndef|elsif|else|endif|define|undef|line)\b[^\n]*"
)
DEFINE_VALUE_RE = re.compile(
    r"^[ \t]*`define\s+([A-Za-z_][$A-Za-z0-9_]*)\s+(`?[A-Za-z_][$A-Za-z0-9_]*)",
    re.M,
)
INSTANCE_SKIP = DIRECTIONS | DATA_KEYWORDS | {
    "assign",
    "always",
    "always_comb",
    "always_ff",
    "always_latch",
    "begin",
    "case",
    "class",
    "covergroup",
    "else",
    "end",
    "endcase",
    "endclass",
    "endfunction",
    "endmodule",
    "endpackage",
    "endtask",
    "for",
    "foreach",
    "function",
    "generate",
    "genvar",
    "if",
    "import",
    "initial",
    "interface",
    "localparam",
    "module",
    "package",
    "parameter",
    "property",
    "return",
    "task",
    "typedef",
}

def _clean(text: str) -> str:
    return normalize_space(mask_syntax(text, keep_newlines=False))

def parse_defines(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in DEFINE_VALUE_RE.finditer(mask_syntax(text, keep_newlines=True))
    }

def _resolve_define_name(name: str, defines: dict[str, str]) -> str:
    key = name[1:] if name.startswith("`") else name
    value = defines.get(key)
    return value[1:] if value and value.startswith("`") else value or name

def _last_identifier(text: str) -> tuple[str, int, int] | None:
    matches = list(IDENT_RE.finditer(mask_syntax(text, keep_newlines=False)))
    if not matches:
        return None
    match = matches[-1]
    return text[match.start() : match.end()].strip(), match.start(), match.end()

def _strip_trailing_unpacked(text: str) -> tuple[str, str]:
    unpacked: list[str] = []
    work = text.rstrip()
    while work.endswith("]"):
        open_pos = work.rfind("[")
        if open_pos < 0:
            break
        dim = work[open_pos:].strip()
        unpacked.insert(0, dim)
        work = work[:open_pos].rstrip()
    return work, " ".join(unpacked)

def _extract_packed(prefix: str) -> tuple[str, str]:
    ranges = iter_bracketed_ranges(prefix)
    dims = [dim for _, _, dim in ranges]
    chars = list(prefix)
    for start, end, _ in ranges:
        chars[start:end] = " " * (end - start)
    no_dims = "".join(chars)
    return normalize_space(no_dims), " ".join(dim.strip() for dim in dims)

def parse_param_item(item: str) -> Param | None:
    item = item.strip().rstrip(",;")
    if not item:
        return None
    left, value = strip_top_level_assignment(item)
    kind_match = re.match(r"^\s*(parameter|localparam|genvar)\b", left)
    kind = kind_match.group(1) if kind_match is not None else "parameter"
    left = re.sub(r"^\s*(parameter|localparam|genvar)\b", "", left).strip()
    left = re.sub(r"^\s*type\b", "", left).strip()
    left = mask_syntax(left, keep_newlines=False).strip()
    left, unpacked = _strip_trailing_unpacked(left)
    ident = _last_identifier(left)
    if ident is None:
        return None
    name, start, _ = ident
    prefix = left[:start].strip()
    data_type, packed = _extract_packed(prefix)
    return Param(
        name=name,
        value=value,
        data_type=data_type,
        packed=packed,
        unpacked=unpacked,
        kind=kind,
    )

def parse_param_list(text: str) -> list[Param]:
    params: list[Param] = []
    data_type = ""
    packed = ""
    for item in split_top_level(text):
        starts_declaration = re.match(r"\s*(parameter|localparam|genvar)\b", item) is not None
        param = parse_param_item(item)
        if param is not None:
            if starts_declaration:
                data_type = param.data_type
                packed = param.packed
            elif param.data_type or param.packed:
                data_type = param.data_type
                packed = param.packed
            elif data_type or packed:
                param = Param(
                    name=param.name,
                    value=param.value,
                    data_type=data_type,
                    packed=packed,
                    unpacked=param.unpacked,
                    kind=param.kind,
                )
            params.append(param)
    return params

def parse_port_item(
    item: str,
    default_direction: str = "",
    default_type: str = "",
    default_packed: str = "",
) -> tuple[Port | None, str, str, str]:
    item = item.strip().rstrip(",;")
    if not item:
        return None, default_direction, default_type, default_packed
    left, _ = strip_top_level_assignment(item)
    left = re.sub(r"\(\*.*?\*\)", " ", left, flags=re.S).strip()
    left = DIRECTIVE_LINE_RE.sub(" ", left).strip()
    left, unpacked = _strip_trailing_unpacked(left)
    ident = _last_identifier(left)
    if ident is None:
        return None, default_direction, default_type, default_packed
    name, start, _ = ident
    prefix = _clean(left[:start])
    words = prefix.split()

    direction = default_direction
    explicit_direction = False
    if words and words[0] in DIRECTIONS:
        direction = words[0]
        words = words[1:]
        explicit_direction = True

    prefix_after_direction = " ".join(words)
    data_type, packed = _extract_packed(prefix_after_direction)
    interface_type: tuple[str, ...] = ()
    if (
        not explicit_direction
        and data_type
        and data_type.split()[0] not in DATA_KEYWORDS
    ):
        direction = ""
        interface_base = data_type.split("#", 1)[0].strip()
        pieces = interface_base.split(".")
        interface_type = tuple(piece for piece in pieces if piece)
    else:
        if not data_type and direction == default_direction and not explicit_direction:
            data_type = default_type
        if not packed and direction == default_direction and not explicit_direction:
            packed = default_packed
        if not direction and data_type and data_type.split()[0] not in DATA_KEYWORDS:
            interface_base = data_type.split("#", 1)[0].strip()
            pieces = interface_base.split(".")
            interface_type = tuple(piece for piece in pieces if piece)

    port = Port(
        name=name,
        direction=direction,
        data_type=data_type,
        packed=packed,
        unpacked=unpacked,
        interface_type=interface_type,
    )
    return port, direction, data_type, packed

def parse_port_items(text: str) -> list[Port]:
    ports: list[Port] = []
    direction = ""
    data_type = ""
    packed = ""
    items: list[str] = []
    for item in split_top_level(text):
        masked_item = mask_syntax(item)
        start = 0
        first_token = skip_ws(masked_item, 0)
        for match in DIRECTION_RE.finditer(masked_item):
            if match.start() == first_token:
                continue
            if masked_item[start : match.start()].strip():
                items.append(item[start : match.start()])
                start = match.start()
        items.append(item[start:])
    for item in items:
        port, direction, data_type, packed = parse_port_item(
            item, direction, data_type, packed
        )
        if port is not None:
            ports.append(port)
    return ports

def _strip_conditional_directive_lines(text: str) -> str:
    directive_re = re.compile(r"^\s*`(?:ifdef|ifndef|elsif|else|endif)\b")
    return "\n".join(
        line for line in text.splitlines() if directive_re.match(line) is None
    )

def parse_header(
    text: str, module_start: int
) -> tuple[list[Param], list[Port], list[str], int | None, int | None]:
    masked = mask_syntax(text)
    match = re.search(
        r"\b(?:module|interface)\b\s*(?:(" + IDENT_RE.pattern + r")\b)?",
        masked,
    )
    if match is None:
        return [], [], [], None, None
    idx = skip_ws(masked, match.end())
    params: list[Param] = []
    ports: list[Port] = []
    port_names: list[str] = []
    port_open_abs: int | None = None
    port_close_abs: int | None = None

    def skip_header_imports(pos: int) -> int:
        pos = skip_ws(masked, pos)
        while re.match(r"import\b", masked[pos:]):
            semicolon = find_top_level_semicolon(text, pos)
            if semicolon is None:
                break
            pos = skip_ws(masked, semicolon + 1)
        return pos

    idx = skip_header_imports(idx)
    if idx < len(masked) and masked[idx] == "#":
        idx = skip_ws(masked, idx + 1)
        if idx < len(masked) and masked[idx] == "(":
            close = find_matching(text, idx)
            if close is not None:
                params = parse_param_list(text[idx + 1 : close])
                idx = skip_ws(masked, close + 1)

    idx = skip_header_imports(idx)
    if idx < len(masked) and masked[idx] == "(":
        close = find_matching(text, idx)
        if close is not None:
            port_open_abs = module_start + idx
            port_close_abs = module_start + close
            port_text = text[idx + 1 : close]
            ports = parse_port_items(port_text)
            port_names = [port.name for port in ports]
            if not any(port.direction or port.interface_type for port in ports):
                ports = []
                port_names = []
                for item in split_top_level(port_text):
                    ident = _last_identifier(item)
                    if ident is not None:
                        port_names.append(ident[0])
    return params, ports, port_names, port_open_abs, port_close_abs

def parse_declaration_statement(statement: str) -> tuple[list[Port], list[Param]]:
    stripped = _strip_conditional_directive_lines(statement).strip().rstrip(";")
    if not stripped:
        return [], []
    masked = mask_syntax(stripped, keep_newlines=False)
    keyword_re = re.compile(
        r"\b("
        + "|".join(sorted(DIRECTIONS | DATA_KEYWORDS | {"parameter", "localparam", "genvar"}))
        + r")\b"
    )

    def parse_custom_signal(text: str) -> tuple[list[Port], list[Param]]:
        if "(" in text:
            return [], []
        head_text = mask_syntax(text, keep_newlines=False).strip()
        if not head_text:
            return [], []
        if head_text.split(None, 1)[0] in INSTANCE_SKIP:
            return [], []
        left, _ = strip_top_level_assignment(text)
        left, unpacked = _strip_trailing_unpacked(left)
        ident = _last_identifier(left)
        if ident is None:
            return [], []
        name, start, _ = ident
        prefix = left[:start].strip()
        if not prefix:
            return [], []
        data_type, packed = _extract_packed(prefix)
        return [
            Port(
                name=name,
                direction="",
                data_type=data_type,
                packed=packed,
                unpacked=unpacked,
            )
        ], []

    keyword_match = None
    for match in keyword_re.finditer(masked):
        if not masked[: match.start()].strip():
            keyword_match = match
            break
    if keyword_match is None:
        return parse_custom_signal(stripped)
    stripped = stripped[keyword_match.start() :].strip()
    first = stripped.split(None, 1)[0]
    if first in DIRECTIONS:
        return parse_port_items(stripped), []
    if first in DATA_KEYWORDS:
        ports = parse_port_items(stripped)
        signals = [
            Port(
                name=port.name,
                direction="",
                data_type=port.data_type or first,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
            for port in ports
        ]
        return signals, []
    if first in {"parameter", "localparam", "genvar"}:
        params = [param for param in parse_param_list(stripped) if param is not None]
        return [], params
    custom_ports, custom_params = parse_custom_signal(stripped)
    if custom_ports or custom_params:
        return custom_ports, custom_params
    return [], []

def order_ports_by_header(ports: list[Port], header_names: list[str]) -> list[Port]:
    if not header_names:
        return ports
    by_name = {port.name: port for port in ports}
    ordered = [by_name[name] for name in header_names if name in by_name]
    seen = {port.name for port in ordered}
    ordered.extend(port for port in ports if port.name not in seen)
    return ordered

def parse_body_declarations(body: str) -> tuple[list[Port], list[Param]]:
    ports: list[Port] = []
    params: list[Param] = []
    seen_ports: set[str] = set()
    for _, _, statement in split_statements(body):
        parsed_ports, parsed_params = parse_declaration_statement(statement)
        for port in parsed_ports:
            if port.name in seen_ports:
                continue
            ports.append(port)
            seen_ports.add(port.name)
        params.extend(parsed_params)
    return ports, params

def parse_clocking_blocks(body: str) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {}
    masked = mask_syntax(body)
    for match in re.finditer(r"\bclocking\s+(" + IDENT_RE.pattern + r")\b", masked):
        name = body[match.start(1) : match.end(1)].strip()
        end_match = re.search(r"\bendclocking\b", masked[match.end() :])
        if end_match is None:
            continue
        block = body[match.end() : match.end() + end_match.start()]
        entries: list[tuple[str, str]] = []
        for decl in re.finditer(
            r"\b(input|output|inout)\s+([^;\n]+)", mask_syntax(block)
        ):
            direction = decl.group(1)
            names_text = block[decl.start(2) : decl.end(2)]
            for item in split_top_level(names_text):
                ident = _last_identifier(item)
                if ident is not None:
                    entries.append((ident[0], f"clocking_{direction}"))
        result[name] = entries
    return result

def parse_modports(body: str) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {}
    masked = mask_syntax(body)
    clockings = parse_clocking_blocks(body)
    result.update(clockings)
    for match in re.finditer(r"\bmodport\s+(" + IDENT_RE.pattern + r")\s*\(", masked):
        name = body[match.start(1) : match.end(1)].strip()
        open_pos = match.end() - 1
        close = find_matching(body, open_pos)
        if close is None:
            continue
        entries: list[tuple[str, str]] = []
        for item in split_top_level(body[open_pos + 1 : close]):
            clean = _clean(item)
            if not clean:
                continue
            words = clean.split()
            if (
                len(words) >= 2
                and words[0] == "clocking"
                and words[1] in clockings
            ):
                entries.extend(clockings[words[1]])
                continue
            if not words or words[0] not in {"input", "output", "inout", "ref"}:
                continue
            direction = words[0]
            for signal in words[1:]:
                signal = signal.strip(",")
                if IDENT_RE.fullmatch(signal):
                    entries.append((signal, direction))
        result.setdefault(name, []).extend(entries)
    return result

def _skip_instance_arrays(text: str, masked: str, idx: int) -> tuple[int, bool]:
    while idx < len(masked) and masked[idx] == "[":
        close = find_matching(text, idx)
        if close is None:
            return idx, False
        idx = skip_ws(masked, close + 1)
    return idx, True

def parse_instances(module_text: str, absolute_start: int) -> list[Instance]:
    masked = mask_syntax(module_text)
    instances: list[Instance] = []
    pos = 0
    while True:
        match = IDENT_RE.search(masked, pos)
        if match is None:
            break
        module_name = module_text[match.start() : match.end()]
        pos = match.end()
        if module_name in INSTANCE_SKIP:
            continue
        if previous_nonspace(masked, match.start()) in {".", "`"}:
            continue
        idx = skip_ws(masked, match.end())
        param_open = param_close = None
        if idx < len(masked) and masked[idx] == "#":
            idx = skip_ws(masked, idx + 1)
            if idx < len(masked) and masked[idx] == "(":
                close = find_matching(module_text, idx)
                if close is None:
                    continue
                param_open = absolute_start + idx
                param_close = absolute_start + close
                idx = skip_ws(masked, close + 1)
            elif module_name in GATE_PRIMITIVES:
                candidate_start = None
                for candidate in IDENT_RE.finditer(masked, idx):
                    candidate_end = skip_ws(masked, candidate.end())
                    candidate_end, ok = _skip_instance_arrays(
                        module_text, masked, candidate_end
                    )
                    if ok and candidate_end < len(masked) and masked[candidate_end] == "(":
                        candidate_start = candidate.start()
                        break
                if candidate_start is None:
                    continue
                idx = candidate_start
            else:
                continue
        elif idx < len(masked) and masked[idx] == "(":
            close = find_matching(module_text, idx)
            if close is not None:
                after_params = skip_ws(masked, close + 1)
                if IDENT_RE.match(masked, after_params):
                    param_open = absolute_start + idx
                    param_close = absolute_start + close
                    idx = after_params
        inst_match = IDENT_RE.match(masked, idx)
        if inst_match is None:
            continue
        inst_name = module_text[inst_match.start() : inst_match.end()]
        idx = skip_ws(masked, inst_match.end())
        idx, ok = _skip_instance_arrays(module_text, masked, idx)
        if not ok:
            continue
        if idx < len(masked) and masked[idx] == "#":
            idx = skip_ws(masked, idx + 1)
            if idx < len(masked) and masked[idx] == "(":
                close = find_matching(module_text, idx)
                if close is None:
                    continue
                param_open = absolute_start + idx
                param_close = absolute_start + close
                idx = skip_ws(masked, close + 1)
            else:
                continue
        if idx >= len(masked) or masked[idx] != "(":
            continue
        port_close = find_matching(module_text, idx)
        if port_close is None:
            continue
        after = skip_ws(masked, port_close + 1)
        if after < len(masked) and masked[after] == ";":
            end = absolute_start + after + 1
        elif re.search(
            r"/\*AUTOINST(?:\([^*]*\))?\*/",
            module_text[idx + 1 : port_close],
            re.I,
        ):
            end = absolute_start + port_close + 1
        else:
            continue
        instances.append(
            Instance(
                module=module_name,
                name=inst_name,
                start=absolute_start + match.start(),
                end=end,
                port_open=absolute_start + idx,
                port_close=absolute_start + port_close,
                param_open=param_open,
                param_close=param_close,
            )
        )
        pos = end - absolute_start
    return instances

def parse_named_connections(port_text: str) -> tuple[set[str], bool]:
    names: set[str] = set()
    has_star = False
    masked = mask_syntax(port_text)
    for match in re.finditer(r"\.\s*(" + IDENT_RE.pattern + r"|\*)", masked):
        name = port_text[match.start(1) : match.end(1)].strip()
        if name == "*":
            has_star = True
        else:
            names.add(name)
    return names, has_star

def parse_modules(text: str, source_path: Path | None = None) -> list[ModuleInfo]:
    masked = mask_syntax(text)
    defines = parse_defines(text)
    modules: list[ModuleInfo] = []
    pattern = re.compile(
        r"\b(module|interface)\b\s*(?:(" + IDENT_RE.pattern + r")\b)?"
    )
    pos = 0
    while True:
        match = pattern.search(masked, pos)
        if match is None:
            break
        kind = match.group(1)
        name = (
            text[match.start(2) : match.end(2)].strip()
            if match.lastindex and match.group(2)
            else ""
        )
        name = _resolve_define_name(name, defines)
        end_keyword = "endmodule" if kind == "module" else "endinterface"
        end_match = re.search(r"\b" + end_keyword + r"\b", masked[match.end() :])
        if end_match is None:
            pos = match.end()
            continue
        end_start = match.end() + end_match.start()
        end = match.end() + end_match.end()
        header_end = find_top_level_semicolon(text, match.end())
        while header_end is not None and header_end < end_start:
            next_pos = skip_ws(masked, header_end + 1)
            if next_pos < end_start and masked[next_pos] in {"#", "("}:
                header_end = find_top_level_semicolon(text, next_pos)
                continue
            break
        if header_end is None or header_end > end_start:
            pos = match.end()
            continue
        header = text[match.start() : header_end + 1]
        params, header_ports, header_names, port_open, port_close = parse_header(
            header, match.start()
        )
        if port_close is not None:
            after_port_close = skip_ws(masked, port_close + 1)
            if after_port_close < end_start and masked[after_port_close] != ";":
                header_end = port_close
                header = text[match.start() : header_end + 1]
                params, header_ports, header_names, port_open, port_close = parse_header(
                    header, match.start()
                )
        body = text[header_end + 1 : end_start]
        declaration_body = body
        if port_close is not None and header_end > port_close:
            trailing_header = text[port_close + 1 : header_end + 1]
            if re.search(
                r"\b(?:input|output|inout)\b",
                mask_syntax(trailing_header),
            ):
                declaration_body = trailing_header + "\n" + body
        body_ports, body_params = parse_body_declarations(declaration_body)
        params.extend(body_params)
        if header_ports:
            ports = header_ports
            signal_names = {port.name for port in ports}
            signals = [port for port in body_ports if port.name not in signal_names]
        else:
            ports = [port for port in body_ports if port.direction]
            signals = [port for port in body_ports if not port.direction]
        modports = parse_modports(body)
        module_body_start = header_end + 1
        instances = parse_instances(body, module_body_start)
        modules.append(
            ModuleInfo(
                name=name,
                kind=kind,
                ports=ports,
                params=params,
                signals=signals,
                modports=modports,
                instances=instances,
                source_path=source_path,
                start=match.start(),
                end=end,
                header_end=header_end,
                header_port_open=port_open,
                header_port_close=port_close,
            )
        )
        pos = end
    return modules

def simple_signal_name(expr: str) -> str | None:
    expr = expr.strip()
    match = IDENT_RE.match(expr)
    if match is None:
        return None
    name = expr[match.start() : match.end()]
    rest = expr[match.end() :].strip()
    if not rest:
        return name
    if is_only_bracketed_dims(rest):
        return name
    return None

# -- Module Library --------------------------------------------------

class ModuleLibrary:
    def __init__(self) -> None:
        self.modules: dict[str, ModuleInfo] = {}
        self.defines: dict[str, str] = {}

    def add_text(self, text: str, source_path: Path | None = None) -> None:
        self.defines.update(parse_defines(text))
        for module in parse_modules(text, source_path):
            self.modules[module.name] = module

    def add_file(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(errors="ignore")
        self.add_text(text, path)

    def lookup(self, name: str) -> ModuleInfo | None:
        module = self.modules.get(name)
        if module is not None:
            return module
        key = name[1:] if name.startswith("`") else name
        resolved = self.defines.get(key)
        if resolved is not None:
            return self.modules.get(resolved[1:] if resolved.startswith("`") else resolved)
        if name.startswith("`"):
            return self.modules.get(key)
        return None

    @classmethod
    def from_top(cls, top_file: Path, top_text: str) -> "ModuleLibrary":
        lib = cls()
        top_file = top_file.resolve()
        suffixes = {".v", ".sv", ".vh", ".svh"}
        for item in sorted(top_file.parent.iterdir()):
            if item.is_file() and item.suffix in suffixes and item.resolve() != top_file:
                lib.add_file(item)
        lib.add_text(top_text, top_file)
        return lib

# -- AUTO: Template --------------------------------------------------

from dataclasses import dataclass

@dataclass(frozen=True)
class TemplateMapping:
    port_name: str
    actual: str
    nohookup: bool = False
    at_value: str = ""
    regex: str = ""

@dataclass(frozen=True)
class ActualSignal:
    name: str
    packed: str = ""
    unpacked: str = ""
    use_port_packed: bool = True

def _comment_blocks_before(text: str, pos: int) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    for match in re.finditer(r"/\*(.*?)\*/", text[:pos], re.S):
        blocks.append((match.start(), match.end(), match.group(1)))
    return blocks

def _template_nohookup_ports(body: str) -> set[str]:
    ports: set[str] = set()
    for line in body.splitlines():
        if "AUTONOHOOKUP" not in line.upper():
            continue
        code = line.split("//", 1)[0]
        match = re.search(r"\.\s*(" + IDENT_RE.pattern + r")\s*\(", code)
        if match is not None:
            ports.add(code[match.start(1) : match.end(1)].strip())
    return ports

def _template_open_pos(block_text: str, auto_match: re.Match[str]) -> int:
    open_pos = -1
    in_string = False
    escaped = False
    for pos in range(auto_match.end(), len(block_text)):
        ch = block_text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "(":
            open_pos = pos
            break
    return open_pos

def _emacs_regexp_to_python(regexp: str) -> str:
    return (
        regexp.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\|", "|")
        .replace(r"\<", r"\b")
        .replace(r"\>", r"\b")
    )

def _template_port_regexp(port_name: str) -> str:
    return _emacs_regexp_to_python(port_name).replace("@", r"([0-9]+)")

def _template_at_value(block_text: str, instance: Instance) -> tuple[bool, str]:
    auto_match = re.search(r"\bAUTO_TEMPLATE\b", block_text, re.I)
    if auto_match is None:
        return False, ""
    open_pos = _template_open_pos(block_text, auto_match)
    if open_pos < 0:
        return False, ""
    header = block_text[auto_match.end() : open_pos]
    regexp_match = re.search(r'"((?:\\.|[^"])*)"', header)
    if regexp_match is None:
        return True, _instance_number(instance)
    regexp = _emacs_regexp_to_python(regexp_match.group(1))
    try:
        match = re.search(regexp, instance.name)
    except re.error:
        return False, ""
    if match is None:
        return False, ""
    if match.lastindex:
        return True, match.group(1)
    return True, match.group(0)

def _template_actual_open(item: str, start: int) -> int:
    for pos in range(start, len(item)):
        if item[pos] == "(" and (pos == 0 or item[pos - 1] != "\\"):
            return pos
    return -1

def _parse_template_block(block_text: str, *, at_value: str = "") -> list[TemplateMapping]:
    auto_match = re.search(r"\bAUTO_TEMPLATE\b", block_text, re.I)
    if auto_match is None:
        return []
    open_pos = _template_open_pos(block_text, auto_match)
    if open_pos < 0:
        return []
    close_pos = find_matching(block_text, open_pos)
    if close_pos is None:
        return []
    body = block_text[open_pos + 1 : close_pos]
    nohookup_ports = _template_nohookup_ports(body)
    result: list[TemplateMapping] = []
    for item in split_top_level(body):
        masked = mask_syntax(item)
        match = re.search(r"\.\s*", masked)
        if match is None:
            continue
        actual_open = _template_actual_open(item, match.end())
        if actual_open < 0:
            continue
        port_name = re.sub(r"\s+", "", item[match.end() : actual_open])
        actual_close = find_matching(item, actual_open) if actual_open >= 0 else None
        if actual_close is None:
            continue
        actual = item[actual_open + 1 : actual_close].strip()
        if port_name:
            regex = (
                ""
                if "\\" not in port_name and IDENT_RE.fullmatch(port_name)
                else _template_port_regexp(port_name)
            )
            result.append(
                TemplateMapping(
                    port_name=port_name,
                    actual=actual,
                    nohookup=port_name in nohookup_ports,
                    at_value=at_value,
                    regex=regex,
                )
            )
    return result

def find_template_for_instance(text: str, instance: Instance) -> list[TemplateMapping]:
    pattern = re.compile(
        r"\b" + re.escape(instance.module) + r"\s+AUTO_TEMPLATE\b",
        re.I,
    )
    for _, _, block_text in reversed(_comment_blocks_before(text, instance.start)):
        if pattern.search(block_text):
            matches, at_value = _template_at_value(block_text, instance)
            if not matches:
                continue
            return _parse_template_block(block_text, at_value=at_value)
    return []

def _instance_number(instance: Instance | None) -> str:
    if instance is None:
        return ""
    match = re.search(r"(\d+)", instance.name)
    return match.group(1) if match else ""

def _apply_template_substitutions(
    actual: str,
    port: Port,
    instance: Instance | None,
    *,
    at_value: str = "",
) -> str:
    number = at_value or _instance_number(instance)
    actual = actual.replace("@", number)
    if "[]" in actual:
        packed_dims = _dims(port.packed)

        def replace_empty_brackets(match: re.Match[str]) -> str:
            count = len(match.group(0)) // 2
            if count >= 2 and (port.unpacked or len(packed_dims) > 1):
                return _dimension_comment(port)
            if port.unpacked and not packed_dims:
                return _dimension_comment(port)
            if packed_dims:
                return packed_dims[-1]
            return ""

        actual = re.sub(r"(?:\[\])+", replace_empty_brackets, actual)
    return actual

def _apply_match_substitutions(actual: str, match: re.Match[str] | None) -> str:
    if match is None:
        return actual
    for index, value in enumerate(match.groups(), start=1):
        actual = actual.replace(f"\\{index}", value)
    return actual

def _mapping_for_port(
    port_name: str, template: list[TemplateMapping]
) -> tuple[TemplateMapping | None, re.Match[str] | None]:
    for mapping in template:
        if not mapping.regex and mapping.port_name == port_name:
            return mapping, None
    for mapping in template:
        if not mapping.regex:
            continue
        try:
            match = re.fullmatch(mapping.regex, port_name)
        except re.error:
            continue
        if match is not None:
            return mapping, match
    return None, None

def _compact_dims(text: str) -> str:
    return text.replace(" ", "")

def _dims(text: str) -> list[str]:
    return split_bracketed_dims(text)

def _dimension_comment(port: Port) -> str:
    packed = _compact_dims(port.packed)
    unpacked = _compact_dims(port.unpacked)
    if unpacked:
        return f"/*{packed}.{unpacked}*/"
    return f"/*{packed}*/"

def _default_actual(port: Port) -> str:
    if port.interface_type:
        return port.name
    if port.unpacked or len(split_bracketed_dims(port.packed)) > 1:
        return f"{port.name}{_dimension_comment(port)}"
    if port.packed:
        return f"{port.name}{port.packed}"
    return port.name

def _simple_actual_signal(actual: str) -> ActualSignal | None:
    actual = actual.strip()
    masked = mask_syntax(actual)
    match = IDENT_RE.match(masked)
    if match is None or match.start() != 0:
        return None
    name = actual[match.start() : match.end()].strip()
    rest = actual[match.end() :].strip()
    if not name:
        return None
    if not rest:
        return ActualSignal(name=name)
    comment = re.fullmatch(r"/\*([^*]*)\*/", rest)
    if comment is not None:
        pieces = comment.group(1).split(".", 1)
        packed_text = pieces[0]
        unpacked_text = pieces[1] if len(pieces) > 1 else ""
        return ActualSignal(
            name=name,
            packed=" ".join(_dims(packed_text)),
            unpacked=" ".join(_dims(unpacked_text)),
            use_port_packed=False,
        )
    if not is_only_bracketed_dims(rest):
        return None
    return ActualSignal(
        name=name,
        packed=" ".join(split_bracketed_dims(rest)),
    )

def actual_for_port(
    port: Port,
    template: list[TemplateMapping],
    *,
    instance: Instance | None = None,
) -> tuple[str, bool]:
    mapping, match = _mapping_for_port(port.name, template)
    if mapping is not None:
        mapped_actual = _apply_match_substitutions(mapping.actual, match)
        actual = _apply_template_substitutions(
            mapped_actual,
            port,
            instance,
            at_value=mapping.at_value,
        )
        return actual, True
    return _default_actual(port), False

def actual_for_param(
    name: str,
    template: list[TemplateMapping],
    *,
    instance: Instance | None = None,
) -> tuple[str, bool]:
    mapping, match = _mapping_for_port(name, template)
    if mapping is None:
        return name, False
    mapped_actual = _apply_match_substitutions(mapping.actual, match)
    actual = _apply_template_substitutions(
        mapped_actual,
        Port(name=name),
        instance,
        at_value=mapping.at_value,
    )
    return actual, True

def is_nohookup(port: Port, template: list[TemplateMapping]) -> bool:
    mapping, _ = _mapping_for_port(port.name, template)
    return bool(mapping and mapping.nohookup)

def extract_actual_signals(actual: str, *, ignore_concat: bool = False) -> list[ActualSignal]:
    simple_signal = _simple_actual_signal(actual)
    if simple_signal is not None:
        return [simple_signal]
    if ignore_concat:
        return []
    masked = mask_syntax(actual)
    signals: list[ActualSignal] = []
    seen: set[str] = set()
    for match in IDENT_RE.finditer(masked):
        name = actual[match.start() : match.end()].strip()
        if not name:
            continue
        prev_pos = match.start() - 1
        while prev_pos >= 0 and masked[prev_pos].isspace():
            prev_pos -= 1
        next_pos = match.end()
        while next_pos < len(masked) and masked[next_pos].isspace():
            next_pos += 1
        prev_ch = masked[prev_pos] if prev_pos >= 0 else ""
        next_ch = masked[next_pos] if next_pos < len(masked) else ""
        if prev_ch in {".", "'"} or next_ch in {".", "'"}:
            continue
        if next_ch == "(":
            continue
        packed_dims: list[str] = []
        if next_ch == "[":
            scan_pos = next_pos
            while scan_pos < len(masked) and masked[scan_pos] == "[":
                close = find_matching(actual, scan_pos)
                if close is None:
                    break
                packed_dims.append(actual[scan_pos : close + 1].strip())
                scan_pos = close + 1
                while scan_pos < len(masked) and masked[scan_pos].isspace():
                    scan_pos += 1
        if name not in seen:
            signals.append(
                ActualSignal(
                    name=name,
                    packed=" ".join(packed_dims),
                    use_port_packed=False,
                )
            )
            seen.add(name)
    return signals

# -- AUTO: Parameter Values --------------------------------------------------

BARE_IDENT_RE = re.compile(r"[A-Za-z_][$A-Za-z0-9_]*")
SCOPED_IDENT_RE = re.compile(
    r"`?[A-Za-z_][$A-Za-z0-9_]*(?:(?:::|\.)`?[A-Za-z_][$A-Za-z0-9_]*)*"
)

def inst_param_value_enabled(text: str, pos: int) -> bool:
    enabled = (
        re.search(
            r"verilog-auto-inst-param-value\s*:\s*t\b",
            text,
            re.I,
        )
        is not None
    )
    pattern = re.compile(
        r"verilog-auto-inst-param-value\s*(?::|\s+)\s*(t|nil)\b",
        re.I,
    )
    for match in pattern.finditer(text[:pos]):
        enabled = match.group(1).lower() == "t"
    return enabled

def instance_param_values(text: str, instance: Instance) -> dict[str, str]:
    if instance.param_open is None or instance.param_close is None:
        return {}
    param_text = text[instance.param_open + 1 : instance.param_close]
    masked = mask_syntax(param_text)
    values: dict[str, str] = {}
    for match in re.finditer(r"\.\s*(" + IDENT_RE.pattern + r")\s*\(", masked):
        name = param_text[match.start(1) : match.end(1)].strip()
        open_pos = match.end() - 1
        close_pos = find_matching(param_text, open_pos)
        if close_pos is None:
            continue
        values[name] = param_text[open_pos + 1 : close_pos].strip()
    return values

def _eval_int_expr(expr: str, env: dict[str, str], stack: set[str] | None = None) -> str | None:
    stack = set() if stack is None else set(stack)
    expr = expr.strip()
    expr = expr.replace("<<<", "<<").replace(">>>", ">>")

    def clog2_repl(match: re.Match[str]) -> str:
        value = _eval_int_expr(match.group(1), env, stack)
        if value is None:
            return match.group(0)
        number = int(value)
        return str((number - 1).bit_length())

    expr = re.sub(r"\$clog2\s*\(([^()]+)\)", clog2_repl, expr)

    def ident_repl(match: re.Match[str]) -> str:
        name = match.group(0)
        if name not in env or name in stack:
            return name
        value = _eval_int_expr(env[name], env, stack | {name})
        return value if value is not None else name

    expr = BARE_IDENT_RE.sub(ident_repl, expr)
    if not re.fullmatch(r"[0-9+\-*/%() <>&|^~]+", expr):
        return None
    try:
        return str(int(eval(expr.replace("/", "//"), {"__builtins__": {}}, {})))
    except Exception:
        return None

def _is_scoped_identifier(text: str) -> bool:
    return SCOPED_IDENT_RE.fullmatch(text.strip()) is not None

def _replacement_for(actual: str, next_char: str) -> str:
    actual = actual.strip()
    if next_char == ".":
        return actual
    if _is_scoped_identifier(actual) or re.fullmatch(r"\d+(?:'[sS]?[bodhBODH][0-9a-fA-F_xXzZ]+)?", actual):
        return actual
    return f"({actual})"

def _resolve_explicit_value(
    name: str,
    explicit_values: dict[str, str],
    stack: tuple[str, ...] = (),
) -> str | None:
    actual = explicit_values.get(name)
    if actual is None:
        return None
    actual = actual.strip()
    if BARE_IDENT_RE.fullmatch(actual) is None:
        return actual
    if actual in stack:
        return max((*stack, actual))
    resolved = _resolve_explicit_value(actual, explicit_values, (*stack, actual))
    return resolved if resolved is not None else actual

def _replace_explicit_param_names(
    text: str,
    explicit_values: dict[str, str],
    *,
    parenthesize_complex: bool = True,
) -> str:
    if not text or not explicit_values:
        return text

    def repl(match: re.Match[str]) -> str:
        name = match.group(0)
        start = match.start()
        end = match.end()
        if text[max(0, start - 2) : start] == "::":
            return name
        if text[end : end + 2] == "::":
            return name
        if start > 0 and text[start - 1] == ".":
            return name
        actual = _resolve_explicit_value(name, explicit_values, (name,))
        if actual is None:
            return name
        if not parenthesize_complex:
            return actual.strip()
        next_char = text[end : end + 1]
        return _replacement_for(actual, next_char)

    return BARE_IDENT_RE.sub(repl, text)

def _resolve_dim_part(
    part: str,
    eval_env: dict[str, str],
    explicit_values: dict[str, str],
) -> str:
    evaluated = _eval_int_expr(part, eval_env)
    if evaluated is not None:
        return evaluated
    return _replace_explicit_param_names(part.strip(), explicit_values)

def resolve_packed_dims(
    text: str,
    params: list[Param],
    source_text: str,
    instance: Instance,
) -> str:
    explicit_values = instance_param_values(source_text, instance)
    eval_env = {param.name: param.value for param in params if param.value}
    eval_env.update(explicit_values)
    if not eval_env and not explicit_values:
        return text

    chunks: list[str] = []
    last = 0
    for start, end, dim in iter_bracketed_ranges(text):
        chunks.append(text[last:start])
        inner = dim[1:-1]
        parts = split_top_level(inner, ":")
        resolved = [
            _resolve_dim_part(part, eval_env, explicit_values) for part in parts
        ]
        chunks.append("[" + ":".join(resolved) + "]")
        last = end
    chunks.append(text[last:])
    return "".join(chunks)

def port_with_param_values(
    port: Port,
    params: list[Param],
    source_text: str,
    instance: Instance,
) -> Port:
    explicit_values = instance_param_values(source_text, instance)
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=_replace_explicit_param_names(
            port.data_type,
            explicit_values,
            parenthesize_complex=False,
        ),
        packed=resolve_packed_dims(port.packed, params, source_text, instance),
        unpacked=resolve_packed_dims(port.unpacked, params, source_text, instance),
        interface_type=port.interface_type,
    )

def ports_with_param_values(
    ports: list[Port],
    params: list[Param],
    source_text: str,
    instance: Instance,
) -> list[Port]:
    explicit_values = instance_param_values(source_text, instance)
    eval_env = {param.name: param.value for param in params if param.value}
    eval_env.update(explicit_values)
    if not eval_env and not explicit_values:
        return ports
    return [
        Port(
            name=port.name,
            direction=port.direction,
            data_type=_replace_explicit_param_names(
                port.data_type,
                explicit_values,
                parenthesize_complex=False,
            ),
            packed=resolve_packed_dims(port.packed, params, source_text, instance),
            unpacked=resolve_packed_dims(port.unpacked, params, source_text, instance),
            interface_type=port.interface_type,
        )
        for port in ports
    ]

# -- AUTO: Delete --------------------------------------------------

AUTOMATIC_BLOCK_RE = re.compile(
    r"^[ \t]*// Beginning of automatic[^\n]*\n"
    r"(?:.*\n)*?"
    r"^[ \t]*// End of automatics[^\n]*(?:\n)?",
    re.M,
)

AUTO_MARKER_RE = re.compile(r"/\*AUTO[A-Z0-9_]*(?:\([^*]*\))?\*/", re.I)

def _delete_marker_automatic_blocks(text: str) -> str:
    spans: list[tuple[int, int]] = []
    for marker in AUTO_MARKER_RE.finditer(text):
        whitespace = re.match(r"\s*", text[marker.end() :])
        first_nonspace = marker.end() + (whitespace.end() if whitespace else 0)
        if first_nonspace >= len(text):
            continue
        block_start = text.rfind("\n", 0, first_nonspace) + 1
        block = AUTOMATIC_BLOCK_RE.match(text, block_start)
        if block is not None:
            spans.append((block.start(), block.end()))
    for start, end in sorted(set(spans), reverse=True):
        text = text[:start] + text[end:]
    return text

def _collapse_marker_region(text: str, marker: str) -> str:
    pattern = re.compile(
        r"/\*" + re.escape(marker) + r"(?:\([^*]*\))?\*/",
        re.I,
    )
    pos = 0
    while True:
        match = pattern.search(text, pos)
        if match is None:
            return text
        close = find_port_close_after_marker(text, match.end())
        if close is None:
            return text
        replacement = text[: match.end()] + ")" + text[close + 1 :]
        if replacement == text:
            pos = match.end()
            continue
        text = replacement
        pos = match.end()

def delete_auto(text: str) -> str:
    text = _delete_marker_automatic_blocks(text)
    for marker in ("AUTOARG", "AUTOINST", "AUTOINSTPARAM", "AUTOSENSE"):
        text = _collapse_marker_region(text, marker)
    text = re.sub(
        r"(/\*AUTOINST(?:\([^*]*\))?\*/\);)[ \t]*//[^\n]*Templated[^\n]*",
        r"\1",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(/\*AUTOINSTPARAM(?:\([^*]*\))?\*/\))[ \t]*//[^\n]*Templated[^\n]*",
        r"\1",
        text,
        flags=re.I,
    )
    return text

# -- AUTO: Instance --------------------------------------------------

AUTOINST_RE = re.compile(r"/\*AUTOINST(?:\((.*?)\))?\*/", re.S | re.I)
AUTOINSTPARAM_RE = re.compile(r"/\*AUTOINSTPARAM(?:\((.*?)\))?\*/", re.S | re.I)

def _inst_vector_mode(text: str) -> str:
    mode = "all"
    pattern = re.compile(
        r"verilog-auto-inst-vector\s*(?::|\s+)\s*(t|nil|unsigned)\b",
        re.I,
    )
    for match in pattern.finditer(text):
        value = match.group(1).lower()
        mode = "all" if value == "t" else value
    return mode

def _inst_sort_enabled(text: str, pos: int) -> bool:
    enabled = re.search(r"verilog-auto-inst-sort\s*:\s*t\b", text, re.I) is not None
    pattern = re.compile(
        r"verilog-auto-inst-sort\s*(?::|\s+)\s*(t|nil)\b",
        re.I,
    )
    for match in pattern.finditer(text[:pos]):
        enabled = match.group(1).lower() == "t"
    return enabled

def _template_required_enabled(text: str, pos: int) -> bool:
    enabled = (
        re.search(r"verilog-auto-inst-template-required\s*:\s*t\b", text, re.I)
        is not None
    )
    pattern = re.compile(
        r"verilog-auto-inst-template-required\s*(?::|\s+)\s*(t|nil)\b",
        re.I,
    )
    for match in pattern.finditer(text[:pos]):
        enabled = match.group(1).lower() == "t"
    return enabled

def _star_save_enabled(text: str) -> bool:
    return re.search(r"verilog-auto-star-save\s*:\s*t\b", text, re.I) is not None

def _regexp_arg(match: re.Match[str]) -> str:
    arg = match.group(1)
    if not arg:
        return ""
    arg = arg.strip()
    if len(arg) >= 2 and arg[0] == '"' and arg[-1] == '"':
        return arg[1:-1]
    return arg

def _matches_marker_filter(name: str, regexp: str) -> bool:
    if not regexp:
        return True
    invert = regexp.startswith("?!")
    if invert:
        regexp = regexp[2:]
    regexp = _emacs_regexp_to_python(regexp)
    try:
        matched = re.search(regexp, name) is not None
    except re.error:
        return False
    return not matched if invert else matched

def _star_marker(port_text: str) -> re.Match[str] | None:
    return re.search(r"\.\s*\*", mask_syntax(port_text))

def _dimension_comment_tmpl(port: Port) -> str:
    packed = port.packed.replace(" ", "")
    unpacked = port.unpacked.replace(" ", "")
    if unpacked:
        return f"/*{packed}.{unpacked}*/"
    return f"/*{packed}*/"

def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)

def _declared_same_packed(parent_module, port: Port) -> bool:
    for declared in parent_module.ports + parent_module.signals:
        if declared.name == port.name:
            return _compact(declared.packed) == _compact(port.packed)
    return False

def _default_actual_no_vector(port: Port, parent_module) -> str:
    if port.interface_type:
        return port.name
    if port.unpacked or len(split_bracketed_dims(port.packed)) > 1:
        return f"{port.name}{_dimension_comment(port)}"
    if port.packed and not _declared_same_packed(parent_module, port):
        return f"{port.name}{port.packed}"
    return port.name

def _port_groups(ports: list[Port], manual: set[str], regexp: str = "") -> list[Port]:
    selected: list[Port] = []
    seen: set[str] = set()
    for direction, group in direction_groups(ports):
        del direction
        for port in group:
            if port.name in seen:
                continue
            if port.name in manual or not _matches_marker_filter(port.name, regexp):
                continue
            selected.append(port)
            seen.add(port.name)
    return selected

def _format_connection(
    indent: str,
    port: Port,
    actual: str,
    templated: bool,
    nohookup: bool,
    terminator: str,
) -> str:
    line = format_connection(indent, port, actual, terminator)
    if templated:
        line += " // Templated"
        if nohookup:
            line += " AUTONOHOOKUP"
    return line

def _parent_declares_modport(module, signal_name: str, modport: str) -> bool:
    for port in module.ports + module.signals:
        if (
            port.name == signal_name
            and len(port.interface_type) > 1
            and port.interface_type[-1] == modport
        ):
            return True
    return False

def _interface_actual(port: Port, actual: str, parent_module) -> str:
    if not port.interface_type:
        return actual
    if len(port.interface_type) > 1:
        modport = port.interface_type[-1]
        if not _parent_declares_modport(parent_module, actual, modport):
            actual = f"{actual}.{modport}"
    if port.unpacked:
        actual = f"{actual}/*.{port.unpacked.replace(' ', '')}*/"
    return actual

def _format_autoinst(
    indent: str,
    ports: list[Port],
    template,
    instance,
    parent_module,
    *,
    inst_vector_mode: str = "all",
    inst_sort: bool = False,
    include_empty_leading_groups: bool = False,
    separate_close: bool = False,
) -> str:
    if not ports:
        return ");"
    lines: list[str] = []
    remaining = set(port.name for port in ports)
    groups = direction_groups(ports)
    for index, (direction, group) in enumerate(groups):
        group = [port for port in group if port.name in remaining]
        if inst_sort:
            group = sorted(group, key=lambda item: item.name)
        if (
            include_empty_leading_groups
            and not group
            and direction != "interface"
            and any(
                later_port.name in remaining
                for _, later_group in groups[index + 1 :]
                for later_port in later_group
            )
        ):
            lines.append(f"\n{indent}// {GROUP_TITLES[direction]}")
            continue
        if not group:
            continue
        lines.append(f"\n{indent}// {GROUP_TITLES[direction]}")
        for port in group:
            remaining.remove(port.name)
            if remaining:
                terminator = ","
            else:
                terminator = "" if separate_close else ");"
            actual, templated = actual_for_port(port, template, instance=instance)
            if not templated:
                if inst_vector_mode == "nil":
                    actual = _default_actual_no_vector(port, parent_module)
                elif (
                    inst_vector_mode == "unsigned"
                    and "signed" in port.data_type.split()
                    and not port.unpacked
                ):
                    actual = port.name
                actual = _interface_actual(port, actual, parent_module)
            nohookup = is_nohookup(port, template)
            lines.append(
                "\n"
                + _format_connection(indent, port, actual, templated, nohookup, terminator)
            )
    if separate_close:
        lines.append(f"\n{indent});")
    return "".join(lines)

def _format_star_save(
    indent: str,
    ports: list[Port],
    instance: Instance,
    parent_module,
    *,
    inst_vector_mode: str = "all",
    inst_sort: bool = False,
) -> str:
    if not ports:
        return ");"
    lines: list[str] = []
    remaining = set(port.name for port in ports)
    for direction, group in direction_groups(ports):
        group = [port for port in group if port.name in remaining]
        if inst_sort:
            group = sorted(group, key=lambda item: item.name)
        if not group:
            continue
        lines.append(f"\n{indent}// {GROUP_TITLES[direction]}")
        for port in group:
            remaining.remove(port.name)
            terminator = ");" if not remaining else ","
            actual, _ = actual_for_port(port, [], instance=instance)
            if inst_vector_mode == "nil":
                actual = _default_actual_no_vector(port, parent_module)
            elif (
                inst_vector_mode == "unsigned"
                and "signed" in port.data_type.split()
                and not port.unpacked
            ):
                actual = port.name
            actual = _interface_actual(port, actual, parent_module)
            lines.append(
                "\n"
                + format_connection(indent, port, actual, terminator)
                + " // Implicit .*"
            )
    return "".join(lines)

def _format_param_connection(
    indent: str, param: Param, actual: str, templated: bool, terminator: str
) -> str:
    line = f"{indent}.{param.name:<31}({actual}){terminator}"
    if templated:
        line += " // Templated"
    return line

def _default_param_actual(param: Param) -> str:
    actual = param.name
    packed = param.packed.replace(" ", "")
    unpacked = param.unpacked.replace(" ", "")
    if packed:
        actual += packed
    if unpacked:
        actual += f"/*.{unpacked}*/"
    return actual

def _format_autoinstparam(indent: str, params: list[Param], template, instance) -> str:
    if not params:
        return ")"
    lines = [f"\n{indent}// Parameters"]
    for idx, param in enumerate(params):
        terminator = ")" if idx == len(params) - 1 else ","
        actual, templated = actual_for_param(param.name, template, instance=instance)
        if not templated:
            actual = _default_param_actual(param)
        lines.append(
            "\n" + _format_param_connection(indent, param, actual, templated, terminator)
        )
    return "".join(lines)

def _template_param_map(
    params: list[Param], template, instance: Instance
) -> dict[str, str]:
    result: dict[str, str] = {}
    for param in params:
        actual, templated = actual_for_param(param.name, template, instance=instance)
        if templated:
            result[param.name] = actual
    return result

def _template_param_map_child(child, template, instance) -> dict[str, str]:
    result: dict[str, str] = {}
    for param in child.params:
        actual, templated = actual_for_param(param.name, template, instance=instance)
        if templated:
            result[param.name] = actual
    return result


def _replace_param_names(text: str, param_map: dict[str, str]) -> str:
    if not text or not param_map:
        return text
    return re.sub(
        r"\b[A-Za-z_][$A-Za-z0-9_]*\b",
        lambda match: param_map.get(match.group(0), match.group(0)),
        text,
    )

def _ports_with_template_param_names(
    ports: list[Port], param_map: dict[str, str]
) -> list[Port]:
    if not param_map:
        return ports
    return [
        Port(
            name=port.name,
            direction=port.direction,
            data_type=port.data_type,
            packed=_replace_param_names(port.packed, param_map),
            unpacked=_replace_param_names(port.unpacked, param_map),
            interface_type=port.interface_type,
        )
        for port in ports
    ]

def expand_autoinst(text: str, library: ModuleLibrary) -> str:
    modules = parse_modules(text)
    replacements: list[tuple[int, int, str]] = []
    for module in modules:
        for instance in module.instances:
            child = library.lookup(instance.module)
            if child is None:
                continue
            port_text = text[instance.port_open + 1 : instance.port_close]
            marker = AUTOINST_RE.search(port_text)
            star = _star_marker(port_text) if marker is None else None
            if marker is None and star is None:
                continue
            if marker is not None:
                manual_text = port_text[: marker.start()]
            else:
                manual_text = port_text
            manual, _ = parse_named_connections(manual_text)
            marker_filter = _regexp_arg(marker) if marker is not None else ""
            ports = _port_groups(child.ports, manual, marker_filter)
            param_values_applied = False
            if inst_param_value_enabled(text, instance.start):
                ports = ports_with_param_values(ports, child.params, text, instance)
                param_values_applied = bool(instance_param_values(text, instance))
            template = find_template_for_instance(text, instance)
            template_required = _template_required_enabled(text, instance.start)
            if template_required and not template:
                continue
            if (
                not param_values_applied
                and inst_param_value_enabled(text, instance.start)
            ):
                ports = _ports_with_template_param_names(
                    ports, _template_param_map(child.params, template, instance)
                )
            if template_required:
                ports = [
                    port
                    for port in ports
                    if actual_for_port(port, template, instance=instance)[1]
                ]
            if marker is not None:
                marker_start = instance.port_open + 1 + marker.start()
                marker_end = instance.port_open + 1 + marker.end()
                indent = line_indent_at(text, marker_start)
                replacement = _format_autoinst(
                    indent,
                    ports,
                    template,
                    instance,
                    module,
                    inst_vector_mode=_inst_vector_mode(text),
                    inst_sort=_inst_sort_enabled(text, instance.start),
                )
                replacements.append((marker_end, instance.end, replacement))
                continue
            if star is None:
                continue
            star_start = instance.port_open + 1 + star.start()
            star_end = instance.port_open + 1 + star.end()
            indent = line_indent_at(text, star_start)
            replacement = ""
            if template:
                templated_ports = [
                    port
                    for port in ports
                    if actual_for_port(port, template, instance=instance)[1]
                ]
                if templated_ports:
                    replacement = "," + _format_autoinst(
                        indent,
                        templated_ports,
                        template,
                        instance,
                        module,
                        inst_vector_mode=_inst_vector_mode(text),
                        inst_sort=_inst_sort_enabled(text, instance.start),
                        include_empty_leading_groups=True,
                        separate_close=True,
                    )
            elif _star_save_enabled(text):
                replacement = "," + _format_star_save(
                    indent,
                    ports,
                    instance,
                    module,
                    inst_vector_mode=_inst_vector_mode(text),
                    inst_sort=_inst_sort_enabled(text, instance.start),
                )
            if not replacement:
                continue
            replacements.append((star_end, instance.end, replacement))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text

def expand_autoinstparam(text: str, library: ModuleLibrary) -> str:
    modules = parse_modules(text)
    replacements: list[tuple[int, int, str]] = []
    for module in modules:
        for instance in module.instances:
            if instance.param_open is None or instance.param_close is None:
                continue
            child = library.lookup(instance.module)
            if child is None:
                continue
            param_text = text[instance.param_open + 1 : instance.param_close]
            marker = AUTOINSTPARAM_RE.search(param_text)
            if marker is None:
                continue
            manual, _ = parse_named_connections(param_text)
            regexp = _regexp_arg(marker)
            params = [
                param
                for param in child.params
                if param.kind not in {"localparam", "genvar"}
                and param.name not in manual
                and _matches_marker_filter(param.name, regexp)
            ]
            if _inst_sort_enabled(text, instance.start):
                params = sorted(params, key=lambda item: item.name)
            template = find_template_for_instance(text, instance)
            marker_start = instance.param_open + 1 + marker.start()
            marker_end = instance.param_open + 1 + marker.end()
            indent = line_indent_at(text, marker_start)
            replacement = _format_autoinstparam(indent, params, template, instance)
            replacements.append((marker_end, instance.param_close + 1, replacement))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text

# -- AUTO: Arguments --------------------------------------------------

AUTOARG_RE = re.compile(r"/\*AUTOARG\*/", re.I)

def _autoarg_format(text: str) -> str:
    if re.search(r"verilog-auto-arg-format\s*:\s*single\b", text):
        return "single"
    return "packed"

def _autoarg_sort(text: str) -> str:
    if re.search(r"verilog-auto-arg-sort\s*:\s*t\b", text):
        return "asc"
    return "none"

def _module_prefers_generated_port_sort(module_text: str) -> bool:
    return re.search(
        r"/\*AUTO(?:INPUT|OUTPUT(?:EVERY)?|INOUT|INOUTMODPORT|INOUTCOMP)\b",
        module_text,
        re.I,
    ) is not None

def _module_has_auto_template(module_text: str) -> bool:
    return re.search(r"\bAUTO_TEMPLATE\b|\bAUTONOHOOKUP\b", module_text, re.I) is not None

def _natural_numeric_sequence(names: list[str]) -> bool:
    if len(names) < 2:
        return False
    pieces: list[tuple[str, int]] = []
    for name in names:
        match = re.fullmatch(r"(.*?)(\d+)", name)
        if match is None:
            return False
        pieces.append((match.group(1), int(match.group(2))))
    prefixes = {prefix for prefix, _ in pieces}
    numbers = [number for _, number in pieces]
    return len(prefixes) == 1 and numbers == sorted(numbers)

def _marker_indent(text: str, marker_start: int) -> tuple[str, bool]:
    start = line_start(text, marker_start)
    prefix = text[start:marker_start]
    if prefix.strip():
        return " " * len(prefix), True
    return line_indent_at(text, marker_start), False

def _has_ansi_ports_before_marker(header_text: str, marker_start: int) -> bool:
    before = mask_syntax(header_text[:marker_start])
    return re.search(r"\b(?:input|output|inout)\b", before) is not None

def _header_names_before_marker(header_text: str, marker_start: int) -> set[str]:
    names: set[str] = set()
    before = header_text[:marker_start]
    for item in split_top_level(before):
        masked = mask_syntax(item)
        matches = list(IDENT_RE.finditer(masked))
        if not matches:
            continue
        match = matches[-1]
        names.add(item[match.start() : match.end()].strip())
    return names

def _format_autoarg(
    indent: str,
    grouped_ports: list[tuple[str, list[str]]],
    *,
    inline_marker: bool = False,
    format_style: str = "packed",
) -> str:
    lines: list[str] = []
    nonempty = [(direction, names) for direction, names in grouped_ports if names]
    if not nonempty:
        return ")"
    arg_indent = indent if inline_marker else (indent[:-1] if indent else indent)
    if format_style == "single":
        flattened: list[tuple[str, str]] = []
        for direction, names in nonempty:
            for name in names:
                flattened.append((direction, name))
        emitted = 0
        for direction, names in nonempty:
            lines.append(f"\n{arg_indent}// {GROUP_TITLES[direction]}")
            for name in names:
                emitted += 1
                suffix = "," if emitted != len(flattened) else ""
                lines.append(f"\n{arg_indent}{format_identifier(name, terminator=suffix)}")
        lines.append(f"\n{arg_indent})")
        return "".join(lines)
    for idx, (direction, names) in enumerate(nonempty):
        lines.append(f"\n{arg_indent}// {GROUP_TITLES[direction]}")
        suffix = "," if idx != len(nonempty) - 1 else ""
        rendered_names = [
            format_identifier(name, terminator="")
            for name in names
        ]
        line = ", ".join(rendered_names)
        if suffix:
            line = format_identifier(line, terminator=suffix)
        lines.append(f"\n{arg_indent}{line}")
    lines.append(f"\n{arg_indent})")
    return "".join(lines)

def expand_autoarg(text: str) -> str:
    modules = parse_modules(text)
    replacements: list[tuple[int, int, str]] = []
    format_style = _autoarg_format(text)
    sort_style = _autoarg_sort(text)
    for module in modules:
        if module.header_port_open is None or module.header_port_close is None:
            continue
        module_text = text[module.start : module.end]
        header_text = text[module.header_port_open + 1 : module.header_port_close]
        marker = AUTOARG_RE.search(header_text)
        if marker is None:
            continue
        if _has_ansi_ports_before_marker(header_text, marker.start()):
            continue
        module_sort_style = sort_style
        if module_sort_style == "none" and _module_prefers_generated_port_sort(module_text):
            module_sort_style = "reverse"
        force_reverse = _module_has_auto_template(module_text)
        seen = _header_names_before_marker(header_text, marker.start())
        grouped: list[tuple[str, list[str]]] = []
        for direction in ("output", "inout", "input"):
            names = [
                port.name
                for port in module.ports
                if port.direction == direction and port.name not in seen
            ]
            for name in names:
                seen.add(name)
            if format_style == "single":
                pass
            elif module_sort_style == "asc":
                names.sort()
            elif module_sort_style == "reverse":
                if force_reverse or not _natural_numeric_sequence(names):
                    names.reverse()
            grouped.append((direction, names))
        marker_start = module.header_port_open + 1 + marker.start()
        marker_end = module.header_port_open + 1 + marker.end()
        indent, inline_marker = _marker_indent(text, marker_start)
        replacement = _format_autoarg(
            indent,
            grouped,
            inline_marker=inline_marker,
            format_style=format_style,
        )
        replacements.append((marker_end, module.header_port_close + 1, replacement))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text

# -- AUTO: Declarations --------------------------------------------------

from dataclasses import dataclass

@dataclass(frozen=True)
class PortUse:
    port: Port
    inst_name: str
    module_name: str
    multiple: bool = False
    primitive: bool = False
    comment: str | None = None

def _merge_duplicate_uses(uses: list[PortUse]) -> list[PortUse]:
    merged: dict[str, PortUse] = {}
    order: list[str] = []
    for use in uses:
        name = use.port.name
        if name not in merged:
            merged[name] = use
            order.append(name)
        else:
            first = merged[name]
            if (
                first.inst_name == use.inst_name
                and first.module_name == use.module_name
                and first.primitive == use.primitive
            ):
                continue
            port, couldnt_merge = _merge_port_ranges(first.port, use.port)
            comment = first.comment
            if couldnt_merge:
                comment = _comment_for(
                    PortUse(
                        port=first.port,
                        inst_name=first.inst_name,
                        module_name=first.module_name,
                        multiple=True,
                        primitive=first.primitive,
                    )
                ) + ", Couldn't Merge"
            merged[name] = PortUse(
                port=port,
                inst_name=first.inst_name,
                module_name=first.module_name,
                multiple=True,
                primitive=first.primitive,
                comment=comment,
            )
    return [merged[name] for name in order]

def _light_simplify_expr(expr: str) -> str:
    expr = expr.strip()
    expr = re.sub(r"\b([A-Za-z_][$A-Za-z0-9_]*|\d+)\s*\*\s*1\b", r"\1", expr)
    expr = re.sub(r"\b1\s*\*\s*([A-Za-z_][$A-Za-z0-9_]*|\d+)\b", r"\1", expr)

    def minus_plus(match: re.Match[str]) -> str:
        name = match.group(1)
        delta = int(match.group(3)) - int(match.group(2))
        if delta == 0:
            return name
        op = "+" if delta > 0 else "-"
        return f"{name}{op}{abs(delta)}"

    expr = re.sub(
        r"\b([A-Za-z_][$A-Za-z0-9_]*)\s*-\s*(\d+)\s*\+\s*(\d+)\b",
        minus_plus,
        expr,
    )
    return expr

def _eval_simple_const(expr: str) -> int | None:
    expr = _light_simplify_expr(expr)
    if not re.fullmatch(r"[0-9+\-*/%() \t]+", expr):
        return None
    try:
        return int(eval(expr.replace("/", "//"), {"__builtins__": {}}, {}))
    except Exception:
        return None

def _single_range(packed: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\[\s*([^:\]]+)\s*:\s*([^:\]]+)\s*\]", packed.strip())
    if match is None:
        return None
    left = _eval_simple_const(match.group(1))
    right = _eval_simple_const(match.group(2))
    if left is None or right is None:
        return None
    return left, right

def _merge_port_ranges(first: Port, second: Port) -> tuple[Port, bool]:
    if (
        first.direction != second.direction
        or first.data_type != second.data_type
        or first.unpacked != second.unpacked
    ):
        return first, False
    if re.sub(r"\s+", "", first.packed) == re.sub(r"\s+", "", second.packed):
        return first, False
    first_dims = split_bracketed_dims(first.packed)
    second_dims = split_bracketed_dims(second.packed)
    if (
        len(first_dims) != 1
        or len(second_dims) != 1
        or ":" not in first_dims[0]
        or ":" not in second_dims[0]
    ):
        return first, False
    first_range = _single_range(first.packed)
    second_range = _single_range(second.packed)
    if first_range is None or second_range is None:
        return second, bool(first.packed or second.packed)
    high = max(first_range[0], first_range[1], second_range[0], second_range[1])
    low = min(first_range[0], first_range[1], second_range[0], second_range[1])
    return Port(
        name=first.name,
        direction=first.direction,
        data_type=first.data_type,
        packed=f"[{high}:{low}]",
        unpacked=first.unpacked,
        interface_type=first.interface_type,
    ), False

MARKERS = {
    "input": re.compile(r"/\*AUTOINPUT(?:\((.*?)\))?\*/", re.S | re.I),
    "output": re.compile(r"/\*AUTOOUTPUT(?:\((.*?)\))?\*/", re.S | re.I),
    "outputevery": re.compile(
        r"/\*AUTOOUTPUTEVERY(?:\((.*?)\))?\*/", re.S | re.I
    ),
    "inout": re.compile(r"/\*AUTOINOUT(?:\((.*?)\))?\*/", re.S | re.I),
    "wire": re.compile(r"/\*AUTOWIRE(?:\((.*?)\))?\*/", re.S | re.I),
    "logic": re.compile(r"/\*AUTOLOGIC(?:\((.*?)\))?\*/", re.S | re.I),
    "reginput": re.compile(r"/\*AUTOREGINPUT(?:\((.*?)\))?\*/", re.S | re.I),
}
AUTOINST_RE = re.compile(r"/\*AUTOINST(?:\((.*?)\))?\*/", re.S | re.I)

BEGIN_TEXT = {
    "input": "inputs (from unused autoinst inputs)",
    "output": "outputs (from unused autoinst outputs)",
    "outputevery": "outputs (every signal)",
    "inout": "inouts (from unused autoinst inouts)",
    "wire": "wires (for undeclared instantiated-module outputs)",
    "logic": "wires (for undeclared instantiated-module outputs)",
    "reginput": "reg inputs (for undeclared instantiated-module inputs)",
}

NET_TYPE_WORDS = {
    "wire",
    "reg",
    "tri",
    "supply0",
    "supply1",
    "wand",
    "wor",
    "triand",
    "trior",
    "tri0",
    "tri1",
    "uwire",
}
TYPE_QUALIFIERS = {"signed", "unsigned"}
CHILD_PORT_DECL_STRIP_WORDS = {"wire", "reg", "var"}

def _auto_ignore_concat(text: str) -> bool:
    return re.search(r"\bverilog-auto-ignore-concat\s*:\s*t\b", text) is not None

def _auto_declare_nettype(text: str) -> str:
    match = re.search(r'\bverilog-auto-declare-nettype\s*:\s*"([^"]+)"', text)
    return match.group(1).strip() if match else ""

def _auto_output_ignore_regexp(text: str) -> str:
    match = re.search(r'\bverilog-auto-output-ignore-regexp\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""

def _with_decl_nettype(port: Port, nettype: str) -> Port:
    if not nettype or port.data_type or port.direction not in {"input", "output", "inout"}:
        return port
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=nettype,
        packed=port.packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )

def _strip_child_nettype(port: Port) -> Port:
    words = port.data_type.split()
    if not words or words[0] not in CHILD_PORT_DECL_STRIP_WORDS:
        return port
    kept = [word for word in words if word not in CHILD_PORT_DECL_STRIP_WORDS]
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=" ".join(kept),
        packed=port.packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )

def _declaration_port_from_child(port: Port, declare_nettype: str) -> Port:
    return _with_decl_nettype(_strip_child_nettype(port), declare_nettype)

def _port_with_template_param_names(port: Port, param_map: dict[str, str]) -> Port:
    if not param_map:
        return port
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=port.data_type,
        packed=_replace_param_names(port.packed, param_map),
        unpacked=_replace_param_names(port.unpacked, param_map),
        interface_type=port.interface_type,
    )

def _primitive_port_uses(
    port_text: str,
    instance,
    *,
    ignore_concat: bool,
) -> list[PortUse] | None:
    directions = GATE_IOS.get(instance.module)
    if directions is None:
        return None
    marker = AUTOINST_RE.search(port_text)
    if marker is None:
        return []
    manual_text = port_text[: marker.start()]
    uses: list[PortUse] = []
    for idx, actual in enumerate(split_top_level(manual_text)):
        direction = directions[idx] if idx < len(directions) else "input"
        if direction not in {"input", "output", "inout"}:
            continue
        for signal in extract_actual_signals(actual, ignore_concat=ignore_concat):
            uses.append(
                PortUse(
                    port=Port(
                        name=signal.name,
                        direction=direction,
                        packed=signal.packed,
                        unpacked="",
                    ),
                    inst_name=instance.name,
                    module_name=instance.module,
                    primitive=True,
                )
            )
    return uses

def _named_connection_actuals(port_text: str) -> dict[str, str]:
    masked = mask_syntax(port_text)
    actuals: dict[str, str] = {}
    for match in re.finditer(r"\.\s*(" + IDENT_RE.pattern + r")\s*\(", masked):
        name = port_text[match.start(1) : match.end(1)].strip()
        open_pos = match.end() - 1
        close_pos = find_matching(port_text, open_pos)
        if close_pos is None:
            continue
        actuals[name] = port_text[open_pos + 1 : close_pos].strip()
    return actuals

def _uses_from_actual(
    port: Port,
    decl_port: Port,
    actual: str,
    instance,
    *,
    ignore_concat: bool,
    use_decl_packed: bool = True,
) -> list[PortUse]:
    uses: list[PortUse] = []
    for signal in extract_actual_signals(actual, ignore_concat=ignore_concat):
        uses.append(
            PortUse(
                port=Port(
                    name=signal.name,
                    direction=port.direction,
                    data_type=decl_port.data_type,
                    packed=signal.packed
                    or (
                        decl_port.packed
                        if use_decl_packed and signal.use_port_packed
                        else ""
                    ),
                    unpacked=signal.unpacked
                    or (decl_port.unpacked if use_decl_packed else ""),
                ),
                inst_name=instance.name,
                module_name=instance.module,
            )
        )
    return uses

def _auto_wire_type(text: str, module_text: str) -> str:
    match = re.search(r'\bverilog-auto-wire-type\s*:\s*"([^"]+)"', text)
    if match is not None:
        return match.group(1).strip()
    if re.search(r"/\*AUTOLOGIC(?:\([^*]*\))?\*/", module_text, re.I):
        return "logic"
    return ""

def _split_decl_type(data_type: str) -> tuple[str, list[str]]:
    words = data_type.split()
    if words and words[0] not in NET_TYPE_WORDS | {"logic"} | TYPE_QUALIFIERS:
        return "custom", words
    return "builtin", [
        word for word in words if word not in NET_TYPE_WORDS and word != "logic"
    ]

def _eval_const_expr(expr: str) -> str | None:
    expr = expr.strip()
    if not re.fullmatch(r"[0-9+\-*/%() \t]+", expr):
        return None
    try:
        return str(int(eval(expr.replace("/", "//"), {"__builtins__": {}}, {})))
    except Exception:
        return None

def _simplify_dim(dim: str, *, eval_constants: bool = True) -> str:
    stripped = dim.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return dim
    parts = split_top_level(stripped[1:-1], ":")
    if len(parts) != 2:
        return dim
    left_text = _light_simplify_expr(parts[0])
    right_text = _light_simplify_expr(parts[1])
    if not eval_constants:
        return f"[{left_text}:{right_text}]"
    left = _eval_const_expr(left_text)
    right = _eval_const_expr(right_text)
    if left is None or right is None:
        return f"[{left_text}:{right_text}]"
    return f"[{left}:{right}]"

def _simplify_packed_dims(port: Port) -> Port:
    dims = split_bracketed_dims(port.packed)
    if not dims:
        return port
    if len(dims) == 1:
        packed = _simplify_dim(dims[0], eval_constants=False)
    else:
        packed = " ".join([dims[0], *(_simplify_dim(dim) for dim in dims[1:])])
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=port.data_type,
        packed=packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )

def _port_for_declaration_kind(port: Port, kind: str, wire_type: str) -> Port:
    if kind == "outputevery":
        kind = "output"
    port = _simplify_packed_dims(port)
    type_kind, words = _split_decl_type(port.data_type)
    if kind == "logic":
        if type_kind == "custom":
            return Port(
                name=port.name,
                direction="",
                data_type=port.data_type,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
        return Port(
            name=port.name,
            direction="logic",
            data_type=" ".join(words),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    if kind == "reginput":
        if type_kind == "custom":
            return Port(
                name=port.name,
                direction="",
                data_type=port.data_type,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
        return Port(
            name=port.name,
            direction="logic",
            data_type=" ".join(words),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    if kind == "wire":
        if type_kind == "custom":
            return Port(
                name=port.name,
                direction="",
                data_type=port.data_type,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
        direction = (
            "logic"
            if wire_type == "logic"
            or (wire_type != "wire" and port.data_type.split()[:1] == ["logic"])
            else "wire"
        )
        return Port(
            name=port.name,
            direction=direction,
            data_type=" ".join(words),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    if wire_type == "wire" and kind in {"input", "output", "inout"} and type_kind != "custom":
        return Port(
            name=port.name,
            direction=port.direction,
            data_type=" ".join(words),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    if wire_type == "logic" and kind in {"input", "output", "inout"} and type_kind != "custom":
        return Port(
            name=port.name,
            direction=port.direction,
            data_type=" ".join(["logic", *words]),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    return port

def _collect_port_uses_for_module(
    text: str,
    library: ModuleLibrary,
    module,
    *,
    ignore_concat: bool,
    declare_nettype: str,
) -> dict[str, list[PortUse]]:
    result: dict[str, list[PortUse]] = {"input": [], "output": [], "inout": []}
    for instance in module.instances:
        port_text = text[instance.port_open + 1 : instance.port_close]
        primitive_uses = _primitive_port_uses(
            port_text,
            instance,
            ignore_concat=ignore_concat,
        )
        if primitive_uses is not None:
            for use in primitive_uses:
                result[use.port.direction].append(use)
            continue
        child = library.lookup(instance.module)
        if child is None:
            continue
        auto_match = AUTOINST_RE.search(port_text)
        has_auto = auto_match is not None
        auto_filter = _regexp_arg(auto_match) if auto_match is not None else ""
        if auto_match is not None:
            manual_text = port_text[: auto_match.start()]
        else:
            manual_text = port_text
        manual, has_star = parse_named_connections(manual_text)
        if not has_auto and not has_star:
            continue
        manual_actuals = _named_connection_actuals(manual_text)
        template = find_template_for_instance(text, instance)
        param_map = _template_param_map_child(child, template, instance)
        skip_template_param_map = (
            inst_param_value_enabled(text, instance.start)
            and bool(instance_param_values(text, instance))
        )
        for child_port in child.ports:
            port = child_port
            if inst_param_value_enabled(text, instance.start):
                port = port_with_param_values(port, child.params, text, instance)
            if (
                not skip_template_param_map
                and inst_param_value_enabled(text, instance.start)
            ):
                port = _port_with_template_param_names(port, param_map)
            if port.direction in result:
                decl_port = _declaration_port_from_child(port, declare_nettype)
                if port.name in manual:
                    actual = manual_actuals.get(port.name)
                    if actual is not None:
                        templated_actual, templated = actual_for_port(
                            port,
                            template,
                            instance=instance,
                        )
                        use_decl_packed = not (
                            has_star
                            and templated
                            and actual.strip() == templated_actual.strip()
                        )
                        result[port.direction].extend(
                            _uses_from_actual(
                                port,
                                decl_port,
                                actual,
                                instance,
                                ignore_concat=ignore_concat,
                                use_decl_packed=use_decl_packed,
                            )
                        )
                    continue
                if has_auto and not _matches_name_filter(port.name, auto_filter):
                    continue
                if is_nohookup(port, template):
                    continue
                actual, templated = actual_for_port(port, template, instance=instance)
                if templated:
                    result[port.direction].extend(
                        _uses_from_actual(
                            port,
                            decl_port,
                            actual,
                            instance,
                            ignore_concat=ignore_concat,
                            use_decl_packed=False,
                        )
                    )
                else:
                    result[port.direction].append(
                        PortUse(
                            port=decl_port,
                            inst_name=instance.name,
                            module_name=instance.module,
                        )
                    )
    for direction, uses in result.items():
        result[direction] = _merge_duplicate_uses(uses)
    return result

def _existing_names_for_module(module) -> set[str]:
    return module.declared_names()

def _output_signal_uses(module) -> list[PortUse]:
    existing_ports = {port.name for port in module.ports}
    uses: list[PortUse] = []
    for signal in module.signals:
        if signal.name in existing_ports:
            continue
        port = _strip_child_nettype(
            Port(
                name=signal.name,
                direction="output",
                data_type=signal.data_type,
                packed=signal.packed,
                unpacked=signal.unpacked,
                interface_type=signal.interface_type,
            )
        )
        uses.append(
            PortUse(
                port=port,
                inst_name="",
                module_name="",
                comment="",
            )
        )
    return uses

def _comment_for(use: PortUse, *, file_suffix: bool = True) -> str:
    if use.comment is not None:
        return use.comment
    if use.primitive:
        module_name = use.module_name
    else:
        module_name = f"{use.module_name}.v" if file_suffix else use.module_name
    suffix = ", ..." if use.multiple else ""
    if use.port.direction == "input":
        return f"// To {use.inst_name} of {module_name}{suffix}"
    if use.port.direction == "output":
        return f"// From {use.inst_name} of {module_name}{suffix}"
    return f"// To/From {use.inst_name} of {module_name}{suffix}"

def _format_block(indent: str, kind: str, uses: list[PortUse], wire_type: str = "") -> str:
    if not uses:
        return ""
    lines = [
        f"\n{indent}// Beginning of automatic {BEGIN_TEXT[kind]}",
    ]
    for use in sorted(uses, key=lambda item: item.port.name):
        port = _port_for_declaration_kind(use.port, kind, wire_type)
        comment = _comment_for(use)
        lines.append("\n" + format_declaration(indent, port, comment))
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)

def _format_header_block(
    indent: str,
    kind: str,
    uses: list[PortUse],
    *,
    trailing_comma: bool = False,
    wire_type: str = "",
) -> str:
    if not uses:
        return ""
    lines = [
        f"\n{indent}// Beginning of automatic {BEGIN_TEXT[kind]}",
    ]
    sorted_uses = sorted(uses, key=lambda use: use.port.name)
    for idx, use in enumerate(sorted_uses):
        port = _port_for_declaration_kind(use.port, kind, wire_type)
        prefix = declaration_prefix(port)
        raw_terminator = "," if idx != len(sorted_uses) - 1 or trailing_comma else ""
        name = format_identifier(port.name, terminator="")
        terminator = format_identifier(port.name, terminator=raw_terminator)[len(port.name) :]
        comment = _comment_for(use, file_suffix=True)
        suffix = f" {comment}" if comment else ""
        lines.append(
            f"\n{indent}{prefix} {name}{port.unpacked}{terminator}{suffix}"
        )
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)

def _matches_name_filter(name: str, regexp: str) -> bool:
    if not regexp:
        return True
    invert = regexp.startswith("?!")
    if invert:
        regexp = regexp[2:]
    regexp = _emacs_regexp_to_python(regexp)
    try:
        matched = re.search(regexp, name) is not None
    except re.error:
        return False
    return not matched if invert else matched

def _matches_marker_filter_name(use: PortUse, regexp: str) -> bool:
    return _matches_name_filter(use.port.name, regexp)

def _existing_for_marker(
    marker_kind: str, existing_ports: set[str], existing_all: set[str]
) -> set[str]:
    if marker_kind in {"output", "outputevery"}:
        return existing_ports
    return existing_all

def expand_declarations(text: str, library: ModuleLibrary) -> str:
    modules = parse_modules(text)
    replacements: list[tuple[int, str]] = []
    ignore_concat = _auto_ignore_concat(text)
    declare_nettype = _auto_declare_nettype(text)
    output_ignore_regexp = _auto_output_ignore_regexp(text)

    for module in modules:
        uses_by_direction = _collect_port_uses_for_module(
            text,
            library,
            module,
            ignore_concat=ignore_concat,
            declare_nettype=declare_nettype,
        )
        outputevery_uses = uses_by_direction["output"] + _output_signal_uses(module)
        names_by_direction = {
            direction: {use.port.name for use in uses}
            for direction, uses in uses_by_direction.items()
        }
        planned: set[str] = set()
        existing_ports = {port.name for port in module.ports} | {
            param.name for param in module.params
        } | planned
        existing_all = _existing_names_for_module(module) | planned
        module_text = text[module.start : module.end]
        wire_type = _auto_wire_type(text, module_text)
        marker_matches: list[tuple[int, str, re.Match[str]]] = []
        for kind, regex in MARKERS.items():
            for match in regex.finditer(module_text):
                marker_matches.append((module.start + match.start(), kind, match))
        for abs_start, kind, match in sorted(marker_matches):
            def marker_candidates(marker_kind: str, marker_match: re.Match[str], existing_names: set[str]) -> list[PortUse]:
                if marker_kind in {"input", "output", "inout"}:
                    candidates = uses_by_direction[marker_kind]
                elif marker_kind == "outputevery":
                    candidates = outputevery_uses
                elif marker_kind == "reginput":
                    candidates = uses_by_direction["input"]
                else:
                    candidates = uses_by_direction["output"] + uses_by_direction["inout"]
                selected_uses: list[PortUse] = []
                regexp = _regexp_arg(marker_match)
                for use in candidates:
                    if marker_kind in {"input", "reginput"} and (
                        use.port.name in names_by_direction["output"]
                        or use.port.name in names_by_direction["inout"]
                    ):
                        continue
                    if marker_kind == "output" and (
                        use.port.name in names_by_direction["input"]
                        or use.port.name in names_by_direction["inout"]
                    ):
                        continue
                    if marker_kind == "output" and not _matches_name_filter(
                        use.port.name,
                        "?!" + output_ignore_regexp if output_ignore_regexp else "",
                    ):
                        continue
                    if use.port.name in existing_names:
                        continue
                    if not _matches_marker_filter_name(use, regexp):
                        continue
                    selected_uses.append(use)
                return selected_uses

            selected = marker_candidates(
                kind,
                match,
                _existing_for_marker(kind, existing_ports, existing_all),
            )
            if kind != "outputevery":
                for use in selected:
                    existing_ports.add(use.port.name)
                    existing_all.add(use.port.name)
                    planned.add(use.port.name)
            if not selected:
                continue
            indent = line_indent_at(text, abs_start)
            in_header = (
                kind in {"input", "output", "outputevery", "inout"}
                and module.header_port_open is not None
                and module.header_port_close is not None
                and module.header_port_open < abs_start < module.header_port_close
            )
            if in_header:
                trailing_comma = any(
                    later_start > abs_start
                    and module.header_port_open < later_start < module.header_port_close
                    and bool(
                        marker_candidates(
                            later_kind,
                            later_match,
                            _existing_for_marker(
                                later_kind, existing_ports, existing_all
                            ),
                        )
                    )
                    for later_start, later_kind, later_match in marker_matches
                )
                insertion = _format_header_block(
                    indent,
                    kind,
                    selected,
                    trailing_comma=trailing_comma,
                    wire_type=wire_type,
                )
            else:
                insertion = _format_block(indent, kind, selected, wire_type)
            replacements.append((module.start + match.end(), insertion))

    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

# -- AUTO: Modport --------------------------------------------------

INOUTMODPORT_RE = re.compile(r"/\*AUTOINOUTMODPORT\((.*?)\)\*/", re.S)
ASSIGNMODPORT_RE = re.compile(r"/\*AUTOASSIGNMODPORT\((.*?)\)\*/", re.S)

def _parse_args(arg_text: str) -> list[str]:
    quoted = re.findall(r'"((?:\\.|[^"])*)"', arg_text)
    if quoted:
        return quoted
    args: list[str] = []
    for item in split_top_level(arg_text):
        item = item.strip()
        if len(item) >= 2 and item[0] == '"' and item[-1] == '"':
            item = item[1:-1]
        args.append(item)
    return args

def _signal_map(interface) -> dict[str, Port]:
    result: dict[str, Port] = {}
    for signal in interface.signals:
        if signal.direction:
            continue
        result[signal.name] = signal
    return result

def _modport_entries(interface, modport: str) -> list[tuple[str, str]]:
    if modport in interface.modports:
        return interface.modports.get(modport, [])
    entries: list[tuple[str, str]] = []
    try:
        regex = re.compile(modport)
    except re.error:
        return entries
    for name, modport_entries in interface.modports.items():
        if name.endswith("_cb") or name.endswith("_clkblk"):
            continue
        if regex.match(name):
            entries.extend(modport_entries)
    return entries

def _decl_direction(direction: str) -> str:
    if direction.startswith("clocking_"):
        return direction.removeprefix("clocking_")
    return direction

def _module_port_from_modport(signal: Port, direction: str, prefix: str) -> Port:
    return Port(
        name=f"{prefix}{signal.name}",
        direction=_decl_direction(direction),
        data_type=signal.data_type,
        packed=signal.packed,
        unpacked=signal.unpacked,
    )

def _format_header_port(indent: str, port: Port, terminator: str) -> str:
    pieces = [port.direction]
    if port.data_type and port.data_type != "logic":
        pieces.append(port.data_type)
    if port.packed:
        pieces.append(port.packed)
    prefix = " ".join(piece for piece in pieces if piece)
    return f"{indent}{prefix:<12}{port.name}{terminator}"

def _format_inoutmodport_block(indent: str, interface, modport: str, prefix: str) -> str:
    entries = _modport_entries(interface, modport)
    if not entries:
        return ""
    signals = _signal_map(interface)
    lines = [f"\n{indent}// Beginning of automatic in/out/inouts (from modport)"]
    for direction in ("output", "inout", "input"):
        for signal_name, entry_direction in entries:
            if _decl_direction(entry_direction) != direction or signal_name not in signals:
                continue
            port = _module_port_from_modport(signals[signal_name], direction, prefix)
            lines.append("\n" + format_declaration(indent, port))
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)

def _format_inoutmodport_header_block(
    indent: str,
    interface,
    modport: str,
    prefix: str,
    existing: set[str] | None = None,
    trailing_comma: bool = False,
) -> str:
    entries = _modport_entries(interface, modport)
    if not entries:
        return ""
    signals = _signal_map(interface)
    ports: list[Port] = []
    existing = existing or set()
    for direction in ("output", "inout", "input"):
        for signal_name, entry_direction in entries:
            if _decl_direction(entry_direction) != direction or signal_name not in signals:
                continue
            port = _module_port_from_modport(signals[signal_name], direction, prefix)
            if port.name in existing:
                continue
            ports.append(port)
    if not ports:
        return ""
    lines = [f"\n{indent}// Beginning of automatic in/out/inouts (from modport)"]
    for idx, port in enumerate(ports):
        terminator = "," if idx != len(ports) - 1 or trailing_comma else ""
        lines.append("\n" + _format_header_port(indent, port, terminator))
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)

def _format_assignmodport_block(
    indent: str, interface, modport: str, inst_name: str, prefix: str
) -> str:
    entries = _modport_entries(interface, modport)
    if not entries:
        return ""
    signals = _signal_map(interface)
    lines = [f"\n{indent}// Beginning of automatic assignments from modport"]
    emitted: set[str] = set()
    for direction in ("output", "inout", "input"):
        matching_entries = [
            (signal_name, entry_direction)
            for signal_name, entry_direction in entries
            if _decl_direction(entry_direction) == direction
        ]
        for signal_name, entry_direction in sorted(matching_entries):
            if signal_name not in signals:
                continue
            emit_key = f"{entry_direction}:{signal_name}"
            if emit_key in emitted:
                continue
            emitted.add(emit_key)
            local = f"{prefix}{signal_name}"
            remote = f"{inst_name}.{signal_name}"
            if entry_direction == "clocking_input":
                lines.append(f"\n{indent}assign {remote} = {local};")
            elif entry_direction == "clocking_output":
                lines.append(f"\n{indent}assign {local} = {remote};")
            elif direction == "input":
                lines.append(f"\n{indent}assign {local} = {remote};")
            else:
                lines.append(f"\n{indent}assign {remote} = {local};")
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)

def expand_modport(text: str, library: ModuleLibrary) -> str:
    replacements: list[tuple[int, str]] = []
    modules = parse_modules(text)
    for match in INOUTMODPORT_RE.finditer(text):
        args = _parse_args(match.group(1))
        if len(args) < 2:
            continue
        interface = library.lookup(args[0])
        if interface is None:
            continue
        prefix = args[3] if len(args) > 3 else ""
        indent = line_indent_at(text, match.start())
        in_header = any(
            module.header_port_open is not None
            and module.header_port_close is not None
            and module.header_port_open < match.start() < module.header_port_close
            for module in modules
        )
        if in_header:
            current_module = next(
                module
                for module in modules
                if module.header_port_open is not None
                and module.header_port_close is not None
                and module.header_port_open < match.start() < module.header_port_close
            )
            insertion = _format_inoutmodport_header_block(
                indent,
                interface,
                args[1],
                prefix,
                existing=current_module.declared_names(),
                trailing_comma=re.search(
                    r"/\*AUTOINOUTMODPORT\b",
                    text[match.end() : current_module.header_port_close],
                    re.I,
                )
                is not None,
            )
        else:
            insertion = _format_inoutmodport_block(indent, interface, args[1], prefix)
        replacements.append(
            (match.end(), insertion)
        )
    for match in ASSIGNMODPORT_RE.finditer(text):
        args = _parse_args(match.group(1))
        if len(args) < 3:
            continue
        interface = library.lookup(args[0])
        if interface is None:
            continue
        prefix = args[4] if len(args) > 4 else ""
        indent = line_indent_at(text, match.start())
        replacements.append(
            (
                match.end(),
                _format_assignmodport_block(indent, interface, args[1], args[2], prefix),
            )
        )
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

# -- AUTO: Sense --------------------------------------------------

AUTOSENSE_RE = re.compile(r"/\*AUTOSENSE\*/")
KEYWORDS = {
    "begin",
    "case",
    "default",
    "else",
    "end",
    "endcase",
    "for",
    "if",
    "or",
}

def _find_block_end(text: str, begin_pos: int) -> int:
    masked = mask_syntax(text)
    token_re = re.compile(r"\bbegin\b|\bend\b")
    depth = 0
    for match in token_re.finditer(masked, begin_pos):
        token = match.group(0)
        if token == "begin":
            depth += 1
        elif token == "end":
            depth -= 1
            if depth == 0:
                return match.end()
    return len(text)

def _assigned_names(body: str) -> set[str]:
    assigned: set[str] = set()
    masked = mask_syntax(body)
    for match in re.finditer(r"\b(" + IDENT_RE.pattern + r")\s*(?:\[[^\]]+\]\s*)?(?:<)?=", masked):
        name = body[match.start(1) : match.end(1)]
        assigned.add(name)
    return assigned

def _read_names(body: str) -> list[str]:
    assigned = _assigned_names(body)
    names: set[str] = set()
    for match in IDENT_RE.finditer(mask_syntax(body)):
        name = body[match.start() : match.end()]
        if name in KEYWORDS or name in assigned:
            continue
        names.add(name)
    return sorted(names)

def expand_autosense(text: str) -> str:
    replacements: list[tuple[int, int, str]] = []
    for match in AUTOSENSE_RE.finditer(text):
        close = find_matching(text, text.find("(", 0, match.start()))
        sense_close = text.find(")", match.end())
        if sense_close == -1:
            continue
        begin_match = re.search(r"\bbegin\b", mask_syntax(text)[sense_close:])
        if begin_match is None:
            continue
        begin_pos = sense_close + begin_match.start()
        end_pos = _find_block_end(text, begin_pos)
        names = _read_names(text[begin_pos:end_pos])
        if not names:
            continue
        del close
        replacements.append((match.end(), sense_close, " or " + " or ".join(names)))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text

# -- AUTO: Stub/Helpers --------------------------------------------------

INOUTPARAM_RE = re.compile(r"/\*AUTOINOUTPARAM\((.*?)\)\*/", re.S)
INOUTMODULE_RE = re.compile(r"/\*AUTOINOUTMODULE\((.*?)\)\*/", re.S)
INOUTCOMP_RE = re.compile(r"/\*AUTOINOUTCOMP\(\"([^\"]+)\"\)\*/")
INOUTIN_RE = re.compile(r"/\*AUTOINOUTIN\(\"([^\"]+)\"\)\*/")
AUTOTIEOFF_RE = re.compile(r"/\*AUTOTIEOFF\*/")
AUTOUNUSED_RE = re.compile(r"/\*AUTOUNUSED\*/")
AUTOUNDEF_RE = re.compile(r"/\*AUTOUNDEF\*/")
DEFINE_RE = re.compile(r"^[ \t]*`define\s+([A-Za-z_][$A-Za-z0-9_]*)", re.M)
NET_TYPE_WORDS = {"wire", "reg", "logic"}
PORT_TYPE_TO_LOGIC = {"wire", "reg"}

def _parse_args_marker(arg_text: str) -> list[str]:
    args: list[str] = []
    for item in split_top_level(arg_text):
        item = item.strip()
        if len(item) >= 2 and item[0] == '"' and item[-1] == '"':
            item = item[1:-1]
        args.append(item)
    return args

def _emacs_regex(pattern: str) -> str:
    return (
        pattern.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\|", "|")
    )

def _matches_optional(
    name: str, include: str = "", ignore: str = "", direction: str = "", direction_include: str = ""
) -> bool:
    if include:
        try:
            if re.search(_emacs_regex(include), name) is None:
                return False
        except re.error:
            return False
    if ignore:
        try:
            if re.search(_emacs_regex(ignore), name) is not None:
                return False
        except re.error:
            return False
    if direction_include:
        try:
            if re.search(_emacs_regex(direction_include), direction) is None:
                return False
        except re.error:
            return False
    return True

def _group_ports(ports: list[Port]) -> list[Port]:
    grouped: list[Port] = []
    for direction in ("output", "inout", "input"):
        grouped.extend(port for port in ports if port.direction == direction)
    grouped.extend(port for port in ports if not port.direction and port.interface_type)
    return grouped

def _logic_wire_type_enabled(text: str) -> bool:
    if re.search(r'\bverilog-auto-wire-type\s*:\s*"logic"', text):
        return True
    return re.search(r"/\*AUTOLOGIC(?:\([^*]*\))?\*/", text, re.I) is not None

def _inout_helper_port(port: Port, *, logic_wire_type: bool = False) -> Port:
    if port.interface_type:
        return port
    words = port.data_type.split()
    if not words or words[0] not in PORT_TYPE_TO_LOGIC:
        return port
    kept = [word for word in words if word not in PORT_TYPE_TO_LOGIC]
    data_type = " ".join(kept)
    if port.direction in {"input", "output"} and logic_wire_type:
        data_type = " ".join(["logic", *kept])
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=data_type,
        packed=port.packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )

def _format_inout_header_line(
    indent: str,
    port: Port,
    *,
    terminator: str = "",
    logic_wire_type: bool = False,
) -> str:
    prefix = declaration_prefix(_inout_helper_port(port, logic_wire_type=logic_wire_type))
    name = format_identifier(port.name, terminator=terminator)
    return f"\n{indent}{prefix} {name}"

def _expand_inout_param(text: str, library: ModuleLibrary) -> str:
    replacements: list[tuple[int, str]] = []
    planned: set[str] = set()
    for match in INOUTPARAM_RE.finditer(text):
        args = _parse_args(match.group(1))
        if not args:
            continue
        module = library.lookup(args[0])
        if module is None or not module.params:
            continue
        include = args[1] if len(args) > 1 else ""
        params = [
            param
            for param in module.params
            if param.name not in planned and _matches_optional(param.name, include)
        ]
        if not params:
            continue
        indent = line_indent_at(text, match.start())
        lines = [f"\n{indent}// Beginning of automatic parameters (from specific module)"]
        for param in params:
            lines.append("\n" + format_parameter(indent, param))
            planned.add(param.name)
        lines.append(f"\n{indent}// End of automatics")
        replacements.append((match.end(), "".join(lines)))
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

def _expand_inout_module(text: str, library: ModuleLibrary) -> str:
    modules = parse_modules(text)
    replacements: list[tuple[int, str]] = []
    logic_wire_type = _logic_wire_type_enabled(text)
    for match in INOUTMODULE_RE.finditer(text):
        args = _parse_args(match.group(1))
        if not args:
            continue
        module = library.lookup(args[0])
        if module is None or not module.ports:
            continue
        indent = line_indent_at(text, match.start())
        lines = [f"\n{indent}// Beginning of automatic in/out/inouts (from specific module)"]
        in_header = any(
            current.header_port_open is not None
            and current.header_port_close is not None
            and current.header_port_open < match.start() < current.header_port_close
            for current in modules
        )
        include = args[1] if len(args) > 1 else ""
        direction_include = args[2] if len(args) > 2 else ""
        ignore = args[3] if len(args) > 3 else ""
        grouped_ports = [
            port
            for port in _group_ports(module.ports)
            if _matches_optional(
                port.name,
                include,
                ignore,
                direction=port.direction,
                direction_include=direction_include,
            )
        ]
        if in_header:
            for idx, port in enumerate(grouped_ports):
                terminator = "," if idx != len(grouped_ports) - 1 else ""
                lines.append(
                    _format_inout_header_line(
                        indent,
                        port,
                        terminator=terminator,
                        logic_wire_type=logic_wire_type,
                    )
                )
        else:
            for port in grouped_ports:
                lines.append(
                    "\n"
                    + format_declaration(
                        indent,
                        _inout_helper_port(
                            port, logic_wire_type=logic_wire_type
                        ),
                    )
                )
        lines.append(f"\n{indent}// End of automatics")
        replacements.append((match.end(), "".join(lines)))
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

def _complement_port(port: Port) -> Port:
    direction = {
        "input": "output",
        "output": "input",
        "inout": "inout",
    }.get(port.direction, port.direction)
    return Port(
        name=port.name,
        direction=direction,
        data_type=port.data_type,
        packed=port.packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )

def _expand_inout_comp(text: str, library: ModuleLibrary) -> str:
    modules = parse_modules(text)
    replacements: list[tuple[int, str]] = []
    logic_wire_type = _logic_wire_type_enabled(text)
    for match in INOUTCOMP_RE.finditer(text):
        ref_module = library.lookup(match.group(1))
        current = next(
            (module for module in modules if module.start <= match.start() <= module.end),
            None,
        )
        if ref_module is None or current is None:
            continue
        existing = {port.name for port in current.ports}
        ports = _group_ports([
            _complement_port(port)
            for port in _group_ports(ref_module.ports)
            if port.name not in existing
        ])
        if not ports:
            continue
        indent = line_indent_at(text, match.start())
        lines = [f"\n{indent}// Beginning of automatic in/out/inouts (from specific module)"]
        in_header = any(
            current_module.header_port_open is not None
            and current_module.header_port_close is not None
            and current_module.header_port_open < match.start() < current_module.header_port_close
            for current_module in modules
        )
        if in_header:
            for idx, port in enumerate(ports):
                terminator = "," if idx != len(ports) - 1 else ""
                lines.append(
                    _format_inout_header_line(
                        indent,
                        port,
                        terminator=terminator,
                        logic_wire_type=logic_wire_type,
                    )
                )
        else:
            for port in ports:
                lines.append(
                    "\n"
                    + format_declaration(
                        indent,
                        _inout_helper_port(
                            port, logic_wire_type=logic_wire_type
                        ),
                    )
                )
        lines.append(f"\n{indent}// End of automatics")
        replacements.append((match.end(), "".join(lines)))
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

def _expand_inout_in(text: str, library: ModuleLibrary) -> str:
    replacements: list[tuple[int, str]] = []
    for match in INOUTIN_RE.finditer(text):
        ref_module = library.lookup(match.group(1))
        if ref_module is None:
            continue
        ordered_ref_ports: list[Port] = []
        for direction in ("input", "inout", "output"):
            ordered_ref_ports.extend(
                port for port in ref_module.ports if port.direction == direction
            )
        ports = [
            Port(
                name=port.name,
                direction="input",
                data_type=port.data_type,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
            for port in ordered_ref_ports
        ]
        if not ports:
            continue
        indent = line_indent_at(text, match.start())
        lines = [f"\n{indent}// Beginning of automatic in/out/inouts (from specific module)"]
        for port in ports:
            lines.append("\n" + format_declaration(indent, port))
        lines.append(f"\n{indent}// End of automatics")
        replacements.append((match.end(), "".join(lines)))
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

def _module_at(text: str, pos: int):
    for module in parse_modules(text):
        if module.start <= pos <= module.end:
            return module
    return None

def _tieoff_mode(text: str) -> str:
    match = re.search(r'\bverilog-auto-tieoff-declaration\s*:\s*"([^"]+)"', text)
    return match.group(1).strip() if match else "wire"

def _tieoff_width(port: Port) -> int | None:
    dims = re.findall(r"\[([^:\]]+):([^:\]]+)\]", port.packed)
    if not dims:
        return 1
    width = 1
    for msb_text, lsb_text in dims:
        try:
            msb = int(msb_text.strip())
            lsb = int(lsb_text.strip())
        except ValueError:
            return None
        width *= abs(msb - lsb) + 1
    return width

def _tieoff_zero(port: Port) -> str:
    width = _tieoff_width(port)
    if width is None:
        return "'0"
    signed = "signed" in port.data_type.split()
    return f"{width}'{'s' if signed else ''}h0"

def _tieoff_wire_port(port: Port) -> Port:
    data_type = " ".join(
        word for word in port.data_type.split() if word not in NET_TYPE_WORDS
    )
    return Port(
        name=port.name,
        direction="wire",
        data_type=data_type,
        packed=port.packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )

def _expand_tieoff(text: str) -> str:
    replacements: list[tuple[int, str]] = []
    mode = _tieoff_mode(text)
    for match in AUTOTIEOFF_RE.finditer(text):
        module = _module_at(text, match.start())
        if module is None:
            continue
        outputs = [port for port in module.ports if port.direction == "output"]
        if not outputs:
            continue
        indent = line_indent_at(text, match.start())
        lines = [
            f"\n{indent}// Beginning of automatic tieoffs (for this module's unterminated outputs)"
        ]
        for port in outputs:
            zero = _tieoff_zero(port)
            if mode == "assign":
                lines.append(f"\n{indent}assign {port.name} = {zero};")
            else:
                wire_port = _tieoff_wire_port(port)
                prefix = declaration_prefix(wire_port)
                name = format_identifier(wire_port.name, terminator="")
                lines.append(
                    f"\n{indent}{prefix:<28}{name}{wire_port.unpacked} = {zero};"
                )
        lines.append(f"\n{indent}// End of automatics")
        replacements.append((match.end(), "".join(lines)))
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

def _expand_unused(text: str) -> str:
    replacements: list[tuple[int, str]] = []
    for match in AUTOUNUSED_RE.finditer(text):
        module = _module_at(text, match.start())
        if module is None:
            continue
        ports: list[Port] = []
        for direction in ("input", "inout"):
            ports.extend(port for port in module.ports if port.direction == direction)
        if not ports:
            continue
        indent = line_indent_at(text, match.start())
        lines = [f"\n{indent}// Beginning of automatic unused inputs"]
        for port in ports:
            lines.append(f"\n{indent}{port.name},")
        lines.append(f"\n{indent}// End of automatics")
        replacements.append((match.end(), "".join(lines)))
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

def _expand_undef(text: str) -> str:
    defines = [match.group(1) for match in DEFINE_RE.finditer(text)]
    if not defines:
        return text
    replacements: list[tuple[int, str]] = []
    for match in AUTOUNDEF_RE.finditer(text):
        indent = line_indent_at(text, match.start())
        lines = [f"\n{indent}// Beginning of automatic undefs"]
        for name in defines:
            lines.append(f"\n{indent}`undef {name}")
        lines.append(f"\n{indent}// End of automatics")
        replacements.append((match.end(), "".join(lines)))
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text

def expand_inout_helpers(text: str, library: ModuleLibrary) -> str:
    text = _expand_inout_param(text, library)
    text = _expand_inout_module(text, library)
    text = _expand_inout_comp(text, library)
    text = _expand_inout_in(text, library)
    text = _expand_tieoff(text)
    text = _expand_unused(text)
    text = _expand_undef(text)
    return text

# -- CLI Entry Point --------------------------------------------------

import argparse
import sys

def run_delete(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(delete_auto(text).rstrip() + "\n", encoding="utf-8")

def run_auto(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = delete_auto(text)
    library = ModuleLibrary.from_top(path, text)
    text = expand_autoinstparam(text, library)
    text = expand_autoinst(text, library)
    text = expand_modport(text, library)
    text = expand_inout_helpers(text, library)
    text = expand_declarations(text, library)
    text = expand_autosense(text)
    text = expand_autoarg(text)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m verilog_mode_py",
        description="Pure Python subset of verilog-mode batch AUTO expansion.",
    )
    parser.add_argument(
        "command",
        choices=("verilog-batch-auto", "verilog-batch-delete-auto"),
    )
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)

    if not args.file.is_file():
        print(f"{args.file}: file not found", file=sys.stderr)
        return 2

    if args.command == "verilog-batch-delete-auto":
        run_delete(args.file)
    else:
        run_auto(args.file)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
