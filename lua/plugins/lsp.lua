


require("mason").setup()
require("mason-lspconfig").setup {
    -- lua sv 
    ensure_installed = { "lua_ls", "verible" },
}


