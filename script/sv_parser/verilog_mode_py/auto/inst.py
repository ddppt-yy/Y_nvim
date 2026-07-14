from __future__ import annotations

import re

from ..formatter import GROUP_TITLES, direction_groups, format_connection
from ..library import ModuleLibrary
from ..model import Instance, Param, Port
from ..sv_parse import parse_modules, parse_named_connections
from ..syntax import line_indent_at, mask_syntax, split_bracketed_dims
from .param_values import (
    inst_param_value_enabled,
    instance_param_values,
    ports_with_param_values,
)
from .template import actual_for_param, actual_for_port, find_template_for_instance, is_nohookup


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


def _emacs_regexp_to_python(regexp: str) -> str:
    return (
        regexp.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\|", "|")
        .replace(r"\<", r"\b")
        .replace(r"\>", r"\b")
    )


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


def _dimension_comment(port: Port) -> str:
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
