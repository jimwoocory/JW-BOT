#!/bin/bash
# ============================================================
# 自动同步定时任务安装脚本
# 功能：
#   - 安装/卸载 macOS launchd 定时任务
#   - 每天凌晨2:00自动执行同步
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.jwbot.baidu-nas-sync.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"
LOG_DIR="$SCRIPT_DIR/nas_sync/logs"

install_plist() {
    echo "正在安装定时任务..."

    # 创建 LaunchAgents 目录
    mkdir -p "$HOME/Library/LaunchAgents"

    # 创建 plist 文件
    cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jwbot.baidu-nas-sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT_DIR/auto_sync_startup.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>RunAtLoad</key>
    <false/>

    <key>KeepAlive</key>
    <false/>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd_stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
PLIST

    echo "✓ 已创建: $PLIST_PATH"

    # 加载定时任务
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load -w "$PLIST_PATH"

    echo "✓ 定时任务已启用"
    echo ""
    echo "任务详情："
    echo "  - 执行时间: 每天凌晨 2:00"
    echo "  - 执行内容: 自动挂载 NAS → 同步百度网盘 → 卸载 NAS"
    echo "  - 日志目录: $LOG_DIR"
    echo ""
}

uninstall_plist() {
    echo "正在卸载定时任务..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo "✓ 定时任务已移除"
}

show_status() {
    echo "=========================================="
    echo "定时任务状态检查"
    echo "=========================================="
    echo ""

    # 检查 launchd 状态
    if launchctl list | grep -q "com.jwbot.baidu-nas-sync"; then
        echo "✓ launchd 定时任务: 已启用"
        launchctl list | grep "com.jwbot.baidu-nas-sync"
    else
        echo "✗ launchd 定时任务: 未启用"
    fi
    echo ""

    # 显示下次执行时间
    echo "计划执行时间: 每天凌晨 2:00"
    echo "（macOS 会自动在系统空闲时执行）"
    echo ""

    # 显示最近的日志
    if [[ -d "$LOG_DIR" ]]; then
        echo "最近的日志文件:"
        ls -lh "$LOG_DIR"/*.log 2>/dev/null | tail -5 || echo "  暂无日志"
    else
        echo "日志目录: $LOG_DIR (尚未创建)"
    fi
    echo ""
}

case "${1:-status}" in
    install)
        mkdir -p "$LOG_DIR"
        install_plist
        ;;
    uninstall)
        uninstall_plist
        ;;
    status)
        show_status
        ;;
    *)
        cat << EOF
用法: $0 [install|uninstall|status]

命令:
  install    - 安装定时任务（每天凌晨2:00自动同步）
  uninstall  - 卸载定时任务
  status     - 查看定时任务状态（默认）

示例:
  $0 install   # 安装定时任务
  $0 status    # 查看状态

EOF
        ;;
esac
