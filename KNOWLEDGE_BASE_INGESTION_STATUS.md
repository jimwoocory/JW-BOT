# 知识库摄入状态报告

## 🔴 当前问题

**Hermes Skill 已创建但无法查询**，原因：所有4个知识库都是空的 (`doc_count: 0`)

### 根本原因：配置冲突

配置文件 `nas_sync/config.yaml` 的 `exclude_dirs` 设置与实际文件位置冲突：

```yaml
exclude_dirs:
  - "#recycle"
  - processed
  - archive
  - .DS_Store
  - 影视部交接文件夹          ← 大量文件在这里！
  - 五菱总备份-具体项目...     ← 大量文件在这里！
  - 五菱老素材备份-...         ← 大量文件在这里！
```

**实际文件分布**：
- ❌ `/nas_kb/中台运营项目/` - 空（无文件）
- ❌ `/nas_kb/品宣运营项目/` - 空（无文件）  
- ❌ `/nas_kb/品牌规范/` - 空（无文件）
- ❌ `/nas_kb/营销素材/` - 空（无文件）
- ✅ `/nas_kb/五菱总备份-具体项目.../**` - 有大量文件
- ✅ `/nas_kb/影视部交接文件夹/**` - 有大量文件
- ✅ `/nas_kb/五菱老素材备份-.../**` - 有大量文件

### 为什么文件在被排除的文件夹中？

根据之前的讨论，用户说"除了视频文件，还有多大？"和"不做复制"。这意味着：
- ✅ **不需要**：手动将这些大文件夹复制到知识库目录
- ❌ **不应该**：从摄入（索引）中排除这些文件

---

## ✅ 解决方案

### 选项 1：移除排除配置（推荐）

编辑 `nas_sync/config.yaml`，移除这三个文件夹：

```yaml
exclude_dirs:
  - "#recycle"
  - processed
  - archive
  - .DS_Store
  # ↓ 移除以下三行
  # - 影视部交接文件夹
  # - 五菱总备份-具体项目务必标注日期
  # - 五菱老素材备份-具体项目务必标注日期
```

**优点**：
- 所有文件自动索引
- 知识库覆盖全面
- 一次性解决

**缺点**：
- 摄入时间较长（数百个文件）

---

### 选项 2：选择性索引

仅在 `kb_mapping` 中配置部分文件夹。但这需要将文件按KB分组，工作量大。

---

## 🚀 建议的执行步骤

### Step 1: 修复配置
```bash
# 编辑配置文件
nano /Users/dianchi/DC-Agent/nas_sync/config.yaml

# 移除那三个 exclude_dirs 条目
```

### Step 2: 运行一次完整扫描
```bash
cd /Users/dianchi/DC-Agent
python nas_sync/watcher.py --once
```

这将开始索引所有文件。根据文件数量，可能需要 5-30 分钟。

### Step 3: 监控进度
```bash
# 在另一个终端查看日志
tail -f nas_sync/watcher.log

# 或检查知识库状态
curl -s http://localhost:6185/api/kb/list \
  -H "Authorization: Bearer <token>" | jq '.data.items[] | {kb_name, doc_count, chunk_count}'
```

### Step 4: 测试 Hermes Skill
一旦有文件被索引，测试查询：
```bash
cd /Users/dianchi/DC-Agent/hermes-agent-temp/skills/productivity/astrbot-knowledge-base
python3 scripts/query_kb.py --query "五菱" --top-k 5
```

---

## 📊 文件索引预期

根据之前的全量扫描：
- 预期 40+ 个可索引文件
- 分布在 4 个知识库中
- 索引到约 200-500 个文本块（chunks）

索引完成后，所有查询都会有结果。

---

## 🔧 Hermes Skill 准备就绪

✅ **已创建**：`/Users/dianchi/DC-Agent/hermes-agent-temp/skills/productivity/astrbot-knowledge-base/`

**文件**：
- `SKILL.md` - Hermes 技能定义（含完整使用说明）
- `scripts/query_kb.py` - Python 查询脚本（已测试认证）

**功能**：
- 查询所有知识库或特定知识库
- 返回相关文档和相似度得分
- 支持 JSON 输出供 Hermes 自动解析

**下一步**：
1. 修复配置（移除 exclude_dirs）
2. 运行 watcher 完成文件索引
3. Hermes 自动加载 Skill，用户可直接查询

---

## 时间表

| 阶段 | 时间 | 状态 |
|------|------|------|
| 创建 Hermes Skill | 已完成 | ✅ |
| 修复 NAS 配置 | **需要** | ⏳ |
| 运行 watcher 索引 | **需要** | ⏳ |
| 验证知识库有内容 | **需要** | ⏳ |
| 测试 Skill 查询 | **需要** | ⏳ |

---

## 推荐的下一个命令

```bash
# 1. 修复配置
sed -i '' '/影视部交接文件夹/d; /五菱总备份/d; /五菱老素材/d' /Users/dianchi/DC-Agent/nas_sync/config.yaml

# 2. 验证修复
grep "exclude_dirs" -A 10 /Users/dianchi/DC-Agent/nas_sync/config.yaml

# 3. 运行摄入
cd /Users/dianchi/DC-Agent && python nas_sync/watcher.py --once &

# 4. 监控日志
tail -f /Users/dianchi/DC-Agent/nas_sync/watcher.log
```
