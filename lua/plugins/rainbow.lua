return {
    "HiPhish/rainbow-delimiters.nvim",
    dependencies = { "nvim-treesitter/nvim-treesitter" }, -- 需 Tree-sitter 支持
    event = { "BufReadPost", "BufNewFile" }, -- 文件打开时加载
    config = function()
        require 'rainbow-delimiters.setup'.setup {
            strategy = {
                [''] = 'rainbow-delimiters.strategy.global',
                commonlisp = 'rainbow-delimiters.strategy.local',
                -- Verilog 语言的策略
                verilog = 'rainbow-delimiters.strategy.global',
                -- Python 语言的策略
                python = 'rainbow-delimiters.strategy.global'
            },
            query = {
                [''] = 'rainbow-delimiters',
                latex = 'rainbow-blocks',
                verilog = 'rainbow-blocks',
                python = 'rainbow-delimiters'
            },
            highlight = {
                'RainbowDelimiterRed',
                'RainbowDelimiterYellow',
                'RainbowDelimiterBlue',
                'RainbowDelimiterOrange',
                'RainbowDelimiterGreen',
                'RainbowDelimiterViolet',
                'RainbowDelimiterCyan',
            },
            -- blacklist = {'c', 'cpp', },
        }
    end
}
