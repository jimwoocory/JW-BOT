#!/bin/bash

# AstrBot + Dashboard 启动脚本

# 设置 PATH（包含 Homebrew 和 uv）
export PATH="/opt/homebrew/bin:/Users/dianchi/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd /Users/dianchi/DC-Agent

# 启动 AstrBot 主服务
echo "Starting AstrBot..."
uv run main.py &
ASTRBOT_PID=$!

# 等待 AstrBot 启动
sleep 5

# 启动 AstrBot Vue Dashboard - 端口 4311
echo "Starting AstrBot Dashboard..."
cd /Users/dianchi/DC-Agent/dashboard
/opt/homebrew/bin/pnpm dev --port 4311 &
DASHBOARD_PID=$!

# 启动 openclaw-control-center - 端口 4312
echo "Starting openclaw-control-center..."
cd /Users/dianchi/Openclaw/openclaw-control-center
/opt/homebrew/bin/node --import tsx src/index.ts &
OPENCLAW_CC_PID=$!

# 等待进程
wait
