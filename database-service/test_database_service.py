"""
数据库服务测试脚本
用于测试数据库服务的基本功能
"""

import asyncio
import httpx
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8089"


async def test_service_health():
    """测试服务健康状态"""
    print("🔍 测试服务健康状态...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 服务健康状态: {data['status']}")
                return True
            else:
                print(f"❌ 健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 连接服务失败: {e}")
            return False


async def test_database_status():
    """测试数据库状态"""
    print("\n🔍 测试数据库状态...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/api/database/status")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 数据库整体状态: {data['status']['overall_status']}")
                
                # 显示各数据库状态
                for db_name, db_status in data['status']['databases'].items():
                    status_icon = "✅" if db_status['status'] == 'healthy' else "❌"
                    print(f"  {status_icon} {db_name}: {db_status['status']}")
                
                return True
            else:
                print(f"❌ 获取数据库状态失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 获取数据库状态失败: {e}")
            return False


async def test_connection_info():
    """测试连接信息"""
    print("\n🔍 测试连接信息...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/api/database/connections")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 服务名称: {data['service_name']}")
                print(f"✅ 服务端口: {data['service_port']}")
                print(f"✅ 支持的数据库数量: {len(data['configurations'])}")
                return True
            else:
                print(f"❌ 获取连接信息失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 获取连接信息失败: {e}")
            return False


async def test_database_connection(db_type: str):
    """测试特定数据库连接"""
    print(f"\n🔍 测试 {db_type} 数据库连接...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/api/database/connections/test/{db_type}")
            if response.status_code == 200:
                data = response.json()
                result_icon = "✅" if data['test_result'] == 'success' else "❌"
                print(f"{result_icon} {db_type} 连接测试: {data['test_result']}")
                if data.get('response_time'):
                    print(f"  响应时间: {data['response_time']:.3f}s")
                if data.get('error_message'):
                    print(f"  错误信息: {data['error_message']}")
                return data['test_result'] == 'success'
            else:
                print(f"❌ {db_type} 连接测试失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ {db_type} 连接测试失败: {e}")
            return False


async def test_service_config():
    """测试服务配置"""
    print("\n🔍 测试服务配置...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/api/database/config")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 调试模式: {data['debug']}")
                print(f"✅ 健康检查启用: {data['health_check_enabled']}")
                print(f"✅ 监控启用: {data['monitoring_enabled']}")
                print(f"✅ 网关注册启用: {data['gateway_enabled']}")
                return True
            else:
                print(f"❌ 获取服务配置失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 获取服务配置失败: {e}")
            return False


async def test_metrics():
    """测试监控指标"""
    print("\n🔍 测试监控指标...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/api/database/metrics")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 整体状态: {data['overall_status']}")
                print(f"✅ 数据库总数: {data['database_count']}")
                print(f"✅ 健康数据库: {data['healthy_databases']}")
                print(f"✅ 不健康数据库: {data['unhealthy_databases']}")
                print(f"✅ 平均响应时间: {data['average_response_time']:.3f}s")
                print(f"✅ 运行时间百分比: {data['uptime_percentage']:.1f}%")
                return True
            else:
                print(f"❌ 获取监控指标失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 获取监控指标失败: {e}")
            return False


async def test_registry_status():
    """测试网关注册状态"""
    print("\n🔍 测试网关注册状态...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/api/database/registry/status")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 服务ID: {data.get('service_id', 'N/A')}")
                print(f"✅ 注册状态: {data.get('status', 'N/A')}")
                return True
            else:
                print(f"❌ 获取注册状态失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 获取注册状态失败: {e}")
            return False


async def test_database_initialization():
    """测试数据库初始化"""
    print("\n🔍 测试数据库初始化...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(f"{BASE_URL}/api/database/migration/initialize")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 数据库初始化: {data['status']}")
                print(f"✅ 消息: {data['message']}")
                return True
            else:
                print(f"❌ 数据库初始化失败: {response.status_code}")
                if response.status_code != 404:  # 如果不是404错误，显示详细信息
                    try:
                        error_data = response.json()
                        print(f"  错误详情: {error_data}")
                    except:
                        print(f"  响应内容: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            return False


async def main():
    """主测试函数"""
    print("🚀 开始测试数据库管理微服务")
    print("=" * 50)
    
    # 基础服务测试
    health_ok = await test_service_health()
    if not health_ok:
        print("\n❌ 服务不健康，停止测试")
        return
    
    # 数据库状态测试
    await test_database_status()
    
    # 连接信息测试
    await test_connection_info()
    
    # 各数据库连接测试
    databases = ["postgresql", "elasticsearch", "milvus", "redis", "rabbitmq"]
    for db in databases:
        await test_database_connection(db)
    
    # 服务配置测试
    await test_service_config()
    
    # 监控指标测试
    await test_metrics()
    
    # 网关注册测试
    await test_registry_status()
    
    # 数据库初始化测试
    await test_database_initialization()
    
    print("\n" + "=" * 50)
    print("✅ 数据库管理微服务测试完成")


if __name__ == "__main__":
    asyncio.run(main())