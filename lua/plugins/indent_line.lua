return {
    "echasnovski/mini.indentscope",
    version = "*",
    event = { "BufReadPost", "BufNewFile" },
    config = function()
        local mix_color = function(hex, target_hex, percent)
            -- 解析源颜色
            local r1 = tonumber(hex:sub(2, 3), 16)
            local g1 = tonumber(hex:sub(4, 5), 16)
            local b1 = tonumber(hex:sub(6, 7), 16)
            -- 解析目标颜色
            local r2 = tonumber(target_hex:sub(2, 3), 16)
            local g2 = tonumber(target_hex:sub(4, 5), 16)
            local b2 = tonumber(target_hex:sub(6, 7), 16)
            -- 混合比例
            local mix = percent / 100
            local new_r = math.floor(r1 * (1 - mix) + r2 * mix + 0.5)
            local new_g = math.floor(g1 * (1 - mix) + g2 * mix + 0.5)
            local new_b = math.floor(b1 * (1 - mix) + b2 * mix + 0.5)
            -- 转回十六进制
            return string.format("#%02X%02X%02X", new_r, new_g, new_b)
        end

        local target = "#24273A" -- RGB(36,39,58) 的十六进制
        local colors = {
            RainbowRed = "#E06C75",
            RainbowYellow = "#E5C07B",
            RainbowBlue = "#61AFEF",
            RainbowOrange = "#D19A66",
            RainbowGreen = "#98C379",
            RainbowViolet = "#C678DD",
            RainbowCyan = "#56B6C2",
        }

        for name, hex in pairs(colors) do
            local new_hex = mix_color(hex, target, 80) -- 变淡 80%
            vim.api.nvim_set_hl(0, name, { fg = new_hex })
        end

        -- 每次切换 colorscheme 时重新设置高亮组
        vim.api.nvim_create_autocmd("ColorScheme", {
            callback = function()
                for name, hex in pairs(colors) do
                    local new_hex = mix_color(hex, target, 80)
                    vim.api.nvim_set_hl(0, name, { fg = new_hex })
                end
            end,
        })

        -- 为不同缩进层级分配彩虹色
        local highlight = {
            "RainbowRed",
            "RainbowYellow",
            "RainbowBlue",
            "RainbowOrange",
            "RainbowGreen",
            "RainbowViolet",
            "RainbowCyan",
        }

        require("mini.indentscope").setup({
            draw = {
                delay = 100,
                animation = require("mini.indentscope").gen_animation.linear(),
            },
            symbol = "│",
            options = {
                try_as_border = true,
            },
        })

        -- 通过覆盖 MiniIndentscopeSymbol 高亮实现按层级着色
        vim.api.nvim_create_autocmd({ "WinScrolled", "BufEnter", "CursorMoved", "CursorMovedI" }, {
            callback = function()
                local line = vim.fn.line(".")
                local col = vim.fn.col(".")
                -- 获取当前行的缩进级别
                local indent = vim.fn.indent(line)
                local shiftwidth = vim.bo.shiftwidth
                if shiftwidth == 0 then
                    shiftwidth = vim.bo.tabstop
                end
                local level = math.floor(indent / shiftwidth)
                local hl_name = highlight[(level % #highlight) + 1]
                vim.api.nvim_set_hl(0, "MiniIndentscopeSymbol", { link = hl_name })
            end,
        })
    end,
}
