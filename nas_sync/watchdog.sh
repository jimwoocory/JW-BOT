#!/bin/bash
# ============================================================
# NAS 挂载看门狗
# 每 60 秒由 launchd 调用一次
# 检查 nas_kb 是否正常，断了自动重新挂载
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOUNT_SH="$SCRIPT_DIR/mount.sh"
MOUNT_POINT="/Users/dianchi/nas_kb"
NAS_IP="192.168.1.35"
LOG="$SCRIPT_DIR/watchdog.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

# 日志滚动（超过 1000 行只保留后 500 行）
[ "$(wc -l < "$LOG" 2>/dev/null || echo 0)" -gt 1000 ] && \
    tail -500 "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"

# ── 1. NAS 是否可达 ──────────────────────────────────────────
if ! ping -c 1 -W 1000 "$NAS_IP" &>/dev/null; then
    log "SKIP  NAS $NAS_IP 不可达"
    exit 0
fi

# ── 2. 检查挂载状态 ──────────────────────────────────────────
is_mounted() {
    mount | grep -q "on ${MOUNT_POINT} "
}

is_healthy() {
    # ls 超时 3 秒；僵死挂载点会卡住
    timeout 3 ls "$MOUNT_POINT" &>/dev/null
}

if is_mounted; then
    if is_healthy; then
        exit 0          # 正常，安静退出
    else
        log "STALE 挂载点僵死，强制卸载..."
        diskutil unmount force "$MOUNT_POINT" 2>>"$LOG" || \
            umount -f "$MOUNT_POINT" 2>>"$LOG"
    fi
fi

# ── 3. 重新挂载 ──────────────────────────────────────────────
log "MOUNT 尝试挂载 $MOUNT_POINT ..."
if bash "$MOUNT_SH" mount >> "$LOG" 2>&1; then
    log "OK    挂载成功"
else
    log "FAIL  挂载失败，下次重试"
fi
