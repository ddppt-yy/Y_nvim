from __future__ import annotations

import re
from pathlib import Path

from .model import Instance, ModuleInfo, Param, Port
from .syntax import (
    IDENT_RE,
    find_matching,
    find_top_level_semicolon,
    mask_syntax,
    normalize_space,
    previous_nonspace,
    skip_ws,
    split_statements,
    split_top_level,
    strip_top_level_assignment,
)


DIRECTIONS = {"input", "output", "inout"}
DATA_KEYWORDS = {
    "wire",
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
    "reg",
    "logic",
    "bit",
    "byte",
    "shortint",
    "int",
    "longint",
    "integer",
    "time",
    "real",
    "realtime",
    "shortreal",
    "signed",
    "unsigned",
}
INSTANCE_SKIP = DIRECTIONS | DATA_KEYWORDS | {
    "assign",
    "always",
    "always_comb",
    "always_ff",
    "always_latch",
    "begin",
    "case",
    "class",
    "covergroup",
    "else",
    "end",
    "endcase",
    "endclass",
    "endfunction",
    "endmodule",
    "endpackage",
    "endtask",
    "for",
    "foreach",
    "function",
    "generate",
    "genvar",
    "if",
    "import",
    "initial",
    "interface",
    "localparam",
    "module",
    "package",
    "parameter",
    "property",
    "return",
    "task",
    "typedef",
}


def _clean(text: str) -> str:
    return normalize_space(mask_syntax(text, keep_newlines=False))


def _last_identifier(text: str) -> tuple[str, int, int] | None:
    matches = list(IDENT_RE.finditer(mask_syntax(text, keep_newlines=False)))
    if not matches:
        return None
    match = matches[-1]
    return text[match.start() : match.end()].strip(), match.start(), match.end()


def _strip_trailing_unpacked(text: str) -> tuple[str, str]:
    unpacked: list[str] = []
    work = text.rstrip()
    while work.endswith("]"):
        open_pos = work.rfind("[")
        if open_pos < 0:
            break
        dim = work[open_pos:].strip()
        unpacked.insert(0, dim)
        work = work[:open_pos].rstrip()
    return work, " ".join(unpacked)


def _extract_packed(prefix: str) -> tuple[str, str]:
    dims = re.findall(r"\[[^\]]+\]", prefix)
    no_dims = re.sub(r"\[[^\]]+\]", " ", prefix)
    return normalize_space(no_dims), " ".join(dim.strip() for dim in dims)


def parse_param_item(item: str) -> Param | None:
    item = item.strip().rstrip(",;")
    if not item:
        return None
    left, value = strip_top_level_assignment(item)
    left = re.sub(r"^\s*(parameter|localparam)\b", "", left).strip()
    left = re.sub(r"^\s*type\b", "", left).strip()
    ident = _last_identifier(left)
    if ident is None:
        return None
    name, start, _ = ident
    prefix = left[:start].strip()
    data_type, packed = _extract_packed(prefix)
    return Param(name=name, value=value, data_type=data_type, packed=packed)


def parse_param_list(text: str) -> list[Param]:
    params: list[Param] = []
    for item in split_top_level(text):
        param = parse_param_item(item)
        if param is not None:
            params.append(param)
    return params


def parse_port_item(
    item: str,
    default_direction: str = "",
    default_type: str = "",
    default_packed: str = "",
) -> tuple[Port | None, str, str, str]:
    item = item.strip().rstrip(",;")
    if not item:
        return None, default_direction, default_type, default_packed
    left, _ = strip_top_level_assignment(item)
    left = re.sub(r"\(\*.*?\*\)", " ", left, flags=re.S).strip()
    left, unpacked = _strip_trailing_unpacked(left)
    ident = _last_identifier(left)
    if ident is None:
        return None, default_direction, default_type, default_packed
    name, start, _ = ident
    prefix = left[:start].strip()
    words = prefix.split()

    direction = default_direction
    if words and words[0] in DIRECTIONS:
        direction = words[0]
        words = words[1:]

    prefix_after_direction = " ".join(words)
    data_type, packed = _extract_packed(prefix_after_direction)
    if not data_type and direction == default_direction:
        data_type = default_type
    if not packed and direction == default_direction:
        packed = default_packed

    interface_type: tuple[str, ...] = ()
    if not direction and data_type and data_type.split()[0] not in DATA_KEYWORDS:
        pieces = data_type.split(".")
        interface_type = tuple(piece for piece in pieces if piece)

    port = Port(
        name=name,
        direction=direction,
        data_type=data_type,
        packed=packed,
        unpacked=unpacked,
        interface_type=interface_type,
    )
    return port, direction, data_type, packed


def parse_port_items(text: str) -> list[Port]:
    ports: list[Port] = []
    direction = ""
    data_type = ""
    packed = ""
    for item in split_top_level(text):
        port, direction, data_type, packed = parse_port_item(
            item, direction, data_type, packed
        )
        if port is not None:
            ports.append(port)
    return ports


def parse_header(
    text: str, module_start: int
) -> tuple[list[Param], list[Port], list[str], int | None, int | None]:
    masked = mask_syntax(text)
    match = re.search(r"\b(?:module|interface)\s+(" + IDENT_RE.pattern + r")", masked)
    if match is None:
        return [], [], [], None, None
    idx = skip_ws(masked, match.end())
    params: list[Param] = []
    ports: list[Port] = []
    port_names: list[str] = []
    port_open_abs: int | None = None
    port_close_abs: int | None = None

    if idx < len(masked) and masked[idx] == "#":
        idx = skip_ws(masked, idx + 1)
        if idx < len(masked) and masked[idx] == "(":
            close = find_matching(text, idx)
            if close is not None:
                params = parse_param_list(text[idx + 1 : close])
                idx = skip_ws(masked, close + 1)

    if idx < len(masked) and masked[idx] == "(":
        close = find_matching(text, idx)
        if close is not None:
            port_open_abs = module_start + idx
            port_close_abs = module_start + close
            port_text = text[idx + 1 : close]
            ports = parse_port_items(port_text)
            port_names = [port.name for port in ports]
            if not any(port.direction for port in ports):
                ports = []
                port_names = []
                for item in split_top_level(port_text):
                    ident = _last_identifier(item)
                    if ident is not None:
                        port_names.append(ident[0])
    return params, ports, port_names, port_open_abs, port_close_abs


def parse_declaration_statement(statement: str) -> tuple[list[Port], list[Param]]:
    stripped = statement.strip().rstrip(";")
    if not stripped:
        return [], []
    masked = mask_syntax(stripped, keep_newlines=False)
    keyword_re = re.compile(
        r"\b("
        + "|".join(sorted(DIRECTIONS | DATA_KEYWORDS | {"parameter", "localparam"}))
        + r")\b"
    )
    keyword_match = None
    for match in keyword_re.finditer(masked):
        if not masked[: match.start()].strip():
            keyword_match = match
            break
    if keyword_match is None:
        return [], []
    stripped = stripped[keyword_match.start() :].strip()
    first = stripped.split(None, 1)[0]
    if first in DIRECTIONS:
        return parse_port_items(stripped), []
    if first in DATA_KEYWORDS:
        ports = parse_port_items(stripped)
        signals = [
            Port(
                name=port.name,
                direction="",
                data_type=port.data_type or first,
                packed=port.packed,
                unpacked=port.unpacked,
                interface_type=port.interface_type,
            )
            for port in ports
        ]
        return signals, []
    if first in {"parameter", "localparam"}:
        params = [param for param in parse_param_list(stripped) if param is not None]
        return [], params
    return [], []


def order_ports_by_header(ports: list[Port], header_names: list[str]) -> list[Port]:
    if not header_names:
        return ports
    by_name = {port.name: port for port in ports}
    ordered = [by_name[name] for name in header_names if name in by_name]
    seen = {port.name for port in ordered}
    ordered.extend(port for port in ports if port.name not in seen)
    return ordered


def parse_body_declarations(body: str) -> tuple[list[Port], list[Param]]:
    ports: list[Port] = []
    params: list[Param] = []
    for _, _, statement in split_statements(body):
        parsed_ports, parsed_params = parse_declaration_statement(statement)
        ports.extend(parsed_ports)
        params.extend(parsed_params)
    return ports, params


def parse_modports(body: str) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {}
    masked = mask_syntax(body)
    for match in re.finditer(r"\bmodport\s+(" + IDENT_RE.pattern + r")\s*\(", masked):
        name = body[match.start(1) : match.end(1)].strip()
        open_pos = match.end() - 1
        close = find_matching(body, open_pos)
        if close is None:
            continue
        entries: list[tuple[str, str]] = []
        for item in split_top_level(body[open_pos + 1 : close]):
            clean = _clean(item)
            if not clean:
                continue
            words = clean.split()
            if not words or words[0] not in {"input", "output", "inout", "ref"}:
                continue
            direction = words[0]
            for signal in words[1:]:
                signal = signal.strip(",")
                if IDENT_RE.fullmatch(signal):
                    entries.append((signal, direction))
        result.setdefault(name, []).extend(entries)
    return result


def parse_instances(module_text: str, absolute_start: int) -> list[Instance]:
    masked = mask_syntax(module_text)
    instances: list[Instance] = []
    pos = 0
    while True:
        match = IDENT_RE.search(masked, pos)
        if match is None:
            break
        module_name = module_text[match.start() : match.end()]
        pos = match.end()
        if module_name in INSTANCE_SKIP:
            continue
        if previous_nonspace(masked, match.start()) in {".", "`"}:
            continue
        idx = skip_ws(masked, match.end())
        param_open = param_close = None
        if idx < len(masked) and masked[idx] == "#":
            idx = skip_ws(masked, idx + 1)
            if idx >= len(masked) or masked[idx] != "(":
                continue
            close = find_matching(module_text, idx)
            if close is None:
                continue
            param_open = absolute_start + idx
            param_close = absolute_start + close
            idx = skip_ws(masked, close + 1)
        inst_match = IDENT_RE.match(masked, idx)
        if inst_match is None:
            continue
        inst_name = module_text[inst_match.start() : inst_match.end()]
        idx = skip_ws(masked, inst_match.end())
        if idx >= len(masked) or masked[idx] != "(":
            continue
        port_close = find_matching(module_text, idx)
        if port_close is None:
            continue
        after = skip_ws(masked, port_close + 1)
        if after >= len(masked) or masked[after] != ";":
            continue
        instances.append(
            Instance(
                module=module_name,
                name=inst_name,
                start=absolute_start + match.start(),
                end=absolute_start + after + 1,
                port_open=absolute_start + idx,
                port_close=absolute_start + port_close,
                param_open=param_open,
                param_close=param_close,
            )
        )
        pos = after + 1
    return instances


def parse_named_connections(port_text: str) -> tuple[set[str], bool]:
    names: set[str] = set()
    has_star = False
    masked = mask_syntax(port_text)
    for match in re.finditer(r"\.\s*(" + IDENT_RE.pattern + r"|\*)", masked):
        name = port_text[match.start(1) : match.end(1)].strip()
        if name == "*":
            has_star = True
        else:
            names.add(name)
    return names, has_star


def parse_modules(text: str, source_path: Path | None = None) -> list[ModuleInfo]:
    masked = mask_syntax(text)
    modules: list[ModuleInfo] = []
    pattern = re.compile(r"\b(module|interface)\s+(" + IDENT_RE.pattern + r")")
    pos = 0
    while True:
        match = pattern.search(masked, pos)
        if match is None:
            break
        kind = match.group(1)
        name = text[match.start(2) : match.end(2)].strip()
        end_keyword = "endmodule" if kind == "module" else "endinterface"
        end_match = re.search(r"\b" + end_keyword + r"\b", masked[match.end() :])
        if end_match is None:
            pos = match.end()
            continue
        end_start = match.end() + end_match.start()
        end = match.end() + end_match.end()
        header_end = find_top_level_semicolon(text, match.end())
        if header_end is None or header_end > end_start:
            pos = match.end()
            continue
        header = text[match.start() : header_end + 1]
        params, header_ports, header_names, port_open, port_close = parse_header(
            header, match.start()
        )
        body = text[header_end + 1 : end_start]
        body_ports, body_params = parse_body_declarations(body)
        params.extend(body_params)
        if header_ports:
            ports = header_ports
            signal_names = {port.name for port in ports}
            signals = [port for port in body_ports if port.name not in signal_names]
        else:
            ports = order_ports_by_header(
                [port for port in body_ports if port.direction], header_names
            )
            signals = [port for port in body_ports if not port.direction]
        modports = parse_modports(body)
        module_body_start = header_end + 1
        instances = parse_instances(body, module_body_start)
        modules.append(
            ModuleInfo(
                name=name,
                kind=kind,
                ports=ports,
                params=params,
                signals=signals,
                modports=modports,
                instances=instances,
                source_path=source_path,
                start=match.start(),
                end=end,
                header_end=header_end,
                header_port_open=port_open,
                header_port_close=port_close,
            )
        )
        pos = end
    return modules


def simple_signal_name(expr: str) -> str | None:
    expr = expr.strip()
    match = IDENT_RE.match(expr)
    if match is None:
        return None
    name = expr[match.start() : match.end()]
    rest = expr[match.end() :].strip()
    if not rest:
        return name
    if re.fullmatch(r"(?:\[[^\]]+\]\s*)+", rest):
        return name
    return None
