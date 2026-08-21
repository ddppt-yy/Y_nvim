return {
  "mikavilpas/yazi.nvim",
  version = "*", -- 使用最新稳定版
  event = "VeryLazy",
  dependencies = {
    "nvim-lua/plenary.nvim",
  },
  keys = {
    -- 推荐快捷键：按 leader + y 打开 Yazi
    {
      -- "<leader>y",
      "<F2>",
      function()
        require("yazi").yazi()
      end,
      desc = "Open Yazi file manager",
    },
    -- 打开当前文件所在的目录
    {
      "<leader>Y",
      function()
        require("yazi").yazi(nil, vim.fn.expand("%:p:h"))
      end,
      desc = "Open Yazi in current file directory",
    },
  },
  opts = {
    -- 关闭 Yazi 时自动切换 Neovim 的工作目录
    change_cwd_on_close = true,
    
    -- 浮动窗口大小
    window = {
      width = 0.85,  -- 占屏幕宽度的 85%
      height = 0.85, -- 占屏幕高度的 85%
    },
    
    -- 可选：完全替代 Neovim 自带的 netrw
    open_for_directories = true,
  },
}
