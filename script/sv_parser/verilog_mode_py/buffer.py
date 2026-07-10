from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass
from re import Match, Pattern
from typing import Iterator

from .syntax import line_end, line_indent_at, line_start


@dataclass
class TextBuffer:
    text: str
    pos: int = 0
    last_match: Match[str] | None = None

    def goto(self, pos: int) -> None:
        self.pos = max(0, min(len(self.text), pos))

    @contextmanager
    def save_pos(self) -> Iterator[None]:
        old_pos = self.pos
        old_match = self.last_match
        try:
            yield
        finally:
            self.pos = old_pos
            self.last_match = old_match

    def looking_at(self, pattern: str | Pattern[str]) -> bool:
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.last_match = regex.match(self.text, self.pos)
        return self.last_match is not None

    def search_forward(self, pattern: str | Pattern[str]) -> int | None:
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.last_match = regex.search(self.text, self.pos)
        if self.last_match is None:
            return None
        self.pos = self.last_match.end()
        return self.last_match.start()

    def insert(self, pos: int, value: str) -> None:
        self.text = self.text[:pos] + value + self.text[pos:]
        if self.pos >= pos:
            self.pos += len(value)

    def delete(self, start: int, end: int) -> None:
        self.text = self.text[:start] + self.text[end:]
        if self.pos > end:
            self.pos -= end - start
        elif self.pos > start:
            self.pos = start

    def replace(self, start: int, end: int, value: str) -> None:
        self.delete(start, end)
        self.insert(start, value)

    def line_bounds(self, pos: int) -> tuple[int, int]:
        return line_start(self.text, pos), line_end(self.text, pos)

    def line_indent(self, pos: int) -> str:
        return line_indent_at(self.text, pos)

    def column(self, pos: int) -> int:
        return pos - line_start(self.text, pos)
