local dictionary_path = "~/.config/nvim/lua/snip/dict.dict"
local custom_snippet_path = vim.fn.stdpath("config") .. "/lua/snip/"

-- Completion source priorities. Higher values rank earlier. These are the
-- effective weights you normally want to edit.
local source_score = {
	buffer = 10,
	minuet = 8,
	lsp = 7,
	snippets = 6,
	dictionary = 2,
	path = 1,
}

-- Blink applies this offset to every completion item whose kind is Snippet.
-- The snippets provider compensates for it below so its effective weight is
-- exactly source_score.snippets.
local snippet_kind_score_offset = -3

-- Completion-source badges. Keep the lookup keys in sync with
-- `sources.providers`: ctx.source_id uses those stable provider IDs.
local source_badges = {
	minuet = { icon = "🐬", highlight = "BlinkCmpSourceMinuet" },
	lsp = { icon = "🧠", highlight = "BlinkCmpSourceLsp" },
	snippets = { icon = "✂️", highlight = "BlinkCmpSourceSnippets" },
	path = { icon = "📁", highlight = "BlinkCmpSourcePath" },
	buffer = { icon = "📄", highlight = "BlinkCmpSourceBuffer" },
	dictionary = { icon = "📚", highlight = "BlinkCmpSourceDictionary" },
	cmdline = { icon = "💻", highlight = "BlinkCmpSourceCmdline" },
}

local fallback_source_badge = { icon = "🔹", highlight = "BlinkCmpSourceFallback" }

-- Solarized accent colors remain readable on both its dark and light variants.
local source_highlight_colors = {
	BlinkCmpSourceMinuet = "#268bd2",      -- 蓝色
	BlinkCmpSourceLsp = "#6c71c4",         -- 紫色
	BlinkCmpSourceSnippets = "#b58900",    -- 黄色
	BlinkCmpSourcePath = "#859900",        -- 绿色
	BlinkCmpSourceBuffer = "#2aa198",      -- 青色
	BlinkCmpSourceDictionary = "#cb4b16",  -- 橙色
	BlinkCmpSourceCmdline = "#d33682",     -- 洋红
	BlinkCmpSourceFallback = "#dc322f",    -- 红色
}


local function get_source_badge(ctx)
	local source_id = string.lower(ctx.source_id or "")
	local source_name = string.lower(ctx.source_name or "")
	return source_badges[source_id] or source_badges[source_name] or fallback_source_badge
end

local function set_source_highlights()
	for group, color in pairs(source_highlight_colors) do
		vim.api.nvim_set_hl(0, group, { fg = color, bold = true })
	end
end

local function get_buffer_numbers()
	local buffers = {}
	for _, win in ipairs(vim.api.nvim_list_wins()) do
		local buf = vim.api.nvim_win_get_buf(win)
		if vim.bo[buf].buftype == "" and vim.bo[buf].filetype ~= "" then
			buffers[buf] = true
		end
	end
	return vim.tbl_keys(buffers)
end

return {
	{
		"saghen/blink.cmp",
		version = "*",
		-- Match the old nvim-cmp lazy-load point.
		event = "InsertEnter",
		dependencies = {
			"rafamadriz/friendly-snippets",
			{
				"L3MON4D3/LuaSnip",
				config = function()
					local luasnip = require("luasnip")
					luasnip.config.setup({})
					require("luasnip.loaders.from_vscode").lazy_load()
					require("luasnip.loaders.from_vscode").lazy_load({
						paths = { custom_snippet_path },
						override_priority = 1500,
					})
				end,
			},
			{
				"uga-rosa/cmp-dictionary",
				-- cmp-dictionary normally registers itself with nvim-cmp from
				-- after/plugin. We use its dictionary implementation directly from
				-- a native Blink source instead.
				init = function()
					vim.g.loaded_cmp_dictionary = true
				end,
			},
			-- Minuet is configured in plugins/minuet-ai.lua. Declaring it here as
			-- a Blink dependency guarantees that its setup runs before the Blink
			-- source is instantiated.
			"milanglacier/minuet-ai.nvim",
			"windwp/nvim-autopairs",
		},
		opts = {
			snippets = {
				preset = "luasnip",
				score_offset = snippet_kind_score_offset,
			},
			appearance = {
				nerd_font_variant = "mono",
				use_nvim_cmp_as_default = false,
			},
			completion = {
				list = {
					selection = {
						preselect = true,
						-- nvim-cmp used `noinsert`; only accept on <CR>/<Tab>.
						auto_insert = false,
					},
				},
				documentation = {
					auto_show = true,
					auto_show_delay_ms = 0,
				},
				accept = {
					-- Equivalent to the old nvim-autopairs confirm_done hook for
					-- function and method completion items.
					auto_brackets = {
						enabled = true,
					},
				},
				menu = {
					draw = {
						-- Equivalent to lspkind's `menu = "[SOURCE]"`.
						columns = {
							{ "label", "label_description", gap = 1 },
							{ "source_name" },
						},
						components = {
							label = {
								width = { fill = true, max = 50 },
							},
							source_name = {
								width = { max = 18 },
								text = function(ctx)
									local badge = get_source_badge(ctx)
									return badge.icon .. " [" .. string.upper(ctx.source_name) .. "]"
								end,
								highlight = function(ctx, text)
									local badge = get_source_badge(ctx)
									local name = string.upper(ctx.source_name)
									local name_start = #(badge.icon .. " [")

									return {
										-- Keep the brackets in Blink's normal source color.
										{ 0, #text, group = "BlinkCmpSource" },
										{ 0, #badge.icon, group = badge.highlight, priority = 20000 },
										{ name_start, name_start + #name, group = badge.highlight, priority = 20000 },
									}
								end,
							},
						},
					},
				},
			},
			keymap = {
				-- Keep the old cmp mappings: Tab cycles the menu first, then
				-- expands/jumps through LuaSnip placeholders.
				preset = "none",
				["<C-p>"] = { "select_prev", "fallback" },
				["<C-n>"] = { "select_next", "fallback" },
				["<C-b>"] = { "scroll_documentation_up", "fallback" },
				["<C-f>"] = { "scroll_documentation_down", "fallback" },
				["<C-e>"] = { "cancel", "fallback" },
				["<C-space>"] = {
					function(cmp)
						if cmp.is_visible() then
							return cmp.show_documentation()
						end
						-- The old cmp preset invoked the normal completion command,
						-- which uses every configured default source.
						cmp.show()
						return true
					end,
				},
				["<Tab>"] = {
					function(cmp)
						local luasnip = require("luasnip")
						if cmp.is_visible() then
							return cmp.select_next()
						elseif luasnip.expandable() then
							luasnip.expand()
							return true
						elseif luasnip.expand_or_jumpable() then
							luasnip.expand_or_jump()
							return true
						end
						return false
					end,
					"fallback",
				},
				["<S-Tab>"] = {
					function(cmp)
						local luasnip = require("luasnip")
						if cmp.is_visible() then
							return cmp.select_prev()
						elseif luasnip.jumpable(-1) then
							luasnip.jump(-1)
							return true
						end
						return false
					end,
					"fallback",
				},
				["<CR>"] = {
					function(cmp)
						if cmp.is_visible() then
							-- Equivalent to cmp.confirm({ select = true }).
							return cmp.select_and_accept()
						end
						return require("nvim-autopairs").autopairs_cr()
					end,
				},
			},
			sources = {
				default = { "minuet", "lsp", "snippets", "path", "buffer", "dictionary" },
				providers = {
					minuet = {
						name = "minuet",
						module = "minuet.blink",
						score_offset = source_score.minuet,
						-- Avoid loading Minuet's HTTP backend (and its warning) when
						-- the endpoint or API-key environment variable is not present.
						enabled = function()
							return vim.env.MINUET_END_POINT ~= nil
								and vim.env.MINUET_END_POINT ~= ""
								and vim.env.MINUET_API_KEY ~= nil
								and vim.env.MINUET_API_KEY ~= ""
						end,
						async = true,
						timeout_ms = 2000,
					},
					lsp = {
						-- nvim-cmp called this source `nvim_lsp`.
						name = "nvim_lsp",
						module = "blink.cmp.sources.lsp",
						score_offset = source_score.lsp,
						fallbacks = {},
					},
					snippets = {
						-- nvim-cmp called this source `luasnip`.
						name = "luasnip",
						module = "blink.cmp.sources.snippets",
						score_offset = source_score.snippets - snippet_kind_score_offset,
					},
					path = {
						name = "path",
						module = "blink.cmp.sources.path",
						score_offset = source_score.path,
						-- `cmp.config.sources({ path }, { cmdline })` only queried
						-- cmdline after path was empty for `:` completion.
						fallbacks = function()
							if vim.fn.getcmdtype() == ":" then
								return { "cmdline" }
							end
							return {}
						end,
					},
					buffer = {
						name = "buffer",
						module = "blink.cmp.sources.buffer",
						score_offset = source_score.buffer,
						-- The old cmp source used keyword_length = 3. Blink keeps
						-- this on the provider, not inside provider.opts.
						min_keyword_length = 3,
						opts = {
							get_bufnrs = get_buffer_numbers,
						},
					},
					dictionary = {
						name = "dictionary",
						module = "config.blink_dictionary",
						score_offset = source_score.dictionary,
						min_keyword_length = 2,
						opts = {
							keyword_length = 2,
						},
					},
				},
				per_filetype = {
					gitcommit = { "buffer" },
				},
			},
			cmdline = {
				sources = function()
					local cmd_type = vim.fn.getcmdtype()
					if cmd_type == "/" or cmd_type == "?" then
						return { "buffer" }
					end
					if cmd_type == ":" then
						return { "path", "cmdline" }
					end
					return {}
				end,
				keymap = {
					preset = "cmdline",
				},
				completion = {
					menu = {
						auto_show = true,
					},
				},
			},
		},
		config = function(_, opts)
			set_source_highlights()
			vim.api.nvim_create_autocmd("ColorScheme", {
				group = vim.api.nvim_create_augroup("BlinkCmpSourceHighlights", { clear = true }),
				callback = set_source_highlights,
			})

			-- Keep the dictionary settings from the old cmp source.
			require("cmp_dictionary").setup({
				paths = { dictionary_path },
				exact_length = 2,
			})

			-- Use Minuet's canonical Blink mapping to request only the Minuet
			-- provider on demand.
			opts.keymap["<A-y>"] = require("minuet").make_blink_map()

			require("blink.cmp").setup(opts)
		end,
	},
}
