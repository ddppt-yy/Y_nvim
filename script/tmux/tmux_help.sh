#!/usr/bin/env bash
# tmux 快捷键帮助菜单 - 二级菜单 + 直接执行 tmux 命令

# --- 获取父窗格 ID（从参数传入）---
PARENT_PANE="$1"
if [ -z "$PARENT_PANE" ]; then
    # 兼容直接运行（测试用），取当前窗格
    PARENT_PANE="$TMUX_PANE"
fi

# 辅助函数：向父窗格所在的会话发送命令（不指定 -t 时作用于当前会话，但需确保命令在正确会话执行）
# 实际上大部分命令需要使用 -t 指定目标窗格或会话，我们通过 -t "$PARENT_PANE" 来定位父窗格所在会话/窗格
tmux_cmd() {
    tmux "$@" -t "$PARENT_PANE"
}

# --- 定义类别及对应的 tmux 命令 ---
# 格式: 显示文本: tmux 命令（不含前导 "tmux" 和 "-t target"）
declare -A categories

categories["📄 窗口操作"]="
新建窗口: new-window
重命名窗口: command-prompt -p \"窗口名称\" \"rename-window '%%'\"
关闭当前窗口: confirm-before -p \"关闭窗口? (y/n)\" \"kill-window\"
窗口列表: choose-window
下一个窗口: next-window
上一个窗口: previous-window
切换至窗口0: select-window -t :0
切换至窗口1: select-window -t :1
切换至窗口2: select-window -t :2
切换至窗口3: select-window -t :3
切换至窗口4: select-window -t :4
切换至窗口5: select-window -t :5
切换至窗口6: select-window -t :6
切换至窗口7: select-window -t :7
切换至窗口8: select-window -t :8
切换至窗口9: select-window -t :9
查找窗口: command-prompt -p \"窗口名/编号\" \"find-window '%%'\"
移动窗口至指定编号: command-prompt -p \"目标窗口编号\" \"move-window -t '%%'\"
"

categories["└─ 窗格操作"]="
水平拆分窗格: split-window -h
垂直拆分窗格: split-window -v
切换至左窗格: select-pane -L
切换至右窗格: select-pane -R
切换至上窗格: select-pane -U
切换至下窗格: select-pane -D
关闭当前窗格: confirm-before -p \"关闭窗格? (y/n)\" \"kill-pane\"
最大化/恢复当前窗格: resize-pane -Z
与上一个窗格交换位置: swap-pane -U
与下一个窗格交换位置: swap-pane -D
切换窗格布局: next-layout
将当前窗格移至新窗口: join-pane -h -s "$PARENT_PANE" -t :new
显示窗格编号: display-panes
"

categories["🖥️ 会话管理"]="
脱离会话: detach-client
会话列表: choose-session
重命名会话: command-prompt -p \"会话名称\" \"rename-session '%%'\"
切换至上个会话: switch-client -l
切换至上一个会话: switch-client -p
切换至下一个会话: switch-client -n
"

categories["📋 复制粘贴"]="
进入复制模式: copy-mode
粘贴缓冲区内容: paste-buffer
列出粘贴缓冲区: list-buffers
进入复制模式并向上滚动: copy-mode -u
"

categories["⚙️ 其他"]="
显示时钟: clock-mode
显示当前窗口信息: display-message \"窗口: #W  (#I)  窗格: #P  会话: #S\"
显示消息历史: show-messages
强制重绘客户端: refresh-client
切换至上一个窗口: previous-window
列出所有快捷键: list-keys
"
# 注意：某些命令需要确认或额外参数，已经处理。

# --- 执行 tmux 命令的函数 ---
execute_tmux_command() {
    local cmd="$1"
    if [ -z "$cmd" ]; then
        return
    fi
    # 对于需要交互的命令（如 command-prompt），直接执行；否则在后台执行避免阻塞 fzf
    if [[ "$cmd" == command-prompt* ]] || [[ "$cmd" == confirm-before* ]] || [[ "$cmd" == choose-* ]]; then
        tmux_cmd $cmd &
    else
        tmux_cmd $cmd
    fi
    # 短暂延迟，让命令生效
    sleep 0.1
}

# --- 二级菜单选择 ---
category_names=()
for cat_name in "${!categories[@]}"; do
    category_names+=("$cat_name")
done
IFS=$'\n' sorted_cats=($(sort <<<"${category_names[*]}"))
unset IFS

selected_cat=$(printf "%s\n" "${sorted_cats[@]}" | fzf \
    --prompt="选择快捷键类别 > " \
    --height 30% \
    --border \
    --reverse \
    --cycle \
    --header "↑/↓ 移动 | 回车选择 | ESC 退出")

[[ -z "$selected_cat" ]] && exit 0

items="${categories[$selected_cat]}"
selected_item=$(echo "$items" | sed '/^$/d' | fzf \
    --prompt="${selected_cat} > " \
    --height 40% \
    --border \
    --reverse \
    --cycle \
    --header "回车执行 | ESC 返回")

[[ -z "$selected_item" ]] && exit 0

# 提取命令部分（冒号后，忽略前导空格）
cmd="${selected_item#*: }"
execute_tmux_command "$cmd"
