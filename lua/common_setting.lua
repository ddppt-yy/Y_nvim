--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- Sections:
--    -> General
--    -> VIM user interface
--    -> Colors and Fonts
--    -> Files and backups
--    -> Text, tab and indent related
--    -> Visual mode related
--    -> Moving around, tabs and buffers
--    -> Status line
--    -> Editing mappings
--    -> vimgrep searching and cope displaying
--    -> Spell checking
--    -> Misc
--    -> Helper functions
--        :help option-list
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => General
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- open mouse in any mode
vim.opt.mouse:append("a")

-- 启用每行超过80列的字符提示（字体变蓝并加下划线），不启用就注释掉
--vim.cmd([[au BufWinEnter * let w:m2=matchadd('Underlined', '\%>' . 80 . 'v.\+', -1)]])
vim.opt.colorcolumn = "100"

vim.opt.cursorline      = true                         --突出显示当前行
vim.opt.cursorcolumn    = true                         --突出显示当前行

vim.opt.writebackup     = true                         --保存文件前建立备份，保存成功后删除该备份
vim.opt.backup          = false                        --设置无备份文件
vim.opt.swapfile        = false

-- -- smaller updatetime
-- vim.o.updatetime = 300
-- -- 设置 timeoutlen 为等待键盘快捷键连击时间500毫秒，可根据需要设置
-- vim.o.timeoutlen = 500

-- Sets how many lines of history VIM has to remember
vim.opt.history=700

-- Enable filetype plugins
vim.opt.filetype.plugin=true
vim.opt.filetype.indent=true

-- Set to auto read when a file is changed from the outside
vim.opt.autoread=true

-- 自动补全不自动选中
vim.g.completeopt = "menu,menuone,noselect,noinsert"
-- 补全增强
vim.opt.wildmenu = true
-- Dont' pass messages to |ins-completin menu|
vim.opt.shortmess = vim.o.shortmess .. 'c'
-- 补全最多显示10行
vim.opt.pumheight = 10

--BLOCK_END
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => VIM user interface
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- Set 7 lines to the cursor - when moving vertically using j/k
vim.opt.scrolloff=8
vim.opt.sidescrolloff = 8
-- Turn on the WiLd menu
vim.opt.wildmenu=true

-- Ignore compiled files
--vim.opt.wildignore="*.o,*~,*.pyc"
vim.opt.wildignore={"*.o","*~","*.pyc"}

-- Always show current position
vim.opt.ruler=true

-- Height of the command bar
vim.opt.cmdheight=2

-- A buffer becomes hidden when it is abandoned
vim.opt.hid=true

-- Configure backspace so it acts as it should act
vim.opt.backspace="eol,start,indent"   --TODO
vim.opt.whichwrap:append("<,>,h,l")

-- Ignore case when searching
vim.opt.ignorecase=true

-- When searching try to be smart about cases 
vim.opt.smartcase=true

-- Highlight search results
vim.opt.hlsearch=true

-- Makes search act like search in modern browsers
vim.opt.incsearch=true

-- Don't redraw while executing macros (good performance config)
vim.opt.lazyredraw=true

-- For regular expressions turn magic on
vim.opt.magic=true

-- Show matching brackets when text indicator is over them
vim.opt.showmatch=true

-- How many tenths of a second to blink when matching brackets
vim.opt.mat=2

-- No annoying sound on errors --TODO
--vim.opt.noerrorbells=true
--vim.opt.novisualbell=true
--vim.opt.t_vb= 
--vim.opt.tm=500

--BLOCK_END
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Colors and Fonts
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- Enable syntax highlighting
vim.opt.syntax="on"
-- Set utf8 as standard encoding and en_US as the standard language
vim.opt.encoding="utf-8"                                    --设置gvim内部编码，默认不更改
vim.opt.fileencoding="utf-8"                                --设置当前文件编码，可以更改，如：gbk（同cp936）
vim.opt.fileencodings={"ucs-bom","utf-8","gbk","cp936","latin-1"}     --设置支持打开的文件的编码

-- Use Unix as the standard file type
-- 文件格式，默认 ffs=dos,unix
vim.opt.fileformat="unix"                                   --设置新（当前）文件的<EOL>格式，可以更改，如：dos（windows系统常用）
vim.opt.fileformats={"unix","dos","mac"}                          --给出文件的<EOL>格式类型

-- split windows
vim.opt.splitright=true
vim.opt.splitbelow=true

-- 256 colors
vim.opt.termguicolors=true

-- 不可见字符的显示，这里只把空格显示为一个◇
vim.o.list = true
-- vim.o.listchars = "space:◇"
vim.opt.listchars:append "eol:↴"

-- add space column in left for debug or plugins
vim.opt.signcolumn="yes"

--BLOCK_END
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Files, backups and undo
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- Turn backup off, since most stuff is in SVN, git et.c anyway... --TODO
--vim.opt.nobackup=true
--vim.opt.nowb=true
--vim.opt.noswapfile=true
--BLOCK_END
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Text, tab and indent related
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- Use spaces instead of tabs
vim.opt.expandtab=true
-- Be smart when using tabs ;)
vim.opt.smarttab=true
-- 1 tab == 4 spaces
vim.opt.shiftwidth=4
vim.opt.tabstop=4
vim.opt.softtabstop=4
vim.opt.shiftround = true

-- Linebreak on 500 characters
vim.opt.lbr=true
vim.opt.tw=500

-- Auto indent
-- Smart indent
-- Wrap lines
vim.opt.autoindent  = true
vim.opt.smartindent = true
vim.opt.wrap =true

--BLOCK_END
--"""""""""""""""""""""""""""""
-- => Visual mode related
--"""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- Visual mode pressing * or # searches for the current selection
-- Super useful! From an idea by Michael Naumann
-- vnoremap <silent> * :call VisualSelection('f')<CR>
-- vnoremap <silent> # :call VisualSelection('b')<CR>
-- keymaps.lua

--BLOCK_END
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Moving around, tabs, windows and buffers
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- keymaps

-- Specify the behavior when switching between buffers 
--try
--  set switchbuf=useopen,usetab,newtab
--  set stal=2
--catch
--endtry

-- Return to last edit position when opening files (You want this!)
-- autocmd BufReadPost *
--      \ if line("'\"") > 0 && line("'\"") <= line("$") |
--      \   exe "normal! g`\"" |
--      \ endif
vim.api.nvim_create_autocmd("BufReadPost", {
    pattern = "*",
    callback = function()
        if vim.fn.line("'\"") > 0 and vim.fn.line("'\"") <= vim.fn.line("$") then
            vim.fn.setpos(".", vim.fn.getpos("'\""))
            vim.cmd("silent! foldopen")
        end
    end,
})

-- Remember info about open buffers on close
--set viminfo^=%  --nvim not support viminfo https://github.com/neovim/neovim/issues/6652

--BLOCK_END
--"""""""""""""""""""""""""""""
-- => Status line
--"""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- Always show the status line
vim.opt.laststatus=2

-- Format the status line
--set statusline=\ %{HasPaste()}%F%m%r%h\ %w\ \ CWD:\ %r%{getcwd()}%h\ \ \ Line:\ %l  
--set statusline=\ %{HasPaste()}%F%m%r%h\ %w\ \ CWD:\ %r%{getcwd()}%h\ \ \ [%l,%c,%p%%,%L]   
--vim.opt.statusline=[%n]CWD=%r%{getcwd()}%h\ [%{&fenc!=''?&fenc:&enc}:%{&ff}]\ %r%{HasPaste()}%F%m%r%h\ %w\ [%b\ 0x%B][%l,%c,%p%%,%L]
vim.opt.statusline = "[%n][%{&fenc!=''?&fenc:&enc}:%{&ff}] %r%F%m%r%h %w [%b 0x%B][%l,%c,%p%%,%L]"


--BLOCK_END
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Editing mappings
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- keymaps


-- " Delete trailing white space on save, useful for Python and CoffeeScript ;)   --TODO
-- func! DeleteTrailingWS()
--   exe "normal mz"
--   %s/\s\+$//ge
--   exe "normal `z"
-- endfunc
-- autocmd BufWrite *.py :call DeleteTrailingWS()
-- autocmd BufWrite *.coffee :call DeleteTrailingWS()

--BLOCK_END
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Spell checking
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN
-- keymaps
--BLOCK_END
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Helper functions
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--BLOCK_BEGIN






--""fold""
vim.opt.foldmethod="marker"
vim.opt.foldmarker="BLOCK_BEGIN,BLOCK_END"
-- vim.opt.foldmarker="translate_off,translate_on"
-- vim.keymap.set('n', '<leader>bb',  '<Esc>aBLOCK_BEGIN<Esc><Leader>cc<Esc>o<Esc>ddiBLOCK_END<Esc><Leader>cc<Esc>O<Esc>0dw<Esc>i')  --TODO



--""Pwdfull""  --TODO
-- command! Pwdfull call <SID>Pwdfull()
-- function! <SID>Pwdfull()
--     echo expand('%:p')
-- endfunction

-- vim.api.nvim_create_autocmd(
--     'Pwdfull',
--     {pattern = {"*"},command = "echo expand('%:p')"}
-- )

--BLOCK_END



------------------------------------------------------------------


--vim.opt.colorscheme = "desert" --TODO
--share clipboard with windows
vim.opt.clipboard:append("unnamed")

vim.opt.autochdir = true

--line num
vim.opt.number = true


-------------------------------------------------------------------------------
-- < 判断操作系统是否是 Windows 还是 Linux >
-------------------------------------------------------------------------------
vim.g.iswindows = 0
vim.g.islinux   = 0
if (vim.fn.has("win32") == 1 or vim.fn.has("win64") == 1 or vim.fn.has("win95") == 1 or vim.fn.has("win16") == 1) then
    vim.g.iswindows = 1
else
    vim.g.islinux = 1
end

-----------------------------------------------------------------------------
--font in win or linux
--font
if(vim.g.iswindows == 1) then
    vim.opt.guifont = 'Courier New:h8:b:cDEFAULT'
else
    vim.opt.guifont = 'Monospace 32'
end

-------------------------------------------------------------------------------
-- < 判断是终端还是 Gvim >
-------------------------------------------------------------------------------
if (vim.fn.has("gui_running") == 1) then
    vim.g.isGUI = 1
else
    vim.g.isGUI = 0
end


-------------------------------------------------------------------------------
-- < Windows Gvim 默认配置> 做了一点修改
-------------------------------------------------------------------------------
--TODO

-------------------------------------------------------------------------------
-- < Linux Gvim/Vim 默认配置> 做了一点修改
-------------------------------------------------------------------------------
--TODO




-- -----------------------------------------------------------------------------
--  < 编码配置 >
-- -----------------------------------------------------------------------------

-- 分享一些 neovim 中的实用自动、用户命令
-- https://zhuanlan.zhihu.com/p/557199534   
-- 1）自动保存编辑的缓冲区：
--if options.auto_save then
--    vim.api.nvim_create_autocmd({ "InsertLeave", "TextChanged" }, {
--        pattern = { "*" },
--        command = "silent! wall",
--        nested = true,
--    })
--end
--上面自动命令的意思是当离开 insert 模式，或者文本在 normal 模式中有变动时，自动将所有缓冲区中的变更写入到文件。其中 nested 是指该自动命令可以被其他BufWrite 自动命令的事件所依赖，再见吧！AutoSave 插件。

-- 重新打开缓冲区恢复光标位置：
vim.api.nvim_create_autocmd("BufReadPost", {
    pattern = "*",
    callback = function()
        if vim.fn.line("'\"") > 0 and vim.fn.line("'\"") <= vim.fn.line("$") then
            vim.fn.setpos(".", vim.fn.getpos("'\""))
            vim.cmd("silent! foldopen")
        end
    end,
})
-- 在保证窗口布局的情况下删除缓冲区：
vim.api.nvim_create_user_command("BufferDelete", function()
    -- @diagnostic disable-next-line: missing-parameter
    local file_exists = vim.fn.filereadable(vim.fn.expand("%p"))
    local modified = vim.api.nvim_buf_get_option(0, "modified")
    if file_exists == 0 and modified then
        local user_choice = vim.fn.input("The file is not saved, whether to force delete? Press enter or input [y/n]:")
        if user_choice == "y" or string.len(user_choice) == 0 then
            vim.cmd("bd!")
        end
        return
    end
    local force = not vim.bo.buflisted or vim.bo.buftype == "nofile"
    vim.cmd(force and "bd!" or string.format("bp | bd! %s", vim.api.nvim_get_current_buf()))
end, { desc = "Delete the current Buffer while maintaining the window layout" })


vim.api.nvim_create_autocmd(
    {
        "BufNewFile",
        "BufWrite",
        "BufRead"
    },
    {
        pattern = "*.v",
        callback = function ()
            local buf = vim.api.nvim_get_current_buf()
            vim.api.nvim_buf_set_option(buf, "filetype", "verilog")
        end
    }
)

-- 检查插件是否已加载，如果已加载则退出
if vim.g.loaded_starsearch then
    return
end
vim.g.loaded_starsearch = 1

-- 保存原有的 cpo 选项
local saved_cpo = vim.o.cpo
vim.o.cpo = vim.o.cpo .. 'vim'

-- 定义普通模式下搜索光标下单词的函数
local function search_cword()
    local word_str = vim.fn.expand("<cword>")
    if #word_str == 0 then
        vim.api.nvim_echo({{'E348: No string under cursor', 'ErrorMsg'}}, true, {})
        return
    end
    if word_str:sub(1, 1) == '\\<' then
        -- vim.o["/"] = '\\<' .. word_str .. '\\>'
        --为什么不能用 vim.o 操作寄存器？
        -- vim.o 仅用于 选项（如 hlsearch、number 等），而寄存器（如 @/、@a）是独立的 Vim 特性，需通过 vim.fn 或 Vimscript 语法访问。
        -- 搜索寄存器 @/ 本质上是一个变量，不是配置选项。
        vim.fn.setreg('/', '\\<' .. word_str .. '\\>') -- 设置 @/ 寄存器的内容
    else
        -- vim.o["/"] = word_str
        vim.fn.setreg('/', word_str) -- 设置 @/ 寄存器的内容
    end
    local saved_unnamed = vim.fn.getreg('"')
    local saved_s = vim.fn.getreg('s')
    vim.cmd('normal! "syiw')
    if word_str ~= vim.fn.getreg('s') then
        vim.cmd('normal! w')
    end
    vim.fn.setreg('s', saved_s)
    vim.fn.setreg('"', saved_unnamed)
end

-- 定义可视模式下搜索选中单词的函数
local function search_vword()
    local saved_unnamed = vim.fn.getreg('"')
    local saved_s = vim.fn.getreg('s')
    vim.cmd('normal! gv"sy')
    local search_str = vim.fn.escape(vim.fn.getreg('s'), '\\'):gsub('\n', '\\n')
    -- vim.o["/"] = '\\V' .. search_str
    vim.fn.setreg('/', '\\V' .. search_str) -- 设置 @/ 寄存器的内容
    vim.fn.setreg('s', saved_s)
    vim.fn.setreg('"', saved_unnamed)
end

-- 普通模式下映射 * 键
vim.keymap.set('n', '*', function()
    search_cword()
    vim.o.hls = true
end, { silent = true })

-- 可视模式下映射 * 键
vim.keymap.set('v', '*', function()
    search_vword()
    vim.o.hls = true
end, { silent = true })

-- 恢复原有的 cpo 选项
vim.o.cpo = saved_cpo

-- 统一换行符和编码
vim.opt.fileformats = 'unix,dos'
vim.opt.fileencoding = 'utf-8'

-- 优化特殊字符显示
vim.opt.list = true
vim.opt.listchars = {
  tab = "▸ ",
  trail = "·",
  eol = "↴",
  extends = "❯",
  precedes = "❮",
  nbsp = "␣",
}

-- vim.notify = require("notify")





