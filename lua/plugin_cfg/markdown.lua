vim.g.markdown_fenced_languages = {
    'html', 'python', 'bash=sh', 'javascript', 'typescript', 'json', 'verilog',
}

-- 启用 Markdown 折叠
vim.wo.foldmethod = 'expr'
vim.wo.foldexpr = 'nvim_treesitter#foldexpr()'

-- 表格模式配置
vim.g.table_mode_corner = '|'  -- 表格边框样式
vim.g.table_mode_separator = '|'
vim.g.table_mode_fillchar = '-' -- 填充字符

-- tpope/vim-markdown 增强配置
vim.g.markdown_recommended_style = 0  -- 禁用自动缩进
vim.g.markdown_syntax_conceal = 1     -- 启用语法隐藏
vim.g.markdown_folding = 1            -- 启用标题折叠
vim.g.markdown_minlines = 100         -- 折叠计算行数

-- vim-table-mode 高级配置
vim.g.table_mode_always_active = 0    -- 需要手动启用表格模式
vim.g.table_mode_auto_align = 1       -- 自动对齐表格
vim.g.table_mode_delimiter = ','       -- CSV 分隔符
vim.g.table_mode_tableize_delimiter = '|' -- 表格化分隔符






-- markdown.lua
-- 基础设置
-- vim.g.vim_markdown_folding_disabled = 1  -- 禁用默认折叠
-- vim.g.vim_markdown_conceal = 0          -- 禁用符号隐藏
-- vim.g.vim_markdown_frontmatter = 1      -- 支持 YAML frontmatter
-- vim.g.vim_markdown_toml_frontmatter = 1 -- 支持 TOML frontmatter
-- vim.g.vim_markdown_json_frontmatter = 1 -- 支持 JSON frontmatter
-- 
-- -- 与表格模式集成
-- vim.g.vim_markdown_table_mode = 0 -- 禁用内置表格模式，使用专用插件
-- 
-- -- 语法高亮
-- vim.g.vim_markdown_strikethrough = 1
-- vim.g.vim_markdown_math = 1






-- 续 markdown.lua
-- 表格模式设置
vim.g.table_mode_corner = '|'
vim.g.table_mode_header_fillchar = '='

-- -- 快捷键映射
-- local map = vim.keymap.set
-- local opts = { noremap = true, silent = true }
-- 
-- -- 启用表格模式（在 Markdown 文件中）
-- map('n', '<leader>tm', ':TableModeToggle<CR>', opts)
-- 
-- -- 快速创建表格（输入 2x2 表格示例）
-- map('n', '<leader>tc', ':TableModeEnable<CR>2<Bar>2<Bar><CR><Bar> <Bar> <Bar><CR><Bar> <Bar> <Bar><ESC>2k', opts)
-- 
-- -- 格式化当前表格
-- map('n', '<leader>tf', ':TableFormat<CR>', opts)
-- 
-- 


