# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH
export PATH=~/.local/share/nvim/mason/bin:$HOME/bin:/usr/local/bin:$PATH
#export PATH=~/tools/zellij/:$PATH
#export PATH=~/tools/startship/:$PATH
#export PATH=~/tools/lsd/:$PATH
#export PATH=~/tools/yazi/:$PATH

# Path to your oh-my-zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="ys"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
# zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change how often to auto-update (in days).
# zstyle ':omz:update' frequency 13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string to have that shown instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1 (see #5765)
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
#plugins=(git z zsh-autosuggestions zsh-syntax-highlighting     )
plugins=(z zsh-autosuggestions zsh-syntax-highlighting history )

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='mvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

f_cd () {
    cd $1
    lsd -l -ah
}
alias cd=f_cd
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias clc="clear"
alias cp="cp -i"
alias g="vim "
alias n="nvim "
alias gd='vimdiff'
alias git_head='git reset --hard origin/master'
alias grep='grep --color=auto --exclude-dir={.bzr,CVS,.git,.hg,.svn}'
alias history='fc -fl 1'
alias h=history
alias la='lsd -lAh'
alias lf='lsd | xargs realpath'
alias ls="lsd -ah"
alias ll="lsd -l -ah"
alias mv='mv -i'
# alias rm='rm -i'
#BLOCK_BEGIN
# 自定义 rm 命令：删除前打包到 ~/.zzzrubbish
rm() {
    # 垃圾桶目录
    local rubbish_dir="$HOME/.zzzrubbish"

    # 创建目录（如果不存在）
    [[ -d "$rubbish_dir" ]] || mkdir -p "$rubbish_dir"

    # 显示垃圾桶当前大小
    if [[ -d "$rubbish_dir" ]]; then
        local size=$(du -sh "$rubbish_dir" 2>/dev/null | cut -f1)
        echo "🗑️  Trash size: $size"
    else
        echo "🗑️  Trash directory created."
    fi

    # ---------- 解析选项 ----------
    local recursive=false
    local force=false
    local files=()
    local opt

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -r|--recursive)
                recursive=true
                shift
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -rf|-fr)
                recursive=true
                force=true
                shift
                ;;
            --)
                shift
                break
                ;;
            -*)
                # 忽略未知选项，保持兼容性
                echo "rm: ignoring unknown option '$1'" >&2
                shift
                ;;
            *)
                break
                ;;
        esac
    done
    files=("$@")

    # 无文件时直接返回
    if [[ ${#files[@]} -eq 0 ]]; then
        return 0
    fi

    # ---------- 收集待删除项（转换为 / 下的相对路径，保留符号链接）----------
    local items_to_delete=()
    local failed=false

    for item in "${files[@]}"; do
        # 文件/链接是否存在
        if [[ ! -e "$item" && ! -L "$item" ]]; then
            if [[ "$force" == false ]]; then
                echo "rm: cannot remove '$item': No such file or directory" >&2
                failed=true
            fi
            continue
        fi

        # 目录且无 -r 则报错
        if [[ -d "$item" && "$recursive" == false ]]; then
            echo "rm: cannot remove '$item': Is a directory" >&2
            failed=true
            continue
        fi

        # 获取不解析符号链接的绝对路径（readlink -m 兼容 Linux，macOS 可安装 coreutils 或使用 realpath -s）
        local abs_path
        if command -v readlink >/dev/null && readlink -m . >/dev/null 2>&1; then
            abs_path=$(readlink -m "$item")
        elif command -v realpath >/dev/null; then
            abs_path=$(realpath -s "$item" 2>/dev/null)
        else
            # 后备方案：若路径已是绝对路径则直接使用，否则拼接 $PWD（不处理符号链接）
            if [[ "$item" = /* ]]; then
                abs_path="$item"
            else
                abs_path="$PWD/$item"
            fi
        fi

        # 去掉开头的 '/'，得到相对于根目录的路径
        local rel_path="${abs_path#/}"
        if [[ -z "$rel_path" ]]; then
            echo "rm: refusing to remove root directory" >&2
            failed=true
            continue
        fi

        items_to_delete+=("$rel_path")
    done

    if [[ "$failed" == true ]]; then
        return 1
    fi

    if [[ ${#items_to_delete[@]} -eq 0 ]]; then
        return 0
    fi

    # ---------- 打包 ----------
    local timestamp=$(date +%Y%m%d%H%M%S)
    local archive="$rubbish_dir/$timestamp.tar.gz"

    if tar -C / -czf "$archive" "${items_to_delete[@]}" 2>/dev/null; then
        # 打包成功，执行真实删除
        local rm_opts="-f"
        [[ "$recursive" == true ]] && rm_opts="-rf"
        command rm $rm_opts "${files[@]}" 2>/dev/null
    else
        echo "rm: failed to create backup archive, no files removed" >&2
        return 1
    fi
}
#BLOCK_END

alias sc='source ~/.zshrc'
alias vimrc='vim ~/.vimrc'
alias which='alias | /usr/bin/which --tty-only --read-alias --show-dot --show-tilde'
alias zellij_naked='sh ~/.config/zellij/naked.sh'
alias zellij_restore='sh ~/.config/zellij/restore.sh'

f_sv_inst () {
    emacs --batch $1 -f verilog-batch-auto
}
alias sv_inst=f_sv_inst

# source ~/tmux_alias.zsh
source ~/minuet-ai.env.zsh

git config --add oh-my-zsh.hide-dirty 1 
git config --add oh-my-zsh.hide-status 1 

#eval $(thefuck --alias)
## You can use whatever you want as an alias, like for Mondays:
#eval $(thefuck --alias FUCK)


export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion





# 初始化 Starship 提示符
eval "$(starship init zsh)"




