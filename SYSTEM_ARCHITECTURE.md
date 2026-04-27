# JW-Bot 系统框架架构与数据流分析

## 📋 系统概览

JW-Bot 是一个多系统集成的企业知识处理平台，由以下核心组件组成：

```
┌─────────────────────────────────────────────────────────────┐
│                      JW-Bot 系统架构                         │
└─────────────────────────────────────────────────────────────┘

       ┌─────────────┐              ┌──────────────┐
       │   QQ Bot    │              │  Hermes      │
       │  (AstrBot)  │──────┐   ┌──│  Agent       │
       └─────────────┘      │   │  └──────────────┘
            │               │   │
            │        ┌──────▼───▼──────┐
            │        │  Webhook Bridge  │ (Port 8645)
            │        │  hermes_bridge   │
            │        └──────────────────┘
            │               ▲
            │               │ (Port 8644)
            │               │
       ┌────▼──────────────┐
       │   AstrBot Core    │
       │  (Port 6185)      │
       │                   │
       │  ┌─────────────┐  │
       │  │ Knowledge   │  │
       │  │ Base Mgmt   │  │ ← 4 Independent KBs
       │  └─────────────┘  │
       │                   │
       │  ┌─────────────┐  │
       │  │ Dashboard   │  │
       │  │ (Port 4311) │  │
       │  └─────────────┘  │
       └───────┬──────────┘
               │
        ┌──────▼──────────┐
        │  NAS Storage    │
        │  (SMB Protocol) │
        │  192.168.1.35   │
        │  /knowledge     │
        │                 │
        │  ├─ 中台运营    │
        │  ├─ 品宣运营    │
        │  ├─ 品牌规范    │
        │  └─ 营销素材    │
        └─────────────────┘
```

---

## 1. 核心组件详解

### 1.1 AstrBot 系统
**主文件**: `/Users/dianchi/JW-Bot/main.py`  
**核心入口**: `astrbot.core.initial_loader.InitialLoader`  
**监听端口**: `6185`（REST API）

#### 功能：
- QQ 聊天机器人框架
- 知识库管理和检索
- 多模型支持（OpenAI、Gemini、MiniMax 等）
- 插件系统（Plugin 架构）

#### 关键插件：
1. **openclaw_file_ingest** - QQ 直接文件接收与分类入库
2. **hermes_bridge** - 与 Hermes Agent 的 Webhook 通信桥接
3. **minimax_token_plugin** - MiniMax 模型集成
4. **dreamina_plugin** - 图像生成能力

---

### 1.2 Hermes Agent 系统
**安装位置**: `/Users/dianchi/JW-Bot/hermes-agent-temp`  
**配置目录**: `/Users/dianchi/JW-Bot/hermes-config`  
**启动脚本**: `./hermes-start.sh`  
**版本**: v0.8.0 (Python 3.11.15)

#### 功能：
- 智能代理决策引擎
- 多模型支持（Claude、Nous、OpenRouter 等）
- Skill（技能）系统 - 自动学习和复用解决方案
- MCP（Model Context Protocol）集成
- 多会话管理

#### 特点：
- 长上下文处理能力
- 自动技能学习和优化
- 跨会话记忆和知识积累
- 支持工具链集成

---

### 1.3 NAS 知识库存储
**协议**: SMB (Server Message Block)  
**地址**: `192.168.1.35:5000`  
**共享名**: `knowledge`  
**本地挂载点**: `/Users/dianchi/nas_kb`

#### 目录结构：
```
/Users/dianchi/nas_kb/
├── 中台运营项目/          ← KB: 106d44aa-771b-4f6f-939c-14e274c3c952
│   ├── 系列项目/
│   └── 活动类/
├── 品宣运营项目/          ← KB: 084c0c08-52fe-471e-aab2-fb2f8477f45c
│   ├── 宣传素材/
│   └── 传播策略/
├── 品牌规范/              ← KB: e5d9756e-83ae-4663-be8f-46a70fb1a894
│   ├── VI 系统/
│   └── 品牌标准/
├── 营销素材/              ← KB: 344196dd-25c6-4765-a161-e265f0e66565
│   ├── 视频素材/
│   └── 文案库/
├── inbox/                 ← 新文件监听目录
├── processed/             ← 已处理文件归档
└── archive/               ← 手动归档
```

---

## 2. 数据流与交互流程

### 2.1 QQ → AstrBot 流程
```
QQ 用户消息
    ↓
AstrBot 接收消息 (on_message)
    ↓
提取文本内容 & 元数据 (user_id, group_id 等)
    ↓
AstrBot 处理逻辑
    ├─ 知识库查询
    ├─ 模型推理
    └─ 响应生成
    ↓
QQ 用户收到回复
```

### 2.2 AstrBot → Hermes 流程（Webhook 桥接）
```
AstrBot 消息
    ↓
hermes_bridge 插件捕获
    ↓
构建 Webhook 数据包：
    {
        "user_id": "qq_user_123",
        "session_key": "qq_user_123_abc12345",
        "message": "用户的问题",
        "message_type": "group|private",
        "platform": "qq"
    }
    ↓
计算 HMAC-SHA256 签名
    ↓
POST 到 Hermes Webhook (http://localhost:8644/webhooks/astrbot_qq)
    Headers:
    - X-Hub-Signature-256: sha256=...
    - X-User-ID: qq_user_123
    - X-Session-Key: qq_user_123_abc12345
    ↓
Hermes 处理并生成响应
    ↓
Hermes 回调 Webhook (http://localhost:8645/hermes_response)
    ↓
hermes_bridge 接收响应
    ↓
根据 session_key 反查 user_id
    ↓
发送回 QQ 用户
```

### 2.3 NAS 文件 → AstrBot 知识库 流程
```
NAS 文件变化 (inbox 目录)
    ↓
nas_sync/watcher.py 监听 (watchdog)
    ↓
检查文件稳定性 (settle_seconds: 3)
    ↓
文件路径解析
    ├─ 匹配 kb_mapping 前缀
    └─ 确定目标知识库 ID
    ↓
调用 AstrBot KB API
    POST /api/knowledge_base/{kb_id}/upload_file
    ↓
文件分块处理
    chunk_size: 512
    chunk_overlap: 50
    ↓
向量化 (aihubmix text-embedding-3-small)
    embedding_dimensions: 1536
    ↓
存储到 SQLite KB 数据库
    ↓
标记为 processed，文件移到 processed 目录
```

### 2.4 知识库查询流程
```
Hermes/AstrBot 查询请求
    ↓
知识库检索模块 (kb_helper.py)
    ↓
向量相似度搜索 (Embedding + Dense Retrieval)
    ├─ 稀疏检索 (Sparse Retriever)
    └─ 排序融合 (Rank Fusion)
    ↓
返回相关文档片段 (Top-K chunks)
    ↓
注入 LLM Prompt
    ↓
LLM 生成最终响应
```

---

## 3. AstrBot 知识库架构

### 3.1 多知识库映射配置
**配置文件**: `nas_sync/config.yaml`

```yaml
astrbot:
  kb_mapping:
    "中台运营项目": "106d44aa-771b-4f6f-939c-14e274c3c952"
    "品宣运营项目": "084c0c08-52fe-471e-aab2-fb2f8477f45c"
    "品牌规范": "e5d9756e-83ae-4663-be8f-46a70fb1a894"
    "营销素材": "344196dd-25c6-4765-a161-e265f0e66565"
  embedding_provider_id: "aihubmix_embedding"
```

### 3.2 Embedding 提供商配置
**配置文件**: `data/config/cmd_config.json`

```json
{
  "provider": [
    {
      "type": "openai_embedding",
      "id": "aihubmix_embedding",
      "enable": true,
      "embedding_api_key": "sk-...",
      "embedding_api_base": "https://aihubmix.com/v1",
      "embedding_model": "text-embedding-3-small",
      "embedding_dimensions": 1536
    }
  ]
}
```

### 3.3 AstrBot KB API 接口

#### 上传文件
```
POST /api/knowledge_base/{kb_id}/upload_file

请求：
{
  "file": <binary file data>,
  "file_name": "document.pdf"
}

响应：
{
  "status": 200 | "ok",
  "data": {
    "file_id": "...",
    "file_name": "document.pdf",
    "file_type": "pdf",
    "size": 1024000
  }
}
```

#### 获取知识库
```
GET /api/knowledge_base?name=nas_knowledge

响应：
{
  "status": 200,
  "data": {
    "id": "106d44aa-...",
    "name": "中台运营项目",
    "description": "...",
    "doc_count": 42,
    "file_count": 15
  }
}
```

#### 查询知识库
```
POST /api/knowledge_base/{kb_id}/query

请求：
{
  "query": "用户的问题",
  "top_k": 5
}

响应：
{
  "status": 200,
  "data": [
    {
      "doc_id": "...",
      "file_name": "...",
      "chunk": "相关文本片段",
      "score": 0.85
    }
  ]
}
```

---

## 4. Hermes Agent 与 AstrBot 的集成点

### 4.1 Webhook Bridge 工作原理

**位置**: `/Users/dianchi/JW-Bot/astrbot/plugins/hermes_bridge/__init__.py`

#### 核心流程：
1. **接收 QQ 消息** → AstrBot `on_message` 事件
2. **转发到 Hermes** → Webhook POST (Port 8644)
3. **维护会话映射** → `session_mapping` (QQ User ↔ Hermes Session)
4. **接收 Hermes 响应** → Webhook 服务器 (Port 8645)
5. **发送回 QQ** → 通过 AstrBot 平台接口

#### 会话映射持久化：
```python
session_mapping_file = "/Users/dianchi/JW-Bot/data/config/hermes_bridge_sessions.json"
# 格式：{"qq_user_123": "qq_user_123_abc12345"}
```

### 4.2 当前集成状态

✅ **已实现**：
- Webhook 双向通信框架
- 会话映射和上下文维护
- HMAC-SHA256 签名验证
- 异步消息处理

⚠️ **待完成**：
- `_send_to_qq()` 方法完整实现（当前为 TODO）
- Hermes 响应错误处理和重试机制
- 消息队列缓冲管理

---

## 5. Hermes Knowledge Base 集成方案

### 5.1 当前状态分析

**Hermes 当前没有内置知识库概念**，但可以通过以下方式集成 AstrBot 的知识库：

### 5.2 推荐的集成方案

#### 方案 A：通过 API 调用 AstrBot 知识库（推荐）

```python
# Hermes Skill 实现示例
async def query_knowledge_base(query: str, kb_id: str = None):
    """
    查询 AstrBot 知识库的 Hermes Skill
    """
    kb_api = AstrBotKBClient(
        api_base="http://localhost:6185/api",
        username="Dianchi.boss",
        password="D!anch!1983"
    )
    
    # 如果未指定知识库，自动选择
    if kb_id is None:
        kb_id = kb_api.ensure_kb("default_kb")
    
    # 查询知识库
    results = kb_api.query_kb(kb_id, query, top_k=5)
    
    return {
        "status": "success",
        "results": results,
        "kb_id": kb_id
    }
```

**优点**：
- 共享同一套知识库，数据一致性强
- 无需重复索引和存储
- Hermes 可以动态选择查询的知识库
- 支持多知识库协同查询

**缺点**：
- 依赖 AstrBot 可用性
- 网络延迟（本机可忽略）

---

#### 方案 B：Hermes 独立知识库 + 定期同步

```
NAS 文件系统
    ↓
Watcher A: AstrBot 索引 → AstrBot KBs
    ↓
Watcher B: Hermes 索引 → Hermes KB
```

**优点**：
- Hermes 完全独立，不依赖 AstrBot
- 可以针对 Hermes 优化索引

**缺点**：
- 数据重复存储
- 维护两套索引，容易不同步
- 额外的磁盘和处理开销

---

#### 方案 C：混合模式

```
实时查询 (Hermes → AstrBot API)
    + 本地缓存 (热门查询结果缓存在 Hermes)
    + 离线模式 (Hermes 可离线工作)
```

---

### 5.3 建议实现步骤（选方案 A）

#### Step 1：创建 Hermes Skill - 知识库查询

文件：`/Users/dianchi/JW-Bot/hermes-workspace/skills/query_kb.py`

```python
"""
Skill: 查询 JW-Bot 知识库
用途：在 Hermes Agent 中查询 AstrBot 的多个知识库
"""

import asyncio
from typing import Optional, List, Dict
import aiohttp
import json
import hashlib
import base64

class KBQuerySkill:
    def __init__(self):
        self.astrbot_api = "http://localhost:6185/api"
        self.username = "Dianchi.boss"
        self.password = "D!anch!1983"
        self.token = None
        self.token_expire = 0
    
    async def _login(self):
        """获取 JWT token"""
        async with aiohttp.ClientSession() as session:
            password_hash = hashlib.md5(
                self.password.encode()
            ).hexdigest()
            
            async with session.post(
                f"{self.astrbot_api}/v1/auth/login",
                json={
                    "username": self.username,
                    "password": password_hash
                }
            ) as resp:
                data = await resp.json()
                if data.get("status") in (200, "ok"):
                    self.token = data["data"]["token"]
                    return True
        return False
    
    async def query(
        self,
        query: str,
        kb_name: Optional[str] = None,
        top_k: int = 5
    ) -> Dict:
        """
        查询知识库
        
        Args:
            query: 查询内容
            kb_name: 知识库名称（可选，为空则查询所有）
            top_k: 返回结果数量
        
        Returns:
            {
                "status": "success|error",
                "results": [
                    {"file": "...", "content": "...", "score": 0.85}
                ]
            }
        """
        # 确保已登录
        if not self.token:
            if not await self._login():
                return {"status": "error", "message": "认证失败"}
        
        results = []
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            # 如果指定了知识库名称，直接查询
            if kb_name:
                async with session.get(
                    f"{self.astrbot_api}/v1/knowledge_base?name={kb_name}",
                    headers=headers
                ) as resp:
                    data = await resp.json()
                    if data.get("status") in (200, "ok"):
                        kb = data["data"]
                        results.extend(
                            await self._query_kb(
                                session, headers, kb["id"], query, top_k
                            )
                        )
            else:
                # 查询所有知识库
                async with session.get(
                    f"{self.astrbot_api}/v1/knowledge_base",
                    headers=headers
                ) as resp:
                    data = await resp.json()
                    if data.get("status") in (200, "ok"):
                        for kb in data["data"]:
                            kb_results = await self._query_kb(
                                session, headers, kb["id"],
                                query, top_k // len(data["data"]) + 1
                            )
                            results.extend(kb_results)
        
        # 按相似度排序，返回 top_k
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return {
            "status": "success",
            "results": results[:top_k]
        }
    
    async def _query_kb(
        self, session, headers, kb_id, query, top_k
    ):
        """查询单个知识库"""
        async with session.post(
            f"{self.astrbot_api}/v1/knowledge_base/{kb_id}/query",
            headers=headers,
            json={"query": query, "top_k": top_k}
        ) as resp:
            data = await resp.json()
            if data.get("status") in (200, "ok"):
                return data.get("data", [])
        return []


# Hermes 集成
async def hermes_query_knowledge_base(query: str, kb_filter: Optional[str] = None):
    """Hermes 可调用的函数"""
    skill = KBQuerySkill()
    return await skill.query(query, kb_name=kb_filter)
```

#### Step 2：创建 Hermes MCP Server（可选增强）

支持更复杂的知识库操作：
```
- 查询
- 上传文件
- 批量操作
- 元数据管理
```

#### Step 3：测试集成

```bash
# 启动 AstrBot
uv run main.py

# 启动 Hermes
./hermes-start.sh

# 在 Hermes 中测试
/kb_query 查询内容
```

---

## 6. 关键文件清单

### AstrBot 核心
- `main.py` - 启动入口
- `astrbot/core/initial_loader.py` - 初始化流程
- `astrbot/core/knowledge_base/kb_mgr.py` - 知识库管理
- `astrbot/core/tools/knowledge_base_tools.py` - KB 工具接口

### Hermes 桥接
- `astrbot/plugins/hermes_bridge/__init__.py` - Webhook 桥接实现
- `hermes-config/config.yaml` - Hermes 配置

### NAS 同步
- `nas_sync/watcher.py` - 文件监听和索引
- `nas_sync/config.yaml` - NAS 配置
- `nas_sync/mount.sh` - NAS 挂载脚本

### 配置文件
- `data/config/cmd_config.json` - AstrBot 主配置（包含 Embedding）
- `data/config/abconf_jwclaw_config.json` - 账户配置

---

## 7. 系统交互时序图

```
时间轴：
────────────────────────────────────────────────────────

QQ 用户消息
    │
    └──→ AstrBot (localhost:6185)
         │
         ├─→ 查询 NAS Knowledge Base
         │   └─→ aihubmix Embedding (向量化)
         │
         └─→ hermes_bridge 插件
             │
             └──→ POST Hermes Webhook (localhost:8644)
                  │
                  └──→ Hermes Agent
                       │
                       ├─→ LLM 处理 (Claude/Qwen/etc)
                       ├─→ Skill 调用 (可再查询 AstrBot KB)
                       │
                       └──→ POST 回复 (localhost:8645)
                            │
                            └──→ hermes_bridge 接收
                                 │
                                 └──→ QQ 用户收到回复

────────────────────────────────────────────────────────
```

---

## 8. 关键考虑点

### 8.1 并发与性能
- **AstrBot 知识库查询** 支持并发，使用连接池
- **Webhook 双向调用** 使用异步 aiohttp，不阻塞主线程
- **Embedding 调用** 缓存相同的向量化请求

### 8.2 错误处理
- Webhook 调用失败时的重试机制（当前缺失）
- 知识库不可用时的 graceful fallback
- 会话超时和清理

### 8.3 安全性
- JWT token 认证（已实现）
- HMAC-SHA256 Webhook 签名（已实现）
- 凭证存储在 `.gitignore` 保护文件中

### 8.4 可扩展性
- 支持添加新的知识库（只需在 `kb_mapping` 中注册）
- 支持多个 Embedding 提供商切换
- Hermes Skill 可动态加载和更新

---

## 9. 下一步建议

### 优先级高：
1. ✅ NAS 文件同步到 4 个独立知识库（已完成）
2. 🔄 **为 Hermes 创建知识库查询 Skill** ← 下一个任务
3. 🔄 增强 Webhook 错误处理和重试机制

### 优先级中：
4. 创建 MCP Server 支持更复杂的 KB 操作
5. 实现知识库权限管理
6. 添加知识库版本控制

### 优先级低：
7. 优化向量化性能（缓存、批处理）
8. 实现知识库自动更新检查
9. 创建 Web UI 管理界面

---

## 10. 常用命令参考

### AstrBot
```bash
# 启动
uv run main.py

# 启动仪表板
cd dashboard && pnpm dev

# 查看知识库
curl -H "Authorization: Bearer $TOKEN" http://localhost:6185/api/v1/knowledge_base
```

### Hermes
```bash
# 启动
./hermes-start.sh

# 选择模型
./hermes-start.sh model

# 查看技能
./hermes-start.sh skills list

# 查看日志
./hermes-start.sh logs
```

### NAS 同步
```bash
# 挂载 NAS
cd nas_sync && ./mount.sh mount

# 运行一次扫描
python watcher.py --once

# 启动监听
python watcher.py
```

---

**文档更新时间**: 2026-04-21  
**系统版本**: AstrBot (latest) + Hermes v0.8.0  
**当前状态**: 多知识库同步已就绪，待 Hermes 集成
