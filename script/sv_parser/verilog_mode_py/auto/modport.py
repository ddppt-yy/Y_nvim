from __future__ import annotations

import re

from ..formatter import format_declaration
from ..library import ModuleLibrary
from ..model import Port
from ..syntax import line_indent_at, split_top_level


INOUTMODPORT_RE = re.compile(r"/\*AUTOINOUTMODPORT\((.*?)\)\*/", re.S)
ASSIGNMODPORT_RE = re.compile(r"/\*AUTOASSIGNMODPORT\((.*?)\)\*/", re.S)


def _parse_args(arg_text: str) -> list[str]:
    args: list[str] = []
    for item in split_top_level(arg_text):
        item = item.strip()
        if len(item) >= 2 and item[0] == '"' and item[-1] == '"':
            item = item[1:-1]
        args.append(item)
    return args


def _signal_map(interface) -> dict[str, Port]:
    return {signal.name: signal for signal in interface.signals}


def _module_port_from_modport(signal: Port, direction: str, prefix: str) -> Port:
    return Port(
        name=f"{prefix}{signal.name}",
        direction=direction,
        data_type=signal.data_type,
        packed=signal.packed,
        unpacked=signal.unpacked,
    )


def _format_inoutmodport_block(indent: str, interface, modport: str, prefix: str) -> str:
    entries = interface.modports.get(modport, [])
    if not entries:
        return ""
    signals = _signal_map(interface)
    lines = [f"\n{indent}// Beginning of automatic in/out/inouts (from modport)"]
    for direction in ("output", "inout", "input"):
        for signal_name, entry_direction in entries:
            if entry_direction != direction or signal_name not in signals:
                continue
            port = _module_port_from_modport(signals[signal_name], direction, prefix)
            lines.append("\n" + format_declaration(indent, port))
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)


def _format_assignmodport_block(
    indent: str, interface, modport: str, inst_name: str, prefix: str
) -> str:
    entries = interface.modports.get(modport, [])
    if not entries:
        return ""
    lines = [f"\n{indent}// Beginning of automatic assignments from modport"]
    for direction in ("output", "inout", "input"):
        for signal_name, entry_direction in entries:
            if entry_direction != direction:
                continue
            local = f"{prefix}{signal_name}"
            remote = f"{inst_name}.{signal_name}"
            if direction == "input":
                lines.append(f"\n{indent}assign {local} = {remote};")
            else:
                lines.append(f"\n{indent}assign {remote} = {local};")
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)


def expand_modport(text: str, library: ModuleLibrary) -> str:
    replacements: list[tuple[int, str]] = []
    for match in INOUTMODPORT_RE.finditer(text):
        args = _parse_args(match.group(1))
        if len(args) < 2:
            continue
        interface = library.lookup(args[0])
        if interface is None:
            continue
        prefix = args[3] if len(args) > 3 else ""
        indent = line_indent_at(text, match.start())
        replacements.append(
            (match.end(), _format_inoutmodport_block(indent, interface, args[1], prefix))
        )
    for match in ASSIGNMODPORT_RE.finditer(text):
        args = _parse_args(match.group(1))
        if len(args) < 4:
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
