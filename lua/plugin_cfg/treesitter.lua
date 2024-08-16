require'nvim-treesitter.configs'.setup {
  -- A list of parser names, or "all" (the five listed parsers should always be installed)
  ensure_installed = { "lua", "vim", "vimdoc", "query" , "verilog", "python", "bash", "markdown"},

    highlight = {
        enable = true,
        additional_vim_regex_highlighting = false
    },

    --启用增量选择
    incremental_selection = {
        enable = true,
        keymaps = {
            init_selection = '<CR>',
            node_incremental = '<CR>',
            node_decremental = '<BS>',
            scope_incremental = '<TAB>'
        }
    },


  indent    = {enable = true},
  rainbow ={
      enable        = true,
      extended_mode = true,
      max_file_lines= nil,
  }
}
