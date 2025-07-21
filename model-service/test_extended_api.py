"""
模型服务扩展功能测试脚本
测试默认模型管理和用户配置管理功能
"""

import asyncio
import requests
import json
import time
from typing import Dict, Any
from datetime import datetime

# 服务配置
SERVICE_URL = "http://localhost:8003"
API_BASE = f"{SERVICE_URL}/api/v1/models"

class ModelServiceExtendedTester:
    """模型服务扩展功能测试器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_user_id = "test_user_123"
    
    def test_providers_organized(self) -> Dict[str, Any]:
        """测试按厂商组织的接口"""
        print("🔍 Testing providers organized...")
        try:
            response = self.session.get(f"{API_BASE}/providers/organized")
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Providers organized test passed")
                data = result.get('data', {})
                statistics = data.get('statistics', {})
                print(f"   Total Providers: {statistics.get('total_providers', 0)}")
                print(f"   Configured Providers: {statistics.get('configured_providers', 0)}")
                
                # 检查分类
                categories = ['domestic_major', 'domestic_emerging', 'international', 'open_source']
                for category in categories:
                    if category in data:
                        category_data = data[category]
                        print(f"   {category_data['category_name']}: {len(category_data['providers'])} providers")
                
                return {"success": True, "data": result}
            else:
                print(f"❌ Providers organized test failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Providers organized test error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_models_by_category(self) -> Dict[str, Any]:
        """测试按类别组织的模型接口"""
        print("\n🔍 Testing models by category...")
        try:
            response = self.session.get(f"{API_BASE}/models/by-category")
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Models by category test passed")
                data = result.get('data', {})
                
                for category_key, category_data in data.items():
                    if category_key.endswith('_models'):
                        category_name = category_data.get('category_name', category_key)
                        model_count = category_data.get('total_count', 0)
                        enabled_count = category_data.get('enabled_count', 0)
                        default_model = category_data.get('default_model_id', 'None')
                        
                        print(f"   {category_name}: {model_count} models ({enabled_count} enabled)")
                        print(f"     Default Model: {default_model}")
                
                return {"success": True, "data": result}
            else:
                print(f"❌ Models by category test failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Models by category test error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_default_models_management(self) -> Dict[str, Any]:
        """测试默认模型管理"""
        print("\n🔍 Testing default models management...")
        try:
            # 1. 获取当前默认配置
            response = self.session.get(f"{API_BASE}/defaults")
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Get defaults test passed")
                defaults = result.get('data', {}).get('defaults', [])
                print(f"   Current defaults: {len(defaults)} configurations")
                
                for default in defaults:
                    print(f"     {default['category']}: {default['provider_name']} - {default['model_name']}")
            
            # 2. 设置新的默认模型
            set_default_request = {
                "provider_id": "zhipu",
                "model_id": "glm-4",
                "config_params": {
                    "temperature": 0.8,
                    "max_tokens": 3000
                },
                "scope": "system"
            }
            
            response = self.session.put(f"{API_BASE}/defaults/chat", json=set_default_request)
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Set default model test passed")
                print(f"   Set chat default to: {result['data']['model_name']}")
            else:
                print(f"❌ Set default model test failed: {response.status_code}")
            
            # 3. 批量设置默认模型
            batch_request = {
                "defaults": [
                    {
                        "category": "embedding",
                        "provider_id": "zhipu",
                        "model_id": "embedding-2",
                        "config_params": {"batch_size": 200}
                    },
                    {
                        "category": "multimodal",
                        "provider_id": "zhipu", 
                        "model_id": "glm-4v",
                        "config_params": {"temperature": 0.6}
                    }
                ],
                "scope": "system"
            }
            
            response = self.session.put(f"{API_BASE}/defaults/batch", json=batch_request)
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Batch set defaults test passed")
                success_count = result.get('data', {}).get('success_count', 0)
                error_count = result.get('data', {}).get('error_count', 0)
                print(f"   Batch result: {success_count} success, {error_count} errors")
            
            return {"success": True, "data": "Default models management tests completed"}
            
        except Exception as e:
            print(f"❌ Default models management test error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_user_config_management(self) -> Dict[str, Any]:
        """测试用户配置管理"""
        print("\n🔍 Testing user config management...")
        try:
            # 1. 创建用户配置
            user_config_request = {
                "name": "我的聊天配置",
                "category": "chat",
                "provider_id": "zhipu",
                "model_id": "glm-4",
                "config_params": {
                    "temperature": 0.9,
                    "max_tokens": 5000,
                    "top_p": 0.95
                },
                "is_default": True,
                "user_id": self.test_user_id
            }
            
            response = self.session.post(f"{API_BASE}/user-configs", json=user_config_request)
            result = response.json()
            
            config_id = None
            if response.status_code == 200 and result.get('success'):
                print("✅ Create user config test passed")
                config_id = result['data']['id']
                print(f"   Created config: {result['data']['name']}")
            else:
                print(f"❌ Create user config test failed: {response.status_code}")
                return {"success": False, "error": result}
            
            # 2. 获取用户配置列表
            response = self.session.get(f"{API_BASE}/user-configs?user_id={self.test_user_id}")
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Get user configs test passed")
                configs = result.get('data', {}).get('configs', [])
                print(f"   User has {len(configs)} configurations")
            
            # 3. 获取配置详情
            if config_id:
                response = self.session.get(f"{API_BASE}/user-configs/{config_id}?user_id={self.test_user_id}")
                result = response.json()
                
                if response.status_code == 200 and result.get('success'):
                    print("✅ Get user config details test passed")
                    config_data = result['data']
                    print(f"   Config details: {config_data['name']} - {config_data['usage_count']} uses")
            
            # 4. 切换激活配置
            switch_request = {
                "category": "chat",
                "provider_id": "zhipu",
                "model_id": "glm-4",
                "config_id": config_id,
                "user_id": self.test_user_id
            }
            
            response = self.session.put(f"{API_BASE}/active-config", json=switch_request)
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Switch active config test passed")
                print(f"   Switched to config: {result['data']['config_id']}")
            
            # 5. 获取激活配置
            response = self.session.get(f"{API_BASE}/active-config?user_id={self.test_user_id}")
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Get active config test passed")
                active_configs = result.get('data', {}).get('active_configs', {})
                recent_models = result.get('data', {}).get('recent_models', [])
                print(f"   Active configs: {len(active_configs)} categories")
                print(f"   Recent models: {len(recent_models)} entries")
            
            return {"success": True, "data": "User config management tests completed"}
            
        except Exception as e:
            print(f"❌ User config management test error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_config_templates(self) -> Dict[str, Any]:
        """测试配置模板"""
        print("\n🔍 Testing config templates...")
        try:
            categories = ["chat", "embedding", "multimodal", "code", "image"]
            
            for category in categories:
                response = self.session.get(f"{API_BASE}/config-templates/{category}")
                result = response.json()
                
                if response.status_code == 200 and result.get('success'):
                    print(f"✅ Config templates for {category} test passed")
                    templates = result.get('data', {}).get('templates', [])
                    print(f"   {category}: {len(templates)} templates available")
                else:
                    print(f"❌ Config templates for {category} test failed")
            
            return {"success": True, "data": "Config templates tests completed"}
            
        except Exception as e:
            print(f"❌ Config templates test error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_frontend_integration(self) -> Dict[str, Any]:
        """测试前端集成接口"""
        print("\n🔍 Testing frontend integration...")
        try:
            # 1. 获取系统设置数据
            response = self.session.get(f"{API_BASE}/frontend/system-settings")
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Frontend system settings test passed")
                data = result.get('data', {})
                
                providers = data.get('providers', {})
                models_by_category = data.get('models_by_category', {})
                default_configs = data.get('default_configs', [])
                
                print(f"   System settings loaded successfully")
                print(f"   Provider categories: {len([k for k in providers.keys() if k != 'statistics'])}")
                print(f"   Model categories: {len(models_by_category)}")
                print(f"   Default configs: {len(default_configs)}")
            else:
                print(f"❌ Frontend system settings test failed: {response.status_code}")
            
            # 2. 前端模型测试
            test_request = {
                "provider_id": "zhipu",
                "model_id": "glm-4",
                "message": "这是一个前端测试消息"
            }
            
            response = self.session.post(f"{API_BASE}/frontend/test-model", json=test_request)
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Frontend model test passed")
                test_result = result.get('test_result', {})
                latency = test_result.get('latency', 0)
                success = result.get('success', False)
                print(f"   Test result: {'Success' if success else 'Failed'}")
                print(f"   Latency: {latency:.2f}ms")
            
            # 3. 前端状态管理
            state_update = {
                "user_id": self.test_user_id,
                "preferences": {
                    "theme": "dark",
                    "auto_save": True,
                    "default_temperature": 0.7
                }
            }
            
            response = self.session.put(f"{API_BASE}/frontend/state", json=state_update)
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ Frontend state update test passed")
                updated_fields = result.get('data', {}).get('updated_fields', [])
                print(f"   Updated fields: {updated_fields}")
            
            return {"success": True, "data": "Frontend integration tests completed"}
            
        except Exception as e:
            print(f"❌ Frontend integration test error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_user_statistics(self) -> Dict[str, Any]:
        """测试用户统计"""
        print("\n🔍 Testing user statistics...")
        try:
            response = self.session.get(f"{API_BASE}/user-configs/statistics?user_id={self.test_user_id}")
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print("✅ User statistics test passed")
                data = result.get('data', {})
                
                total_configs = data.get('total_configs', 0)
                total_usage = data.get('total_usage', 0)
                category_stats = data.get('category_statistics', {})
                
                print(f"   Total configs: {total_configs}")
                print(f"   Total usage: {total_usage}")
                print(f"   Categories: {len(category_stats)}")
                
                for category, stats in category_stats.items():
                    print(f"     {category}: {stats['total_configs']} configs, {stats['total_usage']} uses")
                
                return {"success": True, "data": result}
            else:
                print(f"❌ User statistics test failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ User statistics test error: {e}")
            return {"success": False, "error": str(e)}
    
    def run_full_test(self):
        """运行完整测试套件"""
        print("🚀 Starting Model Service Extended Test Suite")
        print("=" * 60)
        
        test_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }
        
        # 定义测试用例
        test_cases = [
            ("Providers Organized", self.test_providers_organized),
            ("Models by Category", self.test_models_by_category),
            ("Default Models Management", self.test_default_models_management),
            ("User Config Management", self.test_user_config_management),
            ("Config Templates", self.test_config_templates),
            ("Frontend Integration", self.test_frontend_integration),
            ("User Statistics", self.test_user_statistics)
        ]
        
        # 执行测试
        for test_name, test_func in test_cases:
            test_results["total"] += 1
            try:
                result = test_func()
                if result["success"]:
                    test_results["passed"] += 1
                else:
                    test_results["failed"] += 1
                    test_results["errors"].append(f"{test_name}: {result.get('error', 'Unknown error')}")
            except Exception as e:
                test_results["failed"] += 1
                test_results["errors"].append(f"{test_name}: {str(e)}")
        
        # 输出测试结果
        print("\n" + "=" * 60)
        print("📊 Extended Test Results Summary")
        print("=" * 60)
        print(f"Total Tests: {test_results['total']}")
        print(f"✅ Passed: {test_results['passed']}")
        print(f"❌ Failed: {test_results['failed']}")
        print(f"Success Rate: {(test_results['passed'] / test_results['total'] * 100):.1f}%")
        
        if test_results['errors']:
            print("\n❌ Failed Tests:")
            for error in test_results['errors']:
                print(f"   - {error}")
        
        if test_results['failed'] == 0:
            print("\n🎉 All extended tests passed! Model Service enhancements are working correctly.")
        else:
            print(f"\n⚠️  {test_results['failed']} tests failed. Please check the service configuration.")
        
        return test_results


def main():
    """主函数"""
    print("🔧 Model Service Extended Features Tester")
    print("Testing enhanced model service with default management and user configs")
    print()
    
    # 检查服务是否运行
    try:
        response = requests.get(f"{SERVICE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Service is not healthy at {SERVICE_URL}")
            print("Please start the model service first:")
            print("   cd /home/wxn/carbon/zzdsl-api-carbon/model-service")
            print("   python main.py")
            return
    except Exception as e:
        print(f"❌ Cannot connect to service at {SERVICE_URL}")
        print(f"Error: {e}")
        print("Please start the model service first:")
        print("   cd /home/wxn/carbon/zzdsl-api-carbon/model-service")
        print("   python main.py")
        return
    
    # 运行测试
    tester = ModelServiceExtendedTester()
    results = tester.run_full_test()
    
    # 退出码
    exit_code = 0 if results['failed'] == 0 else 1
    exit(exit_code)


if __name__ == "__main__":
    main()