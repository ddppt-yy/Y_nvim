return {
    "nvimdev/lspsaga.nvim",
    event = { "BufReadPost", "BufNewFile" }, -- 文件打开时加载
    -- cmd = "lspsaga",
    dependencies = {
        "neovim/nvim-lspconfig",     -- LSP 配置
        "nvim-tree/nvim-web-devicons", -- 图标支持
        "MunifTanjim/nui.nvim"       -- UI 组件依赖
    },
    config = function()
        require("lspsaga").setup({

        })
    end
}
