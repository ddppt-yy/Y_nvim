local ensure_packer = function()
    local fn = vim.fn
    local install_path = fn.stdpath('data')..'/site/pack/packer/start/packer.nvim'
    if fn.empty(fn.glob(install_path)) > 0 then
        vim.notify("installing Pakcer.nvim，please wait...")
        fn.system({'git', 'clone', '--depth', '1', 'https://github.com/wbthomason/packer.nvim', install_path})
        vim.cmd [[packadd packer.nvim]]
        return true
    end
    return false
end

local packer_bootstrap = ensure_packer()

-- Use a protected call so we don't error out on first use
local status_ok, packer = pcall(require, "packer")
if not status_ok then
    vim.notify("没有安装 packer.nvim")
    return
end

-- updata cmd
--BLOCK_BEGIN
-- :PackerCompile  :每次改变插件配置时，必须运行此命令或 PackerSync, 重新生成编译的加载文件
-- :PackerClean    :清除所有不用的插件
-- :PackerInstall  :清除，然后安装缺失的插件
-- :PackerUpdate   :清除，然后更新并安装插件
-- :PackerSync     :执行 PackerUpdate 后，再执行 PackerCompile
-- :PackerLoad     :立刻加载 opt 插件
-- 通过上边的说明，我们观察到 :PackerSync 命令包含了 :PackerUpdate 和:PackerCompile，而 :PackerUpdate 又包含了 :PackerClean 和 :PackerInstall 流程。
-- :PackerSync-|:PackerUpdate-|:PackerClean
--             |              |:PackerInstall
--             |
--             |:PackerCompile
-- 所以通常情况下，无论安装还是更新插件，我只需要下边这一条命令就够了。
-- :PackerSync
--BLOCK_END
-- open this file will auto updata plugins
if (false) then
    vim.cmd([[
    augroup pack_user_config
    autocmd!
    autocmd BufReadPost plugins_setup.lua source <afile> | PackerSync
    augroup end
    ]])
end

-- user plugin setting path
-- .
-- ├── pack
-- │   ├── packer
-- │   │   ├── opt
-- │   │   └── start
-- │   └── vim-scripts
-- │       └── start
-- │           └── vim-xx
-- └── plugin
--     └── xx.vim

return require('packer').startup({
    function(use)
        use 'wbthomason/packer.nvim'
        -- My plugins here
        -- use 'foo1/bar1.nvim'
        -- use 'foo2/bar2.nvim'

        -- Automatically set up your configuration after cloning packer.nvim
        -- Put this at the end after all plugins

        -- colorscheme
        use 'folke/tokyonight.nvim' --主题

        -- nvim-tree
        use {
            'nvim-tree/nvim-tree.lua',
            requires = { 'nvim-tree/nvim-web-devicons', opt = true }
        }

        --lualine 
        use {
            'nvim-lualine/lualine.nvim',
            requires = { 'nvim-tree/nvim-web-devicons', opt = true }
        }
        use("arkav/lualine-lsp-progress")

        -- bufferline
        use({
            "akinsho/bufferline.nvim",
            requires = { "kyazdani42/nvim-web-devicons", "moll/vim-bbye" },
        })

        -- telescope find file
        use {
            'nvim-telescope/telescope.nvim',
            requires = { {'nvim-lua/plenary.nvim'} }
        }

        -- treesitter
        use({
            "nvim-treesitter/nvim-treesitter",
            run = ":TSUpdate",
        })

        -- -- rainbow
        -- use("p00f/nvim-ts-rainbow")
        -- use("HiPhish/rainbow-delimiters")
        use 'HiPhish/rainbow-delimiters.nvim'
        -- indent-blankline
        use("lukas-reineke/indent-blankline.nvim")

        -- comment
        use "numToStr/Comment.nvim"

        -- autopairs
        use "windwp/nvim-autopairs"

        -- gitsigns
        use "lewis6991/gitsigns.nvim"

        --LSP ----------------------------------------------------
        use {
            "williamboman/mason.nvim",
            "williamboman/mason-lspconfig.nvim",
            "neovim/nvim-lspconfig",
        }

        -- cmp
        use "hrsh7th/nvim-cmp"
        use "hrsh7th/vim-vsnip"
        use "hrsh7th/cmp-vsnip"

        use "hrsh7th/cmp-nvim-lsp"
        use "hrsh7th/cmp-nvim-lua"
        use "hrsh7th/cmp-buffer"
        use "hrsh7th/cmp-path"
        use "hrsh7th/cmp-cmdline"

        use "jose-elias-alvarez/null-ls.nvim"

        use "saadparwaiz1/cmp_luasnip"
        use "onsails/lspkind-nvim"

        use "L3MON4D3/LuaSnip" -- snippets引擎，不装这个自动补全会出问题
        use {'rafamadriz/friendly-snippets'}

        use{"uga-rosa/cmp-dictionary"}


        use{"glepnir/lspsaga.nvim"}

        -- like tagbar
        use {'simrat39/symbols-outline.nvim'}

        use {'xiyaowong/transparent.nvim'}

        if packer_bootstrap then
            require('packer').sync()
        end
    end,

    config = {
        -- -- 锁定插件版本在snapshots目录
        -- snapshot_path = require("packer.util").join_paths(vim.fn.stdpath("config"), "snapshots"),
        -- -- 这里锁定插件版本在v1，不会继续更新插件
        -- snapshot = "v1",

        -- 最大并发数
        max_jobs = 16,
        -- 自定义源
        git = {
            -- default_url_format = "https://hub.fastgit.xyz/%s",
            -- default_url_format = "https://mirror.ghproxy.com/https://github.com/%s",
            -- default_url_format = "https://gitcode.net/mirrors/%s",
            -- default_url_format = "https://gitclone.com/github.com/%s",
        },
        -- display = {
        -- 使用浮动窗口显示
        --   open_fn = function()
        --     return require("packer.util").float({ border = "single" })
        --   end,
        -- },
    },
})
