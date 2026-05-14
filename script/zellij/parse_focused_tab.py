#!/usr/bin/env python3
"""解析 current.kdl 文件，提取含有 focus=true 的 tab 块，并去掉第一个和最后一个顶层 pane。

用法:
    python3 parse_focused_tab.py nake     # 输出用 layout { ... } 包裹
    python3 parse_focused_tab.py restore  # 输出用 layout { + tab-bar + ... + status-bar + } 包裹
"""

import re
import sys
from pathlib import Path


def extract_focused_tab_block(kdl_path: str) -> str | None:
    """解析 KDL 文件，返回含有 focus=true 的 tab 块的完整文本。"""
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
    """找到 tab 块内的顶层子块的位置。

    返回:
        顶层子块的 (start_line_idx, end_line_idx) 列表
    """
    # 第一行是 tab 行，包含 {，所以 depth 从第一行后开始为 1
    children = []
    i = 1  # 跳过 tab 行本身
    depth = 1  # tab 行的 { 已经让 depth=1

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 在 depth==1 时遇到的非空行就是 tab 的直接子节点
        if depth == 1 and stripped and not stripped.startswith("//"):
            child_start = i
            # 追踪这个子节点的结束位置
            child_depth = depth
            for j in range(i, len(lines)):
                child_depth += lines[j].count("{") - lines[j].count("}")
                if child_depth <= 1:
                    # 子节点结束（回到了 depth==1 或 depth==0）
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
    """处理 tab 块：可选去掉首尾 pane，然后进行其他清理操作。

    Args:
        block: tab 块文本
        remove_panes: 是否去掉第一个和最后一个顶层 pane 块
    """
    lines = block.splitlines()

    if remove_panes:
        children = find_top_level_children(lines)

        # 找到第一个和最后一个 pane 子块
        pane_indices = []
        for idx, (start, end) in enumerate(children):
            stripped = lines[start].strip()
            if stripped.startswith("pane"):
                pane_indices.append(idx)

        if len(pane_indices) >= 2:
            first_pane_idx = pane_indices[0]
            last_pane_idx = pane_indices[-1]

            # 标记要删除的行
            remove_lines = set()
            for idx in [first_pane_idx, last_pane_idx]:
                start, end = children[idx]
                for line_no in range(start, end + 1):
                    remove_lines.add(line_no)

            # 构建结果，去掉被标记的行
            lines = [lines[i] for i in range(len(lines)) if i not in remove_lines]

    # 删除第一行和最后一行
    if len(lines) >= 2:
        lines = lines[1:-1]
    # 去掉不包含 "pane" 或 "}" 的行
    lines = [line for line in lines if "pane" in line or "}" in line]
    # 去掉 command="..." 及其前导空格
    lines = [re.sub(r'\s*command="[^"]*"', '', line) for line in lines]
    lines = [re.sub(r'\s*cwd="[^"]*"', '', line) for line in lines]
    return "\n".join(lines)


def wrap_output(content: str, mode: str) -> str:
    """根据模式在内容前后添加包裹文本。"""
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
        print("用法: python3 parse_focused_tab.py <nake|restore>", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    kdl_file = Path(__file__).parent / "current.kdl"

    if not kdl_file.exists():
        print(f"错误: 文件 {kdl_file} 不存在", file=sys.stderr)
        sys.exit(1)

    block = extract_focused_tab_block(str(kdl_file))

    if block is None:
        print("未找到含有 focus=true 的 tab", file=sys.stderr)
        sys.exit(1)

    remove_panes = (mode == "nake")
    result = process_tab_block(block, remove_panes=remove_panes)
    result = wrap_output(result, mode)
    print(result)


if __name__ == "__main__":
    main()
