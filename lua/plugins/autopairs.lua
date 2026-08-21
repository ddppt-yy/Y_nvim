return {
	"windwp/nvim-autopairs",
	event = "InsertEnter",
	dependencies = {
		"nvim-treesitter/nvim-treesitter",
	}, -- 与补全插件配合使用时需要
	config = function()
		local npairs = require("nvim-autopairs")
		local Rule = require("nvim-autopairs.rule")
		local cond = require("nvim-autopairs.conds")

		npairs.setup({
			-- Blink owns <CR>; its mapping calls autopairs_cr when no
			-- completion item is visible.
			map_cr = false,
			check_ts = true, -- 使用Tree-sitter检查
			ts_config = {
				lua = { "string" }, -- lua中不处理字符串内
				javascript = { "template_string" }, -- js忽略模板字符串
			},
			fast_wrap = {
				map = "<M-e>", -- 快速包裹快捷键(Alt+e)
				chars = { "{", "[", "(", '"', "'" },
				pattern = string.gsub([[ [%'%"%)%>%]%)%}%,] ]], "%s+", ""),
				end_key = "$",
				keys = "qwertyuiopzxcvbnmasdfghjkl",
				check_comma = true,
				highlight = "Search",
				highlight_grey = "Comment",
			},
			-- 禁用所有单引号规则（全局生效）
			-- disable_rules = { "'" }
		})

		-- ===== 自定义规则 =====
		-- verilog
		npairs.add_rules({
			-- 禁用 Verilog 中的单引号补全（覆盖全局设置）
			Rule("'", "'", "verilog"):with_pair(cond.none()), -- 完全禁用补全
			Rule("'", "'", "systemverilog"):with_pair(cond.none()), -- 完全禁用补全
		}, true)

		-- 添加空格规则：| 变成 { | }
		npairs.add_rules({
			Rule(" ", " "):with_pair(function(opts)
				local pair = opts.line:sub(opts.col - 1, opts.col)
				return vim.tbl_contains({ "()", "[]", "{}" }, pair)
			end),
		})

		-- HTML标签自动关闭
		npairs.add_rules({
			Rule("<", ">", { "html", "jsx", "tsx", "javascript", "typescript", "javascriptreact", "typescriptreact" })
				:with_pair(cond.not_after_text(">"))
				:with_pair(cond.not_before_text("<"))
				:use_key(">"),
		})
	end,
}
