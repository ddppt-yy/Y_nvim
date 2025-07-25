local cmp_status_ok, cmp = pcall(require, "cmp")
if not cmp_status_ok then
    return
end

local snip_status_ok, luasnip = pcall(require, "luasnip")
if not snip_status_ok then
    return
end

vim.g.vsnip_snippet_dir = "~/.config/nvim/lua/snip/"
require("luasnip.loaders.from_vscode").lazy_load({
    path = {"~/.config/nvim/lua/snip"},
    -- include = {"python"},
})

-- 下面会用到这个函数
local check_backspace = function()
    local col = vim.fn.col "." - 1
    return col == 0 or vim.fn.getline("."):sub(col, col):match "%s"
end

local lspkind = require("lspkind")
cmp.setup({
    snippet = {
        expand = function(args)
            require('luasnip').lsp_expand(args.body)
        end,
    },
    mapping = cmp.mapping.preset.insert({
        ['<C-b>'] = cmp.mapping.scroll_docs(-4),
        ['<C-f>'] = cmp.mapping.scroll_docs(4),
        ['<C-e>'] = cmp.mapping.abort(),  -- 取消补全，esc也可以退出
        ['<CR>'] = cmp.mapping.confirm({ select = true }),


        ["<Tab>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
                cmp.select_next_item()
            elseif luasnip.expandable() then
                luasnip.expand()
            elseif luasnip.expand_or_jumpable() then
                luasnip.expand_or_jump()
            elseif check_backspace() then
                fallback()
            else
                fallback()
            end
        end, {
                "i",
                "s",
            }),

        ["<S-Tab>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
                cmp.select_prev_item()
            elseif luasnip.jumpable(-1) then
                luasnip.jump(-1)
            else
                fallback()
            end
        end, {
                "i",
                "s",
            }),
    }),

    -- 这里重要
    sources = cmp.config.sources({
        { name = 'nvim_lsp' },
        { name = 'luasnip' },
        { name = 'vsnip' },
        --:vsipopen
        { name = 'path' },
        {
            name = 'buffer',
            option = {
                get_bufnrs = function()
                    local bufs = {}
                    for _, win in ipairs(vim.api.nvim_list_wins()) do
                        local buf = vim.api.nvim_win_get_buf(win)
                        -- 只处理普通文本缓冲区 (过滤终端/NvimTree等)
                        if vim.bo[buf].buftype == "" and vim.bo[buf].filetype ~= "" then
                            bufs[buf] = true
                        end
                    end
                    return vim.tbl_keys(bufs)
                end,
                -- 可选：增加补全关键词长度限制
                keyword_length = 3,
                -- 可选：最大补全项数量
                -- max_item_count = 5
            }
        },
        {
            name = "dictionary",
            keyword_length = 2,
        },
    }),
    --根据文件类型来选择补全来源
    cmp.setup.filetype('gitcommit', {
        sources = cmp.config.sources({
            {name = 'buffer'}
        })
    }),

    -- 命令模式下输入 `/` 启用补全
    cmp.setup.cmdline('/', {
        mapping = cmp.mapping.preset.cmdline(),
        sources = {
            { name = 'buffer' }
        }
    }),

    -- 命令模式下输入 `:` 启用补全
    cmp.setup.cmdline(':', {
        mapping = cmp.mapping.preset.cmdline(),
        sources = cmp.config.sources({
            { name = 'path' }
        }, {
                { name = 'cmdline' }
            })
    }),

    -- 设置补全显示的格式
    formatting = {
        format = lspkind.cmp_format({
            with_text = true,
            maxwidth = 50,
            before = function(entry, vim_item)
                vim_item.menu = "[" .. string.upper(entry.source.name) .. "]"
                return vim_item
            end
        }),
    },
})

require("cmp_dictionary").setup({
  paths = { "~/.config/nvim/lua/snip/dict.dict" },
  exact_length = 2,
  -- first_case_insensitive = true,
  -- document = {
  --   enable = true,
  --   command = { "wn", "${label}", "-over" },
  -- },
})
