return {
    {
        "nvim-neo-tree/neo-tree.nvim",
        branch = "v3.x",
        dependencies = {
            "nvim-lua/plenary.nvim",
            "MunifTanjim/nui.nvim",
            "nvim-tree/nvim-web-devicons", -- optional, but recommended
        },
        lazy = true, -- neo-tree will lazily load itself
        keys = {
            {
                "<F2>",
                "<cmd>Neotree toggle<CR>",
                desc = "打开/关闭 Neo-tree",
            },
        },
    },
}
