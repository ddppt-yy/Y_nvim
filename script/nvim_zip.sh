#!/bin/bash

# 备份目录和文件名设置
BACKUP_DIR="$HOME/nvim_zip"
CONFIG_ZIP="nvim_config_$(date +%Y%m%d).zip"
SHARE_ZIP="nvim_share_$(date +%Y%m%d).zip"
COMBINED_ZIP="nvim_backup_$(date +%Y%m%d).zip"


# 创建备份目录
mkdir -p "$BACKUP_DIR" || { echo "无法创建目录 $BACKUP_DIR"; exit 1; }

# 打包 ~/.config/nvim
if [ -d "$HOME/.config/nvim" ]; then
    echo "正在打包 ~/.config/nvim ..."
    cd "$HOME/.config" && zip -r "$BACKUP_DIR/$CONFIG_ZIP" nvim
    echo "已生成: $BACKUP_DIR/$CONFIG_ZIP"
else
    echo "警告：~/.config/nvim 不存在，跳过"
fi

# 打包 ~/.local/share/nvim
if [ -d "$HOME/.local/share/nvim" ]; then
    echo "正在打包 ~/.local/share/nvim ..."
    cd "$HOME/.local/share" && zip -r "$BACKUP_DIR/$SHARE_ZIP" nvim
    echo "已生成: $BACKUP_DIR/$SHARE_ZIP"
else
    echo "警告：~/.local/share/nvim 不存在，跳过"
fi

# 将两个压缩包再次打包
if [ -f "$BACKUP_DIR/$CONFIG_ZIP" ] || [ -f "$BACKUP_DIR/$SHARE_ZIP" ]; then
    echo "正在将两个压缩包打包为 $COMBINED_ZIP ..."
    cd "$BACKUP_DIR" && zip "$COMBINED_ZIP" $CONFIG_ZIP $SHARE_ZIP 2>/dev/null
    echo "已生成: $BACKUP_DIR/$COMBINED_ZIP"
else
    echo "没有可用的压缩包，跳过最终打包"
fi

echo "操作完成。备份文件位于: $BACKUP_DIR"
