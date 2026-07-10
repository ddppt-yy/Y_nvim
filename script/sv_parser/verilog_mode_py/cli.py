from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .auto.arg import expand_autoarg
from .auto.declarations import expand_declarations
from .auto.delete import delete_auto
from .auto.inst import expand_autoinst, expand_autoinstparam
from .auto.modport import expand_modport
from .auto.sense import expand_autosense
from .auto.stub import expand_inout_helpers
from .library import ModuleLibrary


def run_delete(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(delete_auto(text), encoding="utf-8")


def run_auto(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = delete_auto(text)
    library = ModuleLibrary.from_top(path, text)
    text = expand_autoinstparam(text, library)
    text = expand_autoinst(text, library)
    text = expand_modport(text, library)
    text = expand_inout_helpers(text, library)
    text = expand_declarations(text, library)
    text = expand_autosense(text)
    text = expand_autoarg(text)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m verilog_mode_py",
        description="Pure Python subset of verilog-mode batch AUTO expansion.",
    )
    parser.add_argument(
        "command",
        choices=("verilog-batch-auto", "verilog-batch-delete-auto"),
    )
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)

    if not args.file.is_file():
        print(f"{args.file}: file not found", file=sys.stderr)
        return 2

    if args.command == "verilog-batch-delete-auto":
        run_delete(args.file)
    else:
        run_auto(args.file)
    return 0
