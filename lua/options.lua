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
--
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => General
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- Sets how many lines of history VIM has to remember
vim.opt.history=700

-- Enable filetype plugins
vim.opt.filetype.plugin=true
vim.opt.filetype.indent=true

-- Set to auto read when a file is changed from the outside
vim.opt.autoread=true

-- With a map leader it's possible to do extra key combinations
-- like <leader>w saves the current file
vim.mapleader = ","
vim.g.mapleader = ","

--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => VIM user interface
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- Set 7 lines to the cursor - when moving vertically using j/k
vim.opt.scrolloff=7

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

--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Colors and Fonts
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- Enable syntax highlighting
vim.opt.syntax=enable
-- Set utf8 as standard encoding and en_US as the standard language
vim.opt.encoding="utf-8"                                    --设置gvim内部编码，默认不更改
vim.opt.fileencoding="utf-8"                                --设置当前文件编码，可以更改，如：gbk（同cp936）
vim.opt.fileencodings={"ucs-bom","utf-8","gbk","cp936","latin-1"}     --设置支持打开的文件的编码

-- Use Unix as the standard file type
-- 文件格式，默认 ffs=dos,unix
vim.opt.fileformat="unix"                                   --设置新（当前）文件的<EOL>格式，可以更改，如：dos（windows系统常用）
vim.opt.fileformats={"unix","dos","mac"}                          --给出文件的<EOL>格式类型


--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Files, backups and undo
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- Turn backup off, since most stuff is in SVN, git et.c anyway... --TODO
--vim.opt.nobackup=true
--vim.opt.nowb=true
--vim.opt.noswapfile=true

--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Text, tab and indent related
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- Use spaces instead of tabs
vim.opt.expandtab=true
-- Be smart when using tabs ;)
vim.opt.smarttab=true
-- 1 tab == 4 spaces
vim.opt.shiftwidth=4
vim.opt.tabstop=4

-- Linebreak on 500 characters
vim.opt.lbr=true
vim.opt.tw=500

-- Auto indent
-- Smart indent
-- Wrap lines
vim.opt.ai   =true
vim.opt.si   =true
vim.opt.wrap =true

--"""""""""""""""""""""""""""""
-- => Visual mode related
--"""""""""""""""""""""""""""""
-- Visual mode pressing * or # searches for the current selection
-- Super useful! From an idea by Michael Naumann
-- vnoremap <silent> * :call VisualSelection('f')<CR>
-- vnoremap <silent> # :call VisualSelection('b')<CR>
vim.keymap.set('v', '*',  ':call VisualSelection(\'f\')<CR>')
vim.keymap.set('v', '#',  ':call VisualSelection(\'b\')<CR>')

--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- => Moving around, tabs, windows and buffers
--""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
-- Treat long lines as break lines (useful when moving around in them)
vim.keymap.set('n', 'j',  'gj')
vim.keymap.set('n', 'k',  'gk')

-- Map <Space> to / (search) and Ctrl-<Space> to ? (backwards search)
vim.keymap.set('n', '<space>',  '/')
--map <c-space> ? --TODO



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


vim.opt.mouse = a
-- 启用每行超过80列的字符提示（字体变蓝并加下划线），不启用就注释掉
--vim.cmd([[au BufWinEnter * let w:m2=matchadd('Underlined', '\%>' . 80 . 'v.\+', -1)]])
vim.opt.colorcolumn = "100"

vim.opt.cursorline     = true                         --突出显示当前行  --TODO
vim.opt.cursorcolumn   = true                         --突出显示当前行
vim.opt.writebackup    = true                         --保存文件前建立备份，保存成功后删除该备份
vim.cmd([[set nobackup]])                                 --设置无备份文件   --TODO

-- -----------------------------------------------------------------------------
--  < 编码配置 >
-- -----------------------------------------------------------------------------









