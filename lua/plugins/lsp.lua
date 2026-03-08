return {
	"neovim/nvim-lspconfig",
	dependencies = {
		-- 通过mason来自动安装语言服务器并启用
		{ "mason-org/mason.nvim", opts = {} },
		{
			"mason-org/mason-lspconfig.nvim",
			opts = {
				ensure_installed = {
					"verible",
					"pylsp",
					"lua_ls",
					"tclsp",
				},
				automatic_enable = {
					exclude = {},
				},
			},
		},
	},

	config = function()
		require("config.keymaps").set_keymap(0)
		-- 诊断信息的图标
		vim.diagnostic.config({
			signs = {
				text = {
					[vim.diagnostic.severity.ERROR] = "✘",
					[vim.diagnostic.severity.WARN] = "▲",
					[vim.diagnostic.severity.HINT] = "⚑",
					[vim.diagnostic.severity.INFO] = "»",
				},
			},
		})

		vim.lsp.config("pylsp", {
			-- -- uv隔离的虚拟环使用项目根目录下 .venv 里的 Python 解析器来分析代码
			-- 	on_init = function(client)
			-- 		local root_dir = client.config.root_dir
			-- 		local venv_python = root_dir .. "/.venv/bin/python"
			-- 		if vim.fn.filereadable(venv_python) == 1 then
			-- 			client.config.settings.pylsp.plugins.jedi.environment = venv_python
			-- 			client.notify("workspace/didChangeConfiguration", { settings = client.config.settings })
			-- 		end
			-- 		return true
			-- 	end,
			-- 	settings = {
			-- 		pylsp = {
			-- 			plugins = {
			-- 				jedi = {
			-- 					environment = nil,
			-- 				},
			-- 			},
			-- 		},
			-- 	},
			cmd = { "pylsp" },
			filetypes = { "python" },
			root_markers = {
				"pyproject.toml",
				"setup.py",
				"setup.cfg",
				"requirements.txt",
				"Pipfile",
				".git",
			},
		})

		vim.lsp.config("marksman", {
			cmd = { "marksman", "server" },
			filetypes = { "markdown", "markdown.mdx" },
			root_markers = { ".marksman.toml", ".git" },
		})

		vim.lsp.config("tclsp", {
			cmd = { "tclsp" },
			filetypes = { "tcl", "sdc", "xdc", "upf" },
			root_markers = { "tclint.toml", ".tclint", "pyproject.toml", ".git" },
		})

		vim.lsp.config("verible", {
			cmd = {
				"verible-verilog-ls",
				"--rules=+line-length=length:120,+parameter-name-style=parameter_style:ALL_CAPS;localparam_style:ALL_CAPS",
			},
			filetypes = { "systemverilog", "verilog" },
			root_markers = { ".git" },
		})
		local root_markers1 = {
			".emmyrc.json",
			".luarc.json",
			".luarc.jsonc",
		}
		local root_markers2 = {
			".luacheckrc",
			".stylua.toml",
			"stylua.toml",
			"selene.toml",
			"selene.yml",
		}
		vim.lsp.config("lua_ls", {
			cmd = { "lua-language-server" },
			filetypes = { "lua" },
			root_markers = vim.fn.has("nvim-0.11.3") == 1 and { root_markers1, root_markers2, { ".git" } }
				or vim.list_extend(vim.list_extend(root_markers1, root_markers2), { ".git" }),
			settings = {
				Lua = {
					codeLens = { enable = true },
					hint = { enable = true, semicolon = "Disable" },
				},
			},
		})

	end,
}
