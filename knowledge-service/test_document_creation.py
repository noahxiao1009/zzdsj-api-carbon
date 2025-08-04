#!/usr/bin/env python3
"""
测试Document创建
"""

from app.models.database import get_db
from app.models.knowledge_models import Document
from app.repositories import DocumentRepository

async def test_document_creation():
    """测试Document创建"""
    db = next(get_db())
    try:
        doc_repo = DocumentRepository(db)
        
        # 测试数据
        document_data = {
            "kb_id": "2337adac-4659-4802-aeec-4143f38a354e",
            "original_filename": "test.md",
            "file_path": "test/path.md",
            "file_type": ".md",
            "file_size": 100,
            "chunk_count": 5,
            "status": "completed",
            "title": "测试文档"
        }
        
        print("测试Document创建...")
        doc = await doc_repo.create(document_data)
        print(f"✅ Document创建成功: {doc.id}")
        
        # 清理测试数据
        db.delete(doc)
        db.commit()
        print("✅ 测试数据已清理")
        
    except Exception as e:
        print(f"❌ Document创建失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_document_creation()) 