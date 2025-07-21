#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能报告服务测试脚本
测试主要功能模块
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置基本环境变量
os.environ.setdefault("WORKSPACE_PATH", str(project_root / "test_workspace"))


async def test_config_loading():
    """测试配置加载"""
    print("🔧 测试配置加载...")
    
    try:
        from config.config import get_model_config
        config = get_model_config()
        print(f"✅ 配置加载成功: {config.get('model', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


async def test_database_models():
    """测试数据库模型"""
    print("🗄️ 测试数据库模型...")
    
    try:
        from app.models.database_models import User, Report, ReportFile
        
        # 测试模型定义
        user_fields = [column.name for column in User.__table__.columns]
        report_fields = [column.name for column in Report.__table__.columns]
        
        print(f"✅ 用户模型字段: {len(user_fields)} 个")
        print(f"✅ 报告模型字段: {len(report_fields)} 个")
        return True
    except Exception as e:
        print(f"❌ 数据库模型测试失败: {e}")
        return False


async def test_llm_integration():
    """测试LLM集成"""
    print("🤖 测试LLM集成...")
    
    try:
        from llm import get_plan_llm, get_act_llm, get_tool_llm, get_vision_llm
        
        # 测试获取模型实例
        plan_llm = get_plan_llm()
        act_llm = get_act_llm()
        tool_llm = get_tool_llm()
        vision_llm = get_vision_llm()
        
        print(f"✅ 规划模型: {type(plan_llm).__name__}")
        print(f"✅ 执行模型: {type(act_llm).__name__}")
        print(f"✅ 工具模型: {type(tool_llm).__name__}")
        print(f"✅ 视觉模型: {type(vision_llm).__name__}")
        return True
    except Exception as e:
        print(f"❌ LLM集成测试失败: {e}")
        return False


async def test_cosight_import():
    """测试CoSight导入"""
    print("🎯 测试CoSight导入...")
    
    try:
        from CoSight import CoSight
        print(f"✅ CoSight类导入成功: {CoSight}")
        
        # 测试核心组件导入
        from app.cosight.task.plan_report_manager import plan_report_event_manager
        from app.cosight.task.task_manager import TaskManager
        
        print("✅ 事件管理器导入成功")
        print("✅ 任务管理器导入成功")
        return True
    except Exception as e:
        print(f"❌ CoSight导入失败: {e}")
        return False


async def test_workspace_creation():
    """测试工作空间创建"""
    print("📁 测试工作空间创建...")
    
    try:
        workspace_path = Path(os.environ.get("WORKSPACE_PATH"))
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # 创建测试文件
        test_file = workspace_path / "test.txt"
        test_file.write_text("测试文件")
        
        if test_file.exists():
            print(f"✅ 工作空间创建成功: {workspace_path}")
            test_file.unlink()  # 清理测试文件
            return True
        else:
            print("❌ 工作空间创建失败")
            return False
    except Exception as e:
        print(f"❌ 工作空间测试失败: {e}")
        return False


async def test_shared_sdk():
    """测试共享SDK"""
    print("🔗 测试微服务通信SDK...")
    
    try:
        from shared.service_client import CallMethod, ServiceClient
        
        print(f"✅ CallMethod枚举: {list(CallMethod)}")
        print(f"✅ ServiceClient类导入成功")
        return True
    except Exception as e:
        print(f"❌ 共享SDK测试失败: {e}")
        return False


async def test_api_models():
    """测试API模型"""
    print("📋 测试API数据模型...")
    
    try:
        from main import ReportRequest, ReportResponse
        
        # 测试请求模型
        request = ReportRequest(
            query="测试查询",
            output_format="PDF",
            session_id="test_session"
        )
        
        # 测试响应模型
        response = ReportResponse(
            success=True,
            message="测试成功",
            session_id="test_session"
        )
        
        print(f"✅ 请求模型: {request.query}")
        print(f"✅ 响应模型: {response.message}")
        return True
    except Exception as e:
        print(f"❌ API模型测试失败: {e}")
        return False


async def test_logger():
    """测试日志记录"""
    print("📝 测试日志记录...")
    
    try:
        from app.common.logger_util import logger
        
        logger.info("测试信息日志")
        logger.warning("测试警告日志")
        logger.error("测试错误日志")
        
        print("✅ 日志记录功能正常")
        return True
    except Exception as e:
        print(f"❌ 日志测试失败: {e}")
        return False


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行智能报告服务测试套件...\n")
    
    tests = [
        ("配置加载", test_config_loading),
        ("数据库模型", test_database_models),
        ("LLM集成", test_llm_integration),
        ("CoSight导入", test_cosight_import),
        ("工作空间创建", test_workspace_creation),
        ("微服务SDK", test_shared_sdk),
        ("API模型", test_api_models),
        ("日志记录", test_logger)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
        print()  # 添加空行分隔
    
    # 统计结果
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print("=" * 60)
    print("🏁 测试结果摘要")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:<20} {status}")
    
    print("-" * 60)
    print(f"总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！服务基本功能正常。")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关配置和依赖。")
        return False


async def main():
    """主函数"""
    try:
        success = await run_all_tests()
        
        if success:
            print("\n✨ 测试完成，服务准备就绪！")
            print("\n💡 下一步:")
            print("1. 运行 'python start_service.py' 启动服务")
            print("2. 访问 http://localhost:8000/health 检查服务健康状态")
            print("3. 查看 http://localhost:8000/docs 查看API文档")
        else:
            print("\n⚠️ 部分测试失败，请解决问题后重新测试")
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())