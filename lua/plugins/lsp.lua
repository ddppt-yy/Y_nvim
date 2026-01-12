return {
	-- Mason 插件管理
	{
		"williamboman/mason.nvim",
		event = { "BufReadPost", "BufNewFile" },
		opts = {
			ui = {
				icons = {
					package_installed = "✓",
					package_pending = "➜",
					package_uninstalled = "✗",
				},
			},
		},
		config = function(_, opts)
			require("mason").setup(opts)
		end,
	},

	-- Mason LSP 配置管理
	{
		"williamboman/mason-lspconfig.nvim",
		event = { "BufReadPost", "BufNewFile" },
		dependencies = {
			"williamboman/mason.nvim",
			"neovim/nvim-lspconfig",
		},
		opts = {
			ensure_installed = {
				"lua_ls",
				"verible",
				-- "pyright",
				-- "pylsp",  -- 可选
			},
			handlers = {
				-- 默认处理器，为所有 LSP 设置通用配置
				function(server_name)
					local lsp_set_keymap = require("config.keymaps")

					local on_attach = function(client, bufnr)
						lsp_set_keymap.set_keymap(bufnr)

						-- 0.11+ 版本中，语义 token 高亮默认启用
						if client.supports_method("textDocument/semanticTokens") then
							client.server_capabilities.semanticTokensProvider = nil
						end
					end

					require("lspconfig")[server_name].setup({
						on_attach = on_attach,
						capabilities = require("cmp_nvim_lsp").default_capabilities(),
					})
				end,

				-- Lua 语言服务器特殊配置
				["lua_ls"] = function()
					local lsp_set_keymap = require("config.keymaps")

					local on_attach = function(client, bufnr)
						lsp_set_keymap.set_keymap(bufnr)

						if client.supports_method("textDocument/semanticTokens") then
							client.server_capabilities.semanticTokensProvider = nil
						end
					end

					require("lspconfig").lua_ls.setup({
						on_attach = on_attach,
						capabilities = require("cmp_nvim_lsp").default_capabilities(),
						settings = {
							Lua = {
								diagnostics = {
									globals = { "vim" },
								},
								workspace = {
									checkThirdParty = false,
								},
								telemetry = {
									enable = false,
								},
							},
						},
					})
				end,

				-- Verible 语言服务器特殊配置
				["verible"] = function()
					local lsp_set_keymap = require("config.keymaps")

					local on_attach = function(client, bufnr)
						lsp_set_keymap.set_keymap(bufnr)

						if client.supports_method("textDocument/semanticTokens") then
							client.server_capabilities.semanticTokensProvider = nil
						end
					end

					require("lspconfig").verible.setup({
						on_attach = on_attach,
						capabilities = require("cmp_nvim_lsp").default_capabilities(),
						cmd = {
							"verible-verilog-ls",
							"--rules=+line-length=length:120,+parameter-name-style=parameter_style:ALL_CAPS;localparam_style:ALL_CAPS",
						},
						root_dir = function()
							return vim.loop.cwd()
						end,
					})
				end,

				-- Pyright 语言服务器特殊配置
				-- ["pyright"] = function()
				--     local lsp_set_keymap = require("config.keymaps")

				--     local on_attach = function(client, bufnr)
				--         lsp_set_keymap.set_keymap(bufnr)

				--         if client.supports_method("textDocument/semanticTokens") then
				--             client.server_capabilities.semanticTokensProvider = nil
				--         end
				--     end

				--     require("lspconfig").pyright.setup({
				--         on_attach = on_attach,
				--         capabilities = require("cmp_nvim_lsp").default_capabilities(),
				--         settings = {
				--             python = {
				--                 analysis = {
				--                     autoSearchPaths = true,
				--                     diagnosticMode = "workspace",
				--                     useLibraryCodeForTypes = true,
				--                     typeCheckingMode = "basic",
				--                 },
				--             },
				--         },
				--     })
				-- end,
			},
		},
		config = function(_, opts)
			require("mason-lspconfig").setup(opts)
		end,
	},

	-- LSP 核心功能
	{
		"neovim/nvim-lspconfig",
		event = { "BufReadPost", "BufNewFile" },
		dependencies = {
			"williamboman/mason.nvim",
			"williamboman/mason-lspconfig.nvim",
			"hrsh7th/cmp-nvim-lsp",
		},
		opts = {
			-- 全局 LSP 诊断配置
			diagnostics = {
				underline = true,
				update_in_insert = false,
				virtual_text = {
					spacing = 4,
					source = "if_many",
					prefix = "●",
				},
				severity_sort = true,
			},

			-- 自动格式化配置
			autoformat = true,

			-- LSP 服务器设置
			servers = {
				-- 在这里添加额外的服务器配置
			},
		},
		config = function(_, opts)
			-- 设置全局诊断配置
			for name, value in pairs(opts.diagnostics) do
				vim.diagnostic.config({ [name] = value })
			end

			-- 设置 LSP 处理器
			local lsp_set_keymap = require("config.keymaps")

			-- 通用 on_attach 函数
			local on_attach = function(client, bufnr)
				lsp_set_keymap.set_keymap(bufnr)

				-- 在 0.11+ 版本中，语义 token 高亮默认启用
				-- 如果需要禁用，可以取消下面代码的注释
				if client.supports_method("textDocument/semanticTokens") then
					client.server_capabilities.semanticTokensProvider = nil
				end
			end

			-- 通用能力配置
			local capabilities = require("cmp_nvim_lsp").default_capabilities()

			-- 可以为特定服务器添加额外的配置
			-- 这些配置会覆盖 mason-lspconfig 中的配置
			local servers = opts.servers or {}
			for server, server_opts in pairs(servers) do
				if server_opts then
					server_opts.on_attach = on_attach
					server_opts.capabilities = capabilities
					require("lspconfig")[server].setup(server_opts)
				end
			end

			-- 设置自动命令
			local format_on_save_group = vim.api.nvim_create_augroup("LspFormatOnSave", { clear = true })

			vim.api.nvim_create_autocmd("BufWritePre", {
				group = format_on_save_group,
				callback = function()
					if opts.autoformat then
						vim.lsp.buf.format({
							async = false,
							timeout_ms = 3000,
							filter = function(client)
								-- 只允许一个客户端处理格式化
								return client.name ~= "tsserver" and client.name ~= "sumneko_lua"
							end,
						})
					end
				end,
			})

			-- LSP 悬浮窗口样式
			vim.lsp.handlers["textDocument/hover"] = vim.lsp.with(vim.lsp.handlers.hover, { border = "rounded" })

			vim.lsp.handlers["textDocument/signatureHelp"] =
				vim.lsp.with(vim.lsp.handlers.signature_help, { border = "rounded" })
		end,
	},
}
