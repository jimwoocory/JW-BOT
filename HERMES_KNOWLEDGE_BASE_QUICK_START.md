# Hermes 知识库查询 - 快速开始指南

## 🎯 目标实现

通过方案 A，Hermes Agent 现在可以查询 AstrBot 的 4 个知识库：
- 🏢 中台运营项目
- 📢 品宣运营项目  
- 📋 品牌规范
- 🎨 营销素材

---

## 📦 已交付的组件

### 1. Hermes Skill
**路径**: `/Users/dianchi/DC-Agent/hermes-agent-temp/skills/productivity/astrbot-knowledge-base/`

**包含**:
- `SKILL.md` - 完整的技能文档和使用指南
- `scripts/query_kb.py` - Python 查询脚本（已测试）

### 2. 架构文档
- `SYSTEM_ARCHITECTURE.md` - 系统完整架构说明
- `KNOWLEDGE_BASE_INGESTION_STATUS.md` - 当前状态和修复过程
- 本文档 - 快速开始

---

## 🚀 当前进度

| 组件 | 状态 | 说明 |
|------|------|------|
| Hermes Skill 创建 | ✅ 完成 | 已创建并测试 |
| API 认证 | ✅ 完成 | JWT token 工作正常 |
| 配置修复 | ✅ 完成 | 已移除 exclude_dirs |
| **文件索引** | ⏳ **进行中** | watcher 正在摄入文件... |
| 知识库验证 | ⏳ **待开始** | 文件索引完成后验证 |
| 功能测试 | ⏳ **待开始** | 验证查询功能 |

---

## 📝 正在进行的操作

**Watcher 正在运行**：
```bash
python3.11 nas_sync/watcher.py --once
```

**预期行为**：
1. 扫描 `/Users/dianchi/nas_kb/` 所有可索引文件
2. 识别文件所属的知识库（基于 kb_mapping）
3. 上传文件到 AstrBot
4. 分块并向量化（使用 aihubmix embedding）
5. 存储到知识库

**预期结果**：40+ 个文件 → ~200-500 个文本块

---

## ✅ 测试步骤（完成后执行）

### 步骤 1: 验证知识库有内容

```bash
python3.11 -c "
import asyncio, hashlib, aiohttp, json

async def check():
    async with aiohttp.ClientSession() as session:
        resp = await session.post('http://localhost:6185/api/auth/login',
            json={'username':'Dianchi.boss', 'password': hashlib.md5(b'D!anch!1983').hexdigest()})
        token = (await resp.json())['data']['token']
        
        headers = {'Authorization': f'Bearer {token}'}
        resp = await session.get('http://localhost:6185/api/kb/list', headers=headers)
        for kb in (await resp.json())['data']['items']:
            print(f'{kb[\"kb_name\"]}: {kb[\"doc_count\"]} 文档')

asyncio.run(check())
"
```

**期望输出**：
```
中台运营: 10+ 文档
品宣运营: 5+ 文档
品牌规范: 2+ 文档
营销素材: 15+ 文档
```

### 步骤 2: 测试 Skill 查询

```bash
cd /Users/dianchi/DC-Agent/hermes-agent-temp/skills/productivity/astrbot-knowledge-base

# 查询所有知识库
python3 scripts/query_kb.py --query "五菱" --top-k 5

# 或以 JSON 格式查询（供 Hermes 解析）
python3 scripts/query_kb.py --query "品牌" --kb-name "品牌规范" --json-output
```

**期望输出**：
```
📚 知识库查询结果
============================================================
知识库: 全部知识库
查询: 五菱
结果: 5 条

1. 📄 五菱品牌管理.docx
   相似度: 95%
   内容: 五菱品牌的核心价值...
```

### 步骤 3: 在 Hermes 中测试

```bash
# 启动 Hermes
cd /Users/dianchi/DC-Agent
./hermes-start.sh

# 在 Hermes 中询问关于知识库内容的问题
# 示例问题：
# - "五菱汽车的品牌规范是什么？"
# - "你有营销素材库吗？"
# - "品牌指南中关于 Logo 的规范是什么？"

# Hermes 会自动：
# 1. 检测到知识库查询的需要
# 2. 加载 astrbot-knowledge-base skill
# 3. 执行查询脚本
# 4. 整合结果到回答中
```

---

## 🔍 故障排查

### 问题 1: "找不到知识库"

**症状**: Skill 执行时报错 `找不到任何知识库`

**检查**:
```bash
# 验证 AstrBot 是否运行
curl -s http://localhost:6185/api/health

# 验证知识库是否存在
curl -s -H "Authorization: Bearer <token>" http://localhost:6185/api/kb/list
```

### 问题 2: 查询返回 0 结果

**症状**: Skill 执行成功但无结果

**原因**: 知识库仍为空，watcher 仍在索引

**解决**:
```bash
# 检查 watcher 进度
ps aux | grep watcher | grep -v grep

# 查看日志
tail -f /tmp/watcher_ingestion.log  # 当前运行
tail -f nas_sync/watcher.log        # 历史日志
```

### 问题 3: 认证失败

**症状**: `认证失败：...`

**解决**:
```bash
# 验证 AstrBot 凭证
curl -X POST http://localhost:6185/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"Dianchi.boss","password":"5f3319249d1067792c0cc8b0a4a415e0"}'

# 应该返回：{"status":"ok","data":{"token":"..."}}
```

---

## 📚 相关文件

| 文件 | 用途 |
|------|------|
| `SYSTEM_ARCHITECTURE.md` | 系统整体架构 |
| `KNOWLEDGE_BASE_INGESTION_STATUS.md` | 配置问题和修复 |
| `nas_sync/config.yaml` | NAS 和摄入配置 |
| `hermes-agent-temp/skills/productivity/astrbot-knowledge-base/SKILL.md` | Skill 文档 |

---

## 🎓 使用示例

### 示例 1: 查询品牌规范

**用户在 Hermes 中问**：
```
我们公司的品牌 Logo 使用规范是什么？
```

**Hermes 会**：
1. 识别出这是知识库查询
2. 调用 astrbot-knowledge-base Skill
3. 执行: `query_kb.py --query "品牌 Logo 规范" --kb-name "品牌规范"`
4. 获取相关文档
5. 综合回答用户

### 示例 2: 查找营销素材

**用户在 Hermes 中问**：
```
五菱新车上市有什么营销视频脚本吗？
```

**Hermes 会**：
1. 调用 Skill 查询营销素材
2. 执行: `query_kb.py --query "五菱 视频脚本" --kb-name "营销素材"`
3. 返回相关脚本文件
4. 摘要呈现给用户

---

## 🔄 维护和更新

### 添加新文件到知识库

1. **将文件放入 NAS inbox** 或直接到相应项目文件夹
2. **运行 watcher** 自动索引：
   ```bash
   python3.11 nas_sync/watcher.py --once
   ```
3. **Hermes 自动使用新文件**（下次查询时）

### 修改知识库映射

编辑 `nas_sync/config.yaml` 的 `kb_mapping`：
```yaml
astrbot:
  kb_mapping:
    "新文件夹": "新知识库ID"  # 添加新映射
    "修改的名称": "知识库ID"   # 更新映射
```

---

## 📞 支持

**关键命令速查**：

```bash
# 启动 Hermes
./hermes-start.sh

# 测试 Skill
cd hermes-agent-temp/skills/productivity/astrbot-knowledge-base
python3 scripts/query_kb.py --query "test"

# 检查 AstrBot
curl http://localhost:6185/api/health

# 查看知识库状态
python3 nas_sync/show_kb_status.py  # 如果存在
```

---

**下一步**：等待 watcher 完成文件索引，然后按上面的测试步骤验证功能！

