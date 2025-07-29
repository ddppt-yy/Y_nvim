return {
    "numToStr/Comment.nvim",
    -- event = "VeryLazy",  -- 延迟加载
    event = { "BufReadPost", "BufNewFile" }, -- 文件打开时加载
    config = function()
        require('Comment').setup(
            {
                toggler = {
                    ---Line-comment toggle keymap
                    -- line = '<c-_>',
                    line = '<leader>cc',
                },
            }
        )
    end
}
