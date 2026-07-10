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


@dataclasses.dataclass(frozen=True)
class Instance:
    module: str
    name: str
    start: int
    port_open: int
    port_close: int
    param_open: int | None = None
    param_close: int | None = None


@dataclasses.dataclass(frozen=True)
class ConnectionUse:
    instance: Instance
    port: Port
    signal: str


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
                         param_open, param_close)
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


def simple_parse_module_file(path: pathlib.Path) -> ModuleInfo | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(errors="ignore")

    match = re.search(
        r"\b(module|interface)\s+([A-Za-z_][A-Za-z0-9_$]*)"
        r"(?P<rest>.*?)(?:endmodule|endinterface)\b",
        text,
        re.DOTALL,
    )
    if not match:
        return None

    name = match.group(2)
    block = match.group(0)
    params = [
        Param(param_match.group(1))
        for param_match in re.finditer(
            r"\bparameter\b(?:\s+\w+)?(?:\s+\[[^\]]+\])?\s+"
            r"([A-Za-z_][A-Za-z0-9_$]*)",
            block,
        )
    ]
    ports = parse_declarations(block, directions={"input", "output", "inout"})
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

    return ModuleInfo(name, ports, params, signals, interface_ports, modports)


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
        return info or simple_parse_module_file(path)

    def _load(self) -> None:
        for path in self._candidate_files():
            info = self._parse_file(path)
            if info is None or not info.name:
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
    if direction == "inout" and data_type == "wire":
        return ""
    return data_type


def format_declaration(
    port: Port,
    direction: str | None = None,
    name: str | None = None,
    indent: str = "    ",
    comment: str | None = None,
    force_data_type: str | None = None,
) -> str:
    direction = direction or port.direction
    data_type = declaration_data_type(port, direction)
    if force_data_type is not None:
        data_type = force_data_type
    prefix = indent + declaration_prefix(direction, data_type, port.packed)
    target = name or port.name
    if port.unpacked:
        target += port.unpacked
    spaces = " " * max(1, DECL_NAME_COLUMN - len(prefix))
    line = f"{prefix}{spaces}{target};"
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


def format_connection(port: Port, indent: str, is_last: bool) -> str:
    prefix = f"{indent}.{port.name}"
    spaces = " " * max(1, CONNECTION_COLUMN - len(prefix))
    comma = "" if is_last else ","
    return f"{prefix}{spaces}({signal_expr_for_port(port)}){comma}"


def generated_connection_lines(module: ModuleInfo, indent: str,
                               skip_ports: set[str] | None = None) -> list[str]:
    skip_ports = skip_ports or set()
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
            lines.append(format_connection(port, indent, emitted == total))
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
    return set(re.findall(r"\.\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\(", text))


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
        star = re.search(r"\.\*", port_text)
        if star and re.search(r"//\s*Outputs|//\s*Inputs|//\s*Inouts", port_text,
                              re.IGNORECASE):
            replacements.append((inst.port_open + 1 + star.end(), inst.port_close, ""))

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


def expand_instances(text: str, lib: ModuleLibrary) -> tuple[str, list[ConnectionUse]]:
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
            lines = generated_connection_lines(module, indent, skip_ports)
            replacement = "\n" + "\n".join(lines) if lines else ""
            replacements.append(
                (inst.port_open + 1 + marker.end(), inst.port_close, replacement)
            )
            for port in module.ports:
                if port.direction in DIRECTION_ORDER and port.name not in skip_ports:
                    uses.append(ConnectionUse(inst, port, port.name))

        star = re.search(r"\.\*", port_text)
        if star:
            open_line_start = text.rfind("\n", 0, inst.port_open) + 1
            indent = " " * (inst.port_open - open_line_start + 1)
            lines = generated_connection_lines(module, indent, set())
            replacement = ",\n" + "\n".join(lines) if lines else ""
            replacements.append(
                (inst.port_open + 1 + star.end(), inst.port_close, replacement)
            )
            for port in module.ports:
                if port.direction in DIRECTION_ORDER:
                    uses.append(ConnectionUse(inst, port, port.name))

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


def direction_declarations(text: str, direction: str) -> list[Port]:
    return [port for port in parse_declarations(text) if port.direction == direction]


def signal_name_from_connection(use: ConnectionUse) -> str:
    return use.signal


def expand_auto_declaration_kind(
    text: str,
    wanted: str,
    direction: str,
    uses: list[ConnectionUse],
) -> str:
    begin = {
        "input": "inputs (from unused autoinst inputs)",
        "output": "outputs (from unused autoinst outputs)",
        "inout": "inouts (from unused autoinst inouts)",
    }[direction]

    def generator(marker: AutoMarker) -> str:
        names = declared_names(text)
        lines: list[str] = []
        emitted: set[str] = set()
        for use in uses:
            if use.port.direction != direction:
                continue
            signal = signal_name_from_connection(use)
            if signal in names or signal in emitted:
                continue
            emitted.add(signal)
            comment_word = "To" if direction == "input" else "From"
            comment = f"// {comment_word} {use.instance.name} of {use.instance.module}"
            lines.append(format_declaration(use.port, direction, signal,
                                            marker.indent, comment))
        return automatic_block(marker.indent, begin, lines)

    return expand_marker_lines(text, wanted, generator)


def expand_autowire_like(
    text: str,
    wanted: str,
    kind: str,
    uses: list[ConnectionUse],
) -> str:
    begin = "wires (for undeclared instantiated-module outputs)"

    def generator(marker: AutoMarker) -> str:
        names = declared_names(text)
        lines: list[str] = []
        emitted: set[str] = set()
        for use in uses:
            if use.port.direction not in {"output", "inout"}:
                continue
            signal = signal_name_from_connection(use)
            if signal in names or signal in emitted:
                continue
            emitted.add(signal)
            data_type = "logic" if kind == "logic" else "wire"
            port = dataclasses.replace(use.port, data_type=data_type)
            lines.append(format_declaration(port, "", signal,
                                            marker.indent,
                                            f"// From {use.instance.name} of {use.instance.module}",
                                            force_data_type=data_type))
        return automatic_block(marker.indent, begin, lines)

    return expand_marker_lines(text, wanted, generator)


def module_marker_target(marker: AutoMarker) -> str | None:
    args = marker.args
    return args[0] if args else None


def ports_for_direction_groups(module: ModuleInfo, mode: str) -> list[Port]:
    ports: list[Port] = []
    for direction in DIRECTION_ORDER:
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
                ports.append(dataclasses.replace(port, direction=out_direction))
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
        "in": "inputs (from specific module)",
    }[mode]

    def generator(marker: AutoMarker) -> str:
        target = module_marker_target(marker)
        module = lib.get(target or "") if target else None
        if not module:
            return ""
        lines = [
            format_declaration(port, port.direction, port.name, marker.indent)
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
            lines.append(format_declaration(decl_port, direction, top_name,
                                            marker.indent))
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


def expand_autoarg(text: str) -> str:
    names = collect_autoarg_ports(text)
    replacements: list[tuple[int, int, str]] = []
    for marker in iter_auto_markers(text, "AUTOARG"):
        close = text.find(");", marker.end)
        if close < 0:
            continue
        replacement = "".join(names)
        if names:
            replacement = ", ".join(names)
        replacements.append((marker.end, close, replacement))
    return apply_replacements(text, replacements)


def run_batch_auto(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8")
    lib = ModuleLibrary(path, text)
    text = delete_auto(text, lib)
    # The delete pass may expose local variables cleanly; refresh the library in
    # case the original top file was not legal enough for the first scan.
    lib = ModuleLibrary(path, text)

    text, uses = expand_instances(text, lib)
    text = expand_autoinoutmodport(text, lib)
    text = expand_autoinoutmodule_kind(text, lib, "AUTOINOUTMODULE", "module")
    text = expand_autoinoutmodule_kind(text, lib, "AUTOINOUTCOMP", "comp")
    text = expand_autoinoutmodule_kind(text, lib, "AUTOINOUTIN", "in")
    text = expand_autoinoutparam(text, lib)
    text = expand_auto_declaration_kind(text, "AUTOOUTPUT", "output", uses)
    text = expand_auto_declaration_kind(text, "AUTOINPUT", "input", uses)
    text = expand_auto_declaration_kind(text, "AUTOINOUT", "inout", uses)
    text = expand_autotieoff(text)
    text = expand_autoundef(text)
    text = expand_autoassignmodport(text, lib)
    text = expand_autowire_like(text, "AUTOLOGIC", "logic", uses)
    text = expand_autowire_like(text, "AUTOWIRE", "wire", uses)
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
