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
        verilog = 'rainbow-delimiters',
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
