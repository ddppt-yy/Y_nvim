return {
    -- the colorscheme should be available when starting Neovim
    {
        "folke/tokyonight.nvim",
        endtable = false,
        lazy = false, -- make sure we load this during startup if it is your main colorscheme
        priority = 1000, -- make sure to load this before all the other start plugins
        -- config = function()
        --   -- load the colorscheme here
        --   vim.cmd([[colorscheme tokyonight]])
        -- end,
    },
    {
        "catppuccin/nvim",
        name = "catppuccin",
        priority = 1000,

        opts = {
            lsp_styles = {
                underlines = {
                    errors = { "undercurl" },
                    hints = { "undercurl" },
                    warnings = { "undercurl" },
                    information = { "undercurl" },
                },
            },
            integrations = {
                aerial = true,
                alpha = true,
                cmp = true,
                dashboard = true,
                flash = true,
                fzf = true,
                grug_far = true,
                gitsigns = true,
                headlines = true,
                illuminate = true,
                indent_blankline = { enabled = true },
                leap = true,
                lsp_trouble = true,
                mason = true,
                mini = true,
                navic = { enabled = true, custom_bg = "lualine" },
                neotest = true,
                neotree = true,
                noice = true,
                notify = true,
                snacks = true,
                telescope = true,
                treesitter_context = true,
                which_key = true,
            },
        },
    },
    { "nvim-tree/nvim-web-devicons", lazy = true },
}
