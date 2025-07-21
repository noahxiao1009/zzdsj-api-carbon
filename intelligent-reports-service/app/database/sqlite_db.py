"""
SQLite数据库配置和连接管理
"""
import sqlite3
import asyncio
import aiosqlite
import os
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from app.common.logger_util import logger


class SQLiteDB:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认数据库路径在项目根目录下的data文件夹
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "cosight.db")
        
        self.db_path = db_path
        logger.info(f"SQLite数据库路径: {self.db_path}")
    
    async def init_database(self):
        """初始化数据库表结构"""
        await self.create_tables()
        logger.info("SQLite数据库初始化完成")
    
    async def create_tables(self):
        """创建所需的数据表"""
        async with aiosqlite.connect(self.db_path) as db:
            # 会话表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT
                )
            """)
            
            # 消息表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message_type TEXT DEFAULT 'chat',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """)
            
            # 计划表 (CoSight执行计划)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    user_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    plan_data TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """)
            
            # 用户会话表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # 创建索引
            await db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_plans_user_id ON plans(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)")
            
            await db.commit()
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的上下文管理器"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db
    
    async def create_conversation(self, user_id: str, title: str = None, metadata: Dict = None) -> str:
        """创建新会话"""
        conversation_id = f"conv_{int(datetime.now().timestamp() * 1000000)}"
        
        async with self.get_connection() as db:
            await db.execute(
                """INSERT INTO conversations (id, user_id, title, metadata) 
                   VALUES (?, ?, ?, ?)""",
                (conversation_id, user_id, title, json.dumps(metadata) if metadata else None)
            )
            await db.commit()
        
        logger.info(f"创建新会话: {conversation_id} for user: {user_id}")
        return conversation_id
    
    async def get_conversations(self, user_id: str, limit: int = 10) -> List[Dict]:
        """获取用户的会话列表"""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT * FROM conversations 
                   WHERE user_id = ? AND is_active = 1 
                   ORDER BY updated_at DESC LIMIT ?""",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            
            conversations = []
            for row in rows:
                conv = dict(row)
                conv['metadata'] = json.loads(conv['metadata']) if conv['metadata'] else {}
                conversations.append(conv)
            
            return conversations
    
    async def save_message(self, conversation_id: str, content: str, role: str, 
                          message_type: str = 'chat', metadata: Dict = None) -> str:
        """保存消息"""
        message_id = f"msg_{int(datetime.now().timestamp() * 1000000)}"
        
        async with self.get_connection() as db:
            await db.execute(
                """INSERT INTO messages (id, conversation_id, content, role, message_type, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (message_id, conversation_id, content, role, message_type, 
                 json.dumps(metadata) if metadata else None)
            )
            
            # 更新会话的更新时间
            await db.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,)
            )
            
            await db.commit()
        
        return message_id
    
    async def get_conversation_history(self, conversation_id: str, limit: int = 100) -> List[Dict]:
        """获取会话历史"""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT * FROM messages 
                   WHERE conversation_id = ? 
                   ORDER BY timestamp ASC LIMIT ?""",
                (conversation_id, limit)
            )
            rows = await cursor.fetchall()
            
            messages = []
            for row in rows:
                msg = dict(row)
                msg['metadata'] = json.loads(msg['metadata']) if msg['metadata'] else {}
                messages.append(msg)
            
            return messages
    
    async def save_plan(self, plan_id: str, conversation_id: str, user_id: str, 
                       question: str, plan_data: Dict) -> None:
        """保存执行计划"""
        async with self.get_connection() as db:
            await db.execute(
                """INSERT OR REPLACE INTO plans (id, conversation_id, user_id, question, plan_data)
                   VALUES (?, ?, ?, ?, ?)""",
                (plan_id, conversation_id, user_id, question, json.dumps(plan_data))
            )
            await db.commit()
    
    async def get_plan(self, plan_id: str) -> Optional[Dict]:
        """获取执行计划"""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM plans WHERE id = ?", (plan_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                plan = dict(row)
                plan['plan_data'] = json.loads(plan['plan_data'])
                return plan
            return None
    
    async def update_plan_status(self, plan_id: str, status: str) -> None:
        """更新计划状态"""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE plans SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, plan_id)
            )
            await db.commit()
    
    async def create_user_session(self, session_id: str, user_id: str, 
                                 session_data: Dict = None, expires_at: datetime = None) -> None:
        """创建用户会话"""
        async with self.get_connection() as db:
            await db.execute(
                """INSERT OR REPLACE INTO user_sessions (id, user_id, session_data, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (session_id, user_id, json.dumps(session_data) if session_data else None, expires_at)
            )
            await db.commit()
    
    async def get_user_session(self, session_id: str) -> Optional[Dict]:
        """获取用户会话"""
        async with self.get_connection() as db:
            cursor = await db.execute(
                """SELECT * FROM user_sessions 
                   WHERE id = ? AND is_active = 1 AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)""",
                (session_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                session = dict(row)
                session['session_data'] = json.loads(session['session_data']) if session['session_data'] else {}
                return session
            return None


# 全局数据库实例
db_instance = SQLiteDB()


async def get_db() -> SQLiteDB:
    """获取数据库实例"""
    return db_instance


async def init_db():
    """初始化数据库"""
    await db_instance.init_database()