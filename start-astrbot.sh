#!/bin/bash
# 等待 Surge TUN 初始化（固定延迟 30 秒，避免启动时 DNS 失败）
echo "[start-astrbot] Waiting 30s for Surge TUN to initialize..."
sleep 30
echo "[start-astrbot] Starting AstrBot..."
exec /Users/dianchi/JW-Bot/.venv/bin/astrbot run
