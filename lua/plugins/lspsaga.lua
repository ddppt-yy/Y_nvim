return {
    "nvimdev/lspsaga.nvim",
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
