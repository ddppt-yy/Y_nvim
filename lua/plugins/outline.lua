return {
	"hedyhli/outline.nvim",
	lazy = true,
	cmd = { "Outline", "OutlineOpen" },
	keys = { -- 按需加载快捷键
		{ "<leader>so", "<cmd>Outline<CR>", desc = "Toggle outline" },
	},
	opts = {},
}
