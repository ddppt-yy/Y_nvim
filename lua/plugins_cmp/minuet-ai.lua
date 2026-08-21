return {
	"milanglacier/minuet-ai.nvim",
	event = "InsertEnter",
	dependencies = {
		"nvim-lua/plenary.nvim",
	},
	config = function()
		local config = {
			provider = "openai_compatible",
			n_completions = 1, -- recommend for local model for resource saving
			-- I recommend beginning with a small context window size and incrementally
			-- expanding it, depending on your local computing power. A context window
			-- of 512, serves as an good starting point to estimate your computing
			-- power. Once you have a reliable estimate of your local computing power,
			-- you should adjust the context window to a larger value.
			-- context_window: characters of context before/after cursor sent to LLM.
			-- ~4 chars ≈ 1 token, so 16000 chars ≈ 4000 tokens.
			-- 16000 is the default and works well for code completion;
			-- too large wastes tokens and adds latency, too small loses context.
			context_window = 16000,
			-- Keep Minuet available as a Blink source while retaining the
			-- virtual-text completion configured below.
			blink = {
				enable_auto_complete = true,
			},
			-- Remote models may need longer than the local-model default.
			request_timeout = 10,
			provider_options = {
				openai_compatible = {
					api_key = "MINUET_API_KEY",

					name = "DeepSeek-v4-Flash-fp8",
					model = "deepseek-v4-flash-fp8",

					-- name = "glm-4.7-fp8",
					-- model = "glm-4.7-fp8",

					-- name  = "gpt-5.6-luna",
					-- model = "gpt-5.6-luna",

					end_point = os.getenv("MINUET_END_POINT") or "",
					stream = true,
					optional = {
						-- max_tokens: max generated tokens per completion.
						-- Code completion is typically short (1-5 lines),
						-- 512 is sufficient and keeps latency low.
						max_tokens = 512,
						-- top_p: nucleus sampling threshold.
						-- 0.95 balances diversity and coherence for code completion.
						-- top_p = 0.95,
					},
				},
			},
			virtualtext = {
				auto_trigger_ft = { "verilog", "systemverilog", "python", "shell", "cshell", "zshell", "markdown" },
				keymap = {
					-- accept whole completion
					accept = "<A-A>",
					-- accept one line
					accept_line = "<A-a>",
					-- accept n lines (prompts for number)
					-- e.g. "A-z 2 CR" will accept 2 lines
					accept_n_lines = "<A-z>",
					-- Cycle to prev completion item, or manually invoke completion
					prev = "<A-[>",
					-- Cycle to next completion item, or manually invoke completion
					next = "<A-]>",
					dismiss = "<A-e>",
				},
			},
		}

		-- Minuet supports both nvim-cmp and Blink. Its setup probes for
		-- `cmp`; when a stale/partial nvim-cmp module is visible, that probe
		-- enters `minuet.cmp` and fails on `cmp.types.lsp`. Blink is the active
		-- completion engine here, so hide only that probe during setup.
		local previous_cmp_loader = package.preload.cmp
		local previous_cmp_module = package.loaded.cmp
		package.preload.cmp = function()
			error("nvim-cmp is disabled; Blink is the active completion engine")
		end
		package.loaded.cmp = nil

		local ok, err = pcall(require("minuet").setup, config)
		package.preload.cmp = previous_cmp_loader
		package.loaded.cmp = previous_cmp_module

		if not ok then
			error(err)
		end
	end,
}
