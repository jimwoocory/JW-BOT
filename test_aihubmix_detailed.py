#!/usr/bin/env python3
"""
AIHubMix 详细延迟测试
多次请求测试平均延迟
"""

import time
import httpx
import asyncio

API_BASE = "https://aihubmix.com/v1"

async def test_single_request(session: httpx.AsyncClient) -> float:
    """单次请求测试"""
    start = time.perf_counter()
    try:
        response = await session.get(f"{API_BASE}/models", timeout=15.0)
        elapsed = time.perf_counter() - start
        return elapsed, response.status_code
    except Exception as e:
        elapsed = time.perf_counter() - start
        return elapsed, None

async def run_latency_test(num_requests: int = 10):
    """运行多次延迟测试"""
    print(f"开始 {num_requests} 次延迟测试...")
    print("-" * 60)
    
    async with httpx.AsyncClient() as session:
        results = []
        for i in range(num_requests):
            elapsed, status = await test_single_request(session)
            status_str = str(status) if status else "FAILED"
            print(f"请求 {i+1:2d}: {elapsed*1000:7.2f}ms  (状态码：{status_str})")
            results.append(elapsed)
        
        print()
        print("=" * 60)
        print(f"最小延迟：{min(results)*1000:.2f}ms")
        print(f"最大延迟：{max(results)*1000:.2f}ms")
        print(f"平均延迟：{sum(results)/len(results)*1000:.2f}ms")
        print(f"抖动：{(max(results)-min(results))*1000:.2f}ms")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_latency_test(10))
