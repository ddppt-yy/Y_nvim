-- common_setting --

local map = vim.api.nvim_set_keymap
-- 复用 opt 参数
local opt = {noremap = true, silent = true }

-- With a map leader it's possible to do extra key combinations
-- like <leader>w saves the current file
vim.g.mapleader = ","
vim.g.maplocalleader = ","

-- Visual mode pressing * or # searches for the current selection
-- Super useful! From an idea by Michael Naumann
map('v', '*',  ':call VisualSelection(\'f\')<CR>', opt)
map('v', '#',  ':call VisualSelection(\'b\')<CR>', opt)

-- ****************************************
-- Moving around, tabs, windows and buffers
-- ****************************************
--BLOCK_BEGIN
-- Treat long lines as break lines (useful when moving around in them)
map('n', 'j',  'gj', opt)
map('n', 'k',  'gk', opt)

-- Map <Space> to / (search) and Ctrl-<Space> to ? (backwards search)
map('n', '<space>',  '/', opt)

-- Disable highlight when <leader><cr> is pressed
map('n', '<leader><cr>',  ':noh<cr>', opt)

-- Smart way to move between windows
map('n' , '<C-J>'     , '<C-W>j' , opt)
map('n' , '<C-K>'     , '<C-W>k' , opt)
map('n' , '<C-H>'     , '<C-W>h' , opt)
map('n' , '<C-L>'     , '<C-W>l' , opt)
map('n' , '<C-Down>'  , '<C-W>j' , opt)
map('n' , '<C-Up>'    , '<C-W>k' , opt)
map('n' , '<C-Left>'  , '<C-W>h' , opt)
map('n' , '<C-Right>' , '<C-W>l' , opt)


-- 窗口大小调整
map("n" , "<C-h>" , ":vertical resize -2<CR>" , opt)
map("n" , "<C-l>" , ":vertical resize +2<CR>" , opt)
map("n" , "<C-j>" , ":resize -2<CR>"          , opt)
map("n" , "<C-k>" , ":resize +2<CR>"          , opt)



-- Close the current buffer
map('n', '<leader>bd',  ':Bclose<cr>', opt)

-- Close all the buffers
map('n', '<leader>ba',  ':1,$ bd!<cr>', opt) --https://github.com/neovim/neovim/issues/2600

-- Useful mappings for managing tabs
map('n', '<leader>tn',  ':tabnew<cr>'   , opt)
map('n', '<leader>to',  ':tabonly<cr>'  , opt)
map('n', '<leader>tc',  ':tabclose<cr>' , opt)
map('n', '<leader>tm',  ':tabmove'      , opt)

-- Opens a new tab with the current buffer's path
-- Super useful when editing files in the same directory
map('n', '<leader>te',  ':tabedit <c-r>=expand("%:p:h")<cr>/' , opt)

-- Switch CWD to the directory of the open buffer
map('n', '<leader>cd',  ':cd %:p:h<cr>:pwd<cr>' , opt)
--BLOCK_END


--""""""""""""""""""""
-- => Editing mappings
--""""""""""""""""""""
--BLOCK_BEGIN
-- Remap VIM 0 to first non-blank character
map('n', '0',  '^', opt)

-- Move a line of text using ALT+[jk] or Comamnd+[jk] on mac
map('n', '<A-j>',  'mz:m+<cr>`z'                , opt)
map('n', '<A-k>',  'mz:m-2<cr>`z'               , opt)
map('v', '<A-j>',  ':m\'>+<cr>`<my`>mzgv`yo`z'  , opt)
map('v', '<A-k>',  ':m\'<-2<cr>`>my`<mzgv`yo`z' , opt)


if (vim.fn.has("mac") == 1 or vim.fn.has("macunix") == 1) then
    map('n', '<D-j>',  '<M-j>', opt)
    map('n', '<D-k>',  '<M-k>', opt)
    map('n', '<D-j>',  '<M-j>', opt)
    map('n', '<D-k>',  '<M-k>', opt)
end
--BLOCK_END


--""""""""""""""""""
-- => Spell checking
--""""""""""""""""""
--BLOCK_BEGIN
-- Pressing ,ss will toggle and untoggle spell checking
map('n', '<leader>ss',  ':setlocal spell!<cr>', opt)

-- Shortcuts using <leader>
map('n', '<leader>sn',  ']s' , opt)
map('n', '<leader>sp',  '[s' , opt)
map('n', '<leader>sa',  'zg' , opt)
map('n', '<leader>s?',  'z=' , opt)
--BLOCK_END

-- *********
-- code snip
-- *********
--BLOCK_BEGIN
vim.keymap.set('n', '<leader>bb',  '<Esc>aBLOCK_BEGIN<Esc>oBLOCK_END<Esc>O')  --TODO
--BLOCK_END


-- yy2Y
map('n', 'Y',  'yy' , opt)
map('n', '"+Y',  '"+yy' , opt)

-- 定义 ToggleWrap 函数
function ToggleWrap()
  if vim.o.wrap then
    vim.o.wrap = false
  else
    vim.o.wrap = true
  end
end
-- 设置键映射
--aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
map('n', '<a-z>', ':lua ToggleWrap()<CR>', opt)
-- vim.api.nvim_set_keymap('i', '<F9>', '<Esc>:lua ToggleWrap()<CR>a', {noremap = true, silent = true})
------------------ plugins -----------------------

--bufferline move--
vim.keymap.set('n', '<c-table>',  ":bnext<CR>")
vim.keymap.set('n', '<c-s-table>',  ":bprevious<CR>")

--symbol outlne--
vim.api.nvim_set_keymap("n", "<leader>so", "<cmd>SymbolsOutline<CR>", {silent = true, noremap = true})

--terminal exit   help: https://vi.stackexchange.com/questions/4919/exit-from-terminal-mode-in-neovim-vim-8
vim.cmd("tnoremap <Esc> <C-\\><C-n>")
vim.keymap.set('n', '<a-d>',  ":Lspsaga term_toggle<CR>")

-- lsp 快捷键定义
local lsp_keybinds = {}

lsp_keybinds.set_keymap = function (bufnr)
    print("set lsp keymap")
    -- 跳转到声明
    -- vim.api.nvim_buf_set_keymap(bufnr, "n", "gd", "<cmd>lua vim.lsp.buf.declaration()<CR>", {silent = true, noremap = true})
    vim.api.nvim_buf_set_keymap(bufnr, "n", "gd", "<cmd>Lspsaga peek_definition<CR>", {silent = true, noremap = true})

    -- 跳转到定义
    vim.api.nvim_buf_set_keymap(bufnr, "n", "gD", "<cmd>lua vim.lsp.buf.definition()<CR>", {silent = true, noremap = true})
    -- 显示注释文档
    -- vim.api.nvim_buf_set_keymap(bufnr, "n", "gh", "<cmd>lua vim.lsp.buf.hover()<CR>", {silent = true, noremap = true})
    vim.api.nvim_buf_set_keymap(bufnr, "n", "gh", "<cmd>Lspsaga lsp_finder<CR>", {silent = true, noremap = true})
    -- 跳转到实现
    vim.api.nvim_buf_set_keymap(bufnr, "n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>", {silent = true, noremap = true})
    -- 跳转到引用位置
    -- vim.api.nvim_buf_set_keymap(bufnr, "n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>", {silent = true, noremap = true})
    vim.api.nvim_buf_set_keymap(bufnr, "n", "gr", "<cmd>Lspsaga rename<CR>", {silent = true, noremap = true})
    -- 以浮窗形式显示错误
    vim.api.nvim_buf_set_keymap(bufnr, "n", "go", "<cmd>lua vim.diagnostic.open_float()<CR>", {silent = true, noremap = true})
    -- vim.api.nvim_buf_set_keymap(bufnr, "n", "gp", "<cmd>lua vim.diagnostic.goto_prev()<CR>", {silent = true, noremap = true})
    vim.api.nvim_buf_set_keymap(bufnr, "n", "gn", "<cmd>lua vim.diagnostic.goto_next()<CR>", {silent = true, noremap = true})

    vim.api.nvim_buf_set_keymap(bufnr, "n", "<leader>cd", "<cmd>Lspsaga show_cursor_diagnostics<CR>", {silent = true, noremap = true})
    vim.api.nvim_buf_set_keymap(bufnr, "n", "<leader>cd", "<cmd>Lspsaga show_line_diagnostics<CR>", {silent = true, noremap = true})
    vim.api.nvim_buf_set_keymap(bufnr, "n", "<leader>ca", "<cmd>Lspsaga code_action<CR>", {silent = true, noremap = true})
    vim.api.nvim_buf_set_keymap(bufnr, "v", "<leader>ca", "<cmd>Lspsaga code_action<CR>", {silent = true, noremap = true})
end
return lsp_keybinds




