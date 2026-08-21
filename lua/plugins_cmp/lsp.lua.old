return {
    -- Mason 插件管理
    {
        "williamboman/mason.nvim",
        event = { "BufReadPost", "BufNewFile" }, -- 文件打开时加载
        config = function()
            require("mason").setup({
                ui = {
                    icons = {
                        package_installed = "✓",
                        package_pending = "➜",
                        package_uninstalled = "✗"
                    }
                }
            })
        end
    },

    -- Mason LSP 配置管理
    -- {
    --     "williamboman/mason-lspconfig.nvim",
    --     event = { "BufReadPost", "BufNewFile" }, -- 文件打开时加载
    --     dependencies = { "williamboman/mason.nvim" },
    --     config = function()
    --         require("mason-lspconfig").setup({
    --             ensure_installed = {
    --                 "lua_ls",
    --                 "verible",
    --                 "pylsp",
    --                 -- "pyre",
    --             }
    --         })
    --     end
    -- },

    -- LSP 核心功能
    {
        "neovim/nvim-lspconfig",
        event = { "BufReadPost", "BufNewFile" }, -- 文件打开时加载
        dependencies = {
            "williamboman/mason.nvim",
            "williamboman/mason-lspconfig.nvim",
            "hrsh7th/cmp-nvim-lsp"  -- LSP 补全支持
        },
        config = function()
            local capabilities = require("cmp_nvim_lsp").default_capabilities()
            local lsp_set_keymap = require("config.keymaps")

            local on_attach = function(_, bufnr)
                lsp_set_keymap.set_keymap(bufnr)
            end

            local lsp_flags = {
                debounce_text_changes = 150,
            }

            -- 配置 Lua 语言服务器
            require("lspconfig").lua_ls.setup({
                capabilities = capabilities,
                settings = {
                    Lua = {
                        diagnostics = {
                            globals = { "vim" },  -- 识别 vim 全局变量
                        },
                    }
                },
                on_attach = on_attach
            })

            -- 配置 Verible 语言服务器
            require("lspconfig").verible.setup({
                capabilities = capabilities,
                on_attach = on_attach,
                cmd = {
                    "verible-verilog-ls",
                    "--rules=+line-length=length:120,+parameter-name-style=parameter_style:ALL_CAPS;localparam_style:ALL_CAPS"
                },
                flags = lsp_flags,
                root_dir = function() return vim.loop.cwd() end
            })

            -- -- 配置 Python 语言服务器
            -- require("lspconfig").pylsp.setup({
            --     capabilities = capabilities,
            --     on_attach = on_attach
            -- })

            -- 可选: Pyre 配置
            require("lspconfig").pyright.setup({
                capabilities = capabilities,
                on_attach = on_attach,
                -- settings = {
                --     python = {
                --         analysis = {
                --             autoSearchPaths = true,      -- 自动搜索路径
                --             diagnosticMode = "workspace",-- 检查整个项目
                --             useLibraryCodeForTypes = true -- 利用库代码推断类型
                --         }
                --     }
                -- }
            })
        end
    }
}
