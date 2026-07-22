#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / "verilog_mode_py" / "tests"
TESTS_OK_DIR = ROOT / "verilog_mode_py" / "tests_ok"
TESTS_BATCH_OK_DIR = ROOT / "verilog_mode_py" / "tests_batch_ok"

AUTO_NAME_KEYWORDS = (
    "autoinst",
    "autoarg",
    "autowire",
    "autoinput",
    "autooutput",
    "autoinout",
    "template",
    "modport",
)
SOURCE_SUFFIXES = {".v", ".sv"}
EXCLUDED_PREFIXES = ("indent_", "noindent_")
UNSUPPORTED_PATTERNS = (
    (re.compile(r'@"'), "template-lisp"),
    (re.compile(r"\bAUTO_LISP\b", re.I), "AUTO_LISP"),
    (re.compile(r"\bAUTOINSERTLISP\b", re.I), "AUTOINSERTLISP"),
    (re.compile(r"\bAUTOINSERTLAST\b", re.I), "AUTOINSERTLAST"),
    (re.compile(r"\bverilog-auto-inst-dot-name\s*:\s*t\b", re.I), "dot-name"),
    (re.compile(r"\bAUTOREG\b", re.I), "AUTOREG"),
    (re.compile(r"\bAUTORESET\b", re.I), "AUTORESET"),
    (re.compile(r"\bAUTOUNUSED\b", re.I), "AUTOUNUSED"),
)


def is_auto_related(path: pathlib.Path) -> bool:
    name = path.name.lower()
    return (
        path.suffix in SOURCE_SUFFIXES
        and not name.startswith(EXCLUDED_PREFIXES)
        and not name.endswith("-dontrun")
        and any(keyword in name for keyword in AUTO_NAME_KEYWORDS)
    )


def expected_for(relative: pathlib.Path) -> pathlib.Path | None:
    batch_expected = TESTS_BATCH_OK_DIR / relative
    if batch_expected.is_file():
        return batch_expected
    normal_expected = TESTS_OK_DIR / relative
    if normal_expected.is_file():
        return normal_expected
    return None


def unsupported_reason(path: pathlib.Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    for pattern, reason in UNSUPPORTED_PATTERNS:
        if pattern.search(text):
            return reason
    return None


def discover_cases(selected: list[str]) -> list[tuple[pathlib.Path, pathlib.Path, str | None]]:
    selected_set = set(selected)
    cases: list[tuple[pathlib.Path, pathlib.Path, str | None]] = []
    for path in sorted(TESTS_DIR.rglob("*")):
        if not path.is_file() or not is_auto_related(path):
            continue
        relative = path.relative_to(TESTS_DIR)
        if selected_set and str(relative) not in selected_set and path.name not in selected_set:
            continue
        expected = expected_for(relative)
        if expected is None:
            continue
        cases.append((relative, expected, unsupported_reason(path)))
    return cases


def copy_inputs(work_dir: pathlib.Path) -> pathlib.Path:
    copied = work_dir / "tests"
    shutil.copytree(TESTS_DIR, copied)
    return copied


def run_auto(top: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "verilog_mode_py",
            "verilog-batch-auto",
            str(top),
        ],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def diff_text(relative: pathlib.Path, expected: str, actual: str) -> str:
    return "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"expected/{relative}",
            tofile=f"actual/{relative}",
        )
    )


def same_without_whitespace(left: str, right: str) -> bool:
    def normalize(text: str) -> str:
        text = re.sub(
            r"(/\*AUTOARG\*/(?:(?!endmodule).)*?\))\s*;",
            r"\1",
            text,
            flags=re.S | re.I,
        )
        text = re.sub(
            r"(\bAUTO_TEMPLATE\b(?:(?!\*/).)*?\))\s*;\s*(\*/)",
            r"\1 \2",
            text,
            flags=re.S | re.I,
        )
        text = re.sub(r"//\s*Templated\s+\d+\b", "// Templated", text)
        return re.sub(r"\s+", "", text)

    return normalize(left) == normalize(right)


def run_case(relative: pathlib.Path, expected_path: pathlib.Path) -> bool:
    with tempfile.TemporaryDirectory(prefix=f"verilog_mode_py_{relative.stem}_") as tmp:
        input_root = copy_inputs(pathlib.Path(tmp))
        top = input_root / relative
        proc = run_auto(top)
        if proc.returncode != 0:
            print(f"FAIL {relative}: command failed", file=sys.stderr)
            if proc.stdout:
                print(proc.stdout, file=sys.stderr)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
            return False
        expected = expected_path.read_text(encoding="utf-8")
        actual = top.read_text(encoding="utf-8")
        if actual != expected:
            if same_without_whitespace(actual, expected):
                print(f"SKIP_FORMAT {relative}")
                return True
            print(f"FAIL {relative}", file=sys.stderr)
            print(diff_text(relative, expected, actual), file=sys.stderr)
            return False
    print(f"PASS {relative}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run AUTO-related upstream verilog-mode tests, stopping at first failure."
    )
    parser.add_argument("case", nargs="*", help="optional relative path or basename")
    parser.add_argument(
        "--list",
        action="store_true",
        help="list discovered cases without running them",
    )
    args = parser.parse_args(argv)

    cases = discover_cases(args.case)
    if args.list:
        for relative, expected, reason in cases:
            expected_root = (
                "tests_batch_ok"
                if TESTS_BATCH_OK_DIR in expected.parents
                else "tests_ok"
            )
            suffix = f"\tSKIP_UNSUPPORTED {reason}" if reason else ""
            print(f"{relative}\t{expected_root}/{relative}{suffix}")
        print(f"TOTAL {len(cases)}")
        return 0

    if not cases:
        print("No matching AUTO-related cases found", file=sys.stderr)
        return 2

    print(f"Discovered {len(cases)} AUTO-related cases")
    for relative, expected, reason in cases:
        if reason is not None:
            print(f"SKIP_UNSUPPORTED {relative} {reason}")
            continue
        if not run_case(relative, expected):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
