-- require("indent_blankline").setup {
-- show_end_of_line = true,
-- space_char_blankline = " ",
-- show_current_context = true,
-- show_current_context_start = true,
-- }
-- require("ibl").setup {
-- }

return {
	"lukas-reineke/indent-blankline.nvim",
	-- event = 'VeryLazy',
	event = { "BufReadPost", "BufNewFile" },
	config = function()
		local highlight = {
			"RainbowRed",
			"RainbowYellow",
			"RainbowBlue",
			"RainbowOrange",
			"RainbowGreen",
			"RainbowViolet",
			"RainbowCyan",
		}

		local hooks = require("ibl.hooks")
		-- create the highlight groups in the highlight setup hook, so they are reset
		-- every time the colorscheme changes

		local function mix_color(hex, target_hex, percent)
			-- 解析源颜色
			local r1 = tonumber(hex:sub(2, 3), 16)
			local g1 = tonumber(hex:sub(4, 5), 16)
			local b1 = tonumber(hex:sub(6, 7), 16)
			-- 解析目标颜色
			local r2 = tonumber(target_hex:sub(2, 3), 16)
			local g2 = tonumber(target_hex:sub(4, 5), 16)
			local b2 = tonumber(target_hex:sub(6, 7), 16)
			-- 混合比例
			local mix = percent / 100
			local new_r = math.floor(r1 * (1 - mix) + r2 * mix + 0.5)
			local new_g = math.floor(g1 * (1 - mix) + g2 * mix + 0.5)
			local new_b = math.floor(b1 * (1 - mix) + b2 * mix + 0.5)
			-- 转回十六进制
			return string.format("#%02X%02X%02X", new_r, new_g, new_b)
		end

		local target = "#24273A" -- RGB(36,39,58) 的十六进制
		local colors = {
			RainbowRed = "#E06C75",
			RainbowYellow = "#E5C07B",
			RainbowBlue = "#61AFEF",
			RainbowOrange = "#D19A66",
			RainbowGreen = "#98C379",
			RainbowViolet = "#C678DD",
			RainbowCyan = "#56B6C2",
		}

		hooks.register(hooks.type.HIGHLIGHT_SETUP, function()
			-- vim.api.nvim_set_hl(0, "RainbowRed", { fg = "#E06C75" })
			-- vim.api.nvim_set_hl(0, "RainbowYellow", { fg = "#E5C07B" })
			-- vim.api.nvim_set_hl(0, "RainbowBlue", { fg = "#61AFEF" })
			-- vim.api.nvim_set_hl(0, "RainbowOrange", { fg = "#D19A66" })
			-- vim.api.nvim_set_hl(0, "RainbowGreen", { fg = "#98C379" })
			-- vim.api.nvim_set_hl(0, "RainbowViolet", { fg = "#C678DD" })
			-- vim.api.nvim_set_hl(0, "RainbowCyan", { fg = "#56B6C2" })
			for name, hex in pairs(colors) do
				local new_hex = mix_color(hex, target, 80) -- 变淡 90%
				vim.api.nvim_set_hl(0, name, { fg = new_hex })
			end
		end)

		require("ibl").setup({ indent = { highlight = highlight } })
		-- require("ibl").setup({})
	end,
}
