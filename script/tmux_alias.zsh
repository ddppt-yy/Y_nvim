
# 1 新建会话 
alias tm_new='tmux new -s '

# 2 分离会话(ctrl+b d) 
alias tm_detach='tmux detach '

# 3 列出会话(ctrl+b s) 
alias tm_list='tmux ls '

# 4 接入会话 
alias tm_attach='tmux attach -t '

# 5 杀死指定会话 
alias tm_kill='tmux kill-session -t '

# 6 杀死全部会话 
alias tm_killall='tmux kill-server '

# 7 切换会话 
alias tm_switch='tmux switch -t '

# 8 重命名会话(ctrl+b $) 
alias tm_rename='tmux rename-session -t '

# 9 窗口上下划分窗格 
alias tm_splitud='tmux split-window '

# 10 窗口左右划分窗格 
alias tm_splitlr='tmux split-window -h '

# 11 光标到上方窗格 
alias tm_moveu='tmux select-pane -U '

# 12 光标到下方窗格 
alias tm_moved='tmux select-pane -D '

# 13 光标到上方窗格 
alias tm_movel='tmux select-pane -L '

# 14 光标到上方窗格 
alias tm_mover='tmux select-pane -R '

# 15 交换窗格位置(当前窗格上移) 
alias tm_swapu='tmux swap-pane -U '

# 16 交换窗格位置(当前窗格下移) 
alias tm_swapd='tmux swap-pane -D '



# 常用快捷键
##1. 会话快捷键
# Ctrl + b 接 d：分离当前会话（退出会话界面挂在后台）
# Ctrl + b 接 $：重命名当前会话
##2. 窗口快捷键
# Ctrl + b 接 c：新建窗口
# Ctrl + b 接 n：跳转到下个窗口
# Ctrl + b 接 p：跳转到上个窗口
# Ctrl + b 接 <数字键>：跳转到指定窗口
# Ctrl + b 接 w：进入窗口选择列表
# Ctrl + b 接 ,：重命名当前窗口
# Ctrl + b 接 .：修改当前窗口序号
##3. 分屏快捷键
# Ctrl + b 接 %：左右分屏
# Ctrl + b 接 "：上下分屏
# Ctrl + b 接 <方向键>：分屏跳转
# Ctrl + b 接 x：删除所在分屏
# Ctrl + b + <方向键>：调整分屏大小（按住`Ctrl + b`同时按方向键）
# Ctrl + b 接 z：所在分屏全屏，再按一次恢复
# Ctrl + b 接 {：左移分屏
# Ctrl + b 接 }：右移分屏
# Ctrl + b 接 Ctrl + o：上移分屏
# Ctrl + b 接 Alt + o：下移分屏
# Ctrl + b 接 <空格键>：切换分屏布局
# Ctrl + b 接 q：显示分屏序号和分辨率
##4. 翻页
# Ctrl + b 接 [：进入翻页模式，按 q 退出





