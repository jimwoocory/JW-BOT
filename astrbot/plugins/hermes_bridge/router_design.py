"""
Hermes Router 分流层设计文档

目标：统一多平台会话管理，解决 "Session not found" 冲突
"""

from typing import Optional
from dataclasses import dataclass
from enum import Enum
import uuid
import sqlite3
from pathlib import Path
import json


class PlatformType(str, Enum):
    """支持的平台类型"""

    WEBUI = "webui"
    QQ = "qq"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WHATSAPP = "whatsapp"


@dataclass
class PlatformUser:
    """平台用户标识"""

    platform: PlatformType
    user_id: str  # 平台上的用户 ID（如 QQ 号、Telegram ID）
    channel_id: Optional[str] = None  # 可选的频道/群组 ID
    metadata: Optional[dict] = None


class SessionRouter:
    """
    会话路由器 - 统一管理平台会话

    职责：
    1. 为每个平台用户创建统一的 session_id (UUID 格式)
    2. 维护 platform_user ↔ session_id 映射关系
    3. 所有会话数据统一存储到 state.db
    4. 提供会话查询、创建、删除接口
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 平台用户映射表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS platform_users (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_user_id TEXT NOT NULL,
                channel_id TEXT,
                metadata TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                UNIQUE(platform, platform_user_id, channel_id)
            )
        """)

        # 会话映射表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_mapping (
                platform_user_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                title TEXT DEFAULT 'Untitled',
                created_at REAL DEFAULT (strftime('%s', 'now')),
                updated_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (platform_user_id) REFERENCES platform_users(id)
            )
        """)

        # 创建索引加速查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_id 
            ON session_mapping(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_platform_user 
            ON platform_users(platform, platform_user_id)
        """)

        conn.commit()
        conn.close()

    def get_or_create_session(self, platform_user: PlatformUser) -> str:
        """
        获取或创建会话

        Args:
            platform_user: 平台用户信息

        Returns:
            session_id: 统一的 UUID 格式会话 ID
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # 1. 生成平台用户 ID
            platform_user_id = self._generate_platform_user_id(platform_user)

            # 2. 检查是否已有会话映射
            cursor.execute(
                "SELECT session_id FROM session_mapping WHERE platform_user_id = ?",
                (platform_user_id,),
            )
            row = cursor.fetchone()

            if row:
                # 已有会话，返回 session_id
                session_id = row[0]
            else:
                # 3. 创建新会话
                session_id = self._create_new_session(
                    cursor, platform_user, platform_user_id
                )

            conn.commit()
            return session_id

        finally:
            conn.close()

    def _generate_platform_user_id(self, platform_user: PlatformUser) -> str:
        """生成平台用户唯一标识"""
        # 格式：platform:user_id:channel_id
        parts = [
            platform_user.platform.value,
            platform_user.user_id,
        ]
        if platform_user.channel_id:
            parts.append(platform_user.channel_id)
        return ":".join(parts)

    def _create_new_session(
        self, cursor, platform_user: PlatformUser, platform_user_id: str
    ) -> str:
        """创建新会话"""
        # 1. 生成标准 UUID
        session_id = uuid.uuid4().hex[:12]

        # 2. 插入平台用户记录
        cursor.execute(
            """
            INSERT OR REPLACE INTO platform_users 
            (id, platform, platform_user_id, channel_id, metadata)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                platform_user_id,
                platform_user.platform.value,
                platform_user.user_id,
                platform_user.channel_id,
                json.dumps(platform_user.metadata or {}),
            ),
        )

        # 3. 插入会话映射
        cursor.execute(
            """
            INSERT INTO session_mapping (platform_user_id, session_id)
            VALUES (?, ?)
        """,
            (platform_user_id, session_id),
        )

        return session_id

    def get_session_by_platform_user(
        self, platform_user: PlatformUser
    ) -> Optional[str]:
        """通过平台用户信息获取 session_id"""
        platform_user_id = self._generate_platform_user_id(platform_user)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT session_id FROM session_mapping WHERE platform_user_id = ?",
                (platform_user_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

        finally:
            conn.close()

    def get_platform_user_by_session(self, session_id: str) -> Optional[PlatformUser]:
        """通过 session_id 反查平台用户信息"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT pu.platform, pu.platform_user_id, pu.channel_id, pu.metadata
                FROM session_mapping sm
                JOIN platform_users pu ON sm.platform_user_id = pu.id
                WHERE sm.session_id = ?
            """,
                (session_id,),
            )

            row = cursor.fetchone()
            if row:
                return PlatformUser(
                    platform=PlatformType(row[0]),
                    user_id=row[1],
                    channel_id=row[2],
                    metadata=json.loads(row[3]) if row[3] else None,
                )
            return None

        finally:
            conn.close()

    def list_sessions_by_platform(
        self, platform: PlatformType, limit: int = 50
    ) -> list:
        """列出指定平台的所有会话"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT sm.session_id, sm.title, pu.platform_user_id, 
                       sm.created_at, sm.updated_at
                FROM session_mapping sm
                JOIN platform_users pu ON sm.platform_user_id = pu.id
                WHERE pu.platform = ?
                ORDER BY sm.updated_at DESC
                LIMIT ?
            """,
                (platform.value, limit),
            )

            return [
                {
                    "session_id": row[0],
                    "title": row[1],
                    "platform_user_id": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                }
                for row in cursor.fetchall()
            ]

        finally:
            conn.close()

    def set_session_title(self, session_id: str, title: str) -> bool:
        """设置会话标题"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE session_mapping 
                SET title = ?, updated_at = strftime('%s', 'now')
                WHERE session_id = ?
            """,
                (title, session_id),
            )

            conn.commit()
            return cursor.rowcount > 0

        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # 先删除映射
            cursor.execute(
                "DELETE FROM session_mapping WHERE session_id = ?", (session_id,)
            )

            # 清理孤立的平台用户记录（可选）
            cursor.execute("""
                DELETE FROM platform_users 
                WHERE id NOT IN (SELECT platform_user_id FROM session_mapping)
            """)

            conn.commit()
            return cursor.rowcount > 0

        finally:
            conn.close()


# ── 使用示例 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # 初始化路由器
    router = SessionRouter(db_path="~/.hermes/state.db")

    # 场景 1: QQ 用户发送消息
    qq_user = PlatformUser(
        platform=PlatformType.QQ,
        user_id="123456",
        channel_id="group_789",  # 可选的群组 ID
    )

    # 获取或创建会话（返回标准 UUID）
    session_id = router.get_or_create_session(qq_user)
    print(f"QQ 用户会话 ID: {session_id}")

    # 场景 2: WebUI 用户发送消息
    webui_user = PlatformUser(platform=PlatformType.WEBUI, user_id="user_abc123")

    session_id = router.get_or_create_session(webui_user)
    print(f"WebUI 用户会话 ID: {session_id}")

    # 场景 3: 查询 QQ 平台的所有会话
    qq_sessions = router.list_sessions_by_platform(PlatformType.QQ)
    print(f"QQ 平台会话列表：{qq_sessions}")

    # 场景 4: 通过 session_id 反查平台用户
    platform_user = router.get_platform_user_by_session(session_id)
    print(f"会话对应的平台用户：{platform_user}")


# ── 与现有系统集成 ──────────────────────────────────────────────

"""
1. 修改 hermes_bridge 插件：

   从：
   session_key = self._get_or_create_session(user_id)  # 自定义格式
   
   改为：
   platform_user = PlatformUser(
       platform=PlatformType.QQ,
       user_id=user_id,
       channel_id=channel_id
   )
   session_id = router.get_or_create_session(platform_user)  # UUID 格式

2. 修改 Hermes Gateway：
   
   在 /api/session/new 接口中：
   - 识别 platform 参数
   - 使用 SessionRouter 创建会话
   - 返回标准 UUID session_id

3. HermesUI 保持不变：
   - 继续使用 /api/session/new
   - 但底层使用 SessionRouter
   - 会话统一存储到 state.db

优势：
✅ 所有平台使用相同的会话存储
✅ 支持跨平台会话查询
✅ 完整的会话管理功能
✅ 易于扩展新平台
"""
