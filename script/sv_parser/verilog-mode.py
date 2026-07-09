#!/usr/bin/env python3
"""Small Python subset of verilog-mode batch AUTO behavior.

The original verilog-mode.el does many Emacs-buffer-oriented AUTO actions.
This file intentionally keeps only module connection generation:

The public command line intentionally mirrors the two batch entry points:

* verilog-batch-auto <top_file>
* verilog-batch-delete-auto <top_file>

Only module connection AUTO markers are implemented here:
/*AUTOINST*/ and /*AUTOINSTPARAM*/.

Signal, port, parameter and interface parsing is delegated to sv_parser.py.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import sys
from typing import Iterable, Iterator, Sequence

from sv_parser import SvParser


IDENT_RE = re.compile(r"[A-Za-z_`$][A-Za-z0-9_`$]*")
AUTO_INST_RE = re.compile(r"/\*AUTOINST(?:\((.*?)\))?\*/", re.S)
AUTO_INST_PARAM_RE = re.compile(r"/\*AUTOINSTPARAM(?:\((.*?)\))?\*/", re.S)
DEFAULT_EXTENSIONS = (".sv", ".v", ".svh", ".vh")


@dataclasses.dataclass(frozen=True)
class Port:
    """Normalized port entry from SvParser output."""

    name: str
    direction: str
    data_type: str = ""
    packed: str = ""
    unpacked: str = ""
    modport: str = ""

    @property
    def is_interface(self) -> bool:
        return self.direction == "interface"


@dataclasses.dataclass(frozen=True)
class Parameter:
    """Normalized parameter entry from SvParser output."""

    name: str
    value: str = ""
    data_type: str = ""
    packed: str = ""


@dataclasses.dataclass(frozen=True)
class InstanceContext:
    """Instantiation details around an AUTO marker."""

    module_name: str
    instance_name: str
    port_open: int
    port_close: int
    marker_start: int
    marker_end: int


@dataclasses.dataclass
class FormatOptions:
    """Formatting knobs matching the common verilog-mode defaults."""

    inst_column: int = 40
    sort: bool = False
    vector: bool = True
    dot_name: bool = False
    include_section_comments: bool = True
    interface_modport: bool = True
    indent: str = "    "


def parse_module_file(
    file_path: str | pathlib.Path,
    executable: str = "verible-verilog-syntax",
) -> dict:
    """Parse a SystemVerilog file and return the SvParser module info dict."""

    parser = SvParser(str(file_path), executable=executable)
    info = parser.get_sv_port()
    if not info:
        raise ValueError(f"no module or interface parsed from {file_path}")
    return info


def normalize_ports(module_info: dict) -> list[Port]:
    """Convert SvParser port tuples into Port instances."""

    ports: list[Port] = []
    for raw_port in module_info.get("port", []):
        if len(raw_port) == 2 and isinstance(raw_port[1], list):
            intf_type = raw_port[1]
            ports.append(
                Port(
                    name=raw_port[0],
                    direction="interface",
                    data_type=intf_type[0] if intf_type else "",
                    modport=intf_type[1] if len(intf_type) > 1 else "",
                )
            )
        elif len(raw_port) >= 5:
            ports.append(
                Port(
                    name=raw_port[0],
                    direction=raw_port[1],
                    data_type=raw_port[2],
                    packed=_none_to_empty(raw_port[3]),
                    unpacked=_none_to_empty(raw_port[4]),
                )
            )
    return ports


def normalize_parameters(module_info: dict) -> list[Parameter]:
    """Convert SvParser parameter tuples into Parameter instances."""

    params: list[Parameter] = []
    for raw_param in module_info.get("para", []):
        if not raw_param:
            continue
        params.append(
            Parameter(
                name=raw_param[0],
                value=raw_param[1] if len(raw_param) > 1 else "",
                data_type=raw_param[2] if len(raw_param) > 2 else "",
                packed=raw_param[3] if len(raw_param) > 3 else "",
            )
        )
    return params


def generate_autoinst(
    module_info: dict,
    *,
    skip_pins: Iterable[str] = (),
    regex: str | None = None,
    options: FormatOptions | None = None,
    close_suffix: str = "",
) -> str:
    """Generate AUTOINST named port connections for a parsed module."""

    opts = options or FormatOptions()
    skip = set(skip_pins)
    ports = [
        port for port in normalize_ports(module_info)
        if port.name and port.name not in skip and _matches_auto_regex(port.name, regex)
    ]
    grouped_ports = _group_ports(ports, opts.sort)
    return _format_port_groups(grouped_ports, opts, close_suffix=close_suffix)


def generate_autoinstparam(
    module_info: dict,
    *,
    skip_params: Iterable[str] = (),
    regex: str | None = None,
    use_defaults: bool = False,
    options: FormatOptions | None = None,
    close_suffix: str = "",
) -> str:
    """Generate AUTOINSTPARAM named parameter connections."""

    opts = options or FormatOptions()
    skip = set(skip_params)
    params = [
        param for param in normalize_parameters(module_info)
        if param.name and param.name not in skip and _matches_auto_regex(param.name, regex)
    ]
    if opts.sort:
        params.sort(key=lambda item: item.name)

    lines: list[str] = []
    if params and opts.include_section_comments:
        lines.append(f"{opts.indent}// Parameters")

    for index, param in enumerate(params):
        value = param.value if use_defaults and param.value else param.name
        comma = "," if index != len(params) - 1 else ""
        lines.append(
            _format_named_connection(
                name=param.name,
                expr=value,
                comma=comma,
                options=opts,
            )
        )

    if lines and close_suffix:
        lines[-1] += close_suffix
    return "\n".join(lines)


def generate_instance(
    module_info: dict,
    *,
    instance_name: str | None = None,
    include_params: bool = True,
    param_defaults: bool = False,
    options: FormatOptions | None = None,
) -> str:
    """Generate a complete module instance."""

    opts = options or FormatOptions()
    module_name = module_info.get("name", "")
    if not module_name:
        raise ValueError("module info does not contain a module name")

    inst_name = instance_name or f"u_{module_name}"
    params = normalize_parameters(module_info) if include_params else []

    if params:
        param_opts = dataclasses.replace(opts, indent="    ")
        param_body = generate_autoinstparam(
            module_info,
            use_defaults=param_defaults,
            options=param_opts,
        )
        header = f"{module_name} #("
        if param_body:
            header += f"\n{param_body}\n) {inst_name} ("
        else:
            header += f") {inst_name} ("
    else:
        header = f"{module_name} {inst_name} ("

    port_body = generate_autoinst(
        module_info,
        options=dataclasses.replace(opts, indent="    "),
    )
    if port_body:
        return f"{header}\n{port_body}\n);"
    return f"{header});"


def expand_autos_in_file(
    source_file: str | pathlib.Path,
    *,
    write: bool = False,
    library_dirs: Sequence[str | pathlib.Path] = (),
    library_files: Sequence[str | pathlib.Path] = (),
    extensions: Sequence[str] = DEFAULT_EXTENSIONS,
    executable: str = "verible-verilog-syntax",
    options: FormatOptions | None = None,
    param_defaults: bool = False,
) -> str:
    """Expand AUTO markers in a file and optionally write changes back."""

    path = pathlib.Path(source_file)
    text = path.read_text(encoding="utf-8")
    expanded = expand_autos_in_text(
        text,
        source_path=path,
        library_dirs=library_dirs,
        library_files=library_files,
        extensions=extensions,
        executable=executable,
        options=options,
        param_defaults=param_defaults,
    )
    if write and expanded != text:
        path.write_text(expanded, encoding="utf-8")
    return expanded


def verilog_batch_auto(top_file: str | pathlib.Path) -> bool:
    """Expand supported AUTO markers in TOP_FILE and save it.

    Returns True when the file changed.
    """

    path = pathlib.Path(top_file)
    text = path.read_text(encoding="utf-8")
    local_config = _read_verilog_local_config(text, path)
    expanded = expand_autos_in_text(
        text,
        source_path=path,
        library_dirs=local_config["library_dirs"],
        library_files=local_config["library_files"],
        extensions=local_config["extensions"],
    )
    if expanded != text:
        path.write_text(expanded, encoding="utf-8")
        return True
    return False


def verilog_batch_delete_auto(top_file: str | pathlib.Path) -> bool:
    """Delete supported AUTO expansions in TOP_FILE and save it.

    Returns True when the file changed.
    """

    path = pathlib.Path(top_file)
    text = path.read_text(encoding="utf-8")
    deleted = delete_autos_in_text(text)
    if deleted != text:
        path.write_text(deleted, encoding="utf-8")
        return True
    return False


def expand_autos_in_text(
    text: str,
    *,
    source_path: str | pathlib.Path | None = None,
    library_dirs: Sequence[str | pathlib.Path] = (),
    library_files: Sequence[str | pathlib.Path] = (),
    extensions: Sequence[str] = DEFAULT_EXTENSIONS,
    executable: str = "verible-verilog-syntax",
    options: FormatOptions | None = None,
    param_defaults: bool = False,
) -> str:
    """Expand /*AUTOINST*/ and /*AUTOINSTPARAM*/ markers in source text."""

    opts = options or FormatOptions()
    source = pathlib.Path(source_path).resolve() if source_path else None
    matcher = ParenthesisMatcher(text)
    module_cache: dict[str, dict] = {}

    edits: list[tuple[int, int, str]] = []
    for match in _iter_auto_markers(text):
        if _range_overlaps_edit(match.start(), match.end(), edits):
            continue

        context = _read_instance_context(text, matcher, match.start(), match.end())
        module_info = _module_info_for_context(
            context.module_name,
            source,
            library_dirs,
            library_files,
            extensions,
            executable,
            module_cache,
        )
        marker = match.group(0)
        regex = _parse_auto_regex(match.group(1))
        indent = _auto_indent(text, context)
        local_opts = dataclasses.replace(
            opts,
            indent=indent,
            inst_column=_auto_inst_column(opts.inst_column, len(indent)),
        )

        if match.re is AUTO_INST_PARAM_RE:
            skip = _read_named_connections(text[context.port_open + 1:match.start()])
            body = generate_autoinstparam(
                module_info,
                skip_params=skip,
                regex=regex,
                use_defaults=param_defaults,
                options=local_opts,
                close_suffix=")",
            )
        else:
            skip = _read_named_connections(text[context.port_open + 1:match.start()])
            body = generate_autoinst(
                module_info,
                skip_pins=skip,
                regex=regex,
                options=local_opts,
                close_suffix=")",
            )

        replacement = marker if not body else f"{marker}\n{body}"
        if body and _needs_leading_comma(text, context.port_open, match.start()):
            replacement = "," + replacement
        if not body:
            replacement += ")"
        edits.append((match.start(), context.port_close + 1, replacement))

    return _apply_edits(text, edits)


def delete_autos_in_text(text: str) -> str:
    """Delete generated text after /*AUTOINST*/ and /*AUTOINSTPARAM*/."""

    matcher = ParenthesisMatcher(text)
    edits: list[tuple[int, int, str]] = []
    for match in _iter_auto_markers(text):
        if _range_overlaps_edit(match.start(), match.end(), edits):
            continue

        context = _read_instance_context(text, matcher, match.start(), match.end())
        start = _auto_delete_start(text, match.start())
        replacement = match.group(0) + ")"
        edits.append((start, context.port_close + 1, replacement))

    return _apply_edits(text, edits)


class ParenthesisMatcher:
    """Parenthesis/bracket matching while ignoring comments and strings."""

    def __init__(self, text: str):
        self.text = text
        self.open_to_close: dict[int, int] = {}
        self.close_to_open: dict[int, int] = {}
        self._build()

    def enclosing_open(self, start: int, end: int, char: str = "(") -> int | None:
        best: int | None = None
        for open_pos, close_pos in self.open_to_close.items():
            if self.text[open_pos] == char and open_pos < start and close_pos >= end:
                if best is None or open_pos > best:
                    best = open_pos
        return best

    def matching_open(self, close_pos: int) -> int | None:
        return self.close_to_open.get(close_pos)

    def matching_close(self, open_pos: int) -> int | None:
        return self.open_to_close.get(open_pos)

    def _build(self) -> None:
        stack: list[int] = []
        state = "code"
        i = 0
        while i < len(self.text):
            ch = self.text[i]
            nxt = self.text[i + 1] if i + 1 < len(self.text) else ""

            if state == "line_comment":
                if ch == "\n":
                    state = "code"
                i += 1
                continue

            if state == "block_comment":
                if ch == "*" and nxt == "/":
                    state = "code"
                    i += 2
                else:
                    i += 1
                continue

            if state == "string":
                if ch == "\\":
                    i += 2
                elif ch == '"':
                    state = "code"
                    i += 1
                else:
                    i += 1
                continue

            if ch == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            if ch == '"':
                state = "string"
                i += 1
                continue
            if ch in "([":
                stack.append(i)
            elif ch in ")]":
                if stack and _paren_matches(self.text[stack[-1]], ch):
                    open_pos = stack.pop()
                    self.open_to_close[open_pos] = i
                    self.close_to_open[i] = open_pos
            i += 1


def find_module_file(
    module_name: str,
    *,
    source_path: pathlib.Path | None = None,
    library_dirs: Sequence[str | pathlib.Path] = (),
    library_files: Sequence[str | pathlib.Path] = (),
    extensions: Sequence[str] = DEFAULT_EXTENSIONS,
) -> pathlib.Path:
    """Resolve a module name to a source file."""

    search_dirs: list[pathlib.Path] = []
    if source_path is not None:
        search_dirs.append(source_path.parent)
    search_dirs.append(pathlib.Path.cwd())
    search_dirs.extend(pathlib.Path(path) for path in library_dirs)

    seen_dirs: set[pathlib.Path] = set()
    for directory in search_dirs:
        directory = directory.resolve()
        if directory in seen_dirs:
            continue
        seen_dirs.add(directory)
        for ext in extensions:
            candidate = directory / f"{module_name}{ext}"
            if candidate.is_file():
                return candidate

    for file_name in library_files:
        candidate = pathlib.Path(file_name)
        if not candidate.is_absolute() and source_path is not None:
            candidate = source_path.parent / candidate
        if candidate.is_file() and candidate.stem == module_name:
            return candidate.resolve()

    raise FileNotFoundError(f"cannot resolve module '{module_name}' to a file")


def _module_info_for_context(
    module_name: str,
    source_path: pathlib.Path | None,
    library_dirs: Sequence[str | pathlib.Path],
    library_files: Sequence[str | pathlib.Path],
    extensions: Sequence[str],
    executable: str,
    cache: dict[str, dict],
) -> dict:
    if module_name in cache:
        return cache[module_name]

    file_path = find_module_file(
        module_name,
        source_path=source_path,
        library_dirs=library_dirs,
        library_files=library_files,
        extensions=extensions,
    )
    cache[module_name] = parse_module_file(file_path, executable=executable)
    return cache[module_name]


def _group_ports(ports: list[Port], sort_ports: bool) -> list[tuple[str, list[Port]]]:
    groups = [
        ("// Interfaces", [port for port in ports if port.direction == "interface"]),
        ("// Outputs", [port for port in ports if port.direction == "output"]),
        ("// Inouts", [port for port in ports if port.direction == "inout"]),
        ("// Inputs", [port for port in ports if port.direction == "input"]),
    ]
    if sort_ports:
        groups = [(title, sorted(items, key=lambda item: item.name)) for title, items in groups]
    return [(title, items) for title, items in groups if items]


def _format_port_groups(
    groups: list[tuple[str, list[Port]]],
    options: FormatOptions,
    *,
    close_suffix: str = "",
) -> str:
    lines: list[str] = []
    flat_ports = [port for _, ports in groups for port in ports]
    last_port = flat_ports[-1] if flat_ports else None

    for section, ports in groups:
        if options.include_section_comments:
            lines.append(f"{options.indent}{section}")
        for port in ports:
            is_last = port is last_port
            comma = "" if is_last else ","
            lines.append(
                _format_named_connection(
                    name=port.name,
                    expr=_default_port_expression(port, options),
                    comma=comma,
                    options=options,
                )
            )

    if lines and close_suffix:
        lines[-1] += close_suffix
    return "\n".join(lines)


def _format_named_connection(
    *,
    name: str,
    expr: str,
    comma: str,
    options: FormatOptions,
) -> str:
    prefix = f"{options.indent}.{name}"
    if options.dot_name and name == expr:
        return f"{prefix}{comma}"

    pad = " " * max(1, options.inst_column - len(prefix))
    return f"{prefix}{pad}({expr}){comma}"


def _default_port_expression(port: Port, options: FormatOptions) -> str:
    expr = port.name
    if port.is_interface:
        if options.interface_modport and port.modport:
            expr += f".{port.modport}"
        return expr

    if options.vector and port.packed:
        expr += port.packed
    return expr


def _read_instance_context(
    text: str,
    matcher: ParenthesisMatcher,
    marker_start: int,
    marker_end: int,
) -> InstanceContext:
    port_open = matcher.enclosing_open(marker_start, marker_end, "(")
    if port_open is None:
        raise ValueError("AUTO marker is not inside an instance port list")
    port_close = matcher.matching_close(port_open)
    if port_close is None:
        raise ValueError("instance port list has no matching close parenthesis")

    before_open = _skip_ws_backward(text, port_open)
    if before_open > 0 and text[before_open - 1] == "#":
        module_name, _ = _read_identifier_backward(text, before_open - 1)
        instance_name = _read_identifier_forward(text, port_close + 1)[0]
        if not module_name:
            raise ValueError("cannot read module name before AUTOINSTPARAM marker")
        return InstanceContext(
            module_name=module_name,
            instance_name=instance_name,
            port_open=port_open,
            port_close=port_close,
            marker_start=marker_start,
            marker_end=marker_end,
        )

    instance_name, before_instance = _read_identifier_backward(text, port_open)
    if not instance_name:
        raise ValueError("cannot read instance name before AUTO marker")

    module_name, _ = _read_module_name_backward(text, matcher, before_instance)
    if not module_name:
        raise ValueError("cannot read module name before AUTO marker")

    return InstanceContext(
        module_name=module_name,
        instance_name=instance_name,
        port_open=port_open,
        port_close=port_close,
        marker_start=marker_start,
        marker_end=marker_end,
    )


def _read_module_name_backward(
    text: str,
    matcher: ParenthesisMatcher,
    pos: int,
) -> tuple[str, int]:
    pos = _skip_ws_backward(text, pos)
    if pos > 0 and text[pos - 1] == ")":
        param_open = matcher.matching_open(pos - 1)
        if param_open is None:
            return "", pos
        before_hash = _skip_ws_backward(text, param_open)
        if before_hash > 0 and text[before_hash - 1] == "#":
            return _read_identifier_backward(text, before_hash - 1)
    return _read_identifier_backward(text, pos)


def _read_identifier_backward(text: str, pos: int) -> tuple[str, int]:
    pos = _skip_ws_backward(text, pos)
    while pos > 0 and text[pos - 1] == "]":
        open_pos = _find_matching_bracket_backward(text, pos - 1)
        if open_pos is None:
            break
        pos = _skip_ws_backward(text, open_pos)

    end = pos
    while pos > 0 and _is_ident_char(text[pos - 1]):
        pos -= 1
    return text[pos:end], pos


def _read_identifier_forward(text: str, pos: int) -> tuple[str, int]:
    pos = _skip_ws_forward(text, pos)
    match = IDENT_RE.match(text, pos)
    if not match:
        return "", pos
    return match.group(0), match.end()


def _find_matching_bracket_backward(text: str, close_pos: int) -> int | None:
    depth = 0
    i = close_pos
    while i >= 0:
        if text[i] == "]":
            depth += 1
        elif text[i] == "[":
            depth -= 1
            if depth == 0:
                return i
        i -= 1
    return None


def _read_named_connections(source: str) -> set[str]:
    names: set[str] = set()
    i = 0
    state = "code"
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""

        if state == "line_comment":
            if ch == "\n":
                state = "code"
            i += 1
            continue
        if state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
            else:
                i += 1
            continue
        if state == "string":
            if ch == "\\":
                i += 2
            elif ch == '"':
                state = "code"
                i += 1
            else:
                i += 1
            continue

        if ch == "/" and nxt == "/":
            state = "line_comment"
            i += 2
            continue
        if ch == "/" and nxt == "*":
            state = "block_comment"
            i += 2
            continue
        if ch == '"':
            state = "string"
            i += 1
            continue
        if ch == ".":
            match = IDENT_RE.match(source, i + 1)
            if match:
                names.add(match.group(0))
                i = match.end()
                continue
        i += 1
    return names


def _iter_auto_markers(text: str) -> Iterator[re.Match[str]]:
    matches = list(AUTO_INST_PARAM_RE.finditer(text))
    matches.extend(AUTO_INST_RE.finditer(text))
    yield from sorted(matches, key=lambda item: item.start(), reverse=True)


def _apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def _range_overlaps_edit(start: int, end: int, edits: list[tuple[int, int, str]]) -> bool:
    return any(start < edit_end and end > edit_start for edit_start, edit_end, _ in edits)


def _parse_auto_regex(raw: str | None) -> str | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    quoted = re.fullmatch(r"""["'](.*)["']""", raw, re.S)
    return quoted.group(1) if quoted else raw


def _matches_auto_regex(name: str, regex: str | None) -> bool:
    if not regex:
        return True
    if regex.startswith("?!"):
        return re.search(regex[2:], name) is None
    return re.search(regex, name) is not None


def _auto_indent(text: str, context: InstanceContext) -> str:
    line_start = text.rfind("\n", 0, context.port_open) + 1
    return " " * (context.port_open - line_start + 1)


def _auto_inst_column(base_column: int, indent_column: int) -> int:
    return max(base_column, 16 + 8 * ((indent_column + 7) // 8))


def _needs_leading_comma(text: str, open_pos: int, marker_start: int) -> bool:
    before = text[open_pos + 1:marker_start]
    if not before.strip():
        return False

    pos = _skip_ws_backward(text, marker_start)
    if pos == 0:
        return False
    return text[pos - 1] in ")*"


def _auto_delete_start(text: str, marker_start: int) -> int:
    """Delete a comma that was inserted immediately before an AUTO marker."""

    pos = _skip_ws_backward(text, marker_start)
    if pos > 0 and text[pos - 1] == ",":
        return pos - 1
    return marker_start


def _read_verilog_local_config(text: str, source_path: pathlib.Path) -> dict:
    """Read the subset of verilog-mode file locals needed for module lookup."""

    base_dir = source_path.resolve().parent
    library_dirs = [
        _resolve_local_path(base_dir, item)
        for item in _read_local_string_list(text, "verilog-library-directories")
    ]
    library_files = [
        _resolve_local_path(base_dir, item)
        for item in _read_local_string_list(text, "verilog-library-files")
    ]
    extensions = list(DEFAULT_EXTENSIONS)
    extensions.extend(
        _normalize_extension(item)
        for item in _read_local_string_list(text, "verilog-library-extensions")
    )
    extensions.extend(_read_libext_flags(text))

    return {
        "library_dirs": [item for item in library_dirs if str(item)],
        "library_files": [item for item in library_files if str(item)],
        "extensions": _unique_keep_order(item for item in extensions if item),
    }


def _read_local_string_list(text: str, variable: str) -> list[str]:
    match = re.search(rf"{re.escape(variable)}\s*:\s*\((.*?)\)", text, re.S)
    if not match:
        return []
    return [item for item in re.findall(r'"([^"]*)"', match.group(1)) if item]


def _read_libext_flags(text: str) -> list[str]:
    values = _read_local_string_list(text, "verilog-library-flags")
    extensions: list[str] = []
    for value in values:
        if "+libext+" not in value:
            continue
        for item in value.split("+libext+", 1)[1].split("+"):
            if item:
                extensions.append(_normalize_extension(item))
    return extensions


def _resolve_local_path(base_dir: pathlib.Path, value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    return path if path.is_absolute() else base_dir / path


def _normalize_extension(value: str) -> str:
    return value if value.startswith(".") else f".{value}"


def _unique_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _skip_ws_backward(text: str, pos: int) -> int:
    while pos > 0 and text[pos - 1].isspace():
        pos -= 1
    return pos


def _skip_ws_forward(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def _is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch in "_$`"


def _paren_matches(open_ch: str, close_ch: str) -> bool:
    return (open_ch, close_ch) in {("(", ")"), ("[", "]")}


def _none_to_empty(value: str) -> str:
    return "" if value in ("", "None", None) else value


def _cmd_verilog_batch_auto(args: argparse.Namespace) -> int:
    changed = verilog_batch_auto(args.top_file)
    if changed:
        print(f"Updated {args.top_file}")
    return 0


def _cmd_verilog_batch_delete_auto(args: argparse.Namespace) -> int:
    changed = verilog_batch_delete_auto(args.top_file)
    if changed:
        print(f"Updated {args.top_file}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch AUTO tool for /*AUTOINST*/ and /*AUTOINSTPARAM*/.",
    )

    subparsers = parser.add_subparsers(dest="command")

    batch_auto = subparsers.add_parser(
        "verilog-batch-auto",
        help="expand AUTO markers in top_file and save it",
    )
    batch_auto.add_argument("top_file")
    batch_auto.set_defaults(func=_cmd_verilog_batch_auto)

    batch_delete = subparsers.add_parser(
        "verilog-batch-delete-auto",
        help="delete AUTO expansions in top_file and save it",
    )
    batch_delete.add_argument("top_file")
    batch_delete.set_defaults(func=_cmd_verilog_batch_delete_auto)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
