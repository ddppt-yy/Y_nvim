local M = {}

function M.new(opts)
    local source = {
        keyword_length = (opts and opts.keyword_length) or 2,
        cmp_source = require("cmp_dictionary.source").new(),
    }
    return setmetatable(source, { __index = M })
end

function M:get_trigger_characters()
    return {}
end

function M:resolve(item, callback)
    -- Preserve cmp-dictionary's optional documentation resolver as well.
    self.cmp_source:resolve(item, callback)
end

function M:reload()
    self.cmp_source:_update()
end

local function dictionary_ready(source)
    local dictionary = source.cmp_source.dict
    if not dictionary.trie_map then
        return true
    end
    for _, path in ipairs(dictionary.paths or {}) do
        if not dictionary.trie_map[path] then
            return false
        end
    end
    return true
end

function M:get_completions(ctx, callback)
    local cursor_before_line = ctx.line:sub(1, ctx.cursor[2])
    local start_col = ctx.bounds and ctx.bounds.start_col
    if not start_col then
        local word = cursor_before_line:match("[%w_]+$") or ""
        start_col = ctx.cursor[2] - #word + 1
    end

    -- cmp-dictionary builds its trie on a libuv worker. Wait for the first
    -- indexing pass instead of returning a permanent empty completion list.
    if not dictionary_ready(self) then
        local cancelled = false
        local retry
        retry = function()
            if cancelled then
                return
            end
            if dictionary_ready(self) then
                self:get_completions(ctx, callback)
            else
                vim.defer_fn(retry, 50)
            end
        end
        vim.defer_fn(retry, 50)
        return function()
            cancelled = true
        end
    end

    self.cmp_source:complete({
        context = {
            cursor_before_line = cursor_before_line,
        },
        offset = start_col,
        keyword_length = self.keyword_length,
    }, function(response)
        local items = response and response.items or {}
        for _, item in ipairs(items) do
            item.kind = item.kind or vim.lsp.protocol.CompletionItemKind.Text
            item.detail = item.detail or item.info
            item.info = nil
        end

        callback({
            context = ctx,
            is_incomplete_forward = response and response.isIncomplete or false,
            is_incomplete_backward = response and response.isIncomplete or false,
            items = items,
        })
    end)

    return function() end
end

return M
