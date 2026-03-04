return {
	"saghen/blink.cmp",
	version = "*",
	dependencies = {
		"rafamadriz/friendly-snippets",
	},
	event = "VeryLazy",
	opts = {
		completion = {
			documentation = {
				auto_show = true,
			},
			-- you may want to set the following options
			menu = { auto_show = true }, -- only show menu on manual <C-space>
			ghost_text = {
				enabled = false,
				-- Show the ghost text when an item has been selected
				show_with_selection = true,
				-- Show the ghost text when no item has been selected, defaulting to the first item
				show_without_selection = false,
				-- Show the ghost text when the menu is open
				show_with_menu = true,
				-- Show the ghost text when the menu is closed
				show_without_menu = true,
			}, -- only show when menu is closed
		},

		appearance = {
			highlight_ns = vim.api.nvim_create_namespace("blink_cmp"),
			-- Sets the fallback highlight groups to nvim-cmp's highlight groups
			-- Useful for when your theme doesn't support blink.cmp
			-- Will be removed in a future release
			use_nvim_cmp_as_default = false,
			-- Set to 'mono' for 'Nerd Font Mono' or 'normal' for 'Nerd Font'
			-- Adjusts spacing to ensure icons are aligned
			nerd_font_variant = "mono",

			kind_icons = {
				Text = "󰉿",
				Method = "󰊕",
				Function = "󰊕",
				Constructor = "󰒓",

				Field = "󰜢",
				Variable = "󰆦",
				Property = "󰖷",

				Class = "󱡠",
				Interface = "󱡠",
				Struct = "󱡠",
				Module = "󰅩",

				Unit = "󰪚",
				Value = "󰦨",
				Enum = "󰦨",
				EnumMember = "󰦨",

				Keyword = "󰻾",
				Constant = "󰏿",

				Snippet = "󱄽",
				Color = "󰏘",
				File = "󰈔",
				Reference = "󰬲",
				Folder = "󰉋",
				Event = "󱐋",
				Operator = "󰪚",
				TypeParameter = "󰬛",
			},
		},
		signature = {
			enabled = false,
			trigger = {
				-- Show the signature help automatically
				enabled = true,
				-- Show the signature help window after typing any of alphanumerics, `-` or `_`
				show_on_keyword = false,
				blocked_trigger_characters = {},
				blocked_retrigger_characters = {},
				-- Show the signature help window after typing a trigger character
				show_on_trigger_character = true,
				-- Show the signature help window when entering insert mode
				show_on_insert = false,
				-- Show the signature help window when the cursor comes after a trigger character when entering insert mode
				show_on_insert_on_trigger_character = true,
			},
			window = {
				min_width = 1,
				max_width = 100,
				max_height = 10,
				border = nil, -- Defaults to `vim.o.winborder` on nvim 0.11+ or 'padded' when not defined/<=0.10
				winblend = 0,
				winhighlight = "Normal:BlinkCmpSignatureHelp,FloatBorder:BlinkCmpSignatureHelpBorder",
				scrollbar = false, -- Note that the gutter will be disabled when border ~= 'none'
				-- Which directions to show the window,
				-- falling back to the next direction when there's not enough space,
				-- or another window is in the way
				direction_priority = { "n", "s" },
				-- Can accept a function if you need more control
				-- direction_priority = function()
				--   if condition then return { 'n', 's' } end
				--   return { 's', 'n' }
				-- end,

				-- Disable if you run into performance issues
				treesitter_highlighting = true,
				show_documentation = true,
			},
		},
		-- keymap = {
		-- 	preset = "super-tab",
		-- },

		keymap = {
			-- set to 'none' to disable the 'default' preset
			-- preset = "default",
			preset = "super-tab",

			["<C-p>"] = { "select_prev", "fallback" },
			["<C-n>"] = { "select_next", "fallback" },
			-- ["<Space>"] = { "select_and_accept", "fallback" },
			["<CR>"] = { "select_and_accept", "fallback" },

			-- disable a keymap from the preset
			["<C-e>"] = false, -- or {}

			-- show with a list of providers
			["<C-space>"] = {
				function(cmp)
					cmp.show({ providers = { "snippets", "buffer", "lsp" } })
				end,
			},
		},

		sources = {
			default = { "path", "snippets", "buffer", "lsp" },
		},

		providers = {
			snippets = {
				opts = {
					friendly_snippets = true,
					-- search_paths = { "~/.config/nvim/snippets/" },
					search_paths = { "~/.config/nvim/lua/snip/" },
				},
			},
			buffer = {
				module = "blink.cmp.sources.buffer",
				score_offset = -3,
				opts = {
					keyword_pattern = "[a-zA-Z0-9_\\-\\.]+",
				},
			},
		},

		cmdline = {
			sources = function()
				local cmd_type = vim.fn.getcmdtype()
				if cmd_type == "/" or cmd_type == "?" then
					return { "buffer" }
				end
				if cmd_type == ":" then
					return { "cmdline" }
				end
				return {}
			end,
			keymap = {
				preset = "super-tab",
			},
			completion = {
				menu = {
					auto_show = true,
				},
				ghost_text = {
					enabled = true,
				},
			},
		},
	},
}
