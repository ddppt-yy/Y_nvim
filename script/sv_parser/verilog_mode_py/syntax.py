from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager


IDENT_RE = re.compile(r"\\\S+|[A-Za-z_][$A-Za-z0-9_]*")


def mask_syntax(text: str, *, keep_newlines: bool = True) -> str:
    """Replace comments, strings, and attributes with spaces, preserving offsets."""
    chars = list(text)
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = i
            while j < n and text[j] != "\n":
                chars[j] = " "
                j += 1
            i = j
            continue
        if ch == "/" and nxt == "*":
            j = i
            while j + 1 < n and not (text[j] == "*" and text[j + 1] == "/"):
                if not (keep_newlines and text[j] == "\n"):
                    chars[j] = " "
                j += 1
            if j + 1 < n:
                chars[j] = " "
                chars[j + 1] = " "
                j += 2
            i = j
            continue
        if ch == '"':
            quote = ch
            j = i
            chars[j] = " "
            j += 1
            while j < n:
                if not (keep_newlines and text[j] == "\n"):
                    chars[j] = " "
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            i = j
            continue
        if ch == "(" and nxt == "*":
            j = i
            while j + 1 < n and not (text[j] == "*" and text[j + 1] == ")"):
                if not (keep_newlines and text[j] == "\n"):
                    chars[j] = " "
                j += 1
            if j + 1 < n:
                chars[j] = " "
                chars[j + 1] = " "
                j += 2
            i = j
            continue
        i += 1
    return "".join(chars)


def skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def previous_nonspace(text: str, pos: int) -> str:
    pos -= 1
    while pos >= 0 and text[pos].isspace():
        pos -= 1
    return text[pos] if pos >= 0 else ""


def find_matching(text: str, open_pos: int) -> int | None:
    pairs = {"(": ")", "[": "]", "{": "}"}
    open_ch = text[open_pos]
    close_ch = pairs.get(open_ch)
    if close_ch is None:
        return None
    masked = mask_syntax(text)
    depth = 0
    for pos in range(open_pos, len(text)):
        ch = masked[pos]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return pos
    return None


def find_matching_before(text: str, close_pos: int) -> int | None:
    pairs = {")": "(", "]": "[", "}": "{"}
    close_ch = text[close_pos]
    open_ch = pairs.get(close_ch)
    if open_ch is None:
        return None
    masked = mask_syntax(text)
    depth = 0
    for pos in range(close_pos, -1, -1):
        ch = masked[pos]
        if ch == close_ch:
            depth += 1
        elif ch == open_ch:
            depth -= 1
            if depth == 0:
                return pos
    return None


def find_top_level_semicolon(text: str, start: int) -> int | None:
    masked = mask_syntax(text)
    paren = bracket = brace = 0
    for pos in range(start, len(text)):
        ch = masked[pos]
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == ";" and paren == 0 and bracket == 0 and brace == 0:
            return pos
    return None


def split_top_level(text: str, sep: str = ",") -> list[str]:
    masked = mask_syntax(text)
    parts: list[str] = []
    start = 0
    paren = bracket = brace = 0
    for pos, ch in enumerate(masked):
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == sep and paren == 0 and bracket == 0 and brace == 0:
            parts.append(text[start:pos])
            start = pos + 1
    parts.append(text[start:])
    return parts


def split_statements(text: str) -> list[tuple[int, int, str]]:
    masked = mask_syntax(text)
    result: list[tuple[int, int, str]] = []
    start = 0
    paren = bracket = brace = 0
    for pos, ch in enumerate(masked):
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == ";" and paren == 0 and bracket == 0 and brace == 0:
            result.append((start, pos + 1, text[start : pos + 1]))
            start = pos + 1
    return result


def strip_top_level_assignment(text: str) -> tuple[str, str]:
    masked = mask_syntax(text)
    paren = bracket = brace = 0
    for pos, ch in enumerate(masked):
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == "=" and paren == 0 and bracket == 0 and brace == 0:
            return text[:pos].strip(), text[pos + 1 :].strip()
    return text.strip(), ""


def line_start(text: str, pos: int) -> int:
    return text.rfind("\n", 0, pos) + 1


def line_end(text: str, pos: int) -> int:
    end = text.find("\n", pos)
    return len(text) if end == -1 else end


def line_indent_at(text: str, pos: int) -> str:
    start = line_start(text, pos)
    end = start
    while end < len(text) and text[end] in " \t":
        end += 1
    return text[start:end]


def find_port_close_after_marker(text: str, marker_end: int) -> int | None:
    masked = mask_syntax(text)
    depth = 0
    for pos in range(marker_end, len(text)):
        ch = masked[pos]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return pos
            depth -= 1
    return None


@contextmanager
def saved_match_data() -> Iterator[None]:
    """Compatibility placeholder for code that mirrors Emacs-style scanners."""
    yield


def normalize_space(text: str) -> str:
    return " ".join(text.strip().split())


def iter_identifiers(text: str) -> Iterator[str]:
    masked = mask_syntax(text)
    for match in IDENT_RE.finditer(masked):
        yield text[match.start() : match.end()]
