"""
模型服务完整功能测试
测试所有API接口和核心功能
"""

import asyncio
import httpx
import json
import pytest
from datetime import datetime
from typing import Dict, Any

# 测试配置
BASE_URL = "http://localhost:8003"
TEST_USER_ID = "test_user_123"

class ModelServiceTester:
    """模型服务测试器"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    # ==================== 基础功能测试 ====================
    
    async def test_health_check(self):
        """测试健康检查"""
        print("🔍 测试健康检查...")
        
        response = await self.client.get(f"{self.base_url}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "model-service"
        
        print("✅ 健康检查通过")
        return data
    
    async def test_root_endpoint(self):
        """测试根路径"""
        print("🔍 测试根路径...")
        
        response = await self.client.get(f"{self.base_url}/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service"] == "model-service"
        assert "endpoints" in data
        
        print("✅ 根路径测试通过")
        return data
    
    # ==================== 提供商管理测试 ====================
    
    async def test_get_providers(self):
        """测试获取提供商列表"""
        print("🔍 测试获取提供商列表...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/providers")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert len(data["data"]) > 0
        
        # 验证提供商信息结构
        provider = data["data"][0]
        required_fields = ["id", "name", "display_name", "description", "is_configured", "is_enabled"]
        for field in required_fields:
            assert field in provider
        
        print(f"✅ 获取到 {len(data['data'])} 个提供商")
        return data["data"]
    
    async def test_configure_provider(self):
        """测试配置提供商"""
        print("🔍 测试配置提供商...")
        
        config_data = {
            "api_key": "test_api_key_12345",
            "api_base": "https://api.test.com/v1"
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/models/providers/zhipu/configure",
            json=config_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["data"]["provider_id"] == "zhipu"
        assert data["data"]["is_configured"] == True
        
        print("✅ 提供商配置成功")
        return data
    
    async def test_test_provider_connection(self):
        """测试提供商连接"""
        print("🔍 测试提供商连接...")
        
        response = await self.client.post(f"{self.base_url}/api/v1/models/providers/zhipu/test")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "test_result" in data["data"]
        assert data["data"]["test_result"]["success"] == True
        
        print("✅ 提供商连接测试通过")
        return data
    
    async def test_select_models(self):
        """测试选择启用模型"""
        print("🔍 测试选择启用模型...")
        
        selected_models = ["glm-4", "embedding-2"]
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/models/providers/zhipu/models/select",
            json={"selected_models": selected_models}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["data"]["enabled_models"] == selected_models
        
        print(f"✅ 成功启用 {len(selected_models)} 个模型")
        return data
    
    # ==================== 模型管理测试 ====================
    
    async def test_get_models(self):
        """测试获取模型列表"""
        print("🔍 测试获取模型列表...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "models" in data["data"]
        
        models = data["data"]["models"]
        if models:
            model = models[0]
            required_fields = ["id", "model_id", "name", "provider_id", "model_type"]
            for field in required_fields:
                assert field in model
        
        print(f"✅ 获取到 {len(models)} 个模型")
        return models
    
    async def test_get_model_details(self):
        """测试获取模型详情"""
        print("🔍 测试获取模型详情...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/zhipu/glm-4")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["data"]["model_id"] == "glm-4"
        assert data["data"]["provider_id"] == "zhipu"
        
        print("✅ 模型详情获取成功")
        return data["data"]
    
    async def test_test_model(self):
        """测试模型调用"""
        print("🔍 测试模型调用...")
        
        test_request = {
            "message": "你好，这是一个测试消息",
            "temperature": 0.7,
            "max_tokens": 100
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/models/zhipu/glm-4/test",
            json=test_request
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "response" in data
        assert "latency" in data
        
        print(f"✅ 模型测试成功，延迟: {data['latency']}ms")
        return data
    
    # ==================== 默认模型管理测试 ====================
    
    async def test_get_providers_organized(self):
        """测试按类别组织的提供商列表"""
        print("🔍 测试按类别组织的提供商列表...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/providers/organized")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        
        # 验证分类结构
        categories = ["domestic_major", "domestic_emerging", "international", "open_source"]
        for category in categories:
            if category in data["data"]:
                assert "providers" in data["data"][category]
                assert "category_name" in data["data"][category]
        
        print("✅ 按类别组织的提供商列表获取成功")
        return data
    
    async def test_get_models_by_category(self):
        """测试按类别组织的模型列表"""
        print("🔍 测试按类别组织的模型列表...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/models/by-category")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        
        # 验证模型类别
        model_categories = ["chat_models", "embedding_models", "multimodal_models"]
        for category in model_categories:
            if category in data["data"]:
                assert "models" in data["data"][category]
                assert "category_name" in data["data"][category]
        
        print("✅ 按类别组织的模型列表获取成功")
        return data
    
    async def test_set_default_model(self):
        """测试设置默认模型"""
        print("🔍 测试设置默认模型...")
        
        request_data = {
            "provider_id": "zhipu",
            "model_id": "glm-4",
            "config_params": {
                "temperature": 0.7,
                "max_tokens": 4000
            },
            "scope": "system"
        }
        
        response = await self.client.put(
            f"{self.base_url}/api/v1/models/defaults/chat",
            json=request_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["data"]["provider_id"] == "zhipu"
        assert data["data"]["model_id"] == "glm-4"
        
        print("✅ 默认模型设置成功")
        return data
    
    async def test_get_default_models(self):
        """测试获取默认模型配置"""
        print("🔍 测试获取默认模型配置...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/defaults")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "defaults" in data["data"]
        
        print(f"✅ 获取到 {len(data['data']['defaults'])} 个默认配置")
        return data
    
    # ==================== 模型调用接口测试 ====================
    
    async def test_chat_completion(self):
        """测试聊天补全接口"""
        print("🔍 测试聊天补全接口...")
        
        request_data = {
            "provider_id": "zhipu",
            "model_id": "glm-4",
            "messages": [
                {"role": "user", "content": "你好，请介绍一下你自己"}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
            "stream": False
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/models/chat/completions",
            json=request_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        
        print("✅ 聊天补全接口测试成功")
        return data
    
    async def test_text_embedding(self):
        """测试文本嵌入接口"""
        print("🔍 测试文本嵌入接口...")
        
        request_data = {
            "provider_id": "zhipu",
            "model_id": "embedding-2",
            "input": ["这是一个测试文本", "这是另一个测试文本"],
            "encoding_format": "float"
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/models/embeddings",
            json=request_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2  # 两个输入文本
        
        print("✅ 文本嵌入接口测试成功")
        return data
    
    # ==================== 监控接口测试 ====================
    
    async def test_get_realtime_metrics(self):
        """测试获取实时指标"""
        print("🔍 测试获取实时指标...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/usage/realtime")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        
        metrics = data["data"]
        expected_fields = ["total_calls", "total_tokens", "avg_latency", "error_rate"]
        for field in expected_fields:
            assert field in metrics
        
        print("✅ 实时指标获取成功")
        return data
    
    async def test_get_model_statistics(self):
        """测试获取模型统计"""
        print("🔍 测试获取模型统计...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/management/statistics")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        
        stats = data["data"]
        expected_fields = ["total_providers", "configured_providers", "total_models", "enabled_models"]
        for field in expected_fields:
            assert field in stats
        
        print("✅ 模型统计获取成功")
        return data
    
    async def test_get_dashboard_data(self):
        """测试获取仪表板数据"""
        print("🔍 测试获取仪表板数据...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/models/dashboard")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        
        dashboard = data["data"]
        expected_sections = ["overview", "models", "trends"]
        for section in expected_sections:
            assert section in dashboard
        
        print("✅ 仪表板数据获取成功")
        return data
    
    # ==================== 用户配置测试 ====================
    
    async def test_save_user_config(self):
        """测试保存用户配置"""
        print("🔍 测试保存用户配置...")
        
        config_data = {
            "name": "我的GLM-4配置",
            "category": "chat",
            "provider_id": "zhipu",
            "model_id": "glm-4",
            "config_params": {
                "temperature": 0.8,
                "max_tokens": 2000,
                "top_p": 0.95
            },
            "is_default": True,
            "user_id": TEST_USER_ID
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/models/user-configs",
            json=config_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["data"]["name"] == "我的GLM-4配置"
        assert data["data"]["user_id"] == TEST_USER_ID
        
        print("✅ 用户配置保存成功")
        return data["data"]["id"]  # 返回配置ID供后续测试使用
    
    async def test_get_user_configs(self):
        """测试获取用户配置列表"""
        print("🔍 测试获取用户配置列表...")
        
        response = await self.client.get(
            f"{self.base_url}/api/v1/models/user-configs",
            params={"user_id": TEST_USER_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "configs" in data["data"]
        
        print(f"✅ 获取到 {len(data['data']['configs'])} 个用户配置")
        return data["data"]["configs"]
    
    # ==================== 综合测试 ====================
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始模型服务完整功能测试...\n")
        
        try:
            # 基础功能测试
            await self.test_health_check()
            await self.test_root_endpoint()
            
            # 提供商管理测试
            await self.test_get_providers()
            await self.test_configure_provider()
            await self.test_test_provider_connection()
            await self.test_select_models()
            
            # 模型管理测试
            await self.test_get_models()
            await self.test_get_model_details()
            await self.test_test_model()
            
            # 默认模型管理测试
            await self.test_get_providers_organized()
            await self.test_get_models_by_category()
            await self.test_set_default_model()
            await self.test_get_default_models()
            
            # 模型调用接口测试
            await self.test_chat_completion()
            await self.test_text_embedding()
            
            # 监控接口测试
            await self.test_get_realtime_metrics()
            await self.test_get_model_statistics()
            await self.test_get_dashboard_data()
            
            # 用户配置测试
            config_id = await self.test_save_user_config()
            await self.test_get_user_configs()
            
            print("\n🎉 所有测试通过！模型服务功能正常")
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            raise


async def main():
    """主测试函数"""
    print("=" * 60)
    print("模型服务完整功能测试")
    print("=" * 60)
    
    async with ModelServiceTester() as tester:
        await tester.run_all_tests()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())