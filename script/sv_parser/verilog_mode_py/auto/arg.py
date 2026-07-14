from __future__ import annotations

import re

from ..formatter import GROUP_TITLES
from ..formatter import format_identifier
from ..sv_parse import parse_modules
from ..syntax import IDENT_RE, line_indent_at, line_start, mask_syntax, split_top_level


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
