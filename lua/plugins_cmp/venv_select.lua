return {
    "linux-cultist/venv-selector.nvim",
    dependencies = {
        "nvim-telescope/telescope.nvim",
        -- "nvim-lua/plenary.nvim",
        -- "mfussenegger/nvim-dap", -- 可选，用于 DAP 集成
    },
    ft = "python",
    branch = "main", -- 使用 regexp 分支（功能更全），如求稳定可改为 "main"
    -- keys = {
    --     { "<leader>vs", "<cmd>VenvSelect<cr>",       desc = "Select Virtual Environment" },
    --     { "<leader>vc", "<cmd>VenvSelectCached<cr>", desc = "Select Cached Environment" },
    -- },
    opts = {
        -- 基础搜索设置
        parents = 3,                    -- 向上搜索父目录的层级数
        name = { ".venv", "venv", "env", ".env" }, -- 常见的虚拟环境目录名
        auto_refresh = true,            -- 保存文件时自动刷新列表

        -- 搜索各种工具管理的虚拟环境
        search_venv_managers = true,    -- 搜索 Poetry, Pipenv, Hatch 等
        search_workspace = true,        -- 搜索工作区目录

        -- DAP 调试集成
        dap_enabled = false,

        -- 通知用户切换了环境
        notify_user_on_activate = true,

        -- 使用 Telescope 主题
        telescope_filter_type = "substring", -- 搜索过滤方式
    },
}
