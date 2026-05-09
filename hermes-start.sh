#!/bin/bash
# Hermes Agent 启动脚本

HERMES_DIR="/Users/dianchi/DC-Agent/hermes-agent"
VENV_PYTHON="$HERMES_DIR/venv/bin/python"

echo "╔═══════════════════════════════════════════════╗"
echo "║         🚀 启动 Hermes Agent                  ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# 检查虚拟环境
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ 错误：虚拟环境未找到！"
    echo "请先运行安装脚本"
    exit 1
fi

# 设置环境变量
export HERMES_HOME="/Users/dianchi/DC-Agent/hermes-config"

# 启动 Hermes
echo "启动 Hermes Agent..."
echo "配置目录：$HERMES_HOME"
echo ""
cd "$HERMES_DIR"
exec "$VENV_PYTHON" -m hermes_cli.main "$@"
