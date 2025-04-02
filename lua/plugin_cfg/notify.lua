local notify = require("notify")

notify.setup({
  -- 最小日志级别，可参考 vim.log.levels
  level = vim.log.levels.INFO,
  -- 通知的默认超时时间（毫秒）
  timeout = 5000,
  -- 消息的最大列数
  max_width = nil,
  -- 消息的最大行数
  max_height = nil,
  -- 动画阶段
  stages = "fade_in_slide_out",
  -- 渲染风格
  render = "default",
  -- 对于改变不透明度的阶段，这被视为窗口后面的高亮。可以是高亮组、RGB 十六进制值或返回 RGB 代码的函数
  background_colour = "NotifyBackground",
  -- 新窗口打开时调用的函数，可用于更改窗口设置/配置
  on_open = nil,
  -- 窗口关闭时调用的函数
  on_close = nil,
  -- 消息的最小宽度
  minimum_width = 50,
  -- 帧率
  fps = 30,
  -- 是否从上到下显示通知
  top_down = true,
  -- 是否合并重复的通知
  merge_duplicates = true,
  -- 不同类型通知的时间格式
  time_formats = {
    notification_history = "%FT%T",
    notification = "%T",
  },
  -- 每个级别的图标
  icons = {
    ERROR = "",
    WARN = "",
    INFO = "",
    DEBUG = "",
    TRACE = "✎",
  },
})
