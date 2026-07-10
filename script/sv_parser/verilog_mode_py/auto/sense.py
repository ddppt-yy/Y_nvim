from __future__ import annotations

import re

from ..syntax import IDENT_RE, find_matching, mask_syntax


AUTOSENSE_RE = re.compile(r"/\*AUTOSENSE\*/")
KEYWORDS = {
    "begin",
    "case",
    "default",
    "else",
    "end",
    "endcase",
    "for",
    "if",
    "or",
}


def _find_block_end(text: str, begin_pos: int) -> int:
    masked = mask_syntax(text)
    token_re = re.compile(r"\bbegin\b|\bend\b")
    depth = 0
    for match in token_re.finditer(masked, begin_pos):
        token = match.group(0)
        if token == "begin":
            depth += 1
        elif token == "end":
            depth -= 1
            if depth == 0:
                return match.end()
    return len(text)


def _assigned_names(body: str) -> set[str]:
    assigned: set[str] = set()
    masked = mask_syntax(body)
    for match in re.finditer(r"\b(" + IDENT_RE.pattern + r")\s*(?:\[[^\]]+\]\s*)?(?:<)?=", masked):
        name = body[match.start(1) : match.end(1)]
        assigned.add(name)
    return assigned


def _read_names(body: str) -> list[str]:
    assigned = _assigned_names(body)
    names: set[str] = set()
    for match in IDENT_RE.finditer(mask_syntax(body)):
        name = body[match.start() : match.end()]
        if name in KEYWORDS or name in assigned:
            continue
        names.add(name)
    return sorted(names)


def expand_autosense(text: str) -> str:
    replacements: list[tuple[int, int, str]] = []
    for match in AUTOSENSE_RE.finditer(text):
        close = find_matching(text, text.find("(", 0, match.start()))
        sense_close = text.find(")", match.end())
        if sense_close == -1:
            continue
        begin_match = re.search(r"\bbegin\b", mask_syntax(text)[sense_close:])
        if begin_match is None:
            continue
        begin_pos = sense_close + begin_match.start()
        end_pos = _find_block_end(text, begin_pos)
        names = _read_names(text[begin_pos:end_pos])
        if not names:
            continue
        del close
        replacements.append((match.end(), sense_close, " or " + " or ".join(names)))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text
