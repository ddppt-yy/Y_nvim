require("mason").setup({
    ui = {
        icons = {
            package_installed = "✓",
            package_pending = "➜",
            package_uninstalled = "✗"
        }
    }
})

require("mason-lspconfig").setup({
    -- 确保安装，根据需要填写
    ensure_installed = {
        "lua_ls",
        -- find . -name "*.sv" -o -name "*.svh" -o -name "*.v" | sort > verible.filelist
        "verible",
        "pylsp",
        -- "pyre",
    },
})

--lsp & cmp
local capabilities = require('cmp_nvim_lsp').default_capabilities()

local lsp_set_keymap = require("keymaps")
local on_attach = function(_, bufnr)
    lsp_set_keymap.set_keymap(bufnr)
end


require("lspconfig").lua_ls.setup {
    capabilities = capabilities,
    settings = {
        Lua = {
            diagnostics = {
                -- Get the language server to recognize the `vim` global
                globals = {'vim'},
            },
        }
    },
    on_attach = on_attach
}

local lsp_flags = {
  -- This is the default in Nvim 0.7+
  debounce_text_changes = 150,
}
require("lspconfig").verible.setup {
    capabilities = capabilities,
    on_attach = on_attach,
    flags = lsp_flags,
    root_dir = function() return vim.loop.cwd() end
    -- root_dir = function() return vim.loop.cwd() end

}

-- require("lspconfig").pyre.setup {
--     capabilities = capabilities,
--     on_attach = on_attach
-- }

require("lspconfig").pylsp.setup {
    capabilities = capabilities,
    on_attach = on_attach
}

