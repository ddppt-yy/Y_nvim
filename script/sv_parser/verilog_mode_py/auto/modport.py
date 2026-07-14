from __future__ import annotations

import re

from ..formatter import format_declaration
from ..library import ModuleLibrary
from ..model import Port
from ..sv_parse import parse_modules
from ..syntax import line_indent_at, split_top_level


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
