from __future__ import annotations

import re
from pathlib import Path

from .model import Instance, ModuleInfo, Param, Port
from .primitives import GATE_PRIMITIVES
from .syntax import (
    IDENT_RE,
    find_matching,
    find_top_level_semicolon,
    is_only_bracketed_dims,
    iter_bracketed_ranges,
    mask_syntax,
    normalize_space,
    previous_nonspace,
    skip_ws,
    split_statements,
    split_top_level,
    strip_top_level_assignment,
)


DIRECTIONS = {"input", "output", "inout"}
DIRECTION_RE = re.compile(r"\b(?:input|output|inout)\b")
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
DIRECTIVE_LINE_RE = re.compile(
    r"(?m)^[ \t]*`(?:ifdef|ifndef|elsif|else|endif|define|undef|line)\b[^\n]*"
)
DEFINE_VALUE_RE = re.compile(
    r"^[ \t]*`define\s+([A-Za-z_][$A-Za-z0-9_]*)\s+(`?[A-Za-z_][$A-Za-z0-9_]*)",
    re.M,
)
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


def parse_defines(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in DEFINE_VALUE_RE.finditer(mask_syntax(text, keep_newlines=True))
    }


def _resolve_define_name(name: str, defines: dict[str, str]) -> str:
    key = name[1:] if name.startswith("`") else name
    value = defines.get(key)
    return value[1:] if value and value.startswith("`") else value or name


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
    ranges = iter_bracketed_ranges(prefix)
    dims = [dim for _, _, dim in ranges]
    chars = list(prefix)
    for start, end, _ in ranges:
        chars[start:end] = " " * (end - start)
    no_dims = "".join(chars)
    return normalize_space(no_dims), " ".join(dim.strip() for dim in dims)


def parse_param_item(item: str) -> Param | None:
    item = item.strip().rstrip(",;")
    if not item:
        return None
    left, value = strip_top_level_assignment(item)
    kind_match = re.match(r"^\s*(parameter|localparam|genvar)\b", left)
    kind = kind_match.group(1) if kind_match is not None else "parameter"
    left = re.sub(r"^\s*(parameter|localparam|genvar)\b", "", left).strip()
    left = re.sub(r"^\s*type\b", "", left).strip()
    left = mask_syntax(left, keep_newlines=False).strip()
    left, unpacked = _strip_trailing_unpacked(left)
    ident = _last_identifier(left)
    if ident is None:
        return None
    name, start, _ = ident
    prefix = left[:start].strip()
    data_type, packed = _extract_packed(prefix)
    return Param(
        name=name,
        value=value,
        data_type=data_type,
        packed=packed,
        unpacked=unpacked,
        kind=kind,
    )


def parse_param_list(text: str) -> list[Param]:
    params: list[Param] = []
    data_type = ""
    packed = ""
    for item in split_top_level(text):
        starts_declaration = re.match(r"\s*(parameter|localparam|genvar)\b", item) is not None
        param = parse_param_item(item)
        if param is not None:
            if starts_declaration:
                data_type = param.data_type
                packed = param.packed
            elif param.data_type or param.packed:
                data_type = param.data_type
                packed = param.packed
            elif data_type or packed:
                param = Param(
                    name=param.name,
                    value=param.value,
                    data_type=data_type,
                    packed=packed,
                    unpacked=param.unpacked,
                    kind=param.kind,
                )
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
    left = DIRECTIVE_LINE_RE.sub(" ", left).strip()
    left, unpacked = _strip_trailing_unpacked(left)
    ident = _last_identifier(left)
    if ident is None:
        return None, default_direction, default_type, default_packed
    name, start, _ = ident
    prefix = _clean(left[:start])
    words = prefix.split()

    direction = default_direction
    explicit_direction = False
    if words and words[0] in DIRECTIONS:
        direction = words[0]
        words = words[1:]
        explicit_direction = True

    prefix_after_direction = " ".join(words)
    data_type, packed = _extract_packed(prefix_after_direction)
    interface_type: tuple[str, ...] = ()
    if (
        not explicit_direction
        and data_type
        and data_type.split()[0] not in DATA_KEYWORDS
    ):
        direction = ""
        interface_base = data_type.split("#", 1)[0].strip()
        pieces = interface_base.split(".")
        interface_type = tuple(piece for piece in pieces if piece)
    else:
        if not data_type and direction == default_direction and not explicit_direction:
            data_type = default_type
        if not packed and direction == default_direction and not explicit_direction:
            packed = default_packed
        if not direction and data_type and data_type.split()[0] not in DATA_KEYWORDS:
            interface_base = data_type.split("#", 1)[0].strip()
            pieces = interface_base.split(".")
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
    items: list[str] = []
    for item in split_top_level(text):
        masked_item = mask_syntax(item)
        start = 0
        first_token = skip_ws(masked_item, 0)
        for match in DIRECTION_RE.finditer(masked_item):
            if match.start() == first_token:
                continue
            if masked_item[start : match.start()].strip():
                items.append(item[start : match.start()])
                start = match.start()
        items.append(item[start:])
    for item in items:
        port, direction, data_type, packed = parse_port_item(
            item, direction, data_type, packed
        )
        if port is not None:
            ports.append(port)
    return ports


def _strip_conditional_directive_lines(text: str) -> str:
    directive_re = re.compile(r"^\s*`(?:ifdef|ifndef|elsif|else|endif)\b")
    return "\n".join(
        line for line in text.splitlines() if directive_re.match(line) is None
    )


def parse_header(
    text: str, module_start: int
) -> tuple[list[Param], list[Port], list[str], int | None, int | None]:
    masked = mask_syntax(text)
    match = re.search(
        r"\b(?:module|interface)\b\s*(?:(" + IDENT_RE.pattern + r")\b)?",
        masked,
    )
    if match is None:
        return [], [], [], None, None
    idx = skip_ws(masked, match.end())
    params: list[Param] = []
    ports: list[Port] = []
    port_names: list[str] = []
    port_open_abs: int | None = None
    port_close_abs: int | None = None

    def skip_header_imports(pos: int) -> int:
        pos = skip_ws(masked, pos)
        while re.match(r"import\b", masked[pos:]):
            semicolon = find_top_level_semicolon(text, pos)
            if semicolon is None:
                break
            pos = skip_ws(masked, semicolon + 1)
        return pos

    idx = skip_header_imports(idx)
    if idx < len(masked) and masked[idx] == "#":
        idx = skip_ws(masked, idx + 1)
        if idx < len(masked) and masked[idx] == "(":
            close = find_matching(text, idx)
            if close is not None:
                params = parse_param_list(text[idx + 1 : close])
                idx = skip_ws(masked, close + 1)

    idx = skip_header_imports(idx)
    if idx < len(masked) and masked[idx] == "(":
        close = find_matching(text, idx)
        if close is not None:
            port_open_abs = module_start + idx
            port_close_abs = module_start + close
            port_text = text[idx + 1 : close]
            ports = parse_port_items(port_text)
            port_names = [port.name for port in ports]
            if not any(port.direction or port.interface_type for port in ports):
                ports = []
                port_names = []
                for item in split_top_level(port_text):
                    ident = _last_identifier(item)
                    if ident is not None:
                        port_names.append(ident[0])
    return params, ports, port_names, port_open_abs, port_close_abs


def parse_declaration_statement(statement: str) -> tuple[list[Port], list[Param]]:
    stripped = _strip_conditional_directive_lines(statement).strip().rstrip(";")
    if not stripped:
        return [], []
    masked = mask_syntax(stripped, keep_newlines=False)
    keyword_re = re.compile(
        r"\b("
        + "|".join(sorted(DIRECTIONS | DATA_KEYWORDS | {"parameter", "localparam", "genvar"}))
        + r")\b"
    )

    def parse_custom_signal(text: str) -> tuple[list[Port], list[Param]]:
        if "(" in text:
            return [], []
        head_text = mask_syntax(text, keep_newlines=False).strip()
        if not head_text:
            return [], []
        if head_text.split(None, 1)[0] in INSTANCE_SKIP:
            return [], []
        left, _ = strip_top_level_assignment(text)
        left, unpacked = _strip_trailing_unpacked(left)
        ident = _last_identifier(left)
        if ident is None:
            return [], []
        name, start, _ = ident
        prefix = left[:start].strip()
        if not prefix:
            return [], []
        data_type, packed = _extract_packed(prefix)
        return [
            Port(
                name=name,
                direction="",
                data_type=data_type,
                packed=packed,
                unpacked=unpacked,
            )
        ], []

    keyword_match = None
    for match in keyword_re.finditer(masked):
        if not masked[: match.start()].strip():
            keyword_match = match
            break
    if keyword_match is None:
        return parse_custom_signal(stripped)
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
    if first in {"parameter", "localparam", "genvar"}:
        params = [param for param in parse_param_list(stripped) if param is not None]
        return [], params
    custom_ports, custom_params = parse_custom_signal(stripped)
    if custom_ports or custom_params:
        return custom_ports, custom_params
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
    seen_ports: set[str] = set()
    for _, _, statement in split_statements(body):
        parsed_ports, parsed_params = parse_declaration_statement(statement)
        for port in parsed_ports:
            if port.name in seen_ports:
                continue
            ports.append(port)
            seen_ports.add(port.name)
        params.extend(parsed_params)
    return ports, params


def parse_clocking_blocks(body: str) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {}
    masked = mask_syntax(body)
    for match in re.finditer(r"\bclocking\s+(" + IDENT_RE.pattern + r")\b", masked):
        name = body[match.start(1) : match.end(1)].strip()
        end_match = re.search(r"\bendclocking\b", masked[match.end() :])
        if end_match is None:
            continue
        block = body[match.end() : match.end() + end_match.start()]
        entries: list[tuple[str, str]] = []
        for decl in re.finditer(
            r"\b(input|output|inout)\s+([^;\n]+)", mask_syntax(block)
        ):
            direction = decl.group(1)
            names_text = block[decl.start(2) : decl.end(2)]
            for item in split_top_level(names_text):
                ident = _last_identifier(item)
                if ident is not None:
                    entries.append((ident[0], f"clocking_{direction}"))
        result[name] = entries
    return result


def parse_modports(body: str) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {}
    masked = mask_syntax(body)
    clockings = parse_clocking_blocks(body)
    result.update(clockings)
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
            if (
                len(words) >= 2
                and words[0] == "clocking"
                and words[1] in clockings
            ):
                entries.extend(clockings[words[1]])
                continue
            if not words or words[0] not in {"input", "output", "inout", "ref"}:
                continue
            direction = words[0]
            for signal in words[1:]:
                signal = signal.strip(",")
                if IDENT_RE.fullmatch(signal):
                    entries.append((signal, direction))
        result.setdefault(name, []).extend(entries)
    return result


def _skip_instance_arrays(text: str, masked: str, idx: int) -> tuple[int, bool]:
    while idx < len(masked) and masked[idx] == "[":
        close = find_matching(text, idx)
        if close is None:
            return idx, False
        idx = skip_ws(masked, close + 1)
    return idx, True


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
            if idx < len(masked) and masked[idx] == "(":
                close = find_matching(module_text, idx)
                if close is None:
                    continue
                param_open = absolute_start + idx
                param_close = absolute_start + close
                idx = skip_ws(masked, close + 1)
            elif module_name in GATE_PRIMITIVES:
                candidate_start = None
                for candidate in IDENT_RE.finditer(masked, idx):
                    candidate_end = skip_ws(masked, candidate.end())
                    candidate_end, ok = _skip_instance_arrays(
                        module_text, masked, candidate_end
                    )
                    if ok and candidate_end < len(masked) and masked[candidate_end] == "(":
                        candidate_start = candidate.start()
                        break
                if candidate_start is None:
                    continue
                idx = candidate_start
            else:
                continue
        elif idx < len(masked) and masked[idx] == "(":
            close = find_matching(module_text, idx)
            if close is not None:
                after_params = skip_ws(masked, close + 1)
                if IDENT_RE.match(masked, after_params):
                    param_open = absolute_start + idx
                    param_close = absolute_start + close
                    idx = after_params
        inst_match = IDENT_RE.match(masked, idx)
        if inst_match is None:
            continue
        inst_name = module_text[inst_match.start() : inst_match.end()]
        idx = skip_ws(masked, inst_match.end())
        idx, ok = _skip_instance_arrays(module_text, masked, idx)
        if not ok:
            continue
        if idx < len(masked) and masked[idx] == "#":
            idx = skip_ws(masked, idx + 1)
            if idx < len(masked) and masked[idx] == "(":
                close = find_matching(module_text, idx)
                if close is None:
                    continue
                param_open = absolute_start + idx
                param_close = absolute_start + close
                idx = skip_ws(masked, close + 1)
            else:
                continue
        if idx >= len(masked) or masked[idx] != "(":
            continue
        port_close = find_matching(module_text, idx)
        if port_close is None:
            continue
        after = skip_ws(masked, port_close + 1)
        if after < len(masked) and masked[after] == ";":
            end = absolute_start + after + 1
        elif re.search(
            r"/\*AUTOINST(?:\([^*]*\))?\*/",
            module_text[idx + 1 : port_close],
            re.I,
        ):
            end = absolute_start + port_close + 1
        else:
            continue
        instances.append(
            Instance(
                module=module_name,
                name=inst_name,
                start=absolute_start + match.start(),
                end=end,
                port_open=absolute_start + idx,
                port_close=absolute_start + port_close,
                param_open=param_open,
                param_close=param_close,
            )
        )
        pos = end - absolute_start
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
    defines = parse_defines(text)
    modules: list[ModuleInfo] = []
    pattern = re.compile(
        r"\b(module|interface)\b\s*(?:(" + IDENT_RE.pattern + r")\b)?"
    )
    pos = 0
    while True:
        match = pattern.search(masked, pos)
        if match is None:
            break
        kind = match.group(1)
        name = (
            text[match.start(2) : match.end(2)].strip()
            if match.lastindex and match.group(2)
            else ""
        )
        name = _resolve_define_name(name, defines)
        end_keyword = "endmodule" if kind == "module" else "endinterface"
        end_match = re.search(r"\b" + end_keyword + r"\b", masked[match.end() :])
        if end_match is None:
            pos = match.end()
            continue
        end_start = match.end() + end_match.start()
        end = match.end() + end_match.end()
        header_end = find_top_level_semicolon(text, match.end())
        while header_end is not None and header_end < end_start:
            next_pos = skip_ws(masked, header_end + 1)
            if next_pos < end_start and masked[next_pos] in {"#", "("}:
                header_end = find_top_level_semicolon(text, next_pos)
                continue
            break
        if header_end is None or header_end > end_start:
            pos = match.end()
            continue
        header = text[match.start() : header_end + 1]
        params, header_ports, header_names, port_open, port_close = parse_header(
            header, match.start()
        )
        if port_close is not None:
            after_port_close = skip_ws(masked, port_close + 1)
            if after_port_close < end_start and masked[after_port_close] != ";":
                header_end = port_close
                header = text[match.start() : header_end + 1]
                params, header_ports, header_names, port_open, port_close = parse_header(
                    header, match.start()
                )
        body = text[header_end + 1 : end_start]
        declaration_body = body
        if port_close is not None and header_end > port_close:
            trailing_header = text[port_close + 1 : header_end + 1]
            if re.search(
                r"\b(?:input|output|inout)\b",
                mask_syntax(trailing_header),
            ):
                declaration_body = trailing_header + "\n" + body
        body_ports, body_params = parse_body_declarations(declaration_body)
        params.extend(body_params)
        if header_ports:
            ports = header_ports
            signal_names = {port.name for port in ports}
            signals = [port for port in body_ports if port.name not in signal_names]
        else:
            ports = [port for port in body_ports if port.direction]
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
    if is_only_bracketed_dims(rest):
        return name
    return None
