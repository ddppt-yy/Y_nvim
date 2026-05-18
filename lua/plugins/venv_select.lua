return {
    "linux-cultist/venv-selector.nvim",
    dependencies = { "nvim-telescope/telescope.nvim" }, -- 依赖 Telescope UI
    ft = "python",
    opts = {
        -- 在此处添加你的自定义配置
        parents = 3,             -- 向上搜索父目录的层级数，默认为 2
        dap_enabled = true,      -- 如需与 nvim-dap 集成，设为 true
        search_venv_managers = true, -- 是否搜索 Poetry 等工具管理的环境，默认为 true
    },
    -- keys = {
    --     { "<leader>vs", "<cmd>VenvSelect<cr>",       desc = "Select Virtual Environment" },
    --     { "<leader>vc", "<cmd>VenvSelectCached<cr>", desc = "Select Cached Environment" },
    -- },
}
-- vim.api.nvim_create_user_command("ShowCurrentVenv", function()
--     local venv = require('venv-selector').get_active_venv()
--     if venv then
--         print("Current venv: " .. venv)
--     else
--         print("No venv activated")
--     end
-- end, {})
