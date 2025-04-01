require 'rainbow-delimiters.setup'.setup {
    strategy = {
        [''] = 'rainbow-delimiters.strategy.global',
        commonlisp = 'rainbow-delimiters.strategy.local',
    },
    query = {
        [''] = 'rainbow-delimiters',
        latex = 'rainbow-blocks',
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
    blacklist = {'c', 'cpp', 'python', 'verilog'},
}
