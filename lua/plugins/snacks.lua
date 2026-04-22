-- ========== 颜色工具 ==========
local function mix_color(hex, target_hex, percent)
	local r1 = tonumber(hex:sub(2, 3), 16)
	local g1 = tonumber(hex:sub(4, 5), 16)
	local b1 = tonumber(hex:sub(6, 7), 16)
	local r2 = tonumber(target_hex:sub(2, 3), 16)
	local g2 = tonumber(target_hex:sub(4, 5), 16)
	local b2 = tonumber(target_hex:sub(6, 7), 16)
	local mix = percent / 100
	local new_r = math.floor(r1 * (1 - mix) + r2 * mix + 0.5)
	local new_g = math.floor(g1 * (1 - mix) + g2 * mix + 0.5)
	local new_b = math.floor(b1 * (1 - mix) + b2 * mix + 0.5)
	return string.format("#%02X%02X%02X", new_r, new_g, new_b)
end

local target = "#24273A" -- 背景色，用于衰减混合

-- 彩虹色定义
local rainbow_defs = {
	{ name = "Red",    hex = "#E06C75" },
	{ name = "Yellow", hex = "#E5C07B" },
	{ name = "Blue",   hex = "#61AFEF" },
	{ name = "Orange", hex = "#D19A66" },
	{ name = "Green",  hex = "#98C379" },
	{ name = "Violet", hex = "#C678DD" },
	{ name = "Cyan",   hex = "#56B6C2" },
}

-- 缩进线高亮组名（衰减色，用于静态缩进线）
local highlight_faded = {
	"SnacksIndentRed",
	"SnacksIndentYellow",
	"SnacksIndentBlue",
	"SnacksIndentOrange",
	"SnacksIndentGreen",
	"SnacksIndentViolet",
	"SnacksIndentCyan",
}

-- Scope 高亮组名（原色，用于当前作用域）
local highlight_scope = {
	"SnacksScopeRed",
	"SnacksScopeYellow",
	"SnacksScopeBlue",
	"SnacksScopeOrange",
	"SnacksScopeGreen",
	"SnacksScopeViolet",
	"SnacksScopeCyan",
}

--- 设置衰减高亮组（缩进线）
local function setup_faded_highlight()
	for i, def in ipairs(rainbow_defs) do
		local new_hex = mix_color(def.hex, target, 80) -- 变淡 80%
		vim.api.nvim_set_hl(0, highlight_faded[i], { fg = new_hex })
	end
end

--- 设置原色高亮组（Scope 动态线）
local function setup_vivid_highlight()
	for i, def in ipairs(rainbow_defs) do
		vim.api.nvim_set_hl(0, highlight_scope[i], { fg = def.hex })
	end
end

return {
	{
		"folke/snacks.nvim",
		priority = 1000,
		lazy = false,
		opts = {
			-- ========== 推荐开启 ==========
			bigfile = { enabled = true },       -- 大文件保护：自动禁用 Treesitter/折叠等，防止卡死
			quickfile = { enabled = true },     -- 快速文件渲染：nvim 打开文件时先渲染内容再加载插件
			words = { enabled = true },         -- LSP 引用高亮：自动高亮光标下符号的所有引用位置，快速跳转
			scope = { enabled = true },         -- 作用域检测：基于 Treesitter/缩进的作用域 text-object 和跳转
			gitbrowse = { enabled = true },     -- 浏览器打开 Git 链接：一键在 GitHub/GitLab 打开当前文件（含行号）

			-- ========== 可选开启 ==========
			dashboard = { enabled = true },     -- 启动仪表盘：漂亮的启动页面
			-- input = { enabled = true },         -- 美化 vim.ui.input：浮动窗口替代命令行输入
			statuscolumn = { enabled = true },  -- 美化侧边列：整合行号+折叠标记+gitsigns
			scroll = { enabled = true },        -- 平滑滚动动画
			scratch = { enabled = true },       -- 临时便签缓冲区：快速打开可持久化的临时笔记
			bufdelete = { enabled = true },     -- 智能删除缓冲区而不破坏窗口布局
			lazygit = { enabled = true },       -- 浮动终端中打开 LazyGit，自动适配 colorscheme
			terminal = { enabled = true },      -- 浮动/分屏终端管理器

			-- ========== 已有独立插件，保持关闭 ==========
			-- notifier   → 已有 noice.nvim + nvim-notify，更强大
			-- picker     → 已有 telescope.nvim，生态更丰富
			picker = { enabled = true },
			-- explorer   → 已有 nvim-tree.lua，功能成熟
			-- indent     → 下方单独配置（彩虹缩进线）

			-- ========== 彩虹缩进线（保留原有自定义） ==========
			indent = {
				enabled = true,
				indent = {
					hl = highlight_faded, -- 彩虹衰减色缩进线
				},
				scope = {
					hl = highlight_scope, -- 彩虹原色作用域线
				},
			},
		},
		config = function(_, opts)
			-- 设置高亮组
			setup_faded_highlight()
			setup_vivid_highlight()

			-- 切换 colorscheme 时重新设置高亮组
			vim.api.nvim_create_autocmd("ColorScheme", {
				callback = function()
					setup_faded_highlight()
					setup_vivid_highlight()
				end,
			})

			-- 应用 snacks 配置
			require("snacks").setup(opts)
		end,
	},
}
