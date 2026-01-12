hello world
在 **lazy.nvim** 中，插件的加载是通过**触发条件（triggers）** 实现的，这些条件决定了插件何时被加载（例如按键、事件、命令等）。以下是常见的触发加载方式及配置示例：

---

### 1. **基础触发方式**
#### (1) 按事件加载 (`event`)
当指定的事件发生时加载插件：
```lua
{
  "nvim-neo-tree/neo-tree.nvim",
  event = "VimEnter", -- 在 Neovim 启动后加载
  -- 或使用更精确的事件：
  -- event = { "BufRead", "BufNewFile" } -- 打开文件时加载
}
```

#### (2) 按文件类型加载 (`ft`)
打开特定文件类型时加载：
```lua
{
  "lervag/vimtex",
  ft = "tex" -- 仅打开 .tex 文件时加载
}
```

#### (3) 按命令加载 (`cmd`)
调用命令时加载：
```lua
{
  "folke/trouble.nvim",
  cmd = "TroubleToggle" -- 执行 :TroubleToggle 时加载
}
```

#### (4) 按快捷键加载 (`keys`)
按下快捷键时加载：
```lua
{
  "akinsho/toggleterm.nvim",
  keys = "<leader>t", -- 按下 <leader>t 时加载
  -- 或指定模式 + 快捷键：
  -- keys = { { "n", "<leader>t" }, { "i", "<C-t>" } }
}
```

#### (5) 依赖触发 (`dependencies`)
作为其他插件的依赖自动加载：
```lua
{
  "nvim-telescope/telescope.nvim",
  dependencies = {
    "nvim-lua/plenary.nvim" -- 当 telescope 加载时，plenary.nvim 自动加载
  }
}
```

---

### 2. **高级触发方式**
#### (1) 按模块加载 (`module`)
当 Lua 代码调用 `require("module")` 时加载：
```lua
{
  "nvim-lualine/lualine.nvim",
  module = "lualine" -- 当执行 require("lualine") 时加载
}
```

#### (2) 按条件函数加载 (`cond`)
通过自定义函数决定是否加载：
```lua
{
  "lewis6991/gitsigns.nvim",
  cond = function()
    return vim.fn.executable("git") == 1 -- 仅当系统有 git 时加载
  end
}
```

#### (3) 延迟加载 (`lazy = true`)
显式标记为懒加载（需配合其他触发器）：
```lua
{
  "folke/which-key.nvim",
  lazy = true, -- 不会在启动时加载
  event = "VeryLazy" -- 在 Neovim 启动后延迟加载
}
```

---

### 3. **组合触发**
多个条件同时满足时加载：
```lua
{
  "windwp/nvim-autopairs",
  event = "InsertEnter", -- 进入插入模式时加载
  ft = { "markdown", "python" } -- 仅对特定文件类型生效
}
```

---

### 4. **特殊场景**
#### (1) 启动时立即加载
不设置任何触发器（或使用 `lazy = false`）：
```lua
{
  "nvim-tree/nvim-web-devicons",
  lazy = false -- 启动时立即加载（默认行为）
}
```

#### (2) 通过 `config` 函数隐式加载
在插件配置中调用命令/模块可能触发加载（不推荐显式依赖）。

---

### 配置示例
```lua
-- init.lua
require("lazy").setup({
  -- 启动时加载
  { "nvim-lua/plenary.nvim", lazy = false },

  -- 按快捷键加载
  {
    "folke/flash.nvim",
    keys = { "s", "S" } -- 按下 s/S 时加载
  },

  -- 按事件 + 文件类型加载
  {
    "iamcco/markdown-preview.nvim",
    ft = "markdown",
    event = "BufRead"
  },

  -- 依赖触发
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      "hrsh7th/cmp-buffer", -- 当 nvim-cmp 加载时自动加载
      "hrsh7th/cmp-path"
    }
  }
})
```

---

### 验证加载时机
使用命令检查插件状态：
```bash
:Lazy profile # 查看插件加载时间及触发原因
```

---

### 关键原则
1. **避免不必要的启动加载**：优先使用 `event`/`keys`/`ft` 等触发器。
2. **减少 `VeryLazy` 的使用**：仅在插件无需立即初始化时使用。
3. **依赖管理**：将工具类插件（如 plenary.nvim）设为依赖项自动加载。

通过合理配置触发器，可以显著优化 Neovim 启动速度！


 | sddfa sf | askldfj
 | skladfj  | sakdoflk
