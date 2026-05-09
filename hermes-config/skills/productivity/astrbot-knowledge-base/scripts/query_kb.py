#!/usr/bin/env python3
"""
AstrBot 知识库查询工具 - Hermes Skill 脚本

功能：
1. 认证到 AstrBot Dashboard API
2. 查询知识库列表
3. 在指定知识库中搜索内容
4. 输出结构化结果供 Hermes 使用

用法：
    python3 query_kb.py --query "搜索内容" [--kb-name "知识库名称"] [--top-k 5]
"""

import argparse
import json
import sys
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp not installed. Run: pip install aiohttp", file=sys.stderr)
    sys.exit(1)


class AstrBotKBClient:
    """AstrBot 知识库 API 客户端"""

    def __init__(
        self,
        api_base: str = "http://localhost:6185/api",
        username: str = "Dianchi.boss",
        password: str = "D!anch!1983",
    ):
        self.api_base = api_base.rstrip("/")
        self.username = username
        self.password = password
        self.token: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        await self._login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _login(self) -> bool:
        """获取 JWT token"""
        try:
            # MD5 密码哈希
            password_hash = hashlib.md5(self.password.encode()).hexdigest()

            async with self.session.post(
                f"{self.api_base}/auth/login",
                json={
                    "username": self.username,
                    "password": password_hash,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

                # 检查状态码（AstrBot 可能返回 200 或 "ok"）
                if data.get("status") in (200, "ok"):
                    self.token = data.get("data", {}).get("token")
                    if self.token:
                        return True

                print(
                    f"认证失败: {data.get('message', '未知错误')}",
                    file=sys.stderr,
                )
                return False

        except asyncio.TimeoutError:
            print("错误: API 连接超时", file=sys.stderr)
            return False
        except Exception as e:
            print(f"错误: 认证异常 - {e}", file=sys.stderr)
            return False

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头（包含认证 token）"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_all_knowledge_bases(self) -> List[Dict[str, Any]]:
        """获取所有知识库列表"""
        try:
            async with self.session.get(
                f"{self.api_base}/kb/list",
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

                if data.get("status") in (200, "ok"):
                    kbs = data.get("data", {}).get("items", [])
                    return kbs

                return []

        except Exception as e:
            print(f"错误: 获取知识库列表失败 - {e}", file=sys.stderr)
            return []

    async def get_knowledge_base_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """按名称获取知识库"""
        try:
            kbs = await self.get_all_knowledge_bases()
            for kb in kbs:
                # 匹配 kb_name 字段
                if kb.get("kb_name") == name or kb.get("name") == name:
                    return kb
            return None

        except Exception as e:
            print(f"错误: 查询知识库失败 - {e}", file=sys.stderr)
            return None

    async def query_knowledge_bases(
        self,
        kb_names: List[str],
        query: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """在知识库中查询"""
        try:
            async with self.session.post(
                f"{self.api_base}/kb/retrieve",
                headers=self._get_headers(),
                json={
                    "query": query,
                    "kb_names": kb_names,
                    "top_k": top_k,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()

                if data.get("status") in (200, "ok"):
                    return data.get("data", {})
                else:
                    print(
                        f"错误: 查询失败 - {data.get('message', '未知错误')}",
                        file=sys.stderr,
                    )
                    return {}

        except asyncio.TimeoutError:
            print(f"错误: 知识库查询超时", file=sys.stderr)
            return {}
        except Exception as e:
            print(f"错误: 知识库查询失败 - {e}", file=sys.stderr)
            return {}


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="查询 AstrBot 知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 查询所有知识库
  python3 query_kb.py --query "如何创建品牌规范"

  # 查询特定知识库
  python3 query_kb.py --query "营销素材" --kb-name "营销素材"

  # 返回更多结果
  python3 query_kb.py --query "五菱" --top-k 10
        """,
    )

    parser.add_argument(
        "--query",
        required=True,
        help="搜索查询内容",
    )
    parser.add_argument(
        "--kb-name",
        help="知识库名称（可选，不指定则查询所有知识库）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="返回结果数量（默认：5）",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:6185/api",
        help="AstrBot API 地址（默认：http://localhost:6185/api）",
    )
    parser.add_argument(
        "--username",
        default="Dianchi.boss",
        help="AstrBot 用户名（默认：Dianchi.boss）",
    )
    parser.add_argument(
        "--password",
        default="D!anch!1983",
        help="AstrBot 密码（默认：D!anch!1983）",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="输出 JSON 格式（供 Hermes 解析）",
    )

    args = parser.parse_args()

    # 初始化客户端并执行查询
    async with AstrBotKBClient(
        api_base=args.api_base,
        username=args.username,
        password=args.password,
    ) as client:
        if not client.token:
            sys.exit(1)

        # 获取所有知识库列表
        all_kbs = await client.get_all_knowledge_bases()
        if not all_kbs:
            print("错误: 找不到任何知识库", file=sys.stderr)
            sys.exit(1)

        # 确定要查询的知识库
        if args.kb_name:
            # 查询指定知识库
            kb_names = [args.kb_name]
            kb_name = args.kb_name
        else:
            # 查询所有知识库
            kb_names = [kb.get("kb_name") for kb in all_kbs]
            kb_name = "全部知识库"

        # 执行查询
        query_result = await client.query_knowledge_bases(
            kb_names=kb_names,
            query=args.query,
            top_k=args.top_k,
        )

        # 提取结果
        results = query_result.get("results", [])

        # 输出结果
        if args.json_output:
            # JSON 格式输出（供 Hermes 自动解析）
            output = {
                "status": "success",
                "query": args.query,
                "kb_name": kb_name,
                "result_count": len(results),
                "results": results,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            # 人类可读的格式输出
            print(f"\n📚 知识库查询结果")
            print(f"{'=' * 60}")
            print(f"知识库: {kb_name}")
            print(f"查询: {args.query}")
            print(f"结果: {len(results)} 条\n")

            for i, result in enumerate(results, 1):
                score = result.get("score", 0)
                file_name = result.get("file_name", "未知文件")
                chunk = result.get("chunk", "无内容")

                # 截断过长的文本
                if len(chunk) > 200:
                    chunk = chunk[:200] + "..."

                print(f"{i}. 📄 {file_name}")
                print(f"   相似度: {score:.2%}")
                print(f"   内容: {chunk}")
                print()


if __name__ == "__main__":
    asyncio.run(main())
