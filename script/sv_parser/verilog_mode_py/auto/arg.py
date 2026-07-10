from __future__ import annotations

import re

from ..formatter import GROUP_TITLES
from ..sv_parse import parse_modules
from ..syntax import line_indent_at


AUTOARG_RE = re.compile(r"/\*AUTOARG\*/")


def _format_autoarg(indent: str, grouped_ports: list[tuple[str, list[str]]]) -> str:
    lines: list[str] = []
    nonempty = [(direction, names) for direction, names in grouped_ports if names]
    if not nonempty:
        return ")"
    arg_indent = indent[:-1] if indent else indent
    for idx, (direction, names) in enumerate(nonempty):
        lines.append(f"\n{arg_indent}// {GROUP_TITLES[direction]}")
        suffix = "," if idx != len(nonempty) - 1 else ""
        lines.append(f"\n{arg_indent}{', '.join(names)}{suffix}")
    lines.append(f"\n{arg_indent})")
    return "".join(lines)


def expand_autoarg(text: str) -> str:
    modules = parse_modules(text)
    replacements: list[tuple[int, int, str]] = []
    for module in modules:
        if module.header_port_open is None or module.header_port_close is None:
            continue
        header_text = text[module.header_port_open + 1 : module.header_port_close]
        marker = AUTOARG_RE.search(header_text)
        if marker is None:
            continue
        seen: set[str] = set()
        grouped: list[tuple[str, list[str]]] = []
        for direction in ("output", "inout", "input"):
            names = [
                port.name
                for port in module.ports
                if port.direction == direction and port.name not in seen
            ]
            for name in names:
                seen.add(name)
            names.sort(reverse=True)
            grouped.append((direction, names))
        marker_start = module.header_port_open + 1 + marker.start()
        marker_end = module.header_port_open + 1 + marker.end()
        indent = line_indent_at(text, marker_start)
        replacement = _format_autoarg(indent, grouped)
        replacements.append((marker_end, module.header_port_close + 1, replacement))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text
