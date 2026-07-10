from __future__ import annotations

import re
from dataclasses import dataclass

from ..formatter import format_declaration
from ..library import ModuleLibrary
from ..model import Port
from ..sv_parse import parse_modules, parse_named_connections
from ..syntax import line_indent_at


@dataclass(frozen=True)
class PortUse:
    port: Port
    inst_name: str
    module_name: str


MARKERS = {
    "input": re.compile(r"/\*AUTOINPUT\*/"),
    "output": re.compile(r"/\*AUTOOUTPUT\*/"),
    "inout": re.compile(r"/\*AUTOINOUT\*/"),
    "wire": re.compile(r"/\*AUTOWIRE\*/"),
    "logic": re.compile(r"/\*AUTOLOGIC\*/"),
}


BEGIN_TEXT = {
    "input": "inputs (from unused autoinst inputs)",
    "output": "outputs (from unused autoinst outputs)",
    "inout": "inouts (from unused autoinst inouts)",
    "wire": "wires (for undeclared instantiated-module outputs)",
    "logic": "logics (for undeclared instantiated-module outputs)",
}


def _collect_port_uses(text: str, library: ModuleLibrary) -> dict[str, list[PortUse]]:
    result: dict[str, list[PortUse]] = {"input": [], "output": [], "inout": []}
    modules = parse_modules(text)
    for module in modules:
        for instance in module.instances:
            child = library.lookup(instance.module)
            if child is None:
                continue
            port_text = text[instance.port_open + 1 : instance.port_close]
            has_auto = "AUTOINST" in port_text
            if has_auto:
                manual_text = port_text.split("/*AUTOINST*/", 1)[0]
            else:
                manual_text = port_text
            manual, has_star = parse_named_connections(manual_text)
            if not has_auto and not has_star:
                continue
            for port in child.ports:
                if port.name in manual:
                    continue
                if port.direction in result:
                    result[port.direction].append(
                        PortUse(port=port, inst_name=instance.name, module_name=instance.module)
                    )
    return result


def _existing_names_for_module(module) -> set[str]:
    return module.declared_names()


def _comment_for(use: PortUse) -> str:
    if use.port.direction == "input":
        return f"// To {use.inst_name} of {use.module_name}"
    if use.port.direction == "output":
        return f"// From {use.inst_name} of {use.module_name}"
    return f"// To/From {use.inst_name} of {use.module_name}"


def _format_block(indent: str, kind: str, uses: list[PortUse]) -> str:
    if not uses:
        return ""
    lines = [
        f"\n{indent}// Beginning of automatic {BEGIN_TEXT[kind]}",
    ]
    for use in uses:
        port = use.port
        if kind == "wire":
            port = Port(
                name=port.name,
                direction="wire",
                data_type="",
                packed=port.packed,
                unpacked=port.unpacked,
            )
            comment = _comment_for(use)
        elif kind == "logic":
            port = Port(
                name=port.name,
                direction="logic",
                data_type="",
                packed=port.packed,
                unpacked=port.unpacked,
            )
            comment = _comment_for(use)
        else:
            comment = _comment_for(use)
        lines.append("\n" + format_declaration(indent, port, comment))
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)


def expand_declarations(text: str, library: ModuleLibrary) -> str:
    uses_by_direction = _collect_port_uses(text, library)
    modules = parse_modules(text)
    replacements: list[tuple[int, str]] = []
    planned: set[str] = set()

    for module in modules:
        existing = _existing_names_for_module(module) | planned
        module_text = text[module.start : module.end]
        marker_matches: list[tuple[int, str, re.Match[str]]] = []
        for kind, regex in MARKERS.items():
            for match in regex.finditer(module_text):
                marker_matches.append((module.start + match.start(), kind, match))
        for abs_start, kind, match in sorted(marker_matches):
            if kind in {"input", "output", "inout"}:
                candidates = uses_by_direction[kind]
            else:
                candidates = uses_by_direction["output"] + uses_by_direction["inout"]
            selected: list[PortUse] = []
            for use in candidates:
                if use.port.name in existing:
                    continue
                selected.append(use)
                existing.add(use.port.name)
                planned.add(use.port.name)
            if not selected:
                continue
            indent = line_indent_at(text, abs_start)
            insertion = _format_block(indent, kind, selected)
            replacements.append((module.start + match.end(), insertion))

    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text
