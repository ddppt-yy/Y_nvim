return {
    'windwp/nvim-autopairs',
    event = 'InsertEnter',
    dependencies = {
        "nvim-treesitter/nvim-treesitter",
        "hrsh7th/nvim-cmp" 
    }, -- 与补全插件配合使用时需要
    config = function()
        local npairs = require("nvim-autopairs")
        local Rule = require('nvim-autopairs.rule')
        local cond = require('nvim-autopairs.conds')

        npairs.setup({
            check_ts = true,  -- 使用Tree-sitter检查
            ts_config = {
                lua = {'string'},        -- lua中不处理字符串内
                javascript = {'template_string'}, -- js忽略模板字符串
            },
            fast_wrap = {
                map = '<M-e>',           -- 快速包裹快捷键(Alt+e)
                chars = { '{', '[', '(', '"', "'" },
                pattern = string.gsub([[ [%'%"%)%>%]%)%}%,] ]], '%s+', ''),
                end_key = '$',
                keys = 'qwertyuiopzxcvbnmasdfghjkl',
                check_comma = true,
                highlight = 'Search',
                highlight_grey='Comment'
            },
                -- 禁用所有单引号规则（全局生效）
                -- disable_rules = { "'" }
        })

        -- ===== 自定义规则 =====
        -- verilog
        npairs.add_rules({
            -- 禁用 Verilog 中的单引号补全（覆盖全局设置）
            Rule("'", "'", "verilog")
                :with_pair(cond.none()) -- 完全禁用补全
        }, true)


        -- 添加空格规则：| 变成 { | }
        npairs.add_rules({
            Rule(" ", " ")
                :with_pair(function(opts)
                    local pair = opts.line:sub(opts.col - 1, opts.col)
                    return vim.tbl_contains({ "()", "[]", "{}" }, pair)
                end)
        })

        -- HTML标签自动关闭
        npairs.add_rules({
            Rule("<", ">", { "html", "jsx", "tsx", "javascript", "typescript", "javascriptreact", "typescriptreact" })
                :with_pair(cond.not_after_text(">"))
                :with_pair(cond.not_before_text("<"))
                :use_key(">")
        })

        -- ===== 与cmp集成 =====
        local cmp_autopairs = require('nvim-autopairs.completion.cmp')
        local cmp = require('cmp')
        cmp.event:on(
            'confirm_done',
            cmp_autopairs.on_confirm_done()
        )

        -- ===== 修复<CR>行为 =====
        local remap = vim.api.nvim_set_keymap
        local opts = { noremap = true, silent = true, expr = true, replace_keycodes = false }
        remap("i", "<CR>", "v:lua.MUtils.completion_confirm()", opts)

        MUtils = {}
        function MUtils.completion_confirm()
            if vim.fn.pumvisible() ~= 0 then
                return vim.fn["cmp#confirm"]()
            else
                return npairs.autopairs_cr()
            end
        end
    end
}
