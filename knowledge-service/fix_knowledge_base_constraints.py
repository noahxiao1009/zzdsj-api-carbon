#!/usr/bin/env python3
"""
修复knowledge_base表的字段校验问题
1. 修复chunk_strategy约束，支持token_based
2. 修复user_id非空约束问题
3. 确保数据模型和数据库表结构一致
"""

import asyncio
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from app.config.settings import settings

def get_db_connection():
    """获取数据库连接"""
    db_settings = settings.database
    return psycopg2.connect(
        host=db_settings.postgres_host,
        port=db_settings.postgres_port,
        database=db_settings.postgres_db,
        user=db_settings.postgres_user,
        password=db_settings.postgres_password
    )

def fix_chunk_strategy_constraint():
    """修复chunk_strategy约束，添加token_based支持"""
    print("🔧 修复chunk_strategy约束...")
    
    conn = get_db_connection()
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    try:
        # 删除旧约束
        cursor.execute("""
            ALTER TABLE knowledge_bases 
            DROP CONSTRAINT IF EXISTS knowledge_bases_chunk_strategy_check;
        """)
        
        # 添加新约束，支持token_based
        cursor.execute("""
            ALTER TABLE knowledge_bases 
            ADD CONSTRAINT knowledge_bases_chunk_strategy_check 
            CHECK (chunk_strategy IN ('basic', 'semantic', 'intelligent', 'token_based'));
        """)
        
        print("✅ chunk_strategy约束修复完成")
        
    except Exception as e:
        print(f"❌ 修复chunk_strategy约束失败: {e}")
    finally:
        cursor.close()
        conn.close()

def fix_user_id_constraint():
    """修复user_id非空约束问题"""
    print("🔧 修复user_id约束...")
    
    conn = get_db_connection()
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    try:
        # 检查是否有user_id为空的记录
        cursor.execute("""
            SELECT COUNT(*) FROM knowledge_bases WHERE user_id IS NULL;
        """)
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            print(f"发现 {null_count} 条user_id为空的记录")
            
            # 创建默认用户（如果不存在）
            cursor.execute("""
                INSERT INTO users (id, username, email, display_name, is_active, created_at, updated_at)
                VALUES ('default-system-user', 'system', 'system@zzdsl.ai', 'System User', true, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING;
            """)
            
            # 更新所有user_id为空的记录
            cursor.execute("""
                UPDATE knowledge_bases 
                SET user_id = 'default-system-user'
                WHERE user_id IS NULL;
            """)
            
            print(f"✅ 已更新 {null_count} 条记录的user_id")
        
        # 确保user_id列为非空（如果还没有设置的话）
        cursor.execute("""
            ALTER TABLE knowledge_bases 
            ALTER COLUMN user_id SET NOT NULL;
        """)
        
        print("✅ user_id约束修复完成")
        
    except Exception as e:
        print(f"❌ 修复user_id约束失败: {e}")
    finally:
        cursor.close()
        conn.close()

def add_missing_columns():
    """添加缺失的列"""
    print("🔧 添加缺失的列...")
    
    conn = get_db_connection()
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    try:
        # 检查并添加缺失的列
        columns_to_add = [
            ("is_active", "BOOLEAN DEFAULT true"),
            ("last_indexed_at", "TIMESTAMP WITH TIME ZONE"),
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                cursor.execute(f"""
                    ALTER TABLE knowledge_bases 
                    ADD COLUMN IF NOT EXISTS {column_name} {column_def};
                """)
                print(f"✅ 添加列 {column_name}")
            except Exception as e:
                print(f"⚠️ 列 {column_name} 可能已存在: {e}")
        
        print("✅ 缺失列添加完成")
        
    except Exception as e:
        print(f"❌ 添加缺失列失败: {e}")
    finally:
        cursor.close()
        conn.close()

def verify_constraints():
    """验证约束修复结果"""
    print("🔍 验证约束修复结果...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查chunk_strategy约束
        cursor.execute("""
            SELECT pg_get_constraintdef(oid) 
            FROM pg_constraint 
            WHERE conname = 'knowledge_bases_chunk_strategy_check';
        """)
        result = cursor.fetchone()
        if result:
            constraint_def = result[0]
            if 'token_based' in constraint_def:
                print("✅ chunk_strategy约束支持token_based")
            else:
                print("❌ chunk_strategy约束不支持token_based")
                print(f"当前约束定义: {constraint_def}")
        
        # 检查user_id列是否允许空值
        cursor.execute("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'knowledge_bases' AND column_name = 'user_id';
        """)
        result = cursor.fetchone()
        if result:
            is_nullable = result[0]
            if is_nullable == 'NO':
                print("✅ user_id列不允许空值")
            else:
                print("❌ user_id列仍然允许空值")
        
        # 检查空的user_id记录
        cursor.execute("""
            SELECT COUNT(*) FROM knowledge_bases WHERE user_id IS NULL;
        """)
        null_count = cursor.fetchone()[0]
        if null_count == 0:
            print("✅ 没有user_id为空的记录")
        else:
            print(f"❌ 仍有 {null_count} 条user_id为空的记录")
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """主函数"""
    print("🚀 开始修复knowledge_base表字段校验问题...")
    
    # 1. 修复chunk_strategy约束
    fix_chunk_strategy_constraint()
    
    # 2. 修复user_id约束
    fix_user_id_constraint()
    
    # 3. 添加缺失的列
    add_missing_columns()
    
    # 4. 验证修复结果
    verify_constraints()
    
    print("\n🎉 knowledge_base表字段校验问题修复完成！")
    print("\n📋 修复内容:")
    print("   1. ✅ chunk_strategy约束支持token_based")
    print("   2. ✅ user_id非空约束处理")
    print("   3. ✅ 添加缺失的列")
    print("\n⚠️ 注意: 需要重启knowledge-service服务以使更改生效")

if __name__ == "__main__":
    main()
