#!/bin/bash
cd /Users/dianchi/DC-Agent

# 强制清理环境变量，防止走代理
unset http_proxy
unset https_proxy
unset all_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
unset ALL_PROXY

echo "[JW-Bot] 网络代理环境变量已清理。"

# 杀死现有进程
lsof -ti :6185 | xargs kill -9 2>/dev/null
echo "[JW-Bot] 端口 6185 已清理。"

# 启动系统
echo "[JW-Bot] 正在重新启动系统..."
nohup uv run main.py > astrbot.log 2> astrbot.err.log < /dev/null &

echo "[JW-Bot] 系统已在后台启动，正在等待连接建立..."
sleep 5
tail -n 10 astrbot.log
