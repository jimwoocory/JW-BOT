"""
烟雾测试脚本 — 验证 SessionRouter 的实际行为。
"""
import sys
sys.path.insert(0, '/Users/dianchi/JW-Bot')

from pathlib import Path
from astrbot.plugins.hermes_bridge.router import SessionRouter, PlatformUser, PlatformType

# 创建临时测试数据库
router = SessionRouter(db_path="/tmp/smoke_test_router.db")

results = []

# =========================================================================
# 场景 1：/task 家族命令模拟 — 验证平台用户标识生成
# =========================================================================

print("=== 场景 1：平台用户标识生成 ===")

scenarios_1 = [
    ("qq:user1", PlatformUser(platform=PlatformType.QQ, user_id="user1")),
    ("qq:user1:group1", PlatformUser(platform=PlatformType.QQ, user_id="user1", channel_id="group1")),
    ("telegram:user2", PlatformUser(platform=PlatformType.TELEGRAM, user_id="user2")),
]

for label, user in scenarios_1:
    gen_id = user.generate_id()
    sid = router.get_or_create_session(user)
    results.append({
        "scene": "1",
        "input": label,
        "expected": "Valid session_id",
        "actual": f"id={gen_id}, sid={sid}",
        "pass": len(sid) == 12,
        "note": f"generate_id={gen_id}"
    })
    print(f"  {label}: generate_id={gen_id}, session_id={sid} {'✅' if len(sid) == 12 else '❌'}")

# =========================================================================
# 场景 2：多种平台类型
# =========================================================================

print("\n=== 场景 2：多种平台类型 ===")

platforms_to_test = [
    PlatformType.WEBUI, PlatformType.QQ, PlatformType.TELEGRAM,
    PlatformType.DISCORD, PlatformType.SLACK, PlatformType.WHATSAPP,
    PlatformType.HOMEASSISTANT, PlatformType.SIGNAL,
]

for p in platforms_to_test:
    user = PlatformUser(platform=p, user_id=f"user_{p.value}")
    sid = router.get_or_create_session(user)
    ok = len(sid) == 12
    results.append({
        "scene": "2",
        "input": p.value,
        "expected": "12-char session_id",
        "actual": sid,
        "pass": ok,
        "note": ""
    })
    print(f"  {p.value}: {sid} {'✅' if ok else '❌'}")

# =========================================================================
# 场景 3：边界情况
# =========================================================================

print("\n=== 场景 3：边界情况 ===")

# 空 user_id
user_empty = PlatformUser(platform=PlatformType.QQ, user_id="")
sid_empty = router.get_or_create_session(user_empty)
ok_empty = len(sid_empty) == 12
results.append({
    "scene": "3", "input": "empty user_id", "expected": "12-char session_id",
    "actual": sid_empty, "pass": ok_empty, "note": "空 user_id 仍可创建会话"
})
print(f"  空 user_id: {sid_empty} {'✅' if ok_empty else '❌'}")

# 超长 user_id
user_long = PlatformUser(platform=PlatformType.QQ, user_id="a" * 500)
sid_long = router.get_or_create_session(user_long)
ok_long = len(sid_long) == 12
results.append({
    "scene": "3", "input": "very long user_id (500 chars)", "expected": "12-char session_id",
    "actual": sid_long, "pass": ok_long, "note": "超长 user_id 仍可处理"
})
print(f"  超长 user_id: {sid_long} {'✅' if ok_long else '❌'}")

# 特殊字符 user_id
user_special = PlatformUser(platform=PlatformType.QQ, user_id="user!@#$%^&*()_+=[]{}|;:',.<>?/~`")
sid_special = router.get_or_create_session(user_special)
ok_special = len(sid_special) == 12
results.append({
    "scene": "3", "input": "special chars user_id", "expected": "12-char session_id",
    "actual": sid_special, "pass": ok_special, "note": "特殊字符仍可处理"
})
print(f"  特殊字符 user_id: {sid_special} {'✅' if ok_special else '❌'}")

# 中文 user_id
user_chinese = PlatformUser(platform=PlatformType.QQ, user_id="用户测试")
sid_chinese = router.get_or_create_session(user_chinese)
ok_chinese = len(sid_chinese) == 12
results.append({
    "scene": "3", "input": "chinese user_id", "expected": "12-char session_id",
    "actual": sid_chinese, "pass": ok_chinese, "note": "中文字符仍可处理"
})
print(f"  中文 user_id: {sid_chinese} {'✅' if ok_chinese else '❌'}")

# 重复获取同一用户
user_repeat = PlatformUser(platform=PlatformType.QQ, user_id="repeat_test")
sid_r1 = router.get_or_create_session(user_repeat)
sid_r2 = router.get_or_create_session(user_repeat)
ok_repeat = sid_r1 == sid_r2
results.append({
    "scene": "3", "input": "same user twice", "expected": "same session_id",
    "actual": f"{sid_r1} vs {sid_r2}", "pass": ok_repeat,
    "note": "重复获取应返回相同 ID"
})
print(f"  重复获取: {sid_r1} == {sid_r2} {'✅' if ok_repeat else '❌'}")

# 删除后再创建
user_del = PlatformUser(platform=PlatformType.QQ, user_id="delete_test")
sid_del1 = router.get_or_create_session(user_del)
router.delete_session(sid_del1)
sid_del2 = router.get_or_create_session(user_del)
ok_del = sid_del1 != sid_del2
results.append({
    "scene": "3", "input": "delete then recreate", "expected": "different session_id",
    "actual": f"{sid_del1} vs {sid_del2}", "pass": ok_del,
    "note": "删除后重新创建应不同"
})
print(f"  删除后重建: {sid_del1} != {sid_del2} {'✅' if ok_del else '❌'}")

# =========================================================================
# 场景 4：列表与查询
# =========================================================================

print("\n=== 场景 4：列表与查询 ===")

# 创建 20 个 QQ 用户
for i in range(20):
    u = PlatformUser(platform=PlatformType.QQ, user_id=f"list_test_{i}")
    router.get_or_create_session(u)

qq_list = router.list_sessions_by_platform(PlatformType.QQ, limit=10)
ok_list = len(qq_list) == 10
results.append({
    "scene": "4", "input": "20 QQ users, limit 10", "expected": "10 results",
    "actual": str(len(qq_list)), "pass": ok_list, "note": ""
})
print(f"  列表限制 limit=10: 返回 {len(qq_list)} 条 {'✅' if ok_list else '❌'}")

# 查询不存在
info_none = router.get_session_info("nonexistent_0000")
ok_none = info_none is None
results.append({
    "scene": "4", "input": "nonexistent session_id", "expected": "None",
    "actual": str(info_none), "pass": ok_none, "note": ""
})
print(f"  查询不存在: {info_none} {'✅' if ok_none else '❌'}")

# 设置标题后查询
user_title = PlatformUser(platform=PlatformType.QQ, user_id="title_test")
sid_title = router.get_or_create_session(user_title)
router.set_session_title(sid_title, "测试标题")
info = router.get_session_info(sid_title)
ok_title = info.title == "测试标题"
results.append({
    "scene": "4", "input": "set title then get info", "expected": "测试标题",
    "actual": str(info.title if info else None), "pass": ok_title, "note": ""
})
print(f"  设置标题后查询: {info.title if info else None} {'✅' if ok_title else '❌'}")

# =========================================================================
# 汇总
# =========================================================================

total = len(results)
passed = sum(1 for r in results if r["pass"])
failed = total - passed

print(f"\n{'='*50}")
print(f"烟雾测试汇总: {passed}/{total} 通过, {failed} 失败")
print(f"{'='*50}")

for r in results:
    status = "✅" if r["pass"] else "❌"
    print(f"  {status} 场景{r['scene']} | {r['input']} | 期望: {r['expected']} | 实际: {r['actual']}")

# 保存 JSON 结果
import json
Path("/tmp/smoke_test_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
