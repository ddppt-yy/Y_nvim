#!/usr/bin/env python3
"""Small Python implementation of verilog-mode batch AUTO expansion.

This is intentionally a batch tool, not an Emacs compatibility layer.  The
public CLI is kept to the two commands requested by the project:

    python3 verilog-mode.py verilog-batch-auto <top_file>
    python3 verilog-mode.py verilog-batch-delete-auto <top_file>
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import sys
from typing import Callable, Iterable

try:
    from sv_parser import SvParser
except ImportError:  # pragma: no cover - only used when executed elsewhere.
    SvParser = None


AUTO_BEGIN_RE = re.compile(r"^\s*// Beginning of automatic", re.IGNORECASE)
AUTO_END_RE = re.compile(r"^\s*// End of automatics", re.IGNORECASE)
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")
AUTO_RE = re.compile(
    r"/\*(AUTO[A-Za-z0-9_]*|auto[a-z0-9_]*)(?:\((.*?)\))?\*/",
    re.DOTALL,
)
DEFINE_RE = re.compile(r"^\s*`define\s+([A-Za-z_][A-Za-z0-9_$]*)", re.MULTILINE)


DIRECTION_ORDER = ("output", "inout", "input")
DECL_NAME_COLUMN = 32
CONNECTION_COLUMN = 40


@dataclasses.dataclass(frozen=True)
class Port:
    name: str
    direction: str = ""
    data_type: str = ""
    packed: str = ""
    unpacked: str = ""
    interface_type: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Param:
    name: str
    value: str = ""
    data_type: str = ""
    packed: str = ""


@dataclasses.dataclass
class ModuleInfo:
    name: str
    ports: list[Port]
    params: list[Param]
    signals: list[Port]
    interface_ports: dict[str, Port]
    modports: dict[str, list[tuple[str, str]]]
    source_path: pathlib.Path | None = None


@dataclasses.dataclass(frozen=True)
class TemplateEntry:
    port_pattern: str
    expr: str
    regex: re.Pattern[str] | None


@dataclasses.dataclass(frozen=True)
class AutoTemplate:
    module: str
    start: int
    instance_regex: re.Pattern[str] | None
    entries: tuple[TemplateEntry, ...]


@dataclasses.dataclass(frozen=True)
class TemplateResult:
    expr: str
    signal: str
    templated: bool = False
    decl_port: Port | None = None


@dataclasses.dataclass(frozen=True)
class Instance:
    module: str
    name: str
    start: int
    port_open: int
    port_close: int
    param_open: int | None = None
    param_close: int | None = None
    auto_vars: tuple[tuple[str, str], ...] = ()


@dataclasses.dataclass(frozen=True)
class ConnectionUse:
    instance: Instance
    port: Port
    signal: str
    templated: bool = False
    expr: str = ""
    decl_port: Port | None = None


@dataclasses.dataclass(frozen=True)
class AutoMarker:
    name: str
    args_text: str
    start: int
    end: int
    line_start: int
    line_end: int
    indent: str
    text: str

    @property
    def args(self) -> list[str]:
        return parse_auto_args(self.args_text)


def clean_dim(value: str | None) -> str:
    if value is None or value == "None":
        return ""
    return value.strip()


def normalize_type(value: str | None) -> str:
    if value is None or value == "None":
        return ""
    return value.strip()


def port_from_tuple(item: tuple) -> Port:
    if len(item) == 2 and isinstance(item[1], list):
        return Port(item[0], "", "", "", "", tuple(item[1]))
    if len(item) >= 5:
        return Port(
            str(item[0]),
            str(item[1]),
            normalize_type(str(item[2])),
            clean_dim(str(item[3])),
            clean_dim(str(item[4])),
        )
    if len(item) >= 4:
        return Port(
            str(item[0]),
            "",
            normalize_type(str(item[1])),
            clean_dim(str(item[2])),
            clean_dim(str(item[3])),
        )
    return Port(str(item[0]))


def param_from_tuple(item: tuple) -> Param:
    return Param(
        str(item[0]),
        str(item[1]) if len(item) > 1 else "",
        normalize_type(str(item[2])) if len(item) > 2 else "",
        clean_dim(str(item[3])) if len(item) > 3 else "",
    )


def module_from_parser_info(info: dict) -> ModuleInfo | None:
    if not info or not info.get("name"):
        return None

    interface = info.get("interface", {})
    interface_ports = {
        port.name: port for port in (port_from_tuple(item)
                                     for item in interface.get("port", []))
    }

    return ModuleInfo(
        name=info["name"],
        ports=[port_from_tuple(item) for item in info.get("port", [])],
        params=[param_from_tuple(item) for item in info.get("para", [])],
        signals=[port_from_tuple(item) for item in info.get("signal", [])],
        interface_ports=interface_ports,
        modports={
            name: [(str(sig), str(direction)) for sig, direction in ports]
            for name, ports in interface.get("modport", {}).items()
        },
    )


def emacs_regex_to_python(pattern: str) -> str:
    """Translate the common AUTO_TEMPLATE Emacs-regexp subset to Python."""
    result = pattern
    result = result.replace(r"\(", "(").replace(r"\)", ")")
    result = result.replace(r"\{", "{").replace(r"\}", "}")
    return result


def compile_template_regex(pattern: str) -> re.Pattern[str] | None:
    if not any(token in pattern for token in (r"\(", ".*", "[", "^", "$", "@")):
        return None
    try:
        return re.compile("^" + emacs_regex_to_python(pattern) + "$")
    except re.error:
        return None


def find_unescaped_char(text: str, target: str) -> int:
    escaped = False
    for index, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == target:
            return index
    return -1


def parse_template_entry(item: str) -> tuple[str, str] | None:
    item = item.strip()
    if not item.startswith("."):
        return None
    body = item[1:].strip()
    open_pos = find_unescaped_char(body, "(")
    if open_pos < 0:
        return None
    close_pos = body.rfind(")")
    if close_pos <= open_pos:
        return None
    port_pattern = body[:open_pos].strip()
    expr = " ".join(body[open_pos + 1:close_pos].strip().split())
    if not port_pattern:
        return None
    return port_pattern, expr


def parse_auto_templates(text: str) -> list[AutoTemplate]:
    templates: list[AutoTemplate] = []
    pattern = re.compile(
        r"/\*\s*([A-Za-z_][A-Za-z0-9_$]*)\s+AUTO_TEMPLATE"
        r"(?:\s+\"([^\"]*)\")?\s*\((.*?)\)\s*;\s*\*/",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        module = match.group(1)
        instance_pattern = match.group(2)
        instance_regex = None
        if instance_pattern:
            try:
                instance_regex = re.compile(emacs_regex_to_python(instance_pattern))
            except re.error:
                instance_regex = None
        entries: list[TemplateEntry] = []
        for item in split_top_level_commas(match.group(3)):
            parsed_entry = parse_template_entry(item)
            if not parsed_entry:
                continue
            port_pattern, expr = parsed_entry
            entries.append(
                TemplateEntry(
                    port_pattern=port_pattern,
                    expr=expr,
                    regex=compile_template_regex(port_pattern),
                )
            )
        templates.append(
            AutoTemplate(module, match.start(), instance_regex, tuple(entries))
        )
    return templates


def instance_number(instance_name: str) -> str:
    match = re.search(r"(\d+)(?!.*\d)", instance_name)
    return match.group(1) if match else ""


def width_expr_from_port(port: Port) -> str:
    dim = port.packed or port.unpacked
    if not dim.startswith("[") or not dim.endswith("]"):
        return "1"
    body = dim[1:-1].strip()
    if ":" not in body:
        return body or "1"
    left, right = [part.strip() for part in body.split(":", 1)]
    if right == "0":
        minus_one = re.fullmatch(r"(.+)-1", left)
        if minus_one:
            return minus_one.group(1).strip()
        if left.isdigit():
            return str(int(left) + 1)
    if left.isdigit() and right.isdigit():
        return str(abs(int(left) - int(right)) + 1)
    return f"({left})-({right})+1"


def substitute_backrefs(expr: str, groups: tuple[str, ...]) -> str:
    def repl(match: re.Match[str]) -> str:
        digits = match.group(1)
        for end in range(len(digits), 0, -1):
            index = int(digits[:end])
            if 1 <= index <= len(groups):
                return groups[index - 1] + digits[end:]
        return match.group(0)

    return re.sub(r"\\([0-9]+)", repl, expr)


def substitute_template_expr(
    expr: str,
    port: Port,
    groups: tuple[str, ...],
    inst: Instance,
    at_value: str,
) -> str:
    result = expr
    for name, value in inst.auto_vars:
        result = result.replace(f'@"{name}"', value)
    result = result.replace('@"vl-cell-name"', inst.name)
    result = result.replace('@"vl-width"', width_expr_from_port(port))
    result = result.replace('@"(downcase vl-name)"', port.name.lower())
    result = substitute_backrefs(result, groups)
    result = result.replace("@", at_value)

    dims = f"{port.packed}{port.unpacked}"
    result = result.replace("[]", dims)
    return result


def base_signal_from_expr(expr: str) -> str:
    match = re.fullmatch(
        r"\s*([A-Za-z_][A-Za-z0-9_$]*)(?:\s*\[[^\]]+\])*\s*",
        expr,
    )
    return match.group(1) if match else ""


def decl_port_from_template_expr(port: Port, expr: str, templated: bool) -> Port:
    if not templated or "[" in expr:
        return port
    return dataclasses.replace(port, packed="", unpacked="")


def template_instance_at_value(
    template: AutoTemplate,
    inst: Instance,
) -> tuple[bool, str]:
    if template.instance_regex is None:
        return True, instance_number(inst.name)
    match = template.instance_regex.search(inst.name)
    if not match:
        return False, ""
    if match.groups():
        return True, match.group(1)
    return True, match.group(0)


def template_port_match(
    entry: TemplateEntry,
    port: Port,
) -> tuple[bool, tuple[str, ...]]:
    if entry.regex is None and "@" not in entry.port_pattern:
        return entry.port_pattern == port.name, ()

    pattern = emacs_regex_to_python(entry.port_pattern)
    pattern = pattern.replace("@", r"([0-9]+)")
    try:
        regex = re.compile("^" + pattern + "$")
    except re.error:
        return False, ()
    match = regex.match(port.name)
    if not match:
        return False, ()
    return True, match.groups()


def find_template_result(
    templates: list[AutoTemplate],
    inst: Instance,
    port: Port,
) -> TemplateResult:
    for template in reversed(templates):
        if template.module != inst.module or template.start > inst.start:
            continue
        instance_ok, at_value = template_instance_at_value(template, inst)
        if not instance_ok:
            continue
        for entry in template.entries:
            matched, groups = template_port_match(entry, port)
            if not matched:
                continue
            expr = substitute_template_expr(entry.expr, port, groups, inst,
                                            at_value)
            return TemplateResult(
                expr,
                base_signal_from_expr(expr),
                True,
                decl_port_from_template_expr(port, expr, True),
            )
        break
    expr = signal_expr_for_port(port)
    return TemplateResult(expr, port.name, False, port)


def split_top_level_commas(text: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(text[start:i].strip())
            start = i + 1
        i += 1
    tail = text[start:].strip()
    if tail:
        items.append(tail)
    return items


def parse_auto_args(args_text: str) -> list[str]:
    if not args_text:
        return []
    args = []
    for item in split_top_level_commas(args_text):
        value = item.strip()
        if ((value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))):
            value = value[1:-1]
        args.append(value)
    return args


def line_bounds(text: str, pos: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    if end < 0:
        end = len(text)
    else:
        end += 1
    return start, end


def line_indent(text: str, line_start: int) -> str:
    i = line_start
    while i < len(text) and text[i] in " \t":
        i += 1
    return text[line_start:i]


def marker_column(text: str, pos: int) -> int:
    return pos - (text.rfind("\n", 0, pos) + 1)


def iter_auto_markers(text: str, wanted: str | None = None) -> Iterable[AutoMarker]:
    wanted_upper = wanted.upper() if wanted else None
    for match in AUTO_RE.finditer(text):
        name = match.group(1).upper()
        if wanted_upper and name != wanted_upper:
            continue
        start, end = line_bounds(text, match.start())
        yield AutoMarker(
            name=name,
            args_text=match.group(2) or "",
            start=match.start(),
            end=match.end(),
            line_start=start,
            line_end=end,
            indent=line_indent(text, start),
            text=match.group(0),
        )


def find_matching_paren(text: str, open_pos: int) -> int:
    depth = 0
    quote: str | None = None
    line_comment = False
    block_comment = False
    i = open_pos
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue

        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch in ('"', "'"):
            quote = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def parse_identifier_at(text: str, pos: int) -> tuple[str, int] | None:
    match = IDENT_RE.match(text, pos)
    if not match:
        return None
    return match.group(0), match.end()


def is_inside_line_comment(text: str, pos: int) -> bool:
    line_start = text.rfind("\n", 0, pos) + 1
    comment = text.find("//", line_start, pos)
    return comment >= 0


def is_preceded_by_keyword(text: str, pos: int, keyword: str) -> bool:
    prefix = text[max(0, pos - len(keyword) - 4):pos]
    return re.search(rf"\b{re.escape(keyword)}\s*$", prefix) is not None


def auto_lisp_vars_before(text: str, pos: int) -> tuple[tuple[str, str], ...]:
    vars_: dict[str, str] = {}
    pattern = re.compile(
        r"/\*\s*AUTO_LISP\s*\(\s*setq\s+([A-Za-z_][A-Za-z0-9_$]*)\s+([^)]+?)\s*\)\s*\*/",
        re.DOTALL,
    )
    for match in pattern.finditer(text, 0, pos):
        value = match.group(2).strip()
        if ((value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))):
            value = value[1:-1]
        vars_[match.group(1)] = value
    return tuple(sorted(vars_.items()))


def find_instances(text: str, module_names: Iterable[str]) -> list[Instance]:
    names = sorted(set(module_names), key=len, reverse=True)
    instances: list[Instance] = []

    for module in names:
        for match in re.finditer(rf"\b{re.escape(module)}\b", text):
            start = match.start()
            if is_inside_line_comment(text, start):
                continue
            if is_preceded_by_keyword(text, start, "module"):
                continue
            pos = skip_ws(text, match.end())
            param_open = None
            param_close = None
            if pos < len(text) and text[pos] == "#":
                pos = skip_ws(text, pos + 1)
                if pos >= len(text) or text[pos] != "(":
                    continue
                param_open = pos
                param_close = find_matching_paren(text, param_open)
                if param_close < 0:
                    continue
                pos = skip_ws(text, param_close + 1)

            parsed = parse_identifier_at(text, pos)
            if not parsed:
                continue
            inst_name, pos = parsed
            if inst_name in {"module", "interface", "AUTO_TEMPLATE"}:
                continue
            pos = skip_ws(text, pos)
            if pos >= len(text) or text[pos] != "(":
                continue
            port_open = pos
            port_close = find_matching_paren(text, port_open)
            if port_close < 0:
                continue
            instances.append(
                Instance(module, inst_name, start, port_open, port_close,
                         param_open, param_close,
                         auto_lisp_vars_before(text, start))
            )

    instances.sort(key=lambda item: item.start)
    deduped: list[Instance] = []
    seen: set[tuple[int, int]] = set()
    for item in instances:
        key = (item.port_open, item.port_close)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def apply_replacements(text: str, replacements: list[tuple[int, int, str]]) -> str:
    if not replacements:
        return text
    replacements = sorted(replacements, key=lambda item: item[0], reverse=True)
    for start, end, value in replacements:
        text = text[:start] + value + text[end:]
    return text


def parse_local_library_dirs(text: str, top_dir: pathlib.Path) -> list[pathlib.Path]:
    dirs = [top_dir]
    match = re.search(
        r"verilog-library-directories\s*:\s*\((.*?)\)",
        text,
        re.DOTALL,
    )
    if match:
        for item in re.findall(r'"([^"]+)"', match.group(1)):
            path = pathlib.Path(item)
            if not path.is_absolute():
                path = top_dir / path
            dirs.append(path)
    result: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for directory in dirs:
        try:
            resolved = directory.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


def parse_local_extensions(text: str) -> set[str]:
    exts = {".v", ".sv", ".vh", ".svh"}
    for flags in re.findall(r"verilog-library-flags\s*:\s*\((.*?)\)", text, re.DOTALL):
        for plus_ext in re.findall(r"\+libext\+([^\"'\s)]+)", flags):
            for ext in plus_ext.split("+"):
                if ext:
                    exts.add(ext if ext.startswith(".") else f".{ext}")
    return exts


def module_info_from_block(name: str, block: str,
                           path: pathlib.Path | None = None) -> ModuleInfo:
    params = [
        Param(param_match.group(1))
        for param_match in re.finditer(
            r"\bparameter\b(?:\s+\w+)?(?:\s+\[[^\]]+\])?\s+"
            r"([A-Za-z_][A-Za-z0-9_$]*)",
            block,
        )
    ]
    ports = parse_declarations(block, directions={"input", "output", "inout"})
    # Backfill ports from ANSI-style module header (e.g. module Sub(input i, output o);)
    header_match = re.match(
        r"\b(?:module|interface)\s+\w+\s*\(\s*(.*?)\s*\)\s*;",
        block, re.DOTALL,
    )
    if header_match:
        header_text = header_match.group(1)
        if header_text.strip():
            existing = {p.name for p in ports}
            for hp in parse_ansi_port_list(header_text):
                if hp.name not in existing:
                    ports.append(hp)
    signals = parse_signal_declarations(block)
    modports: dict[str, list[tuple[str, str]]] = {}
    interface_ports = {port.name: port for port in signals}

    for mod_match in re.finditer(
        r"\bmodport\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\((.*?)\)\s*;",
        block,
        re.DOTALL,
    ):
        entries: list[tuple[str, str]] = []
        for group in split_top_level_commas(mod_match.group(2)):
            group = group.strip()
            dir_match = re.match(r"\b(input|output|inout|ref)\b\s+(.+)", group)
            if not dir_match:
                continue
            direction, names = dir_match.group(1), dir_match.group(2)
            for name_item in split_top_level_commas(names):
                name_match = IDENT_RE.search(name_item)
                if name_match:
                    entries.append((name_match.group(0), direction))
        modports[mod_match.group(1)] = entries

    return ModuleInfo(name, ports, params, signals, interface_ports, modports,
                      path)


def simple_parse_module_files(path: pathlib.Path) -> list[ModuleInfo]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(errors="ignore")

    result: list[ModuleInfo] = []
    pattern = re.compile(
        r"\b(module|interface)\s+([A-Za-z_][A-Za-z0-9_$]*)"
        r"(?P<rest>.*?)(?:endmodule|endinterface)\b",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        result.append(module_info_from_block(match.group(2), match.group(0),
                                             path))
    return result


def simple_parse_module_file(path: pathlib.Path) -> ModuleInfo | None:
    modules = simple_parse_module_files(path)
    return modules[0] if modules else None


class ModuleLibrary:
    def __init__(self, top_file: pathlib.Path, top_text: str):
        self.top_file = top_file.resolve()
        self.top_dir = self.top_file.parent
        self.dirs = parse_local_library_dirs(top_text, self.top_dir)
        self.extensions = parse_local_extensions(top_text)
        self.modules: dict[str, ModuleInfo] = {}
        self._load()

    def _candidate_files(self) -> list[pathlib.Path]:
        files: list[pathlib.Path] = []
        seen: set[pathlib.Path] = set()
        for directory in self.dirs:
            if not directory.is_dir():
                continue
            for path in sorted(directory.iterdir()):
                if not path.is_file() or path.suffix not in self.extensions:
                    continue
                try:
                    resolved = path.resolve()
                except OSError:
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                files.append(resolved)
        return files

    def _parse_file(self, path: pathlib.Path) -> ModuleInfo | None:
        info = None
        if SvParser is not None:
            try:
                info = module_from_parser_info(SvParser(str(path)).get_sv_port())
            except Exception:
                info = None
        if info is None or (not info.ports and not info.params):
            # SvParser returned empty data (likely syntax errors in the file),
            # fall back to regex-based simple parse.
            fallback = simple_parse_module_file(path)
            if fallback is not None:
                # Preserve the SvParser name if present, fallback name otherwise
                if info is not None and info.name:
                    name = info.name
                else:
                    name = fallback.name
                info = dataclasses.replace(fallback, name=name)
        if info is not None:
            info.source_path = path
        return info

    def _parse_all_files(self, path: pathlib.Path) -> list[ModuleInfo]:
        modules: list[ModuleInfo] = []
        first = self._parse_file(path)
        if first is not None:
            modules.append(first)
        for info in simple_parse_module_files(path):
            if all(existing.name != info.name for existing in modules):
                modules.append(info)
        return modules

    def _load(self) -> None:
        for path in self._candidate_files():
            for info in self._parse_all_files(path):
                if not info.name:
                    continue
                self.modules.setdefault(info.name, info)

    def get(self, name: str) -> ModuleInfo | None:
        return self.modules.get(name)


def declaration_prefix(direction: str, data_type: str, packed: str) -> str:
    words = [direction] if direction else []
    if data_type:
        words.append(data_type)
    if packed:
        words.append(packed)
    return " ".join(words)


def declaration_data_type(port: Port, direction: str | None = None) -> str:
    direction = direction or port.direction
    data_type = normalize_type(port.data_type)
    if direction in {"input", "output", "inout"} and data_type == "reg":
        return ""
    if direction == "inout" and data_type == "wire":
        return ""
    return data_type


def is_in_port_list(text: str, pos: int) -> bool:
    """Check if position is inside the module port list."""
    module_match = None
    for match in re.finditer(r"\bmodule\b", text[:pos]):
        module_match = match
    if not module_match:
        return False

    open_paren = text.find("(", module_match.end())
    if open_paren < 0 or open_paren >= pos:
        return False

    depth = 0
    for i in range(open_paren, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return open_paren < pos < i
    return False


def format_declaration(
    port: Port,
    direction: str | None = None,
    name: str | None = None,
    indent: str = "    ",
    comment: str | None = None,
    force_data_type: str | None = None,
    in_port_list: bool = False,
) -> str:
    direction = port.direction if direction is None else direction
    data_type = declaration_data_type(port, direction)
    if force_data_type is not None:
        data_type = force_data_type
    prefix = indent + declaration_prefix(direction, data_type, port.packed)
    target = name or port.name
    if port.unpacked:
        target += port.unpacked
    spaces = " " * max(1, DECL_NAME_COLUMN - len(prefix))
    line = f"{prefix}{spaces}{target}" + ("" if in_port_list else ";")
    if comment:
        line += f" {comment}"
    return line


def format_param_declaration(param: Param, indent: str = "    ") -> str:
    prefix = indent + "parameter"
    spaces = " " * max(1, DECL_NAME_COLUMN - len(prefix))
    return f"{prefix}{spaces}{param.name};"


def signal_expr_for_port(port: Port, signal: str | None = None) -> str:
    base = signal or port.name
    return f"{base}{port.packed}{port.unpacked}"


def format_connection(
    port: Port,
    indent: str,
    is_last: bool,
    expr: str | None = None,
    templated: bool = False,
) -> str:
    prefix = f"{indent}.{port.name}"
    spaces = " " * max(1, CONNECTION_COLUMN - len(prefix))
    comma = "" if is_last else ","
    line = f"{prefix}{spaces}({expr or signal_expr_for_port(port)}){comma}"
    if templated and comma:
        line += " // Templated"
    return line


def generated_connection_lines(
    module: ModuleInfo,
    indent: str,
    skip_ports: set[str] | None = None,
    resolver: Callable[[Port], TemplateResult] | None = None,
) -> list[str]:
    skip_ports = skip_ports or set()
    resolver = resolver or (lambda port: TemplateResult(signal_expr_for_port(port),
                                                        port.name, False))
    lines: list[str] = []
    selected: list[Port] = [
        port for port in module.ports
        if port.direction in DIRECTION_ORDER and port.name not in skip_ports
    ]
    total = len(selected)
    emitted = 0
    for direction in DIRECTION_ORDER:
        group = [port for port in selected if port.direction == direction]
        if not group:
            continue
        title = {"output": "Outputs", "inout": "Inouts", "input": "Inputs"}[direction]
        lines.append(f"{indent}// {title}")
        for port in group:
            emitted += 1
            resolved = resolver(port)
            lines.append(
                format_connection(
                    port,
                    indent,
                    emitted == total,
                    resolved.expr,
                    resolved.templated,
                )
            )
    return lines


def connection_order_ports(module: ModuleInfo, skip_ports: set[str] | None = None) -> list[Port]:
    skip_ports = skip_ports or set()
    return [
        port
        for direction in DIRECTION_ORDER
        for port in module.ports
        if port.direction == direction and port.name not in skip_ports
    ]


def generated_star_template_lines(
    ports: list[Port],
    indent: str,
    resolver: Callable[[Port], TemplateResult],
) -> list[str]:
    if not ports:
        return []
    lines: list[str] = []
    total = len(ports)
    emitted = 0
    for direction in DIRECTION_ORDER:
        group = [port for port in ports if port.direction == direction]
        if direction == "output" or group:
            title = {"output": "Outputs", "inout": "Inouts", "input": "Inputs"}[direction]
            lines.append(f"{indent}// {title}")
        for port in group:
            emitted += 1
            resolved = resolver(port)
            lines.append(
                format_connection(
                    port,
                    indent,
                    emitted == total,
                    resolved.expr,
                    resolved.templated and emitted != total,
                )
            )
            if resolved.templated and emitted == total:
                lines[-1] += " // Templated"
    return lines


def generated_param_connection_lines(module: ModuleInfo, indent: str,
                                     skip_params: set[str] | None = None) -> list[str]:
    skip_params = skip_params or set()
    params = [param for param in module.params if param.name not in skip_params]
    if not params:
        return []
    lines = [f"{indent}// Parameters"]
    for index, param in enumerate(params):
        prefix = f"{indent}.{param.name}"
        spaces = " " * max(1, CONNECTION_COLUMN - len(prefix))
        comma = "" if index == len(params) - 1 else ","
        lines.append(f"{prefix}{spaces}({param.name}){comma}")
    return lines


def parse_named_connections(text: str) -> set[str]:
    names = set(re.findall(r"\.\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\(", text))
    names.update(
        re.findall(
            r"\.\s*([A-Za-z_][A-Za-z0-9_$]*)\s*(?=,|\)|/\*)",
            text,
        )
    )
    return names


def delete_generated_blocks(text: str) -> str:
    lines = text.splitlines(True)
    output: list[str] = []
    i = 0
    while i < len(lines):
        output.append(lines[i])
        if "/*AUTO" in lines[i].upper():
            j = i + 1
            if j < len(lines) and AUTO_BEGIN_RE.match(lines[j]):
                j += 1
                while j < len(lines):
                    if AUTO_END_RE.match(lines[j]):
                        j += 1
                        break
                    j += 1
                i = j
                continue
        i += 1
    return "".join(output)


def delete_inline_autos(text: str, lib: ModuleLibrary | None = None) -> str:
    module_names = lib.modules.keys() if lib else []
    replacements: list[tuple[int, int, str]] = []

    for inst in find_instances(text, module_names):
        port_text = text[inst.port_open + 1:inst.port_close]
        marker = re.search(r"/\*\s*AUTOINST\s*\*/", port_text, re.IGNORECASE)
        if marker:
            replacements.append((inst.port_open + 1 + marker.end(), inst.port_close, ""))
            semicolon = text.find(";", inst.port_close)
            line_end = text.find("\n", inst.port_close)
            if semicolon >= 0 and (line_end < 0 or semicolon < line_end):
                comment = text.find("// Templated", semicolon, line_end if line_end >= 0 else len(text))
                if comment >= 0:
                    replacements.append((comment, line_end if line_end >= 0 else len(text), ""))
        star = re.search(r"\.\*", port_text)
        if star and re.search(r"//\s*Outputs|//\s*Inputs|//\s*Inouts", port_text,
                              re.IGNORECASE):
            replacements.append((inst.port_open + 1 + star.end(), inst.port_close, ""))
            semicolon = text.find(";", inst.port_close)
            line_end = text.find("\n", inst.port_close)
            if semicolon >= 0 and (line_end < 0 or semicolon < line_end):
                comment = text.find("// Templated", semicolon, line_end if line_end >= 0 else len(text))
                if comment >= 0:
                    replacements.append((comment, line_end if line_end >= 0 else len(text), ""))

        if inst.param_open is not None and inst.param_close is not None:
            param_text = text[inst.param_open + 1:inst.param_close]
            marker = re.search(r"/\*\s*AUTOINSTPARAM\s*\*/", param_text,
                               re.IGNORECASE)
            if marker:
                replacements.append(
                    (inst.param_open + 1 + marker.end(), inst.param_close, "")
                )

    for marker in iter_auto_markers(text, "AUTOARG"):
        close = text.find(");", marker.end)
        if close >= 0:
            replacements.append((marker.end, close, ""))

    for marker in iter_auto_markers(text, "AUTOSENSE"):
        close = text.find(")", marker.end)
        if close >= 0:
            replacements.append((marker.end, close, ""))

    return apply_replacements(text, replacements)


def delete_auto(text: str, lib: ModuleLibrary | None = None) -> str:
    text = delete_generated_blocks(text)
    text = delete_inline_autos(text, lib)
    return text


def expand_instances(
    text: str,
    lib: ModuleLibrary,
    templates: list[AutoTemplate],
) -> tuple[str, list[ConnectionUse]]:
    replacements: list[tuple[int, int, str]] = []
    uses: list[ConnectionUse] = []

    for inst in find_instances(text, lib.modules.keys()):
        module = lib.get(inst.module)
        if module is None:
            continue

        port_text = text[inst.port_open + 1:inst.port_close]
        marker = re.search(r"/\*\s*AUTOINST\s*\*/", port_text, re.IGNORECASE)
        if marker:
            skip_ports = parse_named_connections(port_text[:marker.start()])
            indent = " " * marker_column(text, inst.port_open + 1 + marker.start())
            resolver = lambda port, inst=inst: find_template_result(
                templates, inst, port)
            selected_ports = connection_order_ports(module, skip_ports)
            lines = generated_connection_lines(module, indent, skip_ports,
                                               resolver)
            replacement = "\n" + "\n".join(lines) if lines else ""
            replacements.append(
                (inst.port_open + 1 + marker.end(), inst.port_close, replacement)
            )
            if selected_ports:
                last_resolved = find_template_result(
                    templates, inst, selected_ports[-1])
                if last_resolved.templated:
                    semicolon = text.find(";", inst.port_close)
                    line_end = text.find("\n", inst.port_close)
                    if semicolon >= 0 and (line_end < 0 or semicolon < line_end):
                        replacements.append((semicolon + 1, semicolon + 1,
                                             " // Templated"))
            for port in module.ports:
                if port.direction in DIRECTION_ORDER and port.name not in skip_ports:
                    resolved = find_template_result(templates, inst, port)
                    uses.append(
                        ConnectionUse(inst, port, resolved.signal,
                                      resolved.templated, resolved.expr,
                                      resolved.decl_port)
                    )

        star = re.search(r"\.\*", port_text)
        if star:
            open_line_start = text.rfind("\n", 0, inst.port_open) + 1
            indent = " " * (inst.port_open - open_line_start + 1)
            resolver = lambda port, inst=inst: find_template_result(
                templates, inst, port)
            selected_ports = connection_order_ports(module)
            templated_ports = [
                port for port in selected_ports if resolver(port).templated
            ]
            lines = generated_star_template_lines(templated_ports, indent,
                                                  resolver)
            if lines:
                replacement = ",\n" + "\n".join(lines) + "\n"
                replacements.append(
                    (inst.port_open + 1 + star.end(), inst.port_close,
                     replacement)
                )
            for port in module.ports:
                if port.direction in DIRECTION_ORDER:
                    resolved = find_template_result(templates, inst, port)
                    uses.append(
                        ConnectionUse(inst, port, resolved.signal,
                                      resolved.templated, resolved.expr,
                                      resolved.decl_port)
                    )

        if inst.param_open is not None and inst.param_close is not None:
            param_text = text[inst.param_open + 1:inst.param_close]
            param_marker = re.search(
                r"/\*\s*AUTOINSTPARAM\s*\*/", param_text, re.IGNORECASE
            )
            if param_marker:
                skip_params = parse_named_connections(param_text[:param_marker.start()])
                indent = " " * marker_column(
                    text, inst.param_open + 1 + param_marker.start()
                )
                lines = generated_param_connection_lines(module, indent, skip_params)
                replacement = "\n" + "\n".join(lines) if lines else ""
                replacements.append(
                    (inst.param_open + 1 + param_marker.end(),
                     inst.param_close,
                     replacement)
                )

    return apply_replacements(text, replacements), uses


def automatic_block(indent: str, begin: str, lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(
        [f"{indent}// Beginning of automatic {begin}", *lines,
         f"{indent}// End of automatics"]
    ) + "\n"


def expand_marker_lines(
    text: str,
    wanted: str,
    generator: Callable[[AutoMarker], str],
) -> str:
    replacements: list[tuple[int, int, str]] = []
    for marker in iter_auto_markers(text, wanted):
        block = generator(marker)
        if not block:
            continue
        insert_at = marker.line_end
        replacements.append((insert_at, insert_at, block))
    return apply_replacements(text, replacements)


def parse_declaration_statement(stmt: str) -> list[Port]:
    stmt = re.sub(r"//.*", "", stmt).strip().rstrip(";").strip()
    match = re.match(r"\b(input|output|inout)\b\s*(.*)$", stmt, re.DOTALL)
    if not match:
        return []

    direction = match.group(1)
    rest = " ".join(match.group(2).split())
    rest = re.sub(r"\b(?:wire|var)\b", "", rest).strip()
    parts = split_top_level_commas(rest)
    if not parts:
        return []

    first = parts[0]
    prefix_tokens = first.split()
    if not prefix_tokens:
        return []

    data_type = ""
    packed = ""
    if len(prefix_tokens) > 1:
        candidate_tokens = prefix_tokens[:-1]
        if candidate_tokens and re.fullmatch(r"\[[^\]]+\]", candidate_tokens[-1]):
            packed = candidate_tokens[-1]
            candidate_tokens = candidate_tokens[:-1]
        data_type = " ".join(candidate_tokens)
        if data_type in {"signed", "unsigned"}:
            data_type = ""

    ports: list[Port] = []
    for index, part in enumerate(parts):
        part = part.strip()
        tokens = part.split()
        if not tokens:
            continue
        if index == 0:
            name_token = tokens[-1]
        else:
            name_token = tokens[-1]
        name_match = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)(.*)", name_token)
        if not name_match:
            continue
        name = name_match.group(1)
        unpacked = name_match.group(2) if name_match.group(2).startswith("[") else ""
        ports.append(Port(name, direction, data_type, packed, unpacked))
    return ports


def parse_ansi_port_list(header_text: str) -> list[Port]:
    """Parse ANSI-style port list like 'input i, output o, inout [3:0] io'."""
    result: list[Port] = []
    # Split by direction keywords
    pattern = re.compile(
        r"\b(input|output|inout)\b\s*",
    )
    parts = re.split(r"(\b(?:input|output|inout)\b)", header_text)
    # parts alternates: [before, kw, after, kw, after, ...]
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if part in {"input", "output", "inout"}:
            direction = part
            body = parts[i + 1].rstrip(",").strip() if i + 1 < len(parts) else ""
            for port in parse_declaration_statement(direction + " " + body + ";"):
                result.append(port)
            i += 2
        else:
            i += 1
    return result


def parse_declarations(text: str, directions: set[str] | None = None) -> list[Port]:
    directions = directions or {"input", "output", "inout"}
    result: list[Port] = []
    pattern = r"^\s*(input|output|inout)\b[^;]*;"
    for match in re.finditer(pattern, text, re.MULTILINE):
        if match.group(1) not in directions:
            continue
        result.extend(parse_declaration_statement(match.group(0)))
    return result


def parse_signal_declarations(text: str) -> list[Port]:
    result: list[Port] = []
    pattern = r"^\s*(logic|wire|reg)\b([^;]*);"
    for match in re.finditer(pattern, text, re.MULTILINE):
        data_type = match.group(1)
        rest = " ".join(match.group(2).split())
        packed = ""
        if rest.startswith("["):
            end = rest.find("]")
            if end >= 0:
                packed = rest[:end + 1]
                rest = rest[end + 1:].strip()
        for item in split_top_level_commas(rest):
            name_match = re.match(r"([A-Za-z_][A-Za-z0-9_$]*)(.*)", item.strip())
            if not name_match:
                continue
            unpacked = name_match.group(2).strip()
            if not unpacked.startswith("["):
                unpacked = ""
            result.append(Port(name_match.group(1), "", data_type, packed, unpacked))
    return result


def declared_names(text: str) -> set[str]:
    names = {port.name for port in parse_declarations(text)}
    names.update(port.name for port in parse_signal_declarations(text))
    return names


def module_scope_text(text: str, pos: int) -> str:
    module_start = 0
    for match in re.finditer(r"\bmodule\b", text[:pos]):
        module_start = match.start()
    module_end = text.find("endmodule", pos)
    if module_end < 0:
        module_end = len(text)
    else:
        module_end += len("endmodule")
    return text[module_start:module_end]


def direction_declarations(text: str, direction: str) -> list[Port]:
    return [port for port in parse_declarations(text) if port.direction == direction]


def signal_name_from_connection(use: ConnectionUse) -> str:
    return use.signal


def grouped_signal_uses(uses: list[ConnectionUse]) -> dict[str, list[ConnectionUse]]:
    grouped: dict[str, list[ConnectionUse]] = {}
    for use in uses:
        if not use.signal:
            continue
        grouped.setdefault(use.signal, []).append(use)
    return grouped


def signal_has_direction(uses_for_signal: list[ConnectionUse], direction: str) -> bool:
    return any(use.port.direction == direction for use in uses_for_signal)


def declaration_use_for_signal(
    uses_for_signal: list[ConnectionUse],
    preferred: tuple[str, ...],
) -> ConnectionUse:
    for direction in preferred:
        for use in uses_for_signal:
            if use.port.direction == direction:
                return use
    return uses_for_signal[0]


def declaration_port_for_use(use: ConnectionUse) -> Port:
    return use.decl_port or use.port


def module_display_name(module: ModuleInfo | None, fallback: str) -> str:
    if module and module.source_path and module.source_path.suffix == ".v":
        if module.source_path.stem != fallback:
            return f"{fallback}.v"
        return module.source_path.name
    return fallback


def use_comment(
    lib: ModuleLibrary,
    direction: str,
    uses_for_signal: list[ConnectionUse],
) -> str:
    first = uses_for_signal[0]
    module = lib.get(first.instance.module)
    label = module_display_name(module, first.instance.module)
    if direction == "input":
        prefix = "To"
    elif direction == "inout":
        prefix = "To/From"
    else:
        prefix = "From"
    comment = f"// {prefix} {first.instance.name} of {label}"
    if len(uses_for_signal) > 1:
        comment += ", ..."
    return comment


def wire_comment(lib: ModuleLibrary, uses_for_signal: list[ConnectionUse]) -> str:
    inouts = [
        use for use in uses_for_signal
        if use.port.direction == "inout"
    ]
    if inouts:
        first = inouts[0]
        module = lib.get(first.instance.module)
        label = module_display_name(module, first.instance.module)
        return f"// To/From {first.instance.name} of {label}"
    drivers = [
        use for use in uses_for_signal
        if use.port.direction in {"output", "inout"}
    ]
    return use_comment(lib, "output", drivers or uses_for_signal)


def expand_auto_declaration_kind(
    text: str,
    wanted: str,
    direction: str,
    uses: list[ConnectionUse],
    lib: ModuleLibrary,
) -> str:
    begin = {
        "input": "inputs (from unused autoinst inputs)",
        "output": "outputs (from unused autoinst outputs)",
        "inout": "inouts (from unused autoinst inouts)",
    }[direction]

    def generator(marker: AutoMarker) -> str:
        scope = module_scope_text(text, marker.start)
        names = declared_names(scope)
        by_signal: dict[str, list[ConnectionUse]] = {}
        for signal, signal_uses in grouped_signal_uses(uses).items():
            if signal in names:
                continue
            has_input = signal_has_direction(signal_uses, "input")
            has_output = signal_has_direction(signal_uses, "output")
            has_inout = signal_has_direction(signal_uses, "inout")
            if direction == "input" and has_input and not has_output and not has_inout:
                by_signal[signal] = signal_uses
            elif direction == "output" and has_output and not has_input and not has_inout:
                by_signal[signal] = signal_uses
            elif direction == "inout" and has_inout and not has_input and not has_output:
                by_signal[signal] = signal_uses
        lines: list[str] = []
        for signal in sorted(by_signal):
            uses_for_signal = by_signal[signal]
            use = declaration_use_for_signal(uses_for_signal, (direction,))
            comment = use_comment(lib, direction, uses_for_signal)
            in_port = is_in_port_list(text, marker.start)
            lines.append(format_declaration(declaration_port_for_use(use),
                                            direction, signal,
                                            marker.indent, comment,
                                            in_port_list=in_port))
        return automatic_block(marker.indent, begin, lines)

    return expand_marker_lines(text, wanted, generator)


def expand_autowire_like(
    text: str,
    wanted: str,
    kind: str,
    uses: list[ConnectionUse],
    lib: ModuleLibrary,
) -> str:
    begin = "wires (for undeclared instantiated-module outputs)"

    def generator(marker: AutoMarker) -> str:
        scope = module_scope_text(text, marker.start)
        names = declared_names(scope)
        by_signal: dict[str, list[ConnectionUse]] = {}
        for signal, signal_uses in grouped_signal_uses(uses).items():
            if signal in names:
                continue
            has_input = signal_has_direction(signal_uses, "input")
            has_output = signal_has_direction(signal_uses, "output")
            has_inout = signal_has_direction(signal_uses, "inout")
            if has_output or has_inout:
                by_signal[signal] = signal_uses
        lines: list[str] = []
        for signal in sorted(by_signal):
            uses_for_signal = by_signal[signal]
            use = declaration_use_for_signal(uses_for_signal, ("output", "inout"))
            data_type = "logic" if kind == "logic" else "wire"
            port = dataclasses.replace(declaration_port_for_use(use),
                                       data_type=data_type)
            lines.append(format_declaration(port, "", signal,
                                            marker.indent,
                                            wire_comment(lib, uses_for_signal),
                                            force_data_type=data_type))
        return automatic_block(marker.indent, begin, lines)

    return expand_marker_lines(text, wanted, generator)


def module_marker_target(marker: AutoMarker) -> str | None:
    args = marker.args
    return args[0] if args else None


def ports_for_direction_groups(module: ModuleInfo, mode: str) -> list[Port]:
    ports: list[Port] = []
    for direction in DIRECTION_ORDER:
        group: list[Port] = []
        for port in module.ports:
            if port.direction not in DIRECTION_ORDER:
                continue
            out_direction = port.direction
            if mode == "comp":
                out_direction = {
                    "input": "output",
                    "output": "input",
                    "inout": "inout",
                }[port.direction]
            elif mode == "in":
                out_direction = "input"
            if out_direction == direction:
                group.append(dataclasses.replace(port, direction=out_direction))
        group.sort(key=lambda p: p.name.lower())
        ports.extend(group)
    return ports


def expand_autoinoutparam(text: str, lib: ModuleLibrary) -> str:
    def generator(marker: AutoMarker) -> str:
        target = module_marker_target(marker)
        module = lib.get(target or "") if target else None
        if not module:
            return ""
        lines = [format_param_declaration(param, marker.indent)
                 for param in module.params]
        return automatic_block(marker.indent, "parameters (from specific module)",
                               lines)

    return expand_marker_lines(text, "AUTOINOUTPARAM", generator)


def expand_autoinoutmodule_kind(
    text: str,
    lib: ModuleLibrary,
    wanted: str,
    mode: str,
) -> str:
    begin = {
        "module": "in/out/inouts (from specific module)",
        "comp": "in/out/inouts (from specific module, complemented)",
        "in": "in/out/inouts (from specific module)",
    }[mode]

    def generator(marker: AutoMarker) -> str:
        target = module_marker_target(marker)
        module = lib.get(target or "") if target else None
        if not module:
            return ""
        in_port = is_in_port_list(text, marker.start)
        lines = [
            format_declaration(port, port.direction, port.name, marker.indent,
                               in_port_list=in_port)
            for port in ports_for_direction_groups(module, mode)
        ]
        return automatic_block(marker.indent, begin, lines)

    return expand_marker_lines(text, wanted, generator)


def expand_autoinoutmodport(text: str, lib: ModuleLibrary) -> str:
    def generator(marker: AutoMarker) -> str:
        args = marker.args
        if len(args) < 2:
            return ""
        interface = lib.get(args[0])
        if not interface:
            return ""
        modport_name = args[1]
        suffix = args[2] if len(args) > 2 else ""
        prefix = args[3] if len(args) > 3 else ""
        lines: list[str] = []
        for signal, direction in interface.modports.get(modport_name, []):
            port = interface.interface_ports.get(signal)
            if not port:
                continue
            top_name = f"{prefix}{signal}{suffix}"
            decl_port = dataclasses.replace(port, direction=direction)
            in_port = is_in_port_list(text, marker.start)
            lines.append(format_declaration(decl_port, direction, top_name,
                                            marker.indent,
                                            in_port_list=in_port))
        return automatic_block(marker.indent, "in/out/inouts (from modport)",
                               lines)

    return expand_marker_lines(text, "AUTOINOUTMODPORT", generator)


def expand_autoassignmodport(text: str, lib: ModuleLibrary) -> str:
    def generator(marker: AutoMarker) -> str:
        args = marker.args
        if len(args) < 3:
            return ""
        interface = lib.get(args[0])
        if not interface:
            return ""
        modport_name = args[1]
        instance_name = args[2]
        suffix = args[3] if len(args) > 3 else ""
        prefix = args[4] if len(args) > 4 else ""
        lines: list[str] = []
        for signal, direction in interface.modports.get(modport_name, []):
            top_name = f"{prefix}{signal}{suffix}"
            if direction == "output":
                lines.append(f"{marker.indent}assign {instance_name}.{signal} = {top_name};")
            elif direction == "input":
                lines.append(f"{marker.indent}assign {top_name} = {instance_name}.{signal};")
            elif direction in {"inout", "ref"}:
                lines.append(f"{marker.indent}assign {instance_name}.{signal} = {top_name};")
        return automatic_block(marker.indent, "assignments from modport", lines)

    return expand_marker_lines(text, "AUTOASSIGNMODPORT", generator)


def expand_autotieoff(text: str) -> str:
    def generator(marker: AutoMarker) -> str:
        lines = [
            f"{marker.indent}assign {port.name} = '0;"
            for port in direction_declarations(text, "output")
        ]
        return automatic_block(
            marker.indent,
            "tieoffs (for this module's unterminated outputs)",
            lines,
        )

    return expand_marker_lines(text, "AUTOTIEOFF", generator)


def expand_autounused(text: str) -> str:
    def generator(marker: AutoMarker) -> str:
        ports = direction_declarations(text, "input")
        ports.extend(direction_declarations(text, "inout"))
        lines = [f"{marker.indent}{port.name}," for port in ports]
        return automatic_block(marker.indent, "unused inputs", lines)

    return expand_marker_lines(text, "AUTOUNUSED", generator)


def expand_autoundef(text: str) -> str:
    define_names = DEFINE_RE.findall(text)

    def generator(marker: AutoMarker) -> str:
        lines = [f"{marker.indent}`undef {name}" for name in define_names]
        return automatic_block(marker.indent, "undefs", lines)

    return expand_marker_lines(text, "AUTOUNDEF", generator)


def strip_comments_and_strings(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//.*", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " ", text)
    return text


def find_sensitivity_block(text: str, marker: AutoMarker) -> tuple[int, int] | None:
    close = text.find(")", marker.end)
    if close < 0:
        return None
    begin = re.search(r"\bbegin\b", text[close:])
    if not begin:
        return None
    body_start = close + begin.end()
    depth = 1
    for token in re.finditer(r"\b(begin|end)\b", text[body_start:]):
        word = token.group(1)
        if word == "begin":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return body_start, body_start + token.start()
    return None


SV_KEYWORDS = {
    "always", "always_comb", "always_ff", "always_latch", "begin", "end",
    "if", "else", "case", "endcase", "for", "while", "do", "assign",
    "logic", "wire", "reg", "input", "output", "inout", "module",
    "endmodule", "posedge", "negedge", "or", "and", "not", "function",
    "endfunction", "task", "endtask", "localparam", "parameter",
}


def autosense_names(block_text: str) -> list[str]:
    cleaned = strip_comments_and_strings(block_text)
    assigned = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_$]*)\s*(?:<=|=)", cleaned))
    identifiers = set(IDENT_RE.findall(cleaned))
    identifiers -= assigned
    identifiers -= SV_KEYWORDS
    return sorted(identifiers)


def expand_autosense(text: str) -> str:
    replacements: list[tuple[int, int, str]] = []
    for marker in iter_auto_markers(text, "AUTOSENSE"):
        close = text.find(")", marker.end)
        block = find_sensitivity_block(text, marker)
        if close < 0 or block is None:
            continue
        names = autosense_names(text[block[0]:block[1]])
        replacement = "".join(f" or {name}" for name in names)
        replacements.append((marker.end, close, replacement))
    return apply_replacements(text, replacements)


def collect_autoarg_ports(text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for port in parse_declarations(text):
        if port.name in seen:
            continue
        seen.add(port.name)
        names.append(port.name)
    return names


def collect_autoarg_grouped(text: str) -> dict[str, list[str]]:
    grouped = {"output": [], "inout": [], "input": []}
    seen: set[str] = set()
    for port in parse_declarations(text):
        if port.direction not in grouped or port.name in seen:
            continue
        seen.add(port.name)
        grouped[port.direction].append(port.name)
    return grouped


def local_auto_arg_sort(text: str) -> bool:
    return re.search(r"verilog-auto-arg-sort\s*:\s*t\b", text) is not None


def expand_autoarg(text: str) -> str:
    replacements: list[tuple[int, int, str]] = []
    for marker in iter_auto_markers(text, "AUTOARG"):
        close = text.find(");", marker.end)
        if close < 0:
            continue
        scope = module_scope_text(text, marker.start)
        grouped = collect_autoarg_grouped(scope)
        sort_args = local_auto_arg_sort(text)
        reverse_args = "Beginning of automatic" in text[marker.end:close]
        output_names = (sorted(grouped["output"]) if sort_args
                        else (list(reversed(grouped["output"]))
                              if reverse_args else grouped["output"]))
        inout_names = (sorted(grouped["inout"]) if sort_args
                       else (list(reversed(grouped["inout"]))
                             if reverse_args else grouped["inout"]))
        input_names = (sorted(grouped["input"]) if sort_args
                       else (list(reversed(grouped["input"]))
                             if reverse_args else grouped["input"]))
        lines: list[str] = []
        if output_names:
            lines.append("   // Outputs")
            comma = "," if input_names or inout_names else ""
            lines.append(f"   {', '.join(output_names)}{comma}")
        if inout_names:
            lines.append("   // Inouts")
            comma = "," if input_names else ""
            lines.append(f"   {', '.join(inout_names)}{comma}")
        if input_names:
            lines.append("   // Inputs")
            lines.append(f"   {', '.join(input_names)}")
        replacement = "\n" + "\n".join(lines) + "\n   " if lines else ""
        replacements.append((marker.end, close, replacement))
    return apply_replacements(text, replacements)


def run_batch_auto(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8")
    lib = ModuleLibrary(path, text)
    text = delete_auto(text, lib)
    # The delete pass may expose local variables cleanly; refresh the library in
    # case the original top file was not legal enough for the first scan.
    lib = ModuleLibrary(path, text)
    templates = parse_auto_templates(text)

    text, uses = expand_instances(text, lib, templates)
    text = expand_autoinoutmodport(text, lib)
    text = expand_autoinoutmodule_kind(text, lib, "AUTOINOUTMODULE", "module")
    text = expand_autoinoutmodule_kind(text, lib, "AUTOINOUTCOMP", "comp")
    text = expand_autoinoutmodule_kind(text, lib, "AUTOINOUTIN", "in")
    text = expand_autoinoutparam(text, lib)
    text = expand_auto_declaration_kind(text, "AUTOOUTPUT", "output", uses, lib)
    text = expand_auto_declaration_kind(text, "AUTOINPUT", "input", uses, lib)
    text = expand_auto_declaration_kind(text, "AUTOINOUT", "inout", uses, lib)
    text = expand_autotieoff(text)
    text = expand_autoundef(text)
    text = expand_autoassignmodport(text, lib)
    text = expand_autowire_like(text, "AUTOLOGIC", "logic", uses, lib)
    text = expand_autowire_like(text, "AUTOWIRE", "wire", uses, lib)
    text = expand_autosense(text)
    text = expand_autounused(text)
    text = expand_autoarg(text)
    path.write_text(text, encoding="utf-8")


def run_batch_delete(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8")
    lib = ModuleLibrary(path, text)
    text = delete_auto(text, lib)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] not in {
        "verilog-batch-auto",
        "verilog-batch-delete-auto",
    }:
        print(
            "Usage: python3 verilog-mode.py "
            "<verilog-batch-auto|verilog-batch-delete-auto> <top_file>",
            file=sys.stderr,
        )
        return 2

    command = argv[0]
    path = pathlib.Path(argv[1]).resolve()
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    if command == "verilog-batch-auto":
        run_batch_auto(path)
    else:
        run_batch_delete(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
