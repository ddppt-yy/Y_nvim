#!/usr/bin/env python3
"""Run golden tests for verilog-mode.py batch AUTO commands."""

from __future__ import annotations

import argparse
import difflib
import pathlib
import shutil
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "verilog-mode.py"
CASES_ROOT = pathlib.Path(__file__).resolve().parent


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def copy_case(case_dir: pathlib.Path, work_dir: pathlib.Path) -> pathlib.Path:
    for item in case_dir.iterdir():
        if item.name.startswith("expected_"):
            continue
        if item.is_file():
            shutil.copy2(item, work_dir / item.name)
    return work_dir / "input.sv"


def run_cmd(command: str, top_file: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, str(top_file)],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def assert_text_equal(case_name: str, phase: str, actual: str, expected: str) -> bool:
    if actual == expected:
        return True

    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"{case_name}/{phase}.expected",
            tofile=f"{case_name}/{phase}.actual",
        )
    )
    print(diff, file=sys.stderr)
    return False


def run_case(case_dir: pathlib.Path) -> bool:
    case_name = case_dir.name
    expected_auto = read_text(case_dir / "expected_auto.sv")
    expected_delete = read_text(case_dir / "expected_delete.sv")

    with tempfile.TemporaryDirectory(prefix=f"sv_auto_{case_name}_") as tmp:
        work_dir = pathlib.Path(tmp)
        top_file = copy_case(case_dir, work_dir)

        proc = run_cmd("verilog-batch-auto", top_file)
        if proc.returncode != 0:
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            print(f"{case_name}: verilog-batch-auto failed", file=sys.stderr)
            return False
        actual_auto = read_text(top_file)
        if not assert_text_equal(case_name, "auto", actual_auto, expected_auto):
            return False

        proc = run_cmd("verilog-batch-delete-auto", top_file)
        if proc.returncode != 0:
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            print(f"{case_name}: verilog-batch-delete-auto failed", file=sys.stderr)
            return False
        actual_delete = read_text(top_file)
        if not assert_text_equal(case_name, "delete", actual_delete, expected_delete):
            return False

    print(f"PASS {case_name}")
    return True


def discover_cases(selected: list[str]) -> list[pathlib.Path]:
    cases = [
        item for item in sorted(CASES_ROOT.iterdir())
        if item.is_dir() and (item / "input.sv").is_file()
    ]
    if selected:
        selected_set = set(selected)
        cases = [item for item in cases if item.name in selected_set]
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", nargs="*", help="optional case name filter")
    args = parser.parse_args(argv)

    cases = discover_cases(args.case)
    if not cases:
        print("No golden cases found", file=sys.stderr)
        return 2

    ok = True
    for case_dir in cases:
        ok = run_case(case_dir) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

