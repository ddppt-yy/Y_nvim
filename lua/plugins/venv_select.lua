return {
    "linux-cultist/venv-selector.nvim",
    dependencies = {
        "nvim-telescope/telescope.nvim",
        "nvim-lua/plenary.nvim",
        -- "mfussenegger/nvim-dap", -- 可选，用于 DAP 集成
    },
    ft = "python",
    branch = "main", -- 使用 regexp 分支（功能更全），如求稳定可改为 "main"
    keys = {
        { "<leader>vs", "<cmd>VenvSelect<cr>",       desc = "Select Virtual Environment" },
        { "<leader>vc", "<cmd>VenvSelectCached<cr>", desc = "Select Cached Environment" },
    },
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

    -- 插件加载后执行
    config = function(_, opts)
        require("venv-selector").setup(opts)

        -- 注册 ShowCurrentVenv 用户命令
        vim.api.nvim_create_user_command("VenvShowCurrent", function()
            local venv = require("venv-selector").get_active_venv()
            if venv then
                vim.notify("Current venv: " .. venv, vim.log.levels.INFO, { title = "VenvSelector" })
            else
                vim.notify("No venv activated", vim.log.levels.WARN, { title = "VenvSelector" })
            end
        end, { desc = "Show currently active Python virtual environment" })

        -- 注册 DeactivateVenv 命令
        vim.api.nvim_create_user_command("DeactivateVenv", function()
            require("venv-selector").deactivate_venv()
            vim.notify("Virtual environment deactivated", vim.log.levels.INFO, { title = "VenvSelector" })
        end, { desc = "Deactivate current Python virtual environment" })
    end,
}
