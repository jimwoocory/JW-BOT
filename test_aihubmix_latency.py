#!/usr/bin/env python3
"""
AIHubMix 延迟测试脚本
测试 API 响应时间和连接质量
"""

import time
import httpx
import asyncio
from typing import Optional

# 测试配置
API_BASE = "https://aihubmix.com/v1"
TEST_MODELS = [
    "gpt-4.1-free",
    "gemini-3-flash-preview-free",
]

# 如果你有 API Key，可以在这里配置
API_KEY = ""  # 可选：填入你的 API Key 进行完整测试


async def test_connection_speed(base_url: str = API_BASE) -> dict:
    """测试基础连接速度"""
    results = {
        "dns_lookup": 0.0,
        "tcp_connect": 0.0,
        "tls_handshake": 0.0,
        "first_byte": 0.0,
        "total": 0.0,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            start = time.perf_counter()
            
            # DNS 解析
            dns_start = time.perf_counter()
            url = base_url.replace("/v1", "")
            
            # TCP 连接
            tcp_start = time.perf_counter()
            
            # TLS 握手
            tls_start = time.perf_counter()
            
            # 发送请求并等待第一个字节
            response = await client.get(f"{base_url}/models", timeout=10.0)
            
            first_byte_time = time.perf_counter()
            
            # 总时间
            total_time = time.perf_counter() - start
            
            results["total"] = total_time
            results["status_code"] = response.status_code
            
        except Exception as e:
            results["error"] = str(e)
    
    return results


async def test_api_latency(model: str, api_key: Optional[str] = None) -> dict:
    """测试特定模型的 API 延迟"""
    result = {
        "model": model,
        "ttft": None,  # Time to first token
        "total_time": None,
        "success": False,
        "error": None,
    }
    
    if not api_key:
        result["error"] = "未提供 API Key，跳过实际请求测试"
        return result
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            start_time = time.perf_counter()
            first_token_time = None
            
            async with client.stream(
                "POST",
                f"{API_BASE}/chat/completions",
                json=payload,
                headers=headers,
                timeout=30.0,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        if data.strip():
                            if first_token_time is None:
                                first_token_time = time.perf_counter()
                                result["ttft"] = first_token_time - start_time
            
            result["total_time"] = time.perf_counter() - start_time
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
    
    return result


async def test_endpoint_latency(endpoint: str, api_key: Optional[str] = None) -> dict:
    """测试不同端点的延迟"""
    result = {
        "endpoint": endpoint,
        "latency": None,
        "success": False,
        "error": None,
    }
    
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    async with httpx.AsyncClient() as client:
        try:
            start = time.perf_counter()
            response = await client.get(
                f"{API_BASE}{endpoint}",
                headers=headers,
                timeout=10.0,
            )
            result["latency"] = time.perf_counter() - start
            result["success"] = response.status_code == 200
            result["status_code"] = response.status_code
        except Exception as e:
            result["error"] = str(e)
    
    return result


async def main():
    print("=" * 60)
    print("AIHubMix 延迟测试")
    print("=" * 60)
    print()
    
    # 1. 基础连接测试
    print("1. 基础连接测试...")
    print("-" * 60)
    conn_result = await test_connection_speed()
    if "error" in conn_result:
        print(f"❌ 连接失败：{conn_result['error']}")
    else:
        print(f"✓ 总延迟：{conn_result['total']*1000:.2f}ms")
        if "status_code" in conn_result:
            print(f"  状态码：{conn_result['status_code']}")
    print()
    
    # 2. 端点延迟测试
    print("2. 端点延迟测试...")
    print("-" * 60)
    endpoints = ["/models", "/chat/completions"]
    for endpoint in endpoints:
        result = await test_endpoint_latency(endpoint, API_KEY)
        status = "✓" if result["success"] else "❌"
        latency = f"{result['latency']*1000:.2f}ms" if result["latency"] else "N/A"
        print(f"{status} {endpoint}: {latency}")
        if result.get("error"):
            print(f"   错误：{result['error']}")
    print()
    
    # 3. 模型延迟测试（如果有 API Key）
    if API_KEY:
        print("3. 模型延迟测试...")
        print("-" * 60)
        for model in TEST_MODELS:
            print(f"测试模型：{model}")
            result = await test_api_latency(model, API_KEY)
            if result["success"]:
                ttft = f"{result['ttft']*1000:.2f}ms" if result['ttft'] else "N/A"
                total = f"{result['total_time']*1000:.2f}ms"
                print(f"  ✓ 首 token 延迟：{ttft}")
                print(f"  ✓ 总延迟：{total}")
            else:
                print(f"  ❌ 失败：{result['error']}")
            print()
    else:
        print("3. 模型延迟测试 (跳过)")
        print("-" * 60)
        print("提示：在脚本中设置 API_KEY 可以进行完整的模型延迟测试")
        print()
    
    # 4. 网络诊断
    print("4. 网络诊断...")
    print("-" * 60)
    import socket
    try:
        ip = socket.gethostbyname("aihubmix.com")
        print(f"✓ DNS 解析：aihubmix.com → {ip}")
    except Exception as e:
        print(f"❌ DNS 解析失败：{e}")
    
    # 测试不同地区节点（如果知道的话）
    print()
    print("建议：")
    print("- 如果延迟高，检查是否需要使用代理")
    print("- 尝试在不同时间段测试")
    print("- 联系 AIHubMix 支持获取最优节点")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
