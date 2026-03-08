--------------------------------------------------
-- common function
--------------------------------------------------

-- 定义一个函数，用于获取当前 buffer 所在 Git 仓库的根目录
local function get_git_root()
	local bufnr = vim.api.nvim_get_current_buf()
	local bufpath = vim.api.nvim_buf_get_name(bufnr)
	if bufpath == "" then
		-- 如果当前 buffer 没有文件名（如新文件或无文件），则使用当前工作目录
		return nil
	end
	local file_dir = vim.fn.fnamemodify(bufpath, ":h") -- 获取文件所在目录
	-- 执行 git rev-parse --show-toplevel，获取 Git 根目录
	local git_root = vim.fn.systemlist(
		string.format("git -C %s rev-parse --show-toplevel 2>/dev/null", vim.fn.shellescape(file_dir))
	)[1]
	return git_root and git_root ~= "" and git_root or nil
end

--------------------------------------------------
-- ../plugins/lsp.lua
--------------------------------------------------
-- BLOCK_BEGIN
-- -- 设置自动命令
-- local format_on_save_group = vim.api.nvim_create_augroup("LspFormatOnSave", { clear = true })
-- vim.api.nvim_create_autocmd("BufWritePre", {
-- 	group = format_on_save_group,
-- 	callback = function()
-- 		if opts.autoformat then
-- 			vim.lsp.buf.format({
-- 				async = false,
-- 				timeout_ms = 3000,
-- 				filter = function(client)
-- 					-- 只允许一个客户端处理格式化
-- 					return client.name ~= "tsserver" and client.name ~= "sumneko_lua"
-- 				end,
-- 			})
-- 		end
-- 	end,
-- })
-- vim.keymap.set({ 'n', 'x' }, '<leader>f', function() vim.lsp.buf.format({ async = true }) end, opts) -- <space>f进行代码格式化
-- 创建命令 :format_file 来执行格式化
vim.api.nvim_create_user_command("YhFormatFile", function()
	vim.lsp.buf.format({ async = false, timeout_ms = 3000 })
end, { desc = "Format current file with LSP" })
-- BLOCK_END

--------------------------------------------------
-- ../plugins/telescope.lua
--------------------------------------------------
-- BLOCK_BEGIN
-- telescope find_files in the git_root
vim.api.nvim_create_user_command("YhFindFile", function()
	local git_root = get_git_root()
	if git_root then
		-- 如果获取到 Git 根目录，则以该目录为 cwd 打开 Telescope find_files
		require("telescope.builtin").find_files({ cwd = git_root })
	else
		-- 如果不在 Git 仓库中，则 fallback 到当前文件所在目录（或当前工作目录）
		local fallback_dir = vim.fn.expand("%:p:h")
		if fallback_dir == "" then
			fallback_dir = vim.fn.getcwd()
		end
		require("telescope.builtin").find_files({ cwd = fallback_dir })
	end
end, { desc = "telescope find_files in the git_root" })
-- BLOCK_END
