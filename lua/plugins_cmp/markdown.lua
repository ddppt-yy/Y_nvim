return {
    --------------------------
    -- 1. 表格自动格式化核心（对标 VS Code 表格自动对齐）
    --------------------------
    {
        "dhruvasagar/vim-table-mode",
        ft = "markdown", -- 仅打开 Markdown 文件时加载，零启动开销
        init = function()
            -- 核心配置：打开 Markdown 自动启用表格格式化，输入时实时对齐
            -- vim.g.table_mode_always_active = 1
            -- 兼容 GitHub Flavored Markdown 表格格式，和 VS Code 行为完全一致
            vim.g.table_mode_corner = "|"
            vim.g.table_mode_separator = "|"
            vim.g.table_mode_fillchar = "-"
            -- 可选：手动格式化当前表格快捷键（默认已自动对齐，按需启用）
            -- vim.keymap.set(
            --     "n",
            --     "<leader>tf",
            --     "<CMD>TableModeRealign<CR>",
            --     { buffer = true, desc = "格式化当前表格" }
            -- )
        end,
    },

    --------------------------
    -- 2. 标题编号自动刷新核心
    --------------------------
    {
        "whitestarrain/md-section-number.nvim",
        ft = "markdown",
        opts = {
            -- 编号层级控制（按需调整，比如1-4级标题）
            min_level = 1,
            max_level = 6,
            -- 核心：保存文件时自动刷新标题编号，无需手动触发
            auto_update = true,
            -- 忽略代码块、注释内的标题，避免误编号
            ignore_pairs = {
                { "```", "```" },
                { "<!--", "-->" },
            },
        },
        -- -- 可选：手动更新/清除编号快捷键
        -- keys = {
        --     { "<leader>mn", "<CMD>MdUpdateNumber<CR>", ft = "markdown", desc = "手动更新标题编号" },
        --     { "<leader>mc", "<CMD>MdClearNumber<CR>", ft = "markdown", desc = "清除全文标题编号" },
        -- },
    },
}
