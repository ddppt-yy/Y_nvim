from __future__ import annotations

import re

from ..formatter import declaration_prefix, format_declaration, format_identifier, format_parameter
from ..library import ModuleLibrary
from ..model import Port
from ..sv_parse import parse_modules
from ..syntax import line_indent_at, split_top_level


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


def _parse_args(arg_text: str) -> list[str]:
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
