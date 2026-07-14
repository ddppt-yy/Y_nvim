from __future__ import annotations

import re

from ..model import Instance, Param, Port
from ..syntax import (
    IDENT_RE,
    find_matching,
    iter_bracketed_ranges,
    mask_syntax,
    split_top_level,
)


BARE_IDENT_RE = re.compile(r"[A-Za-z_][$A-Za-z0-9_]*")
SCOPED_IDENT_RE = re.compile(
    r"`?[A-Za-z_][$A-Za-z0-9_]*(?:(?:::|\.)`?[A-Za-z_][$A-Za-z0-9_]*)*"
)


def inst_param_value_enabled(text: str, pos: int) -> bool:
    enabled = (
        re.search(
            r"verilog-auto-inst-param-value\s*:\s*t\b",
            text,
            re.I,
        )
        is not None
    )
    pattern = re.compile(
        r"verilog-auto-inst-param-value\s*(?::|\s+)\s*(t|nil)\b",
        re.I,
    )
    for match in pattern.finditer(text[:pos]):
        enabled = match.group(1).lower() == "t"
    return enabled


def instance_param_values(text: str, instance: Instance) -> dict[str, str]:
    if instance.param_open is None or instance.param_close is None:
        return {}
    param_text = text[instance.param_open + 1 : instance.param_close]
    masked = mask_syntax(param_text)
    values: dict[str, str] = {}
    for match in re.finditer(r"\.\s*(" + IDENT_RE.pattern + r")\s*\(", masked):
        name = param_text[match.start(1) : match.end(1)].strip()
        open_pos = match.end() - 1
        close_pos = find_matching(param_text, open_pos)
        if close_pos is None:
            continue
        values[name] = param_text[open_pos + 1 : close_pos].strip()
    return values


def _eval_int_expr(expr: str, env: dict[str, str], stack: set[str] | None = None) -> str | None:
    stack = set() if stack is None else set(stack)
    expr = expr.strip()
    expr = expr.replace("<<<", "<<").replace(">>>", ">>")

    def clog2_repl(match: re.Match[str]) -> str:
        value = _eval_int_expr(match.group(1), env, stack)
        if value is None:
            return match.group(0)
        number = int(value)
        return str((number - 1).bit_length())

    expr = re.sub(r"\$clog2\s*\(([^()]+)\)", clog2_repl, expr)

    def ident_repl(match: re.Match[str]) -> str:
        name = match.group(0)
        if name not in env or name in stack:
            return name
        value = _eval_int_expr(env[name], env, stack | {name})
        return value if value is not None else name

    expr = BARE_IDENT_RE.sub(ident_repl, expr)
    if not re.fullmatch(r"[0-9+\-*/%() <>&|^~]+", expr):
        return None
    try:
        return str(int(eval(expr.replace("/", "//"), {"__builtins__": {}}, {})))
    except Exception:
        return None


def _is_scoped_identifier(text: str) -> bool:
    return SCOPED_IDENT_RE.fullmatch(text.strip()) is not None


def _replacement_for(actual: str, next_char: str) -> str:
    actual = actual.strip()
    if next_char == ".":
        return actual
    if _is_scoped_identifier(actual) or re.fullmatch(r"\d+(?:'[sS]?[bodhBODH][0-9a-fA-F_xXzZ]+)?", actual):
        return actual
    return f"({actual})"


def _resolve_explicit_value(
    name: str,
    explicit_values: dict[str, str],
    stack: tuple[str, ...] = (),
) -> str | None:
    actual = explicit_values.get(name)
    if actual is None:
        return None
    actual = actual.strip()
    if BARE_IDENT_RE.fullmatch(actual) is None:
        return actual
    if actual in stack:
        return max((*stack, actual))
    resolved = _resolve_explicit_value(actual, explicit_values, (*stack, actual))
    return resolved if resolved is not None else actual


def _replace_explicit_param_names(
    text: str,
    explicit_values: dict[str, str],
    *,
    parenthesize_complex: bool = True,
) -> str:
    if not text or not explicit_values:
        return text

    def repl(match: re.Match[str]) -> str:
        name = match.group(0)
        start = match.start()
        end = match.end()
        if text[max(0, start - 2) : start] == "::":
            return name
        if text[end : end + 2] == "::":
            return name
        if start > 0 and text[start - 1] == ".":
            return name
        actual = _resolve_explicit_value(name, explicit_values, (name,))
        if actual is None:
            return name
        if not parenthesize_complex:
            return actual.strip()
        next_char = text[end : end + 1]
        return _replacement_for(actual, next_char)

    return BARE_IDENT_RE.sub(repl, text)


def _resolve_dim_part(
    part: str,
    eval_env: dict[str, str],
    explicit_values: dict[str, str],
) -> str:
    evaluated = _eval_int_expr(part, eval_env)
    if evaluated is not None:
        return evaluated
    return _replace_explicit_param_names(part.strip(), explicit_values)


def resolve_packed_dims(
    text: str,
    params: list[Param],
    source_text: str,
    instance: Instance,
) -> str:
    explicit_values = instance_param_values(source_text, instance)
    eval_env = {param.name: param.value for param in params if param.value}
    eval_env.update(explicit_values)
    if not eval_env and not explicit_values:
        return text

    chunks: list[str] = []
    last = 0
    for start, end, dim in iter_bracketed_ranges(text):
        chunks.append(text[last:start])
        inner = dim[1:-1]
        parts = split_top_level(inner, ":")
        resolved = [
            _resolve_dim_part(part, eval_env, explicit_values) for part in parts
        ]
        chunks.append("[" + ":".join(resolved) + "]")
        last = end
    chunks.append(text[last:])
    return "".join(chunks)


def port_with_param_values(
    port: Port,
    params: list[Param],
    source_text: str,
    instance: Instance,
) -> Port:
    explicit_values = instance_param_values(source_text, instance)
    return Port(
        name=port.name,
        direction=port.direction,
        data_type=_replace_explicit_param_names(
            port.data_type,
            explicit_values,
            parenthesize_complex=False,
        ),
        packed=resolve_packed_dims(port.packed, params, source_text, instance),
        unpacked=resolve_packed_dims(port.unpacked, params, source_text, instance),
        interface_type=port.interface_type,
    )


def ports_with_param_values(
    ports: list[Port],
    params: list[Param],
    source_text: str,
    instance: Instance,
) -> list[Port]:
    explicit_values = instance_param_values(source_text, instance)
    eval_env = {param.name: param.value for param in params if param.value}
    eval_env.update(explicit_values)
    if not eval_env and not explicit_values:
        return ports
    return [
        Port(
            name=port.name,
            direction=port.direction,
            data_type=_replace_explicit_param_names(
                port.data_type,
                explicit_values,
                parenthesize_complex=False,
            ),
            packed=resolve_packed_dims(port.packed, params, source_text, instance),
            unpacked=resolve_packed_dims(port.unpacked, params, source_text, instance),
            interface_type=port.interface_type,
        )
        for port in ports
    ]
