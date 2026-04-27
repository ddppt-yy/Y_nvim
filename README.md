# Y_nvim Configuration

> take it easy ~~~

A lightweight and efficient Neovim configuration based on Lua, specifically designed for SystemVerilog development with modern IDE features.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Keybindings](#keybindings)
- [Custom Commands](#custom-commands)
- [Installed Plugins](#installed-plugins)
- [Language Support](#language-support)
- [Directory Structure](#directory-structure)

---

## Features

- **SystemVerilog Support**: Integrated Verible language server for syntax analysis and completion
- **AI Code Completion**: Minuet-ai.nvim with OpenAI-compatible API support (GLM-5.1)
- **Modern UI**: Beautiful status line, buffer tabs, and file explorer
- **Enhanced Editing**: Auto pairs, comments, indentation guides
- **Git Integration**: Git signs and blame display, LazyGit integration
- **Powerful Search**: Telescope-based fuzzy finding
- **LSP Features**: Go to definition, references, diagnostics, code actions
- **Snacks Integration**: Dashboard, smooth scroll, bigfile protection, terminal manager, and more
- **Markdown Enhancement**: Table auto-format, section numbering

---

## Quick Start

### Prerequisites

- Neovim 0.5+ (with Lua support)
- Python 3 (for various tools)
- Git
- [Verible](https://github.com/chipsalliance/verible) (for SystemVerilog)
- OpenAI-compatible API endpoint (optional, for AI completion)

### Installation

```bash
# Clone this repository to ~/.config/nvim
git clone <your-repo-url> ~/.config/nvim

# Start Neovim
nvim
```

Lazy.nvim will automatically install plugins on first startup.

---

## Keybindings

### Leader Key

The leader key is set to `,` (comma)

### General Navigation

| Keybinding               | Mode          | Description                                 |
| ------------------------ | ------------- | ------------------------------------------- |
| `j` / `k`                | Normal        | Move cursor visually (handle wrapped lines) |
| `<Space>`                | Normal        | Open search (/)                             |
| `<leader><cr>`           | Normal        | Clear search highlight                      |
| `<C-J/K/H/L>`            | Normal        | Navigate between windows                    |
| `<C-Down/Up/Left/Right>` | Normal        | Navigate between windows (arrow keys)       |
| `<C-h/l>`                | Normal        | Resize window width (±2)                    |
| `<C-j/k>`                | Normal        | Resize window height (±2)                   |
| `<A-j/k>`                | Normal/Visual | Move line(s) up/down                        |
| `<D-j/k>`                | Normal        | Move line(s) up/down (Mac)                  |

### Buffer Management

| Keybinding   | Mode   | Description                     |
| ------------ | ------ | ------------------------------- |
| `<leader>bd` | Normal | Close current buffer            |
| `<leader>ba` | Normal | Close all buffers               |
| `<C-Tab>`    | Normal | Next buffer                     |
| `<C-S-Tab>`  | Normal | Previous buffer                 |
| `<F2>`       | Normal | Toggle file explorer (NvimTree) |

### Tab Management

| Keybinding   | Mode   | Description                             |
| ------------ | ------ | --------------------------------------- |
| `<leader>tn` | Normal | New tab                                 |
| `<leader>to` | Normal | Close other tabs                        |
| `<leader>tc` | Normal | Close current tab                       |
| `<leader>tm` | Normal | Move tab                                |
| `<leader>te` | Normal | Open new tab with current buffer's path |

### File Operations

| Keybinding   | Mode   | Description                              |
| ------------ | ------ | ---------------------------------------- |
| `<leader>cd` | Normal | Change CWD to current buffer's directory |
| `<leader>so` | Normal | Toggle symbols outline                   |

### Spell Checking

| Keybinding   | Mode   | Description               |
| ------------ | ------ | ------------------------- |
| `<leader>ss` | Normal | Toggle spell checking     |
| `<leader>sn` | Normal | Next spelling error       |
| `<leader>sp` | Normal | Previous spelling error   |
| `<leader>sa` | Normal | Add word to dictionary    |
| `<leader>s?` | Normal | Show spelling suggestions |

### Visual Mode

| Keybinding | Mode   | Description                               |
| ---------- | ------ | ----------------------------------------- |
| `*` / `#`  | Visual | Search forward/backward for selected text |
| `<A-j/k>`  | Visual | Move selected lines up/down               |

### LSP Keybindings

| Keybinding   | Mode          | Description                               |
| ------------ | ------------- | ----------------------------------------- |
| `gd`         | Normal        | Peek definition (Lspsaga)                 |
| `gD`         | Normal        | Go to definition                          |
| `gh`         | Normal        | Show documentation/hover (Lspsaga finder) |
| `gi`         | Normal        | Go to implementation                      |
| `gr`         | Normal        | Rename symbol (Lspsaga)                   |
| `go`         | Normal        | Show line diagnostics                     |
| `gn`         | Normal        | Go to next diagnostic                     |
| `<leader>cd` | Normal        | Show cursor/line diagnostics              |
| `<leader>ca` | Normal/Visual | Code action                               |

### AI Completion (Minuet-ai)

| Keybinding | Mode   | Description                         |
| ---------- | ------ | ----------------------------------- |
| `<A-y>`    | Insert | Trigger AI completion               |
| `<A-A>`    | Insert | Accept whole completion             |
| `<A-a>`    | Insert | Accept one line                     |
| `<A-z>`    | Insert | Accept n lines (prompts for number) |
| `<A-[>`    | Insert | Previous completion item            |
| `<A-]>`    | Insert | Next completion item                |
| `<A-e>`    | Insert | Dismiss completion                  |

### Other Useful Keys

| Keybinding          | Mode     | Description                    |
| ------------------- | -------- | ------------------------------ |
| `Y`                 | Normal   | Copy current line (yy)         |
| `"+Y`               | Normal   | Copy to system clipboard       |
| `<leader>cc`        | Normal   | Toggle comment                 |
| `<leader>bb`        | Normal   | Insert BLOCK_BEGIN/END markers |
| `<a-z>`             | Normal   | Toggle line wrap               |
| `<a-d>`             | Normal   | Toggle terminal                |
| `<Esc>`             | Terminal | Exit terminal mode             |
| `<CR>`              | Insert   | Confirm completion or newline  |
| `<Tab>` / `<S-Tab>` | Insert   | Navigate completion menu       |
| `<C-b/f>`           | Insert   | Scroll docs up/down            |
| `<C-e>`             | Insert   | Abort completion               |

---

## Custom Commands

### File & Encoding

| Command             | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `:IConvertEncoding` | Convert file encoding (UTF-8 → LATIN1 → GBK → UTF-8) |
| `:BufferDelete`     | Delete buffer while maintaining window layout        |

### SystemVerilog

| Command                 | Description                                                                  |
| ----------------------- | ---------------------------------------------------------------------------- |
| `:YhGenVeribleFilelist` | Generate verible.filelist for SystemVerilog project (using fd/fdfind)        |
| `:YhFormatFile`         | Format current file (stylua for Lua, LSP for others)                         |
| `:YhSvAlignBlock`       | Align selected SystemVerilog block using Python script (range command)       |

### File Search

| Command       | Description                                      |
| ------------- | ------------------------------------------------ |
| `:YhFindFile` | Open Telescope file finder in Git root directory |

---

## Installed Plugins

### Core Functionality

#### 1. **Package Manager**

- **[lazy.nvim](https://github.com/folke/lazy.nvim)** - Fast plugin manager with lazy loading support

#### 2. **Completion & Snippets**

- **[nvim-cmp](https://github.com/hrsh7th/nvim-cmp)** - Autocompletion engine
  - [cmp-nvim-lsp](https://github.com/hrsh7th/cmp-nvim-lsp) - LSP completion source
  - [cmp-nvim-lua](https:///github.com/hrsh7th/cmp-nvim-lua) - Neovim Lua API completion
  - [cmp-buffer](https://github.com/hrsh7th/cmp-buffer) - Buffer word completion
  - [cmp-path](https://github.com/hrsh7th/cmp-path) - File path completion
  - [cmp-cmdline](https://github.com/hrsh7th/cmp-cmdline) - Command line completion
  - [cmp-vsnip](https://github.com/hrsh7th/cmp-vsnip) - Vsnip completion source
  - [cmp_luasnip](https://github.com/saadparwaiz1/cmp_luasnip) - LuaSnip completion source
  - [cmp-dictionary](https://github.com/uga-rosa/cmp-dictionary) - Dictionary-based completion
  - [lspkind-nvim](https://github.com/onsails/lspkind-nvim) - Pictogram icons for LSP completion
- **[LuaSnip](https://github.com/L3MON4D3/LuaSnip)** - Snippet engine
- **[friendly-snippets](https://github.com/rafamadriz/friendly-snippets)** - Pre-defined snippets
- **[vim-vsnip](https://github.com/hrsh7th/vim-vsnip)** - VSCode snippet format support

#### 3. **AI Assistance**

- **[minuet-ai.nvim](https://github.com/milanglacier/minuet-ai.nvim)** - AI-powered code completion (supports OpenAI-compatible API, currently using GLM-5.1)

#### 4. **Language Server Protocol (LSP)**

- **[nvim-lspconfig](https://github.com/neovim/nvim-lspconfig)** - LSP configuration
- **[lspsaga.nvim](https://github.com/nvimdev/lspsaga.nvim)** - Enhanced LSP UI (diagnostics, code actions, etc.)
- **[mason.nvim](https://github.com/mason-org/mason.nvim)** - Package manager for LSP servers
- **[mason-lspconfig.nvim](https://github.com/mason-org/mason-lspconfig.nvim)** - Bridge between mason and lspconfig

#### 5. **Syntax & Parsing**

- **[nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter)** - Syntax highlighting and code understanding
- **[rainbow-delimiters.nvim](https://github.com/HiPhish/rainbow-delimiters.nvim)** - Rainbow parentheses

#### 6. **Editing Enhancements**

- **[nvim-autopairs](https://github.com/windwp/nvim-autopairs)** - Auto close brackets and quotes
- **[Comment.nvim](https://github.com/numToStr/Comment.nvim)** - Toggle comments
- **[Align](https://github.com/vim-scripts/Align)** - Column alignment tool

#### 7. **Lua Development**

- **[lazydev.nvim](https://github.com/folke/lazydev.nvim)** - Better Lua development with lazy loading support

### UI & Status Line

#### 8. **Status Line**

- **[lualine.nvim](https://github.com/nvim-lualine/lualine.nvim)** - Fast and customizable status line (with Catppuccin theme, AI status, LSP info, file size)

#### 9. **Buffer & Tab Display**

- **[bufferline.nvim](https://github.com/akinsho/bufferline.nvim)** - Buffer tabs with LSP diagnostics

#### 10. **File Explorer**

- **[nvim-tree.lua](https://github.com/nvim-tree/nvim-tree.lua)** - File tree explorer (floating window mode)

#### 11. **Code Outline**

- **[outline.nvim](https://github.com/hedyhli/outline.nvim)** - Code structure outline view

#### 12. **Notifications & Messages**

- **[noice.nvim](https://github.com/folke/noice.nvim)** - Modern UI for notifications and messages
  - [nui.nvim](https://github.com/MunifTanjim/nui.nvim) - UI component library
  - [nvim-notify](https://github.com/rcarriga/nvim-notify) - Notification manager

#### 13. **Cursor Effects**

- **[smear-cursor.nvim](https://github.com/sphamba/smear-cursor.nvim)** - Smooth cursor animation

#### 14. **Themes & Transparency**

- **[tokyonight.nvim](https://github.com/folke/tokyonight.nvim)** - Tokyo Night theme
- **[catppuccin/nvim](https://github.com/catppuccin/nvim)** - Catppuccin theme (current: Macchiato)
- **[transparent.nvim](https://github.com/xiyaowong/transparent.nvim)** - Transparent background support
- **[nvim-web-devicons](https://github.com/nvim-tree/nvim-web-devicons)** - File type icons

### Search & Navigation

#### 15. **Fuzzy Finder**

- **[telescope.nvim](https://github.com/nvim-telescope/telescope.nvim)** - Fuzzy finder with multiple pickers
- **[telescope-fzf-native.nvim](https://github.com/nvim-telescope/telescope-fzf-native.nvim)** - Faster fuzzy search backend

### Git Integration

#### 16. **Git Tools**

- **[gitsigns.nvim](https://github.com/lewis6991/gitsigns.nvim)** - Git signs and blame

### All-in-One Enhancement

#### 17. **Snacks**

- **[snacks.nvim](https://github.com/folke/snacks.nvim)** - Collection of small QoL improvements, including:
  - **bigfile** - Large file protection (auto-disable Treesitter/folding)
  - **quickfile** - Fast file rendering
  - **words** - LSP reference highlight
  - **scope** - Scope detection (Treesitter/indent based)
  - **gitbrowse** - Open Git links in browser
  - **dashboard** - Startup dashboard
  - **statuscolumn** - Beautified side column (line numbers + fold marks + gitsigns)
  - **scroll** - Smooth scroll animation
  - **scratch** - Temporary scratch buffer
  - **bufdelete** - Smart buffer deletion
  - **lazygit** - LazyGit integration
  - **terminal** - Floating/split terminal manager
  - **picker** - Snacks picker
  - **indent** - Rainbow indent lines (replaces indent-blankline)

### Markdown Support

#### 18. **Markdown Tools**

- **[vim-table-mode](https://github.com/dhruvasagar/vim-table-mode)** - Auto table formatting (GitHub Flavored Markdown)
- **[md-section-number.nvim](https://github.com/whitestarrain/md-section-number.nvim)** - Auto section numbering on save

### TODO & Comments

#### 19. **TODO Comments**

- **[todo-comments.nvim](https://github.com/folke/todo-comments.nvim)** - Highlight and search TODO/FIX/HACK comments

---

## Language Support

### Configured Language Servers

| Language          | LSP Server         | File Types                     |
| ----------------- | ------------------ | ------------------------------ |
| **SystemVerilog** | verible-verilog-ls | `.v`, `.sv`, `.svh`, `.vh`     |
| **Python**        | pylsp              | `.py`                          |
| **Lua**           | lua_ls             | `.lua`                         |
| **Tcl**           | tclsp              | `.tcl`, `.sdc`, `.xdc`, `.upf` |
| **Markdown**      | marksman           | `.md`, `.markdown`             |

### Treesitter Parsers

Automatically installed parsers:

- Lua, Vim, Vimdoc, Query
- Verilog, Python, Bash
- Markdown

---

## Directory Structure

```
~/.config/nvim/
├── init.lua                 # Main entry point
├── README.md               # This file
├── lua/
│   ├── config/
│   │   ├── init.lua        # Initialization
│   │   ├── keymaps.lua     # Keybindings
│   │   ├── common_setting.lua  # General settings
│   │   ├── yhcmd.lua       # Custom commands
│   │   ├── lazy.lua        # Lazy.nvim setup
│   │   ├── colorscheme.lua # Theme configuration
│   │   └── stylua.toml     # Stylua formatter config
│   ├── plugins/            # Plugin configurations
│   │   ├── cmp.lua         # Completion
│   │   ├── lsp.lua         # LSP setup
│   │   ├── lspsaga.lua     # LSP UI
│   │   ├── telescope.lua   # Fuzzy finder
│   │   ├── nvim-tree.lua   # File explorer
│   │   ├── bufferline.lua  # Buffer tabs
│   │   ├── lua-line.lua    # Status line
│   │   ├── gitsigns.lua    # Git integration
│   │   ├── treesitter.lua  # Syntax parsing
│   │   ├── autopairs.lua   # Auto pairs
│   │   ├── comment.lua     # Comments
│   │   ├── outline.lua     # Code outline
│   │   ├── noice.lua       # Notifications
│   │   ├── rainbow.lua     # Rainbow delimiters
│   │   ├── snacks.lua      # Snacks (indent, dashboard, scroll, terminal, etc.)
│   │   ├── lazydev.lua     # Lua development
│   │   ├── minuet-ai.lua   # AI completion
│   │   ├── theme.lua       # Themes
│   │   ├── transparent.lua # Transparency
│   │   ├── smear-cursor.lua # Cursor effects
│   │   ├── align.lua       # Alignment
│   │   ├── markdown.lua    # Markdown support
│   │   └── todo_commont.lua # TODO comments
│   └── snip/               # Code snippets
│       ├── snippets/
│       │   ├── global.json
│       │   ├── markdown.json
│       │   ├── systemverilog.json
│       │   └── verilog.json
│       ├── dict.dict       # Dictionary for completion
│       └── package.json
└── script/
    ├── rgb.py              # Background color changer
    ├── nvim_zip.sh         # Backup script
    └── sv_parser/
        └── format_v.py     # SV align script
```

---

## Additional Tools & Scripts

### rgb.py

Located at `script/rgb.py`, used to change background colors for the terminal.

### Verible Filelist Generator

Use the command `:YhGenVeribleFilelist` (automatically uses `fd`/`fdfind` to find `.v`, `.sv`, `.svh`, `.vh` files under `rtl/` directories) or manually:

```bash
fd -t f -e v -e sv -e svh -e vh --full-path ".*/rtl/.*" | sort > verible.filelist
```

### SV Align Block

Use the command `:YhSvAlignBlock` on a visual selection to align SystemVerilog code. This calls `script/sv_parser/format_v.py` to process the selected block.

---

## Configuration Highlights

### General Settings

- **Shell**: `/usr/bin/zsh`
- **Leader Key**: `,`
- **Line Numbers**: Enabled
- **Cursor Line/Column Highlighting**: Enabled
- **Color Column**: 120 (visual column indicator)
- **Auto Read**: Files reloaded when changed externally
- **Auto Chdir**: Automatically change CWD to current buffer's directory
- **Scroll Offset**: 8 lines (sidescroll: 8)
- **Split Windows**: Below and right
- **Colors**: 256 colors with true color support
- **Background**: Dark (Catppuccin Macchiato / Tokyonight Moon)
- **Sign Column**: Always visible (`yes`)

### Indentation

- **Expand Tab**: Spaces instead of tabs
- **Tab Width**: 4 spaces
- **Shift Width**: 4 spaces
- **Soft Tab Stop**: 4

### Search

- **Ignore Case**: Yes (smart case enabled)
- **Highlight Search**: Yes
- **Incremental Search**: Yes

### Files & Backups

- **Backup**: Disabled
- **Write Backup**: Enabled (temp backup before save, deleted after success)
- **Swap Files**: Disabled
- **File Format**: Unix

### Completion

- **Complete Opt**: `menu,menuone,noselect,noinsert`
- **Popup Height**: 10 lines max
- **Wild Menu**: Enabled

### Folding

- **Method**: Marker (`BLOCK_BEGIN` / `BLOCK_END`)

---

## Tips & Tricks

### Telescope Usage

Common Telescope commands:

```vim
:Telescope find_files          " Find files
:Telescope live_grep           " Grep search
:Telescope buffers             " List buffers
:Telescope git_files           " Git tracked files
:Telescope diagnostics         " LSP diagnostics
:Telescope keymaps             " All keymaps
```

### LSP Commands

```vim
:LspInfo                       " Show LSP clients
:LspRestart                    " Restart LSP
:Mason                         " Open Mason UI
```

### Useful Plugins Commands

```vim
:NvimTreeToggle                " Toggle file explorer (<F2>)
:Outline                       " Toggle code outline
:BufferDelete                  " Delete buffer nicely
:TransparentToggle             " Toggle transparency
:Snacks scratch                " Open scratch buffer
:Snacks terminal               " Open terminal
:Snacks lazygit                " Open LazyGit
:Snacks dashboard              " Open dashboard
```

### AI Completion

Minuet-ai is configured with OpenAI-compatible API (GLM-5.1 model). Set the environment variable `MINUET_END_POINT` to your API endpoint. Auto-trigger is enabled for `verilog`, `systemverilog`, `python`, `shell`, and `markdown` file types.

---

## Troubleshooting

### Common Issues

1. **Plugins not loading**: Run `:Lazy sync` to update/install plugins
2. **LSP not working**: Run `:Mason` and check if language servers are installed
3. **Icons not showing**: Install a Nerd Font
4. **Slow startup**: Check `:Lazy profile` for slow plugins
5. **Snacks features missing**: Run `:Lazy sync` to ensure snacks.nvim is up to date

### Debugging

```vim
:Lazy profile                  " Check plugin load times
:LspLog                        " View LSP logs
:messages                      " View Neovim messages
:Snacks                        " Check Snacks status
```

---

## References

- [Neovim Lua Guide](https://github.com/glepnir/nvim-lua-guide-zh)
- [Verible Documentation](https://github.com/chipsalliance/verible)
- [Lazy.nvim Documentation](https://github.com/folke/lazy.nvim)
- [Snacks.nvim Documentation](https://github.com/folke/snacks.nvim)

---

**Last Updated**: 2026-04-22
