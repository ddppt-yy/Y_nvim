from __future__ import annotations

import re
from dataclasses import dataclass

from ..model import Instance, Port
from ..syntax import (
    IDENT_RE,
    find_matching,
    is_only_bracketed_dims,
    mask_syntax,
    split_bracketed_dims,
    split_top_level,
)


@dataclass(frozen=True)
class TemplateMapping:
    port_name: str
    actual: str
    nohookup: bool = False
    at_value: str = ""
    regex: str = ""


@dataclass(frozen=True)
class ActualSignal:
    name: str
    packed: str = ""
    unpacked: str = ""
    use_port_packed: bool = True


def _comment_blocks_before(text: str, pos: int) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    for match in re.finditer(r"/\*(.*?)\*/", text[:pos], re.S):
        blocks.append((match.start(), match.end(), match.group(1)))
    return blocks


def _template_nohookup_ports(body: str) -> set[str]:
    ports: set[str] = set()
    for line in body.splitlines():
        if "AUTONOHOOKUP" not in line.upper():
            continue
        code = line.split("//", 1)[0]
        match = re.search(r"\.\s*(" + IDENT_RE.pattern + r")\s*\(", code)
        if match is not None:
            ports.add(code[match.start(1) : match.end(1)].strip())
    return ports


def _template_open_pos(block_text: str, auto_match: re.Match[str]) -> int:
    open_pos = -1
    in_string = False
    escaped = False
    for pos in range(auto_match.end(), len(block_text)):
        ch = block_text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "(":
            open_pos = pos
            break
    return open_pos


def _emacs_regexp_to_python(regexp: str) -> str:
    return (
        regexp.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\|", "|")
        .replace(r"\<", r"\b")
        .replace(r"\>", r"\b")
    )


def _template_port_regexp(port_name: str) -> str:
    return _emacs_regexp_to_python(port_name).replace("@", r"([0-9]+)")


def _template_at_value(block_text: str, instance: Instance) -> tuple[bool, str]:
    auto_match = re.search(r"\bAUTO_TEMPLATE\b", block_text, re.I)
    if auto_match is None:
        return False, ""
    open_pos = _template_open_pos(block_text, auto_match)
    if open_pos < 0:
        return False, ""
    header = block_text[auto_match.end() : open_pos]
    regexp_match = re.search(r'"((?:\\.|[^"])*)"', header)
    if regexp_match is None:
        return True, _instance_number(instance)
    regexp = _emacs_regexp_to_python(regexp_match.group(1))
    try:
        match = re.search(regexp, instance.name)
    except re.error:
        return False, ""
    if match is None:
        return False, ""
    if match.lastindex:
        return True, match.group(1)
    return True, match.group(0)


def _template_actual_open(item: str, start: int) -> int:
    for pos in range(start, len(item)):
        if item[pos] == "(" and (pos == 0 or item[pos - 1] != "\\"):
            return pos
    return -1


def _parse_template_block(block_text: str, *, at_value: str = "") -> list[TemplateMapping]:
    auto_match = re.search(r"\bAUTO_TEMPLATE\b", block_text, re.I)
    if auto_match is None:
        return []
    open_pos = _template_open_pos(block_text, auto_match)
    if open_pos < 0:
        return []
    close_pos = find_matching(block_text, open_pos)
    if close_pos is None:
        return []
    body = block_text[open_pos + 1 : close_pos]
    nohookup_ports = _template_nohookup_ports(body)
    result: list[TemplateMapping] = []
    for item in split_top_level(body):
        masked = mask_syntax(item)
        match = re.search(r"\.\s*", masked)
        if match is None:
            continue
        actual_open = _template_actual_open(item, match.end())
        if actual_open < 0:
            continue
        port_name = re.sub(r"\s+", "", item[match.end() : actual_open])
        actual_close = find_matching(item, actual_open) if actual_open >= 0 else None
        if actual_close is None:
            continue
        actual = item[actual_open + 1 : actual_close].strip()
        if port_name:
            regex = (
                ""
                if "\\" not in port_name and IDENT_RE.fullmatch(port_name)
                else _template_port_regexp(port_name)
            )
            result.append(
                TemplateMapping(
                    port_name=port_name,
                    actual=actual,
                    nohookup=port_name in nohookup_ports,
                    at_value=at_value,
                    regex=regex,
                )
            )
    return result


def find_template_for_instance(text: str, instance: Instance) -> list[TemplateMapping]:
    pattern = re.compile(
        r"\b" + re.escape(instance.module) + r"\s+AUTO_TEMPLATE\b",
        re.I,
    )
    for _, _, block_text in reversed(_comment_blocks_before(text, instance.start)):
        if pattern.search(block_text):
            matches, at_value = _template_at_value(block_text, instance)
            if not matches:
                continue
            return _parse_template_block(block_text, at_value=at_value)
    return []


def _instance_number(instance: Instance | None) -> str:
    if instance is None:
        return ""
    match = re.search(r"(\d+)", instance.name)
    return match.group(1) if match else ""


def _apply_template_substitutions(
    actual: str,
    port: Port,
    instance: Instance | None,
    *,
    at_value: str = "",
) -> str:
    number = at_value or _instance_number(instance)
    actual = actual.replace("@", number)
    if "[]" in actual:
        packed_dims = _dims(port.packed)

        def replace_empty_brackets(match: re.Match[str]) -> str:
            count = len(match.group(0)) // 2
            if count >= 2 and (port.unpacked or len(packed_dims) > 1):
                return _dimension_comment(port)
            if port.unpacked and not packed_dims:
                return _dimension_comment(port)
            if packed_dims:
                return packed_dims[-1]
            return ""

        actual = re.sub(r"(?:\[\])+", replace_empty_brackets, actual)
    return actual


def _apply_match_substitutions(actual: str, match: re.Match[str] | None) -> str:
    if match is None:
        return actual
    for index, value in enumerate(match.groups(), start=1):
        actual = actual.replace(f"\\{index}", value)
    return actual


def _mapping_for_port(
    port_name: str, template: list[TemplateMapping]
) -> tuple[TemplateMapping | None, re.Match[str] | None]:
    for mapping in template:
        if not mapping.regex and mapping.port_name == port_name:
            return mapping, None
    for mapping in template:
        if not mapping.regex:
            continue
        try:
            match = re.fullmatch(mapping.regex, port_name)
        except re.error:
            continue
        if match is not None:
            return mapping, match
    return None, None


def _compact_dims(text: str) -> str:
    return text.replace(" ", "")


def _dims(text: str) -> list[str]:
    return split_bracketed_dims(text)


def _dimension_comment(port: Port) -> str:
    packed = _compact_dims(port.packed)
    unpacked = _compact_dims(port.unpacked)
    if unpacked:
        return f"/*{packed}.{unpacked}*/"
    return f"/*{packed}*/"


def _default_actual(port: Port) -> str:
    if port.interface_type:
        return port.name
    if port.unpacked or len(split_bracketed_dims(port.packed)) > 1:
        return f"{port.name}{_dimension_comment(port)}"
    if port.packed:
        return f"{port.name}{port.packed}"
    return port.name


def _simple_actual_signal(actual: str) -> ActualSignal | None:
    actual = actual.strip()
    masked = mask_syntax(actual)
    match = IDENT_RE.match(masked)
    if match is None or match.start() != 0:
        return None
    name = actual[match.start() : match.end()].strip()
    rest = actual[match.end() :].strip()
    if not name:
        return None
    if not rest:
        return ActualSignal(name=name)
    comment = re.fullmatch(r"/\*([^*]*)\*/", rest)
    if comment is not None:
        pieces = comment.group(1).split(".", 1)
        packed_text = pieces[0]
        unpacked_text = pieces[1] if len(pieces) > 1 else ""
        return ActualSignal(
            name=name,
            packed=" ".join(_dims(packed_text)),
            unpacked=" ".join(_dims(unpacked_text)),
            use_port_packed=False,
        )
    if not is_only_bracketed_dims(rest):
        return None
    return ActualSignal(
        name=name,
        packed=" ".join(split_bracketed_dims(rest)),
    )


def actual_for_port(
    port: Port,
    template: list[TemplateMapping],
    *,
    instance: Instance | None = None,
) -> tuple[str, bool]:
    mapping, match = _mapping_for_port(port.name, template)
    if mapping is not None:
        mapped_actual = _apply_match_substitutions(mapping.actual, match)
        actual = _apply_template_substitutions(
            mapped_actual,
            port,
            instance,
            at_value=mapping.at_value,
        )
        return actual, True
    return _default_actual(port), False


def actual_for_param(
    name: str,
    template: list[TemplateMapping],
    *,
    instance: Instance | None = None,
) -> tuple[str, bool]:
    mapping, match = _mapping_for_port(name, template)
    if mapping is None:
        return name, False
    mapped_actual = _apply_match_substitutions(mapping.actual, match)
    actual = _apply_template_substitutions(
        mapped_actual,
        Port(name=name),
        instance,
        at_value=mapping.at_value,
    )
    return actual, True


def is_nohookup(port: Port, template: list[TemplateMapping]) -> bool:
    mapping, _ = _mapping_for_port(port.name, template)
    return bool(mapping and mapping.nohookup)


def extract_actual_signals(actual: str, *, ignore_concat: bool = False) -> list[ActualSignal]:
    simple_signal = _simple_actual_signal(actual)
    if simple_signal is not None:
        return [simple_signal]
    if ignore_concat:
        return []
    masked = mask_syntax(actual)
    signals: list[ActualSignal] = []
    seen: set[str] = set()
    for match in IDENT_RE.finditer(masked):
        name = actual[match.start() : match.end()].strip()
        if not name:
            continue
        prev_pos = match.start() - 1
        while prev_pos >= 0 and masked[prev_pos].isspace():
            prev_pos -= 1
        next_pos = match.end()
        while next_pos < len(masked) and masked[next_pos].isspace():
            next_pos += 1
        prev_ch = masked[prev_pos] if prev_pos >= 0 else ""
        next_ch = masked[next_pos] if next_pos < len(masked) else ""
        if prev_ch in {".", "'"} or next_ch in {".", "'"}:
            continue
        if next_ch == "(":
            continue
        packed_dims: list[str] = []
        if next_ch == "[":
            scan_pos = next_pos
            while scan_pos < len(masked) and masked[scan_pos] == "[":
                close = find_matching(actual, scan_pos)
                if close is None:
                    break
                packed_dims.append(actual[scan_pos : close + 1].strip())
                scan_pos = close + 1
                while scan_pos < len(masked) and masked[scan_pos].isspace():
                    scan_pos += 1
        if name not in seen:
            signals.append(
                ActualSignal(
                    name=name,
                    packed=" ".join(packed_dims),
                    use_port_packed=False,
                )
            )
            seen.add(name)
    return signals
