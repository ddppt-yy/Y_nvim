from __future__ import annotations

import re

from ..formatter import GROUP_TITLES, direction_groups, format_connection, port_actual
from ..library import ModuleLibrary
from ..model import Param, Port
from ..sv_parse import parse_modules, parse_named_connections
from ..syntax import line_indent_at


AUTOINST_RE = re.compile(r"/\*AUTOINST\*/")
AUTOINSTPARAM_RE = re.compile(r"/\*AUTOINSTPARAM\*/")


def _port_groups(ports: list[Port], manual: set[str]) -> list[Port]:
    selected: list[Port] = []
    for direction, group in direction_groups(ports):
        del direction
        selected.extend(port for port in group if port.name not in manual)
    return selected


def _format_autoinst(indent: str, ports: list[Port]) -> str:
    if not ports:
        return ")"
    lines: list[str] = []
    remaining = set(port.name for port in ports)
    for direction, group in direction_groups(ports):
        group = [port for port in group if port.name in remaining]
        if not group:
            continue
        lines.append(f"\n{indent}// {GROUP_TITLES[direction]}")
        for port in group:
            remaining.remove(port.name)
            terminator = ")" if not remaining else ","
            lines.append(
                "\n"
                + format_connection(indent, port, port_actual(port), terminator)
            )
    return "".join(lines)


def _format_param_connection(indent: str, param: Param, terminator: str) -> str:
    return f"{indent}.{param.name:<31}({param.name}){terminator}"


def _format_autoinstparam(indent: str, params: list[Param]) -> str:
    if not params:
        return ")"
    lines = [f"\n{indent}// Parameters"]
    for idx, param in enumerate(params):
        terminator = ")" if idx == len(params) - 1 else ","
        lines.append("\n" + _format_param_connection(indent, param, terminator))
    return "".join(lines)


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
            if marker is None:
                continue
            manual, _ = parse_named_connections(port_text)
            ports = _port_groups(child.ports, manual)
            marker_start = instance.port_open + 1 + marker.start()
            marker_end = instance.port_open + 1 + marker.end()
            indent = line_indent_at(text, marker_start)
            replacement = _format_autoinst(indent, ports)
            replacements.append((marker_end, instance.port_close + 1, replacement))
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
            params = [param for param in child.params if param.name not in manual]
            marker_start = instance.param_open + 1 + marker.start()
            marker_end = instance.param_open + 1 + marker.end()
            indent = line_indent_at(text, marker_start)
            replacement = _format_autoinstparam(indent, params)
            replacements.append((marker_end, instance.param_close + 1, replacement))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text
