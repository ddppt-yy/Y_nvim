from __future__ import annotations

import re

from ..syntax import find_port_close_after_marker


AUTOMATIC_BLOCK_RE = re.compile(
    r"^[ \t]*// Beginning of automatic[^\n]*\n"
    r"(?:.*\n)*?"
    r"^[ \t]*// End of automatics[^\n]*(?:\n)?",
    re.M,
)


AUTO_MARKER_RE = re.compile(r"/\*AUTO[A-Z0-9_]*(?:\([^*]*\))?\*/", re.I)


def _delete_marker_automatic_blocks(text: str) -> str:
    spans: list[tuple[int, int]] = []
    for marker in AUTO_MARKER_RE.finditer(text):
        whitespace = re.match(r"\s*", text[marker.end() :])
        first_nonspace = marker.end() + (whitespace.end() if whitespace else 0)
        if first_nonspace >= len(text):
            continue
        block_start = text.rfind("\n", 0, first_nonspace) + 1
        block = AUTOMATIC_BLOCK_RE.match(text, block_start)
        if block is not None:
            spans.append((block.start(), block.end()))
    for start, end in sorted(set(spans), reverse=True):
        text = text[:start] + text[end:]
    return text


def _collapse_marker_region(text: str, marker: str) -> str:
    pattern = re.compile(
        r"/\*" + re.escape(marker) + r"(?:\([^*]*\))?\*/",
        re.I,
    )
    pos = 0
    while True:
        match = pattern.search(text, pos)
        if match is None:
            return text
        close = find_port_close_after_marker(text, match.end())
        if close is None:
            return text
        replacement = text[: match.end()] + ")" + text[close + 1 :]
        if replacement == text:
            pos = match.end()
            continue
        text = replacement
        pos = match.end()


def delete_auto(text: str) -> str:
    text = _delete_marker_automatic_blocks(text)
    for marker in ("AUTOARG", "AUTOINST", "AUTOINSTPARAM", "AUTOSENSE"):
        text = _collapse_marker_region(text, marker)
    text = re.sub(
        r"(/\*AUTOINST(?:\([^*]*\))?\*/\);)[ \t]*//[^\n]*Templated[^\n]*",
        r"\1",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(/\*AUTOINSTPARAM(?:\([^*]*\))?\*/\))[ \t]*//[^\n]*Templated[^\n]*",
        r"\1",
        text,
        flags=re.I,
    )
    return text
