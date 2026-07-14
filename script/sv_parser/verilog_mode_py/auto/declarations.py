from __future__ import annotations

import re
from dataclasses import dataclass

from ..formatter import declaration_prefix, format_declaration, format_identifier
from ..library import ModuleLibrary
from ..model import Port
from ..primitives import GATE_IOS
from ..sv_parse import parse_modules, parse_named_connections
from ..syntax import (
    IDENT_RE,
    find_matching,
    line_indent_at,
    mask_syntax,
    split_bracketed_dims,
    split_top_level,
)
from .param_values import (
    inst_param_value_enabled,
    instance_param_values,
    port_with_param_values,
)
from .template import (
    actual_for_param,
    actual_for_port,
    extract_actual_signals,
    find_template_for_instance,
    is_nohookup,
)


@dataclass(frozen=True)
class PortUse:
    port: Port
    inst_name: str
    module_name: str
    multiple: bool = False
    primitive: bool = False
    comment: str | None = None


def _merge_duplicate_uses(uses: list[PortUse]) -> list[PortUse]:
    merged: dict[str, PortUse] = {}
    order: list[str] = []
    for use in uses:
        name = use.port.name
        if name not in merged:
            merged[name] = use
            order.append(name)
        else:
            first = merged[name]
            if (
                first.inst_name == use.inst_name
                and first.module_name == use.module_name
                and first.primitive == use.primitive
            ):
                continue
            port, couldnt_merge = _merge_port_ranges(first.port, use.port)
            comment = first.comment
            if couldnt_merge:
                comment = _comment_for(
                    PortUse(
                        port=first.port,
                        inst_name=first.inst_name,
                        module_name=first.module_name,
                        multiple=True,
                        primitive=first.primitive,
                    )
                ) + ", Couldn't Merge"
            merged[name] = PortUse(
                port=port,
                inst_name=first.inst_name,
                module_name=first.module_name,
                multiple=True,
                primitive=first.primitive,
                comment=comment,
            )
    return [merged[name] for name in order]


def _light_simplify_expr(expr: str) -> str:
    expr = expr.strip()
    expr = re.sub(r"\b([A-Za-z_][$A-Za-z0-9_]*|\d+)\s*\*\s*1\b", r"\1", expr)
    expr = re.sub(r"\b1\s*\*\s*([A-Za-z_][$A-Za-z0-9_]*|\d+)\b", r"\1", expr)

    def minus_plus(match: re.Match[str]) -> str:
        name = match.group(1)
        delta = int(match.group(3)) - int(match.group(2))
        if delta == 0:
            return name
        op = "+" if delta > 0 else "-"
        return f"{name}{op}{abs(delta)}"

    expr = re.sub(
        r"\b([A-Za-z_][$A-Za-z0-9_]*)\s*-\s*(\d+)\s*\+\s*(\d+)\b",
        minus_plus,
        expr,
    )
    return expr


def _eval_simple_const(expr: str) -> int | None:
    expr = _light_simplify_expr(expr)
    if not re.fullmatch(r"[0-9+\-*/%() \t]+", expr):
        return None
    try:
        return int(eval(expr.replace("/", "//"), {"__builtins__": {}}, {}))
    except Exception:
        return None


def _single_range(packed: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\[\s*([^:\]]+)\s*:\s*([^:\]]+)\s*\]", packed.strip())
    if match is None:
        return None
    left = _eval_simple_const(match.group(1))
    right = _eval_simple_const(match.group(2))
    if left is None or right is None:
        return None
    return left, right


def _merge_port_ranges(first: Port, second: Port) -> tuple[Port, bool]:
    if (
        first.direction != second.direction
        or first.data_type != second.data_type
        or first.unpacked != second.unpacked
    ):
        return first, False
    if re.sub(r"\s+", "", first.packed) == re.sub(r"\s+", "", second.packed):
        return first, False
    first_dims = split_bracketed_dims(first.packed)
    second_dims = split_bracketed_dims(second.packed)
    if (
        len(first_dims) != 1
        or len(second_dims) != 1
        or ":" not in first_dims[0]
        or ":" not in second_dims[0]
    ):
        return first, False
    first_range = _single_range(first.packed)
    second_range = _single_range(second.packed)
    if first_range is None or second_range is None:
        return second, bool(first.packed or second.packed)
    high = max(first_range[0], first_range[1], second_range[0], second_range[1])
    low = min(first_range[0], first_range[1], second_range[0], second_range[1])
    return Port(
        name=first.name,
        direction=first.direction,
        data_type=first.data_type,
        packed=f"[{high}:{low}]",
        unpacked=first.unpacked,
        interface_type=first.interface_type,
    ), False


MARKERS = {
    "input": re.compile(r"/\*AUTOINPUT(?:\((.*?)\))?\*/", re.S | re.I),
    "output": re.compile(r"/\*AUTOOUTPUT(?:\((.*?)\))?\*/", re.S | re.I),
    "outputevery": re.compile(
        r"/\*AUTOOUTPUTEVERY(?:\((.*?)\))?\*/", re.S | re.I
    ),
    "inout": re.compile(r"/\*AUTOINOUT(?:\((.*?)\))?\*/", re.S | re.I),
    "wire": re.compile(r"/\*AUTOWIRE(?:\((.*?)\))?\*/", re.S | re.I),
    "logic": re.compile(r"/\*AUTOLOGIC(?:\((.*?)\))?\*/", re.S | re.I),
    "reginput": re.compile(r"/\*AUTOREGINPUT(?:\((.*?)\))?\*/", re.S | re.I),
}
AUTOINST_RE = re.compile(r"/\*AUTOINST(?:\((.*?)\))?\*/", re.S | re.I)


BEGIN_TEXT = {
    "input": "inputs (from unused autoinst inputs)",
    "output": "outputs (from unused autoinst outputs)",
    "outputevery": "outputs (every signal)",
    "inout": "inouts (from unused autoinst inouts)",
    "wire": "wires (for undeclared instantiated-module outputs)",
    "logic": "wires (for undeclared instantiated-module outputs)",
    "reginput": "reg inputs (for undeclared instantiated-module inputs)",
}

NET_TYPE_WORDS = {
    "wire",
    "reg",
    "tri",
    "supply0",
    "supply1",
    "wand",
    "wor",
    "triand",
    "trior",
    "tri0",
    "tri1",
    "uwire",
}
TYPE_QUALIFIERS = {"signed", "unsigned"}
CHILD_PORT_DECL_STRIP_WORDS = {"wire", "reg", "var"}


def _auto_ignore_concat(text: str) -> bool:
    return re.search(r"\bverilog-auto-ignore-concat\s*:\s*t\b", text) is not None


def _auto_declare_nettype(text: str) -> str:
    match = re.search(r'\bverilog-auto-declare-nettype\s*:\s*"([^"]+)"', text)
    return match.group(1).strip() if match else ""


def _auto_output_ignore_regexp(text: str) -> str:
    match = re.search(r'\bverilog-auto-output-ignore-regexp\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def _with_decl_nettype(port: Port, nettype: str) -> Port:
    if not nettype or port.data_type or port.direction not in {"input", "output", "inout"}:
        return port
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=nettype,
        packed=port.packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )


def _strip_child_nettype(port: Port) -> Port:
    words = port.data_type.split()
    if not words or words[0] not in CHILD_PORT_DECL_STRIP_WORDS:
        return port
    kept = [word for word in words if word not in CHILD_PORT_DECL_STRIP_WORDS]
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=" ".join(kept),
        packed=port.packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )


def _declaration_port_from_child(port: Port, declare_nettype: str) -> Port:
    return _with_decl_nettype(_strip_child_nettype(port), declare_nettype)


def _template_param_map(child, template, instance) -> dict[str, str]:
    result: dict[str, str] = {}
    for param in child.params:
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


def _port_with_template_param_names(port: Port, param_map: dict[str, str]) -> Port:
    if not param_map:
        return port
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=port.data_type,
        packed=_replace_param_names(port.packed, param_map),
        unpacked=_replace_param_names(port.unpacked, param_map),
        interface_type=port.interface_type,
    )


def _primitive_port_uses(
    port_text: str,
    instance,
    *,
    ignore_concat: bool,
) -> list[PortUse] | None:
    directions = GATE_IOS.get(instance.module)
    if directions is None:
        return None
    marker = AUTOINST_RE.search(port_text)
    if marker is None:
        return []
    manual_text = port_text[: marker.start()]
    uses: list[PortUse] = []
    for idx, actual in enumerate(split_top_level(manual_text)):
        direction = directions[idx] if idx < len(directions) else "input"
        if direction not in {"input", "output", "inout"}:
            continue
        for signal in extract_actual_signals(actual, ignore_concat=ignore_concat):
            uses.append(
                PortUse(
                    port=Port(
                        name=signal.name,
                        direction=direction,
                        packed=signal.packed,
                        unpacked="",
                    ),
                    inst_name=instance.name,
                    module_name=instance.module,
                    primitive=True,
                )
            )
    return uses


def _named_connection_actuals(port_text: str) -> dict[str, str]:
    masked = mask_syntax(port_text)
    actuals: dict[str, str] = {}
    for match in re.finditer(r"\.\s*(" + IDENT_RE.pattern + r")\s*\(", masked):
        name = port_text[match.start(1) : match.end(1)].strip()
        open_pos = match.end() - 1
        close_pos = find_matching(port_text, open_pos)
        if close_pos is None:
            continue
        actuals[name] = port_text[open_pos + 1 : close_pos].strip()
    return actuals


def _uses_from_actual(
    port: Port,
    decl_port: Port,
    actual: str,
    instance,
    *,
    ignore_concat: bool,
    use_decl_packed: bool = True,
) -> list[PortUse]:
    uses: list[PortUse] = []
    for signal in extract_actual_signals(actual, ignore_concat=ignore_concat):
        uses.append(
            PortUse(
                port=Port(
                    name=signal.name,
                    direction=port.direction,
                    data_type=decl_port.data_type,
                    packed=signal.packed
                    or (
                        decl_port.packed
                        if use_decl_packed and signal.use_port_packed
                        else ""
                    ),
                    unpacked=signal.unpacked
                    or (decl_port.unpacked if use_decl_packed else ""),
                ),
                inst_name=instance.name,
                module_name=instance.module,
            )
        )
    return uses


def _auto_wire_type(text: str, module_text: str) -> str:
    match = re.search(r'\bverilog-auto-wire-type\s*:\s*"([^"]+)"', text)
    if match is not None:
        return match.group(1).strip()
    if re.search(r"/\*AUTOLOGIC(?:\([^*]*\))?\*/", module_text, re.I):
        return "logic"
    return ""


def _split_decl_type(data_type: str) -> tuple[str, list[str]]:
    words = data_type.split()
    if words and words[0] not in NET_TYPE_WORDS | {"logic"} | TYPE_QUALIFIERS:
        return "custom", words
    return "builtin", [
        word for word in words if word not in NET_TYPE_WORDS and word != "logic"
    ]


def _eval_const_expr(expr: str) -> str | None:
    expr = expr.strip()
    if not re.fullmatch(r"[0-9+\-*/%() \t]+", expr):
        return None
    try:
        return str(int(eval(expr.replace("/", "//"), {"__builtins__": {}}, {})))
    except Exception:
        return None


def _simplify_dim(dim: str, *, eval_constants: bool = True) -> str:
    stripped = dim.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return dim
    parts = split_top_level(stripped[1:-1], ":")
    if len(parts) != 2:
        return dim
    left_text = _light_simplify_expr(parts[0])
    right_text = _light_simplify_expr(parts[1])
    if not eval_constants:
        return f"[{left_text}:{right_text}]"
    left = _eval_const_expr(left_text)
    right = _eval_const_expr(right_text)
    if left is None or right is None:
        return f"[{left_text}:{right_text}]"
    return f"[{left}:{right}]"


def _simplify_packed_dims(port: Port) -> Port:
    dims = split_bracketed_dims(port.packed)
    if not dims:
        return port
    if len(dims) == 1:
        packed = _simplify_dim(dims[0], eval_constants=False)
    else:
        packed = " ".join([dims[0], *(_simplify_dim(dim) for dim in dims[1:])])
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=port.data_type,
        packed=packed,
        unpacked=port.unpacked,
        interface_type=port.interface_type,
    )


def _port_for_declaration_kind(port: Port, kind: str, wire_type: str) -> Port:
    if kind == "outputevery":
        kind = "output"
    port = _simplify_packed_dims(port)
    type_kind, words = _split_decl_type(port.data_type)
    if kind == "logic":
        if type_kind == "custom":
            return Port(
                name=port.name,
                direction="",
                data_type=port.data_type,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
        return Port(
            name=port.name,
            direction="logic",
            data_type=" ".join(words),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    if kind == "reginput":
        if type_kind == "custom":
            return Port(
                name=port.name,
                direction="",
                data_type=port.data_type,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
        return Port(
            name=port.name,
            direction="logic",
            data_type=" ".join(words),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    if kind == "wire":
        if type_kind == "custom":
            return Port(
                name=port.name,
                direction="",
                data_type=port.data_type,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
        direction = (
            "logic"
            if wire_type == "logic"
            or (wire_type != "wire" and port.data_type.split()[:1] == ["logic"])
            else "wire"
        )
        return Port(
            name=port.name,
            direction=direction,
            data_type=" ".join(words),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    if wire_type == "wire" and kind in {"input", "output", "inout"} and type_kind != "custom":
        return Port(
            name=port.name,
            direction=port.direction,
            data_type=" ".join(words),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    if wire_type == "logic" and kind in {"input", "output", "inout"} and type_kind != "custom":
        return Port(
            name=port.name,
            direction=port.direction,
            data_type=" ".join(["logic", *words]),
            packed=port.packed,
            unpacked=port.unpacked,
            interface_type=port.interface_type,
        )
    return port


def _collect_port_uses_for_module(
    text: str,
    library: ModuleLibrary,
    module,
    *,
    ignore_concat: bool,
    declare_nettype: str,
) -> dict[str, list[PortUse]]:
    result: dict[str, list[PortUse]] = {"input": [], "output": [], "inout": []}
    for instance in module.instances:
        port_text = text[instance.port_open + 1 : instance.port_close]
        primitive_uses = _primitive_port_uses(
            port_text,
            instance,
            ignore_concat=ignore_concat,
        )
        if primitive_uses is not None:
            for use in primitive_uses:
                result[use.port.direction].append(use)
            continue
        child = library.lookup(instance.module)
        if child is None:
            continue
        auto_match = AUTOINST_RE.search(port_text)
        has_auto = auto_match is not None
        auto_filter = _regexp_arg(auto_match) if auto_match is not None else ""
        if auto_match is not None:
            manual_text = port_text[: auto_match.start()]
        else:
            manual_text = port_text
        manual, has_star = parse_named_connections(manual_text)
        if not has_auto and not has_star:
            continue
        manual_actuals = _named_connection_actuals(manual_text)
        template = find_template_for_instance(text, instance)
        param_map = _template_param_map(child, template, instance)
        skip_template_param_map = (
            inst_param_value_enabled(text, instance.start)
            and bool(instance_param_values(text, instance))
        )
        for child_port in child.ports:
            port = child_port
            if inst_param_value_enabled(text, instance.start):
                port = port_with_param_values(port, child.params, text, instance)
            if (
                not skip_template_param_map
                and inst_param_value_enabled(text, instance.start)
            ):
                port = _port_with_template_param_names(port, param_map)
            if port.direction in result:
                decl_port = _declaration_port_from_child(port, declare_nettype)
                if port.name in manual:
                    actual = manual_actuals.get(port.name)
                    if actual is not None:
                        templated_actual, templated = actual_for_port(
                            port,
                            template,
                            instance=instance,
                        )
                        use_decl_packed = not (
                            has_star
                            and templated
                            and actual.strip() == templated_actual.strip()
                        )
                        result[port.direction].extend(
                            _uses_from_actual(
                                port,
                                decl_port,
                                actual,
                                instance,
                                ignore_concat=ignore_concat,
                                use_decl_packed=use_decl_packed,
                            )
                        )
                    continue
                if has_auto and not _matches_name_filter(port.name, auto_filter):
                    continue
                if is_nohookup(port, template):
                    continue
                actual, templated = actual_for_port(port, template, instance=instance)
                if templated:
                    result[port.direction].extend(
                        _uses_from_actual(
                            port,
                            decl_port,
                            actual,
                            instance,
                            ignore_concat=ignore_concat,
                            use_decl_packed=False,
                        )
                    )
                else:
                    result[port.direction].append(
                        PortUse(
                            port=decl_port,
                            inst_name=instance.name,
                            module_name=instance.module,
                        )
                    )
    for direction, uses in result.items():
        result[direction] = _merge_duplicate_uses(uses)
    return result


def _existing_names_for_module(module) -> set[str]:
    return module.declared_names()


def _output_signal_uses(module) -> list[PortUse]:
    existing_ports = {port.name for port in module.ports}
    uses: list[PortUse] = []
    for signal in module.signals:
        if signal.name in existing_ports:
            continue
        port = _strip_child_nettype(
            Port(
                name=signal.name,
                direction="output",
                data_type=signal.data_type,
                packed=signal.packed,
                unpacked=signal.unpacked,
                interface_type=signal.interface_type,
            )
        )
        uses.append(
            PortUse(
                port=port,
                inst_name="",
                module_name="",
                comment="",
            )
        )
    return uses


def _comment_for(use: PortUse, *, file_suffix: bool = True) -> str:
    if use.comment is not None:
        return use.comment
    if use.primitive:
        module_name = use.module_name
    else:
        module_name = f"{use.module_name}.v" if file_suffix else use.module_name
    suffix = ", ..." if use.multiple else ""
    if use.port.direction == "input":
        return f"// To {use.inst_name} of {module_name}{suffix}"
    if use.port.direction == "output":
        return f"// From {use.inst_name} of {module_name}{suffix}"
    return f"// To/From {use.inst_name} of {module_name}{suffix}"


def _format_block(indent: str, kind: str, uses: list[PortUse], wire_type: str = "") -> str:
    if not uses:
        return ""
    lines = [
        f"\n{indent}// Beginning of automatic {BEGIN_TEXT[kind]}",
    ]
    for use in sorted(uses, key=lambda item: item.port.name):
        port = _port_for_declaration_kind(use.port, kind, wire_type)
        comment = _comment_for(use)
        lines.append("\n" + format_declaration(indent, port, comment))
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)


def _format_header_block(
    indent: str,
    kind: str,
    uses: list[PortUse],
    *,
    trailing_comma: bool = False,
    wire_type: str = "",
) -> str:
    if not uses:
        return ""
    lines = [
        f"\n{indent}// Beginning of automatic {BEGIN_TEXT[kind]}",
    ]
    sorted_uses = sorted(uses, key=lambda use: use.port.name)
    for idx, use in enumerate(sorted_uses):
        port = _port_for_declaration_kind(use.port, kind, wire_type)
        prefix = declaration_prefix(port)
        raw_terminator = "," if idx != len(sorted_uses) - 1 or trailing_comma else ""
        name = format_identifier(port.name, terminator="")
        terminator = format_identifier(port.name, terminator=raw_terminator)[len(port.name) :]
        comment = _comment_for(use, file_suffix=True)
        suffix = f" {comment}" if comment else ""
        lines.append(
            f"\n{indent}{prefix} {name}{port.unpacked}{terminator}{suffix}"
        )
    lines.append(f"\n{indent}// End of automatics")
    return "".join(lines)


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


def _matches_name_filter(name: str, regexp: str) -> bool:
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


def _matches_marker_filter(use: PortUse, regexp: str) -> bool:
    return _matches_name_filter(use.port.name, regexp)


def _existing_for_marker(
    marker_kind: str, existing_ports: set[str], existing_all: set[str]
) -> set[str]:
    if marker_kind in {"output", "outputevery"}:
        return existing_ports
    return existing_all


def expand_declarations(text: str, library: ModuleLibrary) -> str:
    modules = parse_modules(text)
    replacements: list[tuple[int, str]] = []
    ignore_concat = _auto_ignore_concat(text)
    declare_nettype = _auto_declare_nettype(text)
    output_ignore_regexp = _auto_output_ignore_regexp(text)

    for module in modules:
        uses_by_direction = _collect_port_uses_for_module(
            text,
            library,
            module,
            ignore_concat=ignore_concat,
            declare_nettype=declare_nettype,
        )
        outputevery_uses = uses_by_direction["output"] + _output_signal_uses(module)
        names_by_direction = {
            direction: {use.port.name for use in uses}
            for direction, uses in uses_by_direction.items()
        }
        planned: set[str] = set()
        existing_ports = {port.name for port in module.ports} | {
            param.name for param in module.params
        } | planned
        existing_all = _existing_names_for_module(module) | planned
        module_text = text[module.start : module.end]
        wire_type = _auto_wire_type(text, module_text)
        marker_matches: list[tuple[int, str, re.Match[str]]] = []
        for kind, regex in MARKERS.items():
            for match in regex.finditer(module_text):
                marker_matches.append((module.start + match.start(), kind, match))
        for abs_start, kind, match in sorted(marker_matches):
            def marker_candidates(marker_kind: str, marker_match: re.Match[str], existing_names: set[str]) -> list[PortUse]:
                if marker_kind in {"input", "output", "inout"}:
                    candidates = uses_by_direction[marker_kind]
                elif marker_kind == "outputevery":
                    candidates = outputevery_uses
                elif marker_kind == "reginput":
                    candidates = uses_by_direction["input"]
                else:
                    candidates = uses_by_direction["output"] + uses_by_direction["inout"]
                selected_uses: list[PortUse] = []
                regexp = _regexp_arg(marker_match)
                for use in candidates:
                    if marker_kind in {"input", "reginput"} and (
                        use.port.name in names_by_direction["output"]
                        or use.port.name in names_by_direction["inout"]
                    ):
                        continue
                    if marker_kind == "output" and (
                        use.port.name in names_by_direction["input"]
                        or use.port.name in names_by_direction["inout"]
                    ):
                        continue
                    if marker_kind == "output" and not _matches_name_filter(
                        use.port.name,
                        "?!" + output_ignore_regexp if output_ignore_regexp else "",
                    ):
                        continue
                    if use.port.name in existing_names:
                        continue
                    if not _matches_marker_filter(use, regexp):
                        continue
                    selected_uses.append(use)
                return selected_uses

            selected = marker_candidates(
                kind,
                match,
                _existing_for_marker(kind, existing_ports, existing_all),
            )
            if kind != "outputevery":
                for use in selected:
                    existing_ports.add(use.port.name)
                    existing_all.add(use.port.name)
                    planned.add(use.port.name)
            if not selected:
                continue
            indent = line_indent_at(text, abs_start)
            in_header = (
                kind in {"input", "output", "outputevery", "inout"}
                and module.header_port_open is not None
                and module.header_port_close is not None
                and module.header_port_open < abs_start < module.header_port_close
            )
            if in_header:
                trailing_comma = any(
                    later_start > abs_start
                    and module.header_port_open < later_start < module.header_port_close
                    and bool(
                        marker_candidates(
                            later_kind,
                            later_match,
                            _existing_for_marker(
                                later_kind, existing_ports, existing_all
                            ),
                        )
                    )
                    for later_start, later_kind, later_match in marker_matches
                )
                insertion = _format_header_block(
                    indent,
                    kind,
                    selected,
                    trailing_comma=trailing_comma,
                    wire_type=wire_type,
                )
            else:
                insertion = _format_block(indent, kind, selected, wire_type)
            replacements.append((module.start + match.end(), insertion))

    for pos, insertion in sorted(replacements, reverse=True):
        text = text[:pos] + insertion + text[pos:]
    return text
