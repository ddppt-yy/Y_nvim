return {
	{
		"nvim-lualine/lualine.nvim",
		event = { "BufReadPost", "BufNewFile" }, -- 文件打开时加载
		dependencies = {
			"nvim-tree/nvim-web-devicons",
			"catppuccin/nvim",
		},
		config = function()
			-- 1. 获取 Catppuccin 调色板（需要 catppuccin 已安装）
			local C = require("catppuccin.palettes").get_palette()

			-- 2. 定义透明背景变量（根据你的需求修改）
			--    如果你启用了透明背景，可以将下面的 false 改为 true
			local transparent_enabled = false
			local transparent_bg = transparent_enabled and "NONE" or C.mantle

			-- 3. 构建自定义主题表（直接使用之前你提供的代码片段）
			local custom_theme = {
				normal = {
					a = { bg = C.blue, fg = C.mantle, gui = "bold" },
					b = { bg = C.surface0, fg = C.blue },
					c = { bg = transparent_bg, fg = C.text },
					-- 如果你需要为 x/y/z 部分也指定颜色，可以添加：
					-- x = { bg = transparent_bg, fg = C.text },
					-- y = { bg = transparent_bg, fg = C.text },
					-- z = { bg = transparent_bg, fg = C.text },
				},
				insert = {
					a = { bg = C.green, fg = C.base, gui = "bold" },
					b = { bg = C.surface0, fg = C.green },
					-- 其他模式以此类推...
				},
				terminal = {
					a = { bg = C.green, fg = C.base, gui = "bold" },
					b = { bg = C.surface0, fg = C.green },
				},
				command = {
					a = { bg = C.peach, fg = C.base, gui = "bold" },
					b = { bg = C.surface0, fg = C.peach },
				},
				visual = {
					a = { bg = C.mauve, fg = C.base, gui = "bold" },
					b = { bg = C.surface0, fg = C.mauve },
				},
				replace = {
					a = { bg = C.red, fg = C.base, gui = "bold" },
					b = { bg = C.surface0, fg = C.red },
				},
				inactive = {
					a = { bg = transparent_bg, fg = C.blue },
					b = { bg = transparent_bg, fg = C.surface1, gui = "bold" },
					c = { bg = transparent_bg, fg = C.overlay0 },
				},
			}

			-- vim.print(C)
			local config = {
				options = {
					theme = "custom_theme",
					-- theme = "tokyonight",
					-- theme = "onelight",
				},
				sections = {
					lualine_a = { "mode" },
					lualine_b = { "branch", "diff", "diagnostics" },
					lualine_c = {
						{
							function()
								local path = vim.fn.fnamemodify(vim.fn.expand("%:p:h"), ":~:.")
								local filename = vim.fn.expand("%:t")
								return path .. "/" .. filename
							end,
						},
					},
					lualine_x = {
						{
							function()
								local col = vim.api.nvim_win_get_cursor(0)[2]
								local line = vim.api.nvim_get_current_line()
								local char = string.sub(line, col + 1, col + 1)
								if char == "" then
									return ""
								end
								return string.format(" U+%04X", vim.fn.char2nr(char))
							end,
						},
						"encoding",
						"fileformat",
						"filetype",
						{
							function()
								local msg = "No Active Lsp"
								local buf_ft = vim.api.nvim_get_option_value("filetype", { buf = 0 })
								local clients = vim.lsp.get_clients()
								if next(clients) == nil then
									return msg
								end
								for _, client in ipairs(clients) do
									local filetypes = client.config.filetypes
									if filetypes and vim.fn.index(filetypes, buf_ft) ~= -1 then
										return client.name
									end
								end
								return string.format(" LSP:", msg)
							end,
						},
					},
					lualine_y = {
						{
							function()
								local filepath = vim.fn.expand("%:p")
								local size = vim.fn.getfsize(filepath)
								if size < 0 then
									return "0 B"
								elseif size < 1024 then
									return string.format("%d B", size)
								elseif size < 1024 * 1024 then
									return string.format("%.1f KB", size / 1024)
								elseif size < 1024 * 1024 * 1024 then
									return string.format("%.1f MB", size / (1024 * 1024))
								else
									return string.format("%.1f GB", size / (1024 * 1024 * 1024))
								end
							end,
						},
						--{
						--	function()
						--		local total_lines = vim.api.nvim_buf_line_count(0)
						--		local current_line = vim.api.nvim_win_get_cursor(0)[1]
						--		return string.format("%d/%d", current_line, total_lines)
						--	end,
						--},
					},
					lualine_z = {
						{
							function()
								local total_lines = vim.api.nvim_buf_line_count(0)
								local cursor = vim.api.nvim_win_get_cursor(0)
								local current_line = cursor[1]
								local current_col = cursor[2]
								return string.format("%d/%d,%d", total_lines, current_line, current_col)
							end,
						},
					},
				},
			}

			require("lualine").setup(config)
		end,
	},
}
