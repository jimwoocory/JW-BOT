---
name: nas-knowledge
description: Access and search the company NAS knowledge base mounted at /Users/dianchi/nas_kb. Use for finding internal documents, brand assets, marketing materials, and company knowledge.
version: 1.0.0
author: JW-Bot
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [NAS, knowledge-base, documents, company, internal]
    related_skills: []
prerequisites:
  commands: []
---

# 公司 NAS 知识库

公司内部知识库挂载在本机 `/Users/dianchi/nas_kb`，包含所有品牌文档、营销素材、行业资料。

## 目录结构

```
/Users/dianchi/nas_kb/
├── inbox/          ← 待摄入文件（放这里会被自动索引到 AstrBot）
├── processed/      ← 已完成向量化索引的文件归档
└── archive/        ← 手动归档文件，不自动处理
```

## 何时使用此技能

- 用户询问公司内部文档、规范、品牌资料
- 需要在 NAS 上查找某类文件
- 需要将新文件提交到知识库供 AstrBot 索引
- 用户要求列出知识库中已有的文档

## 何时不用

- 需要语义检索（"跟XX相关的内容"）→ 直接使用 AstrBot 知识库工具（AstrBot 已对 NAS 文件做了向量化）
- NAS 未挂载时不要尝试访问文件路径

## 快速操作

### 检查 NAS 是否已挂载

```bash
mount | grep nas_kb
# 或
ls /Users/dianchi/nas_kb 2>/dev/null && echo "已挂载" || echo "未挂载"
```

### 挂载 / 卸载

> NAS 地址：192.168.1.35（群晖 DSM 管理界面 :5000，SMB 共享 :445）

```bash
# 挂载
/Users/dianchi/DC-Agent/nas_sync/mount.sh mount

# 卸载
/Users/dianchi/DC-Agent/nas_sync/mount.sh unmount

# 查看状态
/Users/dianchi/DC-Agent/nas_sync/mount.sh status
```

### 浏览文件

```bash
# 列出所有文件（按修改时间排序）
ls -lt /Users/dianchi/nas_kb/

# 搜索关键词
grep -rl "五菱" /Users/dianchi/nas_kb/ --include="*.md" --include="*.txt"

# 查找特定类型文件
find /Users/dianchi/nas_kb/ -name "*.pdf" | head -20
```

### 阅读文件

```bash
# Markdown / txt
cat /Users/dianchi/nas_kb/archive/品牌规范.md

# PDF（使用 pdftotext）
pdftotext /Users/dianchi/nas_kb/archive/document.pdf -
```

### 将新文件提交到 AstrBot 知识库索引

将文件放入 `inbox/`，watcher 会自动摄入：

```bash
cp ~/Downloads/新文档.pdf /Users/dianchi/nas_kb/inbox/

# 或者立即触发一次摄入（而不等待 watchdog）
cd /Users/dianchi/DC-Agent
python nas_sync/watcher.py --once
```

### 查看摄入状态

```bash
# 查看已摄入文件记录
cat /Users/dianchi/DC-Agent/nas_sync/state.json | python3 -m json.tool

# 查看摄入日志
tail -50 /Users/dianchi/DC-Agent/nas_sync/watcher.log
```

### 启动/重启 watcher 后台进程

```bash
# 前台运行（调试用）
cd /Users/dianchi/DC-Agent
python nas_sync/watcher.py

# 后台运行
nohup python nas_sync/watcher.py > nas_sync/watcher.log 2>&1 &
echo $! > nas_sync/watcher.pid

# 停止
kill $(cat nas_sync/watcher.pid) && rm nas_sync/watcher.pid
```

## 注意事项

- NAS 未挂载时，`/Users/dianchi/nas_kb` 目录不存在，不要尝试读写
- 大文件（>50MB）摄入可能需要数分钟，通过 `watcher.log` 跟踪进度
- 已摄入的文件会移到 `processed/`，`inbox/` 里看不到说明已处理
- 若需重新摄入某文件，删除 `state.json` 中对应条目后重新放入 `inbox/`
