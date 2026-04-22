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
			-- 只开启 indent，其他模块保持默认关闭
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
