vim.opt.termguicolors = true

require("bufferline").setup {
    options = {
        mode = "buffers",
        -- 使用 nvim 内置lsp
        diagnostics = "nvim_lsp",
        -- 左侧让出 nvim-tree 的位置
        offsets = {{
            filetype = "NvimTree",
            text = "File Explorer",
            highlight = "Directory",
            text_align = "left"
        }},
        numbers = function(opts)
            return string.format('%s|%s', opts.lower(opts.ordinal), opts.id)
        end,
    }
}
