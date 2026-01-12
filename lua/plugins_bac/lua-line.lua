return {
    {
        'nvim-lualine/lualine.nvim',
        event = { "BufReadPost", "BufNewFile" }, -- 文件打开时加载
        dependencies = { 'nvim-tree/nvim-web-devicons' },
        config = function()
            require('lualine').setup({
                options = {
                    -- theme = 'tokyonight'
                    theme = 'onelight'
                }
            })
        end
    },
}
