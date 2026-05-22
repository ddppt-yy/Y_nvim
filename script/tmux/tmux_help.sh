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
# 格式: 显示文本（含对应 tmux 快捷键）: tmux 命令（不含前导 "tmux" 和 "-t target"）
declare -A categories

categories["📄 窗口操作"]="
新建窗口（Prefix + c）: new-window
重命名窗口（Prefix + ,）: command-prompt -p \"窗口名称\" \"rename-window '%%'\"
关闭当前窗口（Prefix + &）: confirm-before -p \"关闭窗口? (y/n)\" \"kill-window\"
窗口列表/选择窗口（Prefix + w）: choose-window
下一个窗口（Prefix + n）: next-window
上一个窗口（Prefix + p）: previous-window
最近使用的窗口（Prefix + l）: last-window
切换至窗口0（Prefix + 0）: select-window -t :0
切换至窗口1（Prefix + 1）: select-window -t :1
切换至窗口2（Prefix + 2）: select-window -t :2
查找窗口（Prefix + f）: command-prompt -p \"窗口名/编号\" \"find-window '%%'\"
移动当前窗口至指定编号（Prefix + .）: command-prompt -p \"目标窗口编号\" \"move-window -t '%%'\"
交换当前窗口与指定窗口（Prefix + : swap-window -t）: command-prompt -p \"目标窗口编号\" \"swap-window -t '%%'\"
"

categories["└─ 窗格操作"]="
水平拆分窗格/左右分屏（Prefix + %）: split-window -h
垂直拆分窗格/上下分屏（Prefix + \"）: split-window -v
切换至左窗格（Prefix + ←）: select-pane -L
切换至右窗格（Prefix + →）: select-pane -R
切换至上窗格（Prefix + ↑）: select-pane -U
切换至下窗格（Prefix + ↓）: select-pane -D
切换至上一个窗格（Prefix + ;）: last-pane
顺序切换下一个窗格（Prefix + o）: select-pane -t :.+
关闭当前窗格（Prefix + x）: confirm-before -p \"关闭窗格? (y/n)\" \"kill-pane\"
最大化/恢复当前窗格（Prefix + z）: resize-pane -Z
向上调整窗格大小（Prefix + Ctrl+↑）: resize-pane -U 5
向下调整窗格大小（Prefix + Ctrl+↓）: resize-pane -D 5
向左调整窗格大小（Prefix + Ctrl+←）: resize-pane -L 5
向右调整窗格大小（Prefix + Ctrl+→）: resize-pane -R 5
与上一个窗格交换位置（Prefix + {）: swap-pane -U
与下一个窗格交换位置（Prefix + }）: swap-pane -D
顺时针轮换窗格（Prefix + Ctrl+o）: rotate-window
切换窗格布局（Prefix + Space）: next-layout
切换至 even-horizontal 布局（Prefix + Alt+1）: select-layout even-horizontal
切换至 even-vertical 布局（Prefix + Alt+2）: select-layout even-vertical
切换至 main-horizontal 布局（Prefix + Alt+3）: select-layout main-horizontal
切换至 main-vertical 布局（Prefix + Alt+4）: select-layout main-vertical
切换至 tiled 布局（Prefix + Alt+5）: select-layout tiled
将当前窗格拆成新窗口（Prefix + !）: break-pane
显示窗格编号（Prefix + q）: display-panes
显示窗格信息（自定义菜单项）: display-message \"窗格: #P  ID: #D  路径: #{pane_current_path}\"
"

categories["🖥️ 会话管理"]="
脱离会话（Prefix + d）: detach-client
会话列表/选择会话（Prefix + s）: choose-session
重命名会话（Prefix + $）: command-prompt -p \"会话名称\" \"rename-session '%%'\"
切换至最近使用会话（Prefix + L）: switch-client -l
切换至上一个会话（Prefix + (）: switch-client -p
切换至下一个会话（Prefix + )）: switch-client -n
新建会话（Prefix + : new-session）: command-prompt -p \"新会话名称\" \"new-session -s '%%'\"
关闭当前会话（Prefix + : kill-session）: confirm-before -p \"关闭当前会话? (y/n)\" \"kill-session\"
"

categories["📋 复制粘贴"]="
进入复制模式（Prefix + [）: copy-mode
进入复制模式并向上滚动（无默认快捷键）: copy-mode -u
粘贴缓冲区内容（Prefix + ]）: paste-buffer
列出粘贴缓冲区（Prefix + #）: list-buffers
选择粘贴缓冲区（Prefix + =）: choose-buffer
删除最近的粘贴缓冲区（Prefix + -）: delete-buffer
"

categories["⚙️ 其他"]="
命令提示符（Prefix + :）: command-prompt
显示快捷键帮助菜单（Prefix + /，当前自定义）: display-popup -E \"~/.tmux/tmux_help.sh\"
列出所有快捷键（Prefix + ?）: list-keys
显示时钟（Prefix + t）: clock-mode
显示消息历史（Prefix + ~）: show-messages
强制重绘客户端（Prefix + r）: refresh-client
显示 tab 栏/状态栏（Prefix + : set -g status on）: set-option -g status on
关闭 tab 栏/状态栏（Prefix + : set -g status off）: set-option -g status off
刷新 tmux 配置（Prefix + : source-file ~/.tmux.conf）: source-file ~/.tmux.conf
显示当前窗口信息（自定义菜单项）: display-message \"窗口: #W  (#I)  窗格: #P  会话: #S\"
显示 tmux 版本（自定义菜单项）: display-message \"tmux #{version}\"
"
# 注意：某些命令需要确认或额外参数，已经处理。

# --- 执行 tmux 命令的函数 ---
execute_tmux_command() {
    local cmd="$1"
    if [ -z "$cmd" ]; then
        return
    fi

    # 对于命令文本中包含引号的项目，不直接执行，改为把需要执行的 tmux 命令 echo 到父窗格终端中。
    # 这类命令通常包含 command-prompt / confirm-before / display-message 等复杂 quoting，直接拆词执行容易出错。
    if [[ "$cmd" == *\"* ]]; then
        tmux send-keys -t "$PARENT_PANE" "echo $(printf '%q' "tmux $cmd")" C-m
        sleep 0.1
        return
    fi

    # 对于需要交互的命令，直接执行；否则在后台执行避免阻塞 fzf
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

# 提取命令部分（快捷键说明后的全角右括号 + 冒号后，忽略前导空格）
cmd="${selected_item#*）: }"
execute_tmux_command "$cmd"
