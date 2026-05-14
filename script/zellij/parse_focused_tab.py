#!/usr/bin/env python3
"""Parse current.kdl, extract the tab block with focus=true, and process it.

Usage:
    python3 parse_focused_tab.py nake     # wrap output with layout { ... }
    python3 parse_focused_tab.py restore  # wrap output with layout { + tab-bar + ... + status-bar + }
"""

import re
import sys
from pathlib import Path


def extract_focused_tab_block(kdl_path: str) -> str | None:
    """Parse KDL file and return the full text of the tab block containing focus=true."""
    content = Path(kdl_path).read_text()
    lines = content.splitlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("tab ") and "focus=true" in stripped:
            depth = 0
            block_lines = []
            for j in range(i, len(lines)):
                current_line = lines[j]
                block_lines.append(current_line)
                depth += current_line.count("{") - current_line.count("}")
                if depth <= 0:
                    break
            return "\n".join(block_lines)

    return None


def find_top_level_children(lines: list[str]) -> list[tuple[int, int]]:
    """Find positions of top-level child blocks within the tab block.

    Returns:
        List of (start_line_idx, end_line_idx) for each top-level child block
    """
    # First line is the tab line containing {, so depth starts at 1 after it
    children = []
    i = 1  # skip the tab line itself
    depth = 1  # tab line's { makes depth=1

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Non-empty lines at depth==1 are direct children of tab
        if depth == 1 and stripped and not stripped.startswith("//"):
            child_start = i
            # Track the end position of this child block
            child_depth = depth
            for j in range(i, len(lines)):
                child_depth += lines[j].count("{") - lines[j].count("}")
                if child_depth <= 1:
                    # Child block ended (back to depth==1 or depth==0)
                    children.append((child_start, j))
                    i = j + 1
                    depth = child_depth
                    break
            else:
                break
        else:
            depth += line.count("{") - line.count("}")
            i += 1

    return children


def process_tab_block(block: str, remove_panes: bool = True) -> str:
    """Process tab block: optionally remove first and last panes, then clean up.

    Args:
        block: tab block text
        remove_panes: whether to remove the first and last top-level pane blocks
    """
    lines = block.splitlines()

    if remove_panes:
        children = find_top_level_children(lines)

        # Find the first and last pane child blocks
        pane_indices = []
        for idx, (start, end) in enumerate(children):
            stripped = lines[start].strip()
            if stripped.startswith("pane"):
                pane_indices.append(idx)

        if len(pane_indices) >= 2:
            first_pane_idx = pane_indices[0]
            last_pane_idx = pane_indices[-1]

            # Mark lines to remove
            remove_lines = set()
            for idx in [first_pane_idx, last_pane_idx]:
                start, end = children[idx]
                for line_no in range(start, end + 1):
                    remove_lines.add(line_no)

            # Build result, removing marked lines
            lines = [lines[i] for i in range(len(lines)) if i not in remove_lines]

    # Remove first and last lines
    if len(lines) >= 2:
        lines = lines[1:-1]
    # Remove lines that contain neither "pane" nor "}"
    lines = [line for line in lines if "pane" in line or "}" in line]
    # Remove command="..." and its leading whitespace
    lines = [re.sub(r'\s*command="[^"]*"', '', line) for line in lines]
    lines = [re.sub(r'\s*cwd="[^"]*"', '', line) for line in lines]
    return "\n".join(lines)


def wrap_output(content: str, mode: str) -> str:
    """Wrap content with header/footer text based on mode."""
    if mode == "nake":
        header = "layout {"
        footer = "}"
    elif mode == "restore":
        header = "layout {\n    pane size=1 borderless=true {\n        plugin location=\"zellij:tab-bar\"\n    }"
        footer = "    pane size=1 borderless=true {\n        plugin location=\"zellij:status-bar\"\n    }\n}"
    else:
        return content

    return f"{header}\n{content}\n{footer}"


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("nake", "restore"):
        print("Usage: python3 parse_focused_tab.py <nake|restore>", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    kdl_file = Path(__file__).parent / "current.kdl"

    if not kdl_file.exists():
        print(f"Error: file {kdl_file} not found", file=sys.stderr)
        sys.exit(1)

    block = extract_focused_tab_block(str(kdl_file))

    if block is None:
        print("No tab with focus=true found", file=sys.stderr)
        sys.exit(1)

    remove_panes = (mode == "nake")
    result = process_tab_block(block, remove_panes=remove_panes)
    result = wrap_output(result, mode)
    print(result)


if __name__ == "__main__":
    main()
