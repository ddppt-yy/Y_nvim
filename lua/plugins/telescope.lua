return {
	"nvim-telescope/telescope.nvim",
	version = "*",
    events = "VeryLazy",
	dependencies = {
		"nvim-lua/plenary.nvim",
		"nvim-tree/nvim-web-devicons",
		-- optional but recommended
		{ "nvim-telescope/telescope-fzf-native.nvim", build = "make" },
	},
	-- opts = {
	-- 	file_ignore_patterns = {
	-- 		-- 忽略一些常见目录和文件
	-- 		"^%.git/",
	-- 		"^node_modules/",
	-- 		"^vendor/",
	-- 		"%.class$",
	-- 		"%.jpg$",
	-- 		"%.jpeg$",
	-- 		"%.png$",
	-- 		"%.gif$",
	-- 		"%.mp4$",
	-- 		"%.ico$",
	-- 	},
	-- 	-- 设置默认的文件查找器使用 fd 或 ripgrep（需要安装）
	-- 	vimgrep_arguments = {
	-- 		"rg",
	-- 		"--color=never",
	-- 		"--no-heading",
	-- 		"--with-filename",
	-- 		"--line-number",
	-- 		"--column",
	-- 		"--smart-case",
	-- 	},
	-- 	pickers = {
	-- 		-- 可以针对特定 picker 进行配置
	-- 		find_files = {
	-- 			-- 查找文件时隐藏某些文件
	-- 			hidden = true,
	-- 			-- 使用 fd 命令（如果安装了 fd）
	-- 			find_command = { "fd", "--type", "f", "--strip-cwd-prefix" },
	-- 		},
	-- 		live_grep = {
	-- 			-- 实时搜索时也隐藏某些文件
	-- 			additional_args = { "--hidden" },
	-- 		},
	-- 	},
	-- 	extensions = {
	-- 		fzf = {
	-- 			fuzzy = true, -- 启用模糊搜索
	-- 			override_generic_sorter = true, -- 覆盖默认的 sorter
	-- 			override_file_sorter = true, -- 覆盖文件 sorter
	-- 			case_mode = "smart_case", -- 智能大小写
	-- 		},
	-- 	},
	-- },
}
-- 以下是几条常用的 Telescope 命令，你可以直接在 Neovim 的命令模式（:）下输入使用：
-- 
-- 命令	说明
-- :Telescope find_files    查找当前工作目录下的所有文件
-- :Telescope live_grep 在当前项目中进行全文搜索（需要 ripgrep）
-- :Telescope buffers   列出已打开的缓冲区，方便切换
-- :Telescope help_tags 查看 Neovim 帮助标签
-- :Telescope oldfiles  显示最近打开的文件历史
-- :Telescope git_files 仅显示当前 Git 仓库中的文件（更快）
-- :Telescope grep_string   搜索当前光标下的单词
-- :Telescope command_history   查看命令历史
-- :Telescope diagnostics   显示 LSP 诊断信息（需要 LSP 配置）
-- :Telescope keymaps   列出所有快捷键映射
-- 带参数的用法
-- 你可以给命令附加参数来指定搜索路径或行为，例如：
-- 
-- :Telescope find_files cwd=~/projects/myapp — 在指定目录下查找文件。
-- 
-- :Telescope live_grep search_dirs={"src","test"} — 只在 src 和 test 目录中搜索。
-- 
-- 提示
-- 如果安装了扩展（如 telescope-fzf-native），命令会获得更快的模糊搜索性能。
-- 
-- 大多数命令支持交互式预览，在结果列表中按 ? 可以查看当前 picker 的帮助。
