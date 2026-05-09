#!/bin/bash
# AstrBot → Hermes Webhook 桥接配置脚本

set -e

echo "╔═══════════════════════════════════════════════╗"
echo "║   AstrBot → Hermes Webhook 桥接配置工具      ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
HERMES_CONFIG_DIR="/Users/dianchi/DC-Agent/hermes-config"
ASTRBOT_DIR="/Users/dianchi/DC-Agent"
BRIDGE_DIR="/Users/dianchi/DC-Agent/astrbot-hermes-bridge"
HERMES_WEBHOOK_PORT=8644
ASTRBOT_RESPONSE_PORT=8645
WEBHOOK_SECRET="astrbot_hermes_bridge_secret_$(date +%s | sha256sum | head -c 16)"

echo "📋 配置信息："
echo "  Hermes 配置目录：$HERMES_CONFIG_DIR"
echo "  AstrBot 目录：$ASTRBOT_DIR"
echo "  桥接插件目录：$BRIDGE_DIR"
echo ""

# 步骤 1：配置 Hermes Webhook
echo "📝 步骤 1: 配置 Hermes Webhook..."
read -p "是否自动配置 Hermes Webhook？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 创建 Hermes Webhook 配置
    cat > "$BRIDGE_DIR/hermes_webhook_config.yaml" <<EOF
# Hermes Webhook 配置 - AstrBot 桥接
# 将此配置添加到 hermes-config/config.yaml

gateway:
  platforms:
    webhook:
      enabled: true
      host: "0.0.0.0"
      port: $HERMES_WEBHOOK_PORT
      
      # HMAC 密钥（用于验证 AstrBot 请求）
      secret: "$WEBHOOK_SECRET"
      
      # 配置路由：接收 AstrBot 转发的 QQ 消息
      routes:
        astrbot_qq:
          secret: "$WEBHOOK_SECRET"
          prompt: |
            你正在通过 QQ 与用户对话。
            
            用户信息：
            - 用户 ID: {{user_id}}
            - 昵称：{{sender_nickname}}
            - 消息类型：{{message_type}}
            
            用户消息：
            {{message}}
            
            请以友好、简洁的方式回复用户。
          
          # 响应返回方式
          deliver: "webhook_response"
          deliver_extra:
            response_url: "http://localhost:$ASTRBOT_RESPONSE_PORT/hermes_response"
EOF
    
    echo -e "${GREEN}✓ Hermes Webhook 配置已创建${NC}"
    echo "  文件：$BRIDGE_DIR/hermes_webhook_config.yaml"
    echo ""
fi

# 步骤 2：配置 AstrBot
echo "📝 步骤 2: 配置 AstrBot..."
read -p "是否自动配置 AstrBot？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 创建 AstrBot 配置
    cat > "$BRIDGE_DIR/astrbot_config.json" <<EOF
{
  "hermes_bridge": {
    "webhook_url": "http://localhost:$HERMES_WEBHOOK_PORT/webhooks/astrbot_qq",
    "secret": "$WEBHOOK_SECRET",
    "response_port": $ASTRBOT_RESPONSE_PORT,
    "enable_forwarding": true,
    "message_format": "text"
  }
}
EOF
    
    echo -e "${GREEN}✓ AstrBot 配置已创建${NC}"
    echo "  文件：$BRIDGE_DIR/astrbot_config.json"
    echo ""
fi

# 步骤 3：生成环境变量文件
echo "📝 步骤 3: 生成环境变量..."
cat > "$BRIDGE_DIR/.env" <<EOF
# AstrBot → Hermes Bridge 环境变量

# Hermes Webhook 配置
HERMES_WEBHOOK_URL=http://localhost:$HERMES_WEBHOOK_PORT/webhooks/astrbot_qq
HERMES_WEBHOOK_SECRET=$WEBHOOK_SECRET
HERMES_RESPONSE_PORT=$ASTRBOT_RESPONSE_PORT

# AstrBot 配置
ASTRBOT_WEBHOOK_PORT=$HERMES_WEBHOOK_PORT
ASTRBOT_RESPONSE_PORT=$ASTRBOT_RESPONSE_PORT
EOF

echo -e "${GREEN}✓ 环境变量文件已创建${NC}"
echo "  文件：$BRIDGE_DIR/.env"
echo ""

# 步骤 4：创建 systemd 服务文件（可选）
echo "📝 步骤 4: 创建 systemd 服务（可选）..."
if command -v systemctl &> /dev/null; then
    read -p "是否创建 systemd 服务？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cat > "$BRIDGE_DIR/astrbot-hermes-bridge.service" <<EOF
[Unit]
Description=AstrBot to Hermes Webhook Bridge
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BRIDGE_DIR
ExecStart=/usr/bin/python3 -m astrbot_hermes_bridge
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        echo -e "${GREEN}✓ systemd 服务文件已创建${NC}"
        echo "  文件：$BRIDGE_DIR/astrbot-hermes-bridge.service"
        echo ""
        echo "  安装命令："
        echo "    sudo cp $BRIDGE_DIR/astrbot-hermes-bridge.service /etc/systemd/system/"
        echo "    sudo systemctl daemon-reload"
        echo "    sudo systemctl enable astrbot-hermes-bridge"
        echo "    sudo systemctl start astrbot-hermes-bridge"
        echo ""
    fi
fi

# 完成
echo "╔═══════════════════════════════════════════════╗"
echo "║              配置完成！                       ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""
echo -e "${YELLOW}下一步操作：${NC}"
echo ""
echo "1. 将 Hermes Webhook 配置添加到 hermes-config/config.yaml："
echo "   cat $BRIDGE_DIR/hermes_webhook_config.yaml >> $HERMES_CONFIG_DIR/config.yaml"
echo ""
echo "2. 启动 Hermes Gateway："
echo "   cd $HERMES_CONFIG_DIR/.."
echo "   ./hermes-start.sh gateway"
echo ""
echo "3. 将插件复制到 AstrBot 插件目录："
echo "   cp $BRIDGE_DIR/hermes_bridge.py $ASTRBOT_DIR/astrbot/plugins/"
echo ""
echo "4. 重启 AstrBot："
echo "   cd $ASTRBOT_DIR"
echo "   uv run main.py"
echo ""
echo "5. 测试连接："
echo "   curl -X POST http://localhost:$HERMES_WEBHOOK_PORT/health"
echo ""
echo -e "${YELLOW}安全提示：${NC}"
echo "  - 请妥善保管密钥：$WEBHOOK_SECRET"
echo "  - 不要将密钥提交到版本控制"
echo "  - 生产环境请使用 HTTPS"
echo ""
