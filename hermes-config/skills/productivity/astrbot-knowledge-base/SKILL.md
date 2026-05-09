---
name: astrbot-knowledge-base
description: Query AstrBot's knowledge bases (中台运营项目、品宣运营项目、品牌规范、营销素材). Fast retrieval of company knowledge by semantic search.
version: 1.0.0
author: JW-Bot Team
license: MIT
metadata:
  hermes:
    tags: [Knowledge, AstrBot, Search, Company, Documentation, 知识库]
    related_skills: []
    requires_tools: [terminal]
prerequisites:
  python: "3.8+"
  packages: [aiohttp]
---

# AstrBot Knowledge Base

Query JW-Bot's corporate knowledge bases for company guidelines, marketing materials, operational strategies, and brand standards.

**Knowledge Bases Available:**
- 🏢 **中台运营项目** - Central platform operations projects
- 📢 **品宣运营项目** - Brand promotion and marketing operations
- 📋 **品牌规范** - Brand guidelines and standards
- 📝 **营销素材** - Marketing materials and content library

## When to Use

Query this skill when the user asks about:
- Company brand guidelines, VI systems, or design standards
- Marketing campaigns, strategies, or past copywriting
- Project plans, proposals, or strategic documentation
- Marketing materials, video scripts, or content templates
- Company operational standards or procedures
- Competitor analysis or case studies
- Any company internal documentation or knowledge

## When NOT to Use

- For general web searches → use `web_search` skill
- For real-time data or current events → use `web_extract`
- For code snippets or technical documentation → use `terminal` with `curl` directly

## Quick Reference

| Action | Command |
|--------|---------|
| Search all KBs | `./scripts/query_kb.py --query "搜索内容"` |
| Search specific KB | `./scripts/query_kb.py --query "内容" --kb-name "品牌规范"` |
| More results | `./scripts/query_kb.py --query "内容" --top-k 10` |
| JSON output | `./scripts/query_kb.py --query "内容" --json-output` |

## Procedure

### Step 1: Understand the Query

Parse the user's question to extract:
- What information they're looking for
- Which knowledge base category (if specified)
- How many results they want (default: 5)

### Step 2: Execute the Query

Use the Python script to search:

```bash
cd /Users/dianchi/DC-Agent/hermes-agent-temp/skills/productivity/astrbot-knowledge-base

# Option A: Simple text output
python3 scripts/query_kb.py --query "用户的问题"

# Option B: JSON output (for parsing by Hermes)
python3 scripts/query_kb.py --query "用户的问题" --json-output
```

### Step 3: Parse Results

When using `--json-output`, you get:
```json
{
  "status": "success",
  "query": "搜索内容",
  "kb_name": "知识库名称",
  "result_count": 5,
  "results": [
    {
      "file_name": "document.pdf",
      "chunk": "相关内容摘录",
      "score": 0.95
    }
  ]
}
```

### Step 4: Present Results to User

Organize findings:
1. **Source**: Which knowledge base(s) matched
2. **Relevance**: Show matching document names and scores
3. **Content**: Quote relevant sections from results
4. **Context**: Add interpretation or next steps

## Examples

### Example 1: Brand Guidelines Question
```
User: "我们公司的品牌 Logo 有什么使用规范吗？"

Command:
python3 scripts/query_kb.py --query "logo 品牌规范" --kb-name "品牌规范"

Output:
找到 3 条结果：
1. VI系统手册.pdf - 相似度 98%
2. 品牌标准指南.docx - 相似度 92%
3. Design_Guidelines.pdf - 相似度 87%

Present: Quote relevant sections about logo usage, size, spacing, etc.
```

### Example 2: Marketing Material Search
```
User: "你有五菱汽车的营销视频脚本吗？"

Command:
python3 scripts/query_kb.py --query "五菱视频脚本" --kb-name "营销素材"

Output:
3 results found, ranked by relevance
```

### Example 3: Multi-KB Search
```
User: "我们的品牌价值主张是什么？"

Command:
python3 scripts/query_kb.py --query "品牌价值主张" --top-k 8

Output:
搜索所有知识库，返回前 8 条结果
```

## Pitfalls

### Pitfall 1: Network/API Issues
**Problem**: `错误: API 连接超时`
**Solution**:
1. Check if AstrBot is running: `lsof -i :6185`
2. Restart AstrBot if needed: `uv run main.py`
3. Verify API URL is correct (default: `http://localhost:6185/api`)

### Pitfall 2: Authentication Failed
**Problem**: `认证失败: ...`
**Solution**:
1. Verify username/password are correct in script
2. Check AstrBot Dashboard is accessible
3. Reset password if needed in AstrBot settings

### Pitfall 3: No Results Found
**Problem**: Empty result set
**Solution**:
1. Try broader search terms
2. Remove filters (don't specify `--kb-name`)
3. Check if knowledge bases are properly indexed (may take 30s-1min after upload)
4. Verify files were uploaded: Check AstrBot Dashboard

### Pitfall 4: Results Not Relevant
**Problem**: Results don't match user's intent
**Solution**:
1. Rephrase query with different keywords
2. Search in specific KB if you know the category
3. Suggest user refine their question

## Verification

Verify successful knowledge base query:

```bash
# 1. Check AstrBot is running
curl http://localhost:6185/api/v1/health

# 2. Verify script works
python3 scripts/query_kb.py --query "test" --json-output

# 3. Check result format
# Should return: { "status": "success", "results": [...] }

# 4. Spot-check a result
# - Has "file_name" (source document)
# - Has "chunk" (text excerpt)
# - Has "score" between 0-1 (relevance)
```

## Configuration

### Edit credentials (if needed):
```bash
# The script defaults to:
# - User: Dianchi.boss
# - Password: D!anch!1983
# - API: http://localhost:6185/api

# To use different credentials, modify the script or pass arguments:
python3 scripts/query_kb.py \
  --query "..." \
  --api-base "http://other-host:6185/api" \
  --username "other_user" \
  --password "other_pass"
```

## Integration with Hermes Agent

When Hermes loads this skill, it can:

1. **Auto-query on knowledge questions**
   ```
   User: "公司品牌规范是什么？"
   Hermes: Detects → Loads this skill → Executes query → Synthesizes results
   ```

2. **Chain with other skills**
   ```
   KB Results → Web Extract (for additional context) → Summarize
   ```

3. **Multi-step research**
   ```
   Initial query → Refine search → Combine results from multiple KBs → Present findings
   ```

## Related Resources

- AstrBot Dashboard: `http://localhost:4311`
- NAS Knowledge Files: `/Users/dianchi/nas_kb/`
- Watcher Status: `cd nas_sync && tail -f watcher.log`
- System Architecture: See `SYSTEM_ARCHITECTURE.md`
