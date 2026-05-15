-- 与 yazi.toml 同目录下的 init.lua
function Linemode:size_time_perm()
    -- 获取文件修改时间（使用官方推荐的 mtime）
    local time = (self._file.cha.mtime or 0) // 1
    local time_str = ""
    
    if time > 0 then
        local current_year = os.date("%Y")
        local file_year = os.date("%Y", time)
        
        if file_year == current_year then
            -- 当年文件显示：月 日 时:分
            time_str = os.date("%b %d %H:%M", time)
        else
            -- 往年文件显示：月 日  年
            time_str = os.date("%b %d  %Y", time)
        end
    end

    -- 获取文件大小（人类可读格式）
    local size = self._file:size()
    local size_str = size and ya.readable_size(size):gsub(" ", "") or "-"

    -- 获取文件权限（仅Unix-like系统可用）
    local perm_str = ""
    if ya.target_family() == "unix" then
        perm_str = (self._file.cha and self._file.cha:perm()) or "----------"
    end

    -- 组合显示内容，调整顺序和间距
    return ui.Line(string.format(" %s  %s  %s ", perm_str, size_str, time_str))
end
