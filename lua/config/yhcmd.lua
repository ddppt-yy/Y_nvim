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
-- user func
--------------------------------------------------
-- BLOCK_BEGIN

-- verible filelist generate
-- BLOCK_BEGIN
function GenerateVeribleFilelist()
    -- 检查是否在 Git 仓库中
    local git_cmd = "git rev-parse --is-inside-work-tree 2>/dev/null"
    local git_handle = io.popen(git_cmd)
    local git_result = git_handle:read("*a")
    git_handle:close()

    if git_result:match("true") then
        -- 获取 Git 根目录
        local toplevel_cmd = "git rev-parse --show-toplevel"
        local toplevel_handle = io.popen(toplevel_cmd)
        local git_root = toplevel_handle:read("*l"):gsub("\n", "")
        toplevel_handle:close()

        -- 检查系统中是否有 fdfind 命令，有则用 fdfind，没有则使用 fd
        local fd_cmd = vim.fn.executable("fdfind") == 1 and "fdfind" or "fd"

        -- 构建 find 命令
        local find_cmd = string.format(
            -- 'find "%s" -type f \\( -name "*.v" -o -name "*.sv" -o -name "*.svh" -o -name "*.vh" \\)  -path "*/rtl/*"    | sort > "%s/verible.filelist"',
            '%s -t f -e v -e sv -e svh -e vh -e svh  --full-path ".*/rtl/.*"   %s | sort > "%s/verible.filelist"',
            fd_cmd,
            git_root,
            git_root
        )

        -- 执行命令
        local result = os.execute(find_cmd)

        if result then
            vim.notify(string.format("Verible filelist created at: %s/verible.filelist", git_root), vim.log.levels.INFO)
        else
            vim.notify("Failed to generate Verible filelist", vim.log.levels.ERROR)
        end
    else
        vim.notify("Current directory is not a Git repository", vim.log.levels.WARN)
    end
end
-- 创建用户命令方便调用
vim.api.nvim_create_user_command("YhGenVeribleFilelist", GenerateVeribleFilelist, {})
-- BLOCK_END


-- code convert encoding
-- BLOCK_BEGIN
function IConvertFileEncoding()
    -- 获取当前文件路径
    local current_file = vim.fn.expand('%:p')
    if current_file == '' then
        print("Error: No file name")
        return
    end

    -- 创建临时文件路径
    local middle_file = current_file .. "_iconv.mid"
    local output_file = current_file .. "_iconv.out"

    local cmd0 = "iconv -f UTF-8 -t LATIN1 " .. current_file  ..  "   -o " ..  middle_file 
    local cmd1 = "iconv -f GBK   -t UTF-8  " .. middle_file   ..  "   -o " ..  output_file

    local result = vim.fn.system(cmd0)
    if vim.v.shell_error ~= 0 then
        print("转码失败: " .. result)
        os.remove(middle_file)
        return
    end
    vim.fn.system(cmd1)

    -- 用转码后的文件替换原始文件
    local backup_file = current_file .. ".bak"
    os.rename(current_file, backup_file)
    os.rename(output_file, current_file)

    -- 清理临时文件
    os.remove(middle_file)
    os.remove(output_file)

    vim.cmd("e!")
    print("finish")
end
-- 创建命令
-- vim.cmd [[command! IConvertEncoding lua IConvertFileEncoding()]]
vim.api.nvim_create_user_command("IConvertEncoding", IConvertFileEncoding, {})
-- BLOCK_END


-- sv align
-- BLOCK_BEGIN
function SvAlignBlock(opts)
    local line1 = vim.fn.getpos("'<")[2]
    local col1  = vim.fn.getpos("'<")[3]
    local line2 = vim.fn.getpos("'>")[2]
    local col2  = vim.fn.getpos("'>")[3]
    local lines = vim.fn.getline(line1, line2)
    local block = {}
    for i, line in ipairs(lines) do
        local start_col = (i == 1) and (col1 - 1) or 0
        local end_col   = (i == #lines) and col2 or #line
        table.insert(block, line:sub(start_col + 1, end_col))
    end
    local input_text = table.concat(block, "\n")
    local python_script = vim.fn.expand('~/.config/nvim/script/sv_parser/format_v.py')
    local output_text = vim.fn.system(
        'python3 ' .. vim.fn.shellescape(python_script),
        input_text
    )
    local aligned_lines = vim.split(output_text, "\n")
    for i, aligned in ipairs(aligned_lines) do
        local new_line = (i == 1) and lines[i]:sub(1, col1 - 1) or ''
        new_line = new_line .. aligned
        new_line = new_line .. ((i == #aligned_lines) and lines[i]:sub(col2 + 1) or '')
        vim.fn.setline(line1 + i - 1, new_line)
    end
end
vim.api.nvim_create_user_command("SvAlignBlock", SvAlignBlock, { range = true })
-- BLOCK_END


-- BLOCK_END


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
	local filetype = vim.bo.filetype
	-- 对 Lua 文件使用 stylua 进行格式化
	if filetype == "lua" then
		local stylua_path = vim.fn.exepath("stylua")
		if stylua_path ~= "" then
			local file_path = vim.fn.expand("%:p")
			-- 指定 stylua 配置文件路径
			local stylua_config = vim.fn.expand("~/.config/nvim/lua/config/stylua.toml")
			local config_arg = ""
			if vim.fn.filereadable(stylua_config) == 1 then
				config_arg = " --config-path " .. vim.fn.shellescape(stylua_config)
			end
			vim.cmd("write") -- 先保存文件
			local result = vim.fn.system(stylua_path .. config_arg .. " " .. vim.fn.shellescape(file_path))
			if vim.v.shell_error == 0 then
				vim.cmd("edit!") -- 重新加载文件
				vim.notify("Formatted with stylua", vim.log.levels.INFO)
			else
				vim.notify("stylua format failed: " .. result, vim.log.levels.ERROR)
			end
		else
			-- 如果没有 stylua，使用 LSP 格式化
			vim.lsp.buf.format({ async = false, timeout_ms = 3000 })
		end
	else
		vim.lsp.buf.format({ async = false, timeout_ms = 3000 })
	end
end, { desc = "Format current file with LSP or stylua for lua files" })
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
