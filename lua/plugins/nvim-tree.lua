return {
    { 
        'nvim-tree/nvim-tree.lua',
        lazy = true,
        keys = "<F2>",
        config = function()
            -- disable netrw at the very start of your init.lua
            vim.g.loaded_netrw = 1
            vim.g.loaded_netrwPlugin = 1
            require("nvim-tree").setup({
                -- 关闭文件时，自动关闭
                auto_close = true,
                view = {
                    float = {
                        enable = true,
                        open_win_config = {
                            relative = "editor",
                            border = "rounded",
                            width = 40,
                            height = 30,
                            row = 1,
                            col = 1,
                        }
                    }
                },
                filters = {
                    -- 不显示 .git 目录中的内容
                    custom = {
                        ".git/"
                    },
                    -- 显示 .gitignore
                    exclude = {
                        ".gitignore"
                    },
                    -- 不显示隐藏文件
                    dotfiles = false
                },
                -- 以图标显示git 状态
                git = {
                    enable = true
                }
            })
            vim.api.nvim_set_keymap("n", "<F2>", ":NvimTreeToggle<CR>", {noremap = true, silent = true})
            -- vim.cmd([[    -- open this will not open dir.
            --   autocmd BufEnter * ++nested if winnr('$') == 1 && bufname() == 'NvimTree_' . tabpagenr() | quit | endif
            -- ]])
        end,
    },

}
