from __future__ import annotations

from pathlib import Path

from .model import ModuleInfo
from .sv_parse import parse_modules


class ModuleLibrary:
    def __init__(self) -> None:
        self.modules: dict[str, ModuleInfo] = {}

    def add_text(self, text: str, source_path: Path | None = None) -> None:
        for module in parse_modules(text, source_path):
            self.modules[module.name] = module

    def add_file(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(errors="ignore")
        self.add_text(text, path)

    def lookup(self, name: str) -> ModuleInfo | None:
        return self.modules.get(name)

    @classmethod
    def from_top(cls, top_file: Path, top_text: str) -> "ModuleLibrary":
        lib = cls()
        top_file = top_file.resolve()
        suffixes = {".v", ".sv", ".vh", ".svh"}
        for item in sorted(top_file.parent.iterdir()):
            if item.is_file() and item.suffix in suffixes and item.resolve() != top_file:
                lib.add_file(item)
        lib.add_text(top_text, top_file)
        return lib
