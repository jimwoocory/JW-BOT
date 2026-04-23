"""
Hermes Router 分流层 - 生产实现

这个模块提供统一的会话路由服务，解决多平台会话冲突问题。

使用方式：
1. 作为独立服务运行（推荐）
2. 集成到 Hermes Gateway 中
3. 作为库被 hermes_bridge 导入
"""

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

# ── 日志配置 ─────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# ── 枚举和数据类 ──────────────────────────────────────────────────


class PlatformType(str, Enum):
    """支持的平台类型"""
    WEBUI = "webui"
    QQ = "qq"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    HOMEASSISTANT = "homeassistant"
    SIGNAL = "signal"

    @classmethod
    def from_astrbot_platform_id(cls, platform_id: str) -> "PlatformType":
        """Map AstrBot platform_id strings to PlatformType.

        Known mappings:
          qq_official → QQ
          lark        → FEISHU
        Falls back to from_string for unlisted adapters.
        """
        _map = {
            "qq_official": cls.QQ,
            "lark": cls.FEISHU,
            "webchat": cls.WEBUI,
        }
        result = _map.get(platform_id.lower())
        if result is not None:
            return result
        return cls.from_string(platform_id)

    @classmethod
    def from_string(cls, value: str) -> 'PlatformType':
        """从字符串解析平台类型（大小写不敏感）"""
        try:
            return cls[value.upper()]
        except KeyError:
            value_lower = value.lower()
            for platform in cls:
                if platform.value.lower() == value_lower:
                    return platform
            raise ValueError(f"Unknown platform: {value}")


@dataclass
class PlatformUser:
    """平台用户标识"""
    platform: PlatformType
    user_id: str  # 平台上的用户 ID
    channel_id: Optional[str] = None  # 可选的频道/群组 ID
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlatformUser':
        """从字典创建"""
        platform = data.get('platform')
        if isinstance(platform, str):
            platform = PlatformType.from_string(platform)
        
        return cls(
            platform=platform,
            user_id=data.get('user_id', ''),
            channel_id=data.get('channel_id'),
            metadata=data.get('metadata')
        )
    
    def generate_id(self) -> str:
        """生成平台用户唯一标识"""
        parts = [self.platform.value, self.user_id]
        if self.channel_id:
            parts.append(self.channel_id)
        return ":".join(parts)


@dataclass
class SessionInfo:
    """会话信息"""
    session_id: str
    platform_user_id: str
    title: str
    created_at: float
    updated_at: float
    platform: str
    platform_user_id_raw: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


# ── Session Router 核心类 ────────────────────────────────────────


class SessionRouter:
    """
    会话路由器 - 统一管理平台会话
    
    职责：
    1. 为每个平台用户创建统一的 session_id (UUID 格式)
    2. 维护 platform_user ↔ session_id 映射关系
    3. 所有会话数据统一存储到 SQLite 数据库
    4. 提供会话查询、创建、删除接口
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser().resolve()
        self._init_database()
        logger.info(f"SessionRouter initialized with database: {self.db_path}")
    
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
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # 会话映射表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_mapping (
                platform_user_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                title TEXT DEFAULT 'Untitled',
                created_at REAL DEFAULT (strftime('%s', 'now')),
                updated_at REAL DEFAULT (strftime('%s', 'now'))
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
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_updated 
            ON session_mapping(updated_at DESC)
        """)
        
        conn.commit()
        conn.close()
        logger.debug("Database tables initialized")
    
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
            platform_user_id = platform_user.generate_id()
            
            # 1. 检查是否已有会话映射
            cursor.execute(
                "SELECT session_id FROM session_mapping WHERE platform_user_id = ?",
                (platform_user_id,)
            )
            row = cursor.fetchone()
            
            if row:
                session_id = row[0]
                logger.debug(f"Found existing session {session_id} for {platform_user_id}")
            else:
                # 2. 创建新会话
                session_id = self._create_new_session(
                    cursor, platform_user, platform_user_id
                )
                logger.info(f"Created new session {session_id} for {platform_user_id}")
            
            conn.commit()
            return session_id
        
        except Exception as e:
            logger.error(f"Error getting/creating session: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _create_new_session(
        self, 
        cursor, 
        platform_user: PlatformUser, 
        platform_user_id: str
    ) -> str:
        """创建新会话"""
        # 1. 生成标准 UUID
        session_id = uuid.uuid4().hex[:12]
        
        # 2. 插入平台用户记录
        cursor.execute("""
            INSERT OR REPLACE INTO platform_users 
            (id, platform, platform_user_id, channel_id, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            platform_user_id,
            platform_user.platform.value,
            platform_user.user_id,
            platform_user.channel_id,
            json.dumps(platform_user.metadata or {})
        ))
        
        # 3. 插入会话映射
        now = datetime.now(timezone.utc).timestamp()
        cursor.execute("""
            INSERT INTO session_mapping 
            (platform_user_id, session_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (platform_user_id, session_id, 'Untitled', now, now))
        
        return session_id
    
    def get_session_by_platform_user(self, platform_user: PlatformUser) -> Optional[str]:
        """通过平台用户信息获取 session_id"""
        platform_user_id = platform_user.generate_id()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT session_id FROM session_mapping WHERE platform_user_id = ?",
                (platform_user_id,)
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
            cursor.execute("""
                SELECT pu.platform, pu.platform_user_id, pu.channel_id, pu.metadata
                FROM session_mapping sm
                JOIN platform_users pu ON sm.platform_user_id = pu.id
                WHERE sm.session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                return PlatformUser(
                    platform=PlatformType.from_string(row[0]),
                    user_id=row[1],
                    channel_id=row[2],
                    metadata=json.loads(row[3]) if row[3] else None
                )
            return None
        
        finally:
            conn.close()
    
    def list_sessions_by_platform(
        self, 
        platform: PlatformType, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列出指定平台的所有会话"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT sm.session_id, sm.title, pu.platform_user_id, 
                       sm.created_at, sm.updated_at, pu.platform
                FROM session_mapping sm
                JOIN platform_users pu ON sm.platform_user_id = pu.id
                WHERE pu.platform = ?
                ORDER BY sm.updated_at DESC
                LIMIT ?
            """, (platform.value, limit))
            
            return [
                {
                    "session_id": row[0],
                    "title": row[1],
                    "platform_user_id": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                    "platform": row[5],
                }
                for row in cursor.fetchall()
            ]
        
        finally:
            conn.close()
    
    def list_all_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出所有会话"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT sm.session_id, sm.title, pu.platform, pu.platform_user_id,
                       pu.channel_id, sm.created_at, sm.updated_at
                FROM session_mapping sm
                JOIN platform_users pu ON sm.platform_user_id = pu.id
                ORDER BY sm.updated_at DESC
                LIMIT ?
            """, (limit,))
            
            return [
                {
                    "session_id": row[0],
                    "title": row[1],
                    "platform": row[2],
                    "platform_user_id": row[3],
                    "channel_id": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
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
            cursor.execute("""
                UPDATE session_mapping 
                SET title = ?, updated_at = strftime('%s', 'now')
                WHERE session_id = ?
            """, (title, session_id))
            
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.debug(f"Updated session {session_id} title to: {title}")
            return updated
        
        except Exception as e:
            logger.error(f"Error setting session title: {e}")
            conn.rollback()
            return False
        
        finally:
            conn.close()
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # 先删除映射
            cursor.execute(
                "DELETE FROM session_mapping WHERE session_id = ?",
                (session_id,)
            )
            
            # 清理孤立的平台用户记录（可选）
            cursor.execute("""
                DELETE FROM platform_users 
                WHERE id NOT IN (SELECT platform_user_id FROM session_mapping)
            """)
            
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted session: {session_id}")
            return deleted
        
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            conn.rollback()
            return False
        
        finally:
            conn.close()
    
    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话详细信息"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT sm.session_id, sm.platform_user_id, sm.title,
                       sm.created_at, sm.updated_at,
                       pu.platform, pu.platform_user_id
                FROM session_mapping sm
                JOIN platform_users pu ON sm.platform_user_id = pu.id
                WHERE sm.session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                return SessionInfo(
                    session_id=row[0],
                    platform_user_id=row[1],
                    title=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                    platform=row[5],
                    platform_user_id_raw=row[6]
                )
            return None
        
        finally:
            conn.close()


# ── HTTP API Server（可选） ──────────────────────────────────────


async def create_router_api_server(router: SessionRouter, host: str = '0.0.0.0', port: int = 8788):
    """创建 Router 的 HTTP API 服务"""
    try:
        from aiohttp import web
    except ImportError:
        logger.error("aiohttp not installed, cannot create API server")
        return None
    
    routes = web.RouteTableDef()
    
    @routes.post('/api/session/create')
    async def create_session(request):
        """创建或获取会话"""
        try:
            data = await request.json()
            platform_user = PlatformUser.from_dict(data)
            session_id = router.get_or_create_session(platform_user)
            return web.json_response({
                'session_id': session_id,
                'platform_user': platform_user.to_dict()
            })
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return web.json_response({'error': str(e)}, status=400)
    
    @routes.get('/api/session/{session_id}')
    async def get_session(request):
        """获取会话信息"""
        session_id = request.match_info['session_id']
        info = router.get_session_info(session_id)
        
        if info:
            return web.json_response(info.to_dict())
        else:
            return web.json_response({'error': 'Session not found'}, status=404)
    
    @routes.get('/api/sessions')
    async def list_sessions(request):
        """列出所有会话"""
        limit = int(request.query.get('limit', 100))
        sessions = router.list_all_sessions(limit=limit)
        return web.json_response({'sessions': sessions})
    
    @routes.get('/api/sessions/{platform}')
    async def list_platform_sessions(request):
        """列出指定平台的会话"""
        try:
            platform = PlatformType.from_string(request.match_info['platform'])
            limit = int(request.query.get('limit', 50))
            sessions = router.list_sessions_by_platform(platform, limit=limit)
            return web.json_response({'sessions': sessions})
        except ValueError as e:
            return web.json_response({'error': str(e)}, status=400)
    
    @routes.put('/api/session/{session_id}/title')
    async def set_title(request):
        """设置会话标题"""
        session_id = request.match_info['session_id']
        data = await request.json()
        title = data.get('title', '')
        
        if router.set_session_title(session_id, title):
            return web.json_response({'ok': True})
        else:
            return web.json_response({'error': 'Session not found'}, status=404)
    
    @routes.delete('/api/session/{session_id}')
    async def delete_session(request):
        """删除会话"""
        session_id = request.match_info['session_id']
        
        if router.delete_session(session_id):
            return web.json_response({'ok': True})
        else:
            return web.json_response({'error': 'Session not found'}, status=404)
    
    # 启动服务
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info(f"Router API server started on http://{host}:{port}")
    return runner


# ── CLI 入口 ─────────────────────────────────────────────────────

def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Hermes Session Router')
    parser.add_argument('--db', default='~/.hermes/state.db', help='Database path')
    parser.add_argument('--api-port', type=int, default=8788, help='API server port')
    parser.add_argument('--api-host', default='0.0.0.0', help='API server host')
    parser.add_argument('--no-api', action='store_true', help='Disable API server')
    
    args = parser.parse_args()
    
    # 初始化 Router
    router = SessionRouter(args.db)
    
    if not args.no_api:
        # 启动 API 服务
        print(f"Starting Router API server on http://{args.api_host}:{args.api_port}")
        asyncio.run(create_router_api_server(router, args.api_host, args.api_port))


if __name__ == '__main__':
    main()
