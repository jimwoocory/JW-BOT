#!/usr/bin/env python3
"""
测试 AIHubMix 实际聊天延迟（模拟 AstrBot 的测试方式）
"""

import asyncio
import time
import os
import httpx

# 从你的配置中获取
API_KEY = "sk-tKFerl7qPiogeEU2D7480083"
API_BASE = "https://aihubmix.com/v1"
MODEL = "qwen3.5-397b-a17b"


async def test_chat_completion():
    """模拟 AstrBot 的 test 方法"""
    print(f"测试模型：{MODEL}")
    print(f"API Base: {API_BASE}")
    print("-" * 60)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 使用 AstrBot 相同的测试 prompt
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "REPLY `PONG` ONLY"}],
        "stream": False,  # 非流式，等待完整响应
        "max_tokens": 50,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            start = time.perf_counter()
            response = await client.post(
                f"{API_BASE}/chat/completions",
                json=payload,
                headers=headers,
            )
            elapsed = time.perf_counter() - start

            print(f"请求完成！")
            print(f"HTTP 状态码：{response.status_code}")
            print(f"总延迟：{elapsed * 1000:.2f}ms ({elapsed:.2f}s)")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                print(f"响应内容：{content}")
                print(f"Token 使用：{usage}")

                # 计算 token/秒
                if usage.get("total_tokens", 0) > 0:
                    tps = usage["total_tokens"] / elapsed
                    print(f"Token/秒：{tps:.2f}")
            else:
                print(f"错误响应：{response.text}")

        except httpx.TimeoutException as e:
            print(f"❌ 请求超时：{e}")
        except Exception as e:
            print(f"❌ 请求失败：{e}")


if __name__ == "__main__":
    print("=" * 60)
    print("AIHubMix 聊天延迟测试（模拟 AstrBot 测试方式）")
    print("=" * 60)
    print()
    asyncio.run(test_chat_completion())
