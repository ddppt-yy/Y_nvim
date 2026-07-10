from __future__ import annotations

import re

from ..syntax import find_port_close_after_marker


AUTOMATIC_BLOCK_RE = re.compile(
    r"^[ \t]*// Beginning of automatic[^\n]*\n"
    r"(?:.*\n)*?"
    r"^[ \t]*// End of automatics[^\n]*(?:\n)?",
    re.M,
)


def _collapse_marker_region(text: str, marker: str) -> str:
    pattern = re.compile(r"/\*" + re.escape(marker) + r"(?:\([^*]*\))?\*/")
    while True:
        match = pattern.search(text)
        if match is None:
            return text
        close = find_port_close_after_marker(text, match.end())
        if close is None:
            return text
        replacement = text[: match.end()] + ")" + text[close + 1 :]
        if replacement == text:
            return text
        text = replacement


def delete_auto(text: str) -> str:
    text = AUTOMATIC_BLOCK_RE.sub("", text)
    for marker in ("AUTOARG", "AUTOINST", "AUTOINSTPARAM", "AUTOSENSE"):
        text = _collapse_marker_region(text, marker)
    return text
