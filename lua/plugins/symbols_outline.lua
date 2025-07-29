return {
  "simrat39/symbols-outline.nvim",
  cmd = "SymbolsOutline",  -- 按需加载命令
  keys = {  -- 按需加载快捷键
    { "<leader>so", "<cmd>SymbolsOutline<cr>", desc = "Toggle Symbols Outline" },
  },
  config = function()
    require("symbols-outline").setup({
    })

    -- -- 可选：自定义自动命令，在特定文件类型中自动打开大纲
    -- vim.api.nvim_create_autocmd("FileType", {
    --   pattern = { "python", "javascript", "typescript", "lua", "go", "rust" },
    --   callback = function()
    --     vim.schedule(function()
    --       require("symbols-outline").open_outline()
    --     end)
    --   end,
    -- })
  end
}
