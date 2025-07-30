"""
测试MinIO和Redis连接
验证配置是否正确
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config.settings import settings
from app.utils.minio_client import test_minio_connection, get_minio_client
from app.queues.redis_queue import get_redis_queue

async def test_all_connections():
    """测试所有连接"""
    print("=" * 60)
    print("NextAgent - 知识库服务连接测试")
    print("=" * 60)
    
    # 1. 测试配置加载
    print("\n1. 配置信息:")
    print(f"   MinIO端点: {settings.storage.minio_endpoint}")
    print(f"   MinIO存储桶: {settings.storage.minio_bucket_name}")
    print(f"   存储后端: {settings.storage.storage_backend}")
    print(f"   Redis URL: {settings.get_redis_url()}")
    print(f"   默认队列: {settings.processing.default_queue_name}")
    print(f"   工作进程数: {settings.processing.worker_concurrency}")
    
    # 2. 测试MinIO连接
    print("\n2. 测试MinIO连接:")
    try:
        minio_result = test_minio_connection()
        if minio_result:
            print("   ✅ MinIO连接成功")
            
            # 测试MinIO客户端详细信息
            client = get_minio_client()
            bucket_name = settings.storage.minio_bucket_name
            
            # 检查存储桶是否存在
            bucket_exists = client.bucket_exists(bucket_name)
            print(f"   📦 存储桶 '{bucket_name}' 存在: {bucket_exists}")
            
            # 列出存储桶内容（前5个文件）
            try:
                objects = list(client.list_objects(bucket_name, recursive=True))
                print(f"   📄 存储桶文件数量: {len(objects)}")
                if objects:
                    print("   📋 最近文件:")
                    for obj in objects[:5]:
                        print(f"      - {obj.object_name} ({obj.size} bytes)")
            except Exception as e:
                print(f"   ⚠️  无法列出文件: {e}")
                
        else:
            print("   ❌ MinIO连接失败")
            return False
            
    except Exception as e:
        print(f"   ❌ MinIO测试异常: {e}")
        return False
    
    # 3. 测试Redis连接
    print("\n3. 测试Redis连接:")
    try:
        redis_queue = get_redis_queue()
        health = await redis_queue.health_check()
        
        if health.get("status") == "healthy":
            print("   ✅ Redis连接成功")
            print(f"   📊 队列长度: {health.get('default_queue_length', 0)}")
            print(f"   📈 总任务数: {health.get('total_tasks', 0)}")
            print(f"   🏓 Ping响应: {health.get('redis_ping', False)}")
        else:
            print(f"   ❌ Redis连接不健康: {health}")
            return False
            
    except Exception as e:
        print(f"   ❌ Redis测试异常: {e}")
        return False
    
    # 4. 测试队列操作
    print("\n4. 测试队列操作:")
    try:
        redis_queue = get_redis_queue()
        
        # 测试任务入队
        from app.queues.task_models import TaskModel, TaskTypes
        test_task = TaskModel(
            task_type=TaskTypes.DOCUMENT_PROCESSING,
            metadata={"test": True, "description": "连接测试任务"}
        )
        
        success = await redis_queue.enqueue_task(test_task, "test_queue")
        if success:
            print("   ✅ 任务入队成功")
            
            # 测试任务查询
            task_info = await redis_queue.get_task(test_task.task_id)
            if task_info:
                print("   ✅ 任务查询成功")
                print(f"      任务ID: {task_info.task_id}")
                print(f"      状态: {task_info.status.value}")
                
                # 清理测试任务
                await redis_queue.delete_task(test_task.task_id)
                print("   🧹 测试任务已清理")
            else:
                print("   ⚠️  任务查询失败")
        else:
            print("   ❌ 任务入队失败")
            
    except Exception as e:
        print(f"   ❌ 队列操作测试异常: {e}")
        return False
    
    # 5. 测试文件上传流程
    print("\n5. 测试文件上传流程:")
    try:
        import io
        from app.utils.minio_client import upload_to_minio, download_from_minio, delete_from_minio
        
        # 创建测试文件
        test_content = b"This is a test file for connection validation."
        test_filename = "test/connection_test.txt"
        file_data = io.BytesIO(test_content)
        
        # 上传测试文件
        upload_success = upload_to_minio(test_filename, file_data, "text/plain")
        if upload_success:
            print("   ✅ 测试文件上传成功")
            
            # 下载测试文件
            downloaded_content = download_from_minio(test_filename)
            if downloaded_content == test_content:
                print("   ✅ 测试文件下载验证成功")
            else:
                print("   ⚠️  文件内容验证失败")
            
            # 删除测试文件
            delete_success = delete_from_minio(test_filename)
            if delete_success:
                print("   🧹 测试文件已清理")
            else:
                print("   ⚠️  测试文件清理失败")
        else:
            print("   ❌ 测试文件上传失败")
            
    except Exception as e:
        print(f"   ❌ 文件上传测试异常: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有连接测试通过！知识库服务已准备就绪。")
    print("=" * 60)
    
    print("\n📋 下一步操作:")
    print("   1. 重启知识库服务: pm2 restart knowledge-service")
    print("   2. 启动任务处理器: python start_worker.py")
    print("   3. 测试文件上传: curl -X POST .../upload-async")
    
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_all_connections())
        if not result:
            print("\n❌ 连接测试失败，请检查配置！")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试脚本异常: {e}")
        sys.exit(1)