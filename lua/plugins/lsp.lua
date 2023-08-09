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
        "pyre",
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
    on_attach = on_attach
}

require("lspconfig").pyre.setup {
    capabilities = capabilities,
    on_attach = on_attach
}

-- local lspconfig = require('lspconfig')
--
-- require("mason-lspconfig").setup_handlers({
--     function (server_name)
--         require("lspconfig")[server_name].setup{}
--     end,
--     -- Next, you can provide targeted overrides for specific servers.
--     ["lua_ls"] = function ()
--         lspconfig.lua_ls.setup {
--             settings = {
--                 Lua = {
--                     diagnostics = {
--                         globals = { "vim" }
--                     }
--                 }
--             }
--         }
--     end,
-- })












