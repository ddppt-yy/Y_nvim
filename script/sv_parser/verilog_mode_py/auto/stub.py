from __future__ import annotations

import re

from ..formatter import format_declaration, format_parameter
from ..library import ModuleLibrary
from ..model import Port
from ..sv_parse import parse_modules
from ..syntax import line_indent_at


INOUTPARAM_RE = re.compile(r"/\*AUTOINOUTPARAM\(\"([^\"]+)\"\)\*/")
INOUTMODULE_RE = re.compile(r"/\*AUTOINOUTMODULE\(\"([^\"]+)\"\)\*/")
AUTOTIEOFF_RE = re.compile(r"/\*AUTOTIEOFF\*/")
AUTOUNUSED_RE = re.compile(r"/\*AUTOUNUSED\*/")
AUTOUNDEF_RE = re.compile(r"/\*AUTOUNDEF\*/")
DEFINE_RE = re.compile(r"^[ \t]*`define\s+([A-Za-z_][$A-Za-z0-9_]*)", re.M)


def _group_ports(ports: list[Port]) -> list[Port]:
    grouped: list[Port] = []
    for direction in ("output", "inout", "input"):
        grouped.extend(port for port in ports if port.direction == direction)
    return grouped


def _expand_inout_param(text: str, library: ModuleLibrary) -> str:
    replacements: list[tuple[int, str]] = []
    for match in INOUTPARAM_RE.finditer(text):
        module = library.lookup(match.group(1))
        if module is None or not module.params:
            continue
        indent = line_indent_at(text, match.start())
        lines = [f"\n{indent}// Beginning of automatic parameters (from specific module)"]
        for param in module.params:
            lines.append("\n" + format_parameter(indent, param))
        lines.append(f"\n{indent}// End of automatics")
        replacements.append((match.end(), "".join(lines)))
    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text


def _expand_inout_module(text: str, library: ModuleLibrary) -> str:
    replacements: list[tuple[int, str]] = []
    for match in INOUTMODULE_RE.finditer(text):
        module = library.lookup(match.group(1))
        if module is None or not module.ports:
            continue
        indent = line_indent_at(text, match.start())
        lines = [f"\n{indent}// Beginning of automatic in/out/inouts (from specific module)"]
        for port in _group_ports(module.ports):
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


def _expand_tieoff(text: str) -> str:
    replacements: list[tuple[int, str]] = []
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
            lines.append(f"\n{indent}assign {port.name} = '0;")
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
    text = _expand_tieoff(text)
    text = _expand_unused(text)
    text = _expand_undef(text)
    return text
