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

require("lspconfig").verible.setup {
    capabilities = capabilities,
    on_attach = on_attach,

    root_dir = function() return vim.loop.cwd() end

}

-- require("lspconfig").pyre.setup {
--     capabilities = capabilities,
--     on_attach = on_attach
-- }

require("lspconfig").pylsp.setup {
    capabilities = capabilities,
    on_attach = on_attach
}

