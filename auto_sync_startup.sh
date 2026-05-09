#!/bin/bash
# ============================================================
# NAS 自动同步启动器
# 每天凌晨2:00自动执行：
#   1. 挂载 NAS
#   2. 同步百度网盘文件
#   3. 记录日志
#   4. 卸载 NAS（可选）
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/auto_sync_$(date +%Y%m%d).log"
ERROR_LOG="$LOG_DIR/auto_sync_errors.log"

# 创建日志目录
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" | tee -a "$ERROR_LOG" >&2
}

cd "$SCRIPT_DIR"

log "=========================================="
log "开始自动同步任务"
log "=========================================="

# 1. 挂载 NAS
log "[1/4] 挂载 NAS..."
if bash nas_sync/mount.sh mount >> "$LOG_FILE" 2>&1; then
    log "✓ NAS 挂载成功"
else
    log_error "✗ NAS 挂载失败"
    exit 1
fi

# 2. 执行同步
log "[2/4] 开始同步..."
if bash nas_sync/sync_baidu_to_nas.sh >> "$LOG_FILE" 2>&1; then
    log "✓ 同步任务完成"
else
    log_error "✗ 同步任务失败"
    # 继续执行，不要因为同步失败就停止
fi

# 3. 验证同步结果
log "[3/4] 验证同步结果..."
NAS_MOUNT="/Users/dianchi/nas_kb"
SYNC_DIR="$NAS_MOUNT/百度网盘同步/柳汽"

if [[ -d "$SYNC_DIR" ]]; then
    local_count=$(find "$SYNC_DIR" -type f | wc -l | tr -d ' ')
    log "✓ NAS 上共有 $local_count 个文件"

    # 显示各文件夹大小
    if [[ -d "$SYNC_DIR/封面模板&尾版" ]]; then
        size1=$(du -sh "$SYNC_DIR/封面模板&尾版" 2>/dev/null | cut -f1 || echo "N/A")
        log "  - 封面模板&尾版: $size1"
    fi
    if [[ -d "$SYNC_DIR/柳汽Q1季度素材成片汇总" ]]; then
        size2=$(du -sh "$SYNC_DIR/柳汽Q1季度素材成片汇总" 2>/dev/null | cut -f1 || echo "N/A")
        log "  - 柳汽Q1季度素材成片汇总: $size2"
    fi
    if [[ -d "$SYNC_DIR/柳汽后市场新媒体运营视频" ]]; then
        size3=$(du -sh "$SYNC_DIR/柳汽后市场新媒体运营视频" 2>/dev/null | cut -f1 || echo "N/A")
        log "  - 柳汽后市场新媒体运营视频: $size3"
    fi
else
    log_error "同步目录不存在: $SYNC_DIR"
fi

# 4. 卸载 NAS（可选，保持关闭以便于其他应用访问）
log "[4/4] 卸载 NAS..."
if bash nas_sync/mount.sh unmount >> "$LOG_FILE" 2>&1; then
    log "✓ NAS 已卸载"
else
    log_error "NAS 卸载失败（可能正在使用中）"
fi

log "=========================================="
log "自动同步任务完成"
log "日志文件: $LOG_FILE"
log "=========================================="

# 保留最近30天的日志
find "$LOG_DIR" -name "auto_sync_*.log" -mtime +30 -delete 2>/dev/null || true
find "$LOG_DIR" -name "sync_*.log" -mtime +30 -delete 2>/dev/null || true

exit 0
