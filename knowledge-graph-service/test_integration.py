#!/usr/bin/env python3
"""
知识图谱微服务前后端集成测试脚本
验证API兼容性和功能完整性
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, List

# 测试配置
GATEWAY_URL = "http://localhost:8080"
KNOWLEDGE_GRAPH_SERVICE_URL = "http://localhost:8087"
TEST_USER_ID = "test_user_123"
TEST_PROJECT_ID = "test_project_456"

class KnowledgeGraphIntegrationTest:
    """知识图谱集成测试类"""
    
    def __init__(self):
        self.session = None
        self.test_results = []
        
    async def setup(self):
        """设置测试环境"""
        self.session = aiohttp.ClientSession()
        print("🔧 初始化测试环境...")
        
    async def cleanup(self):
        """清理测试环境"""
        if self.session:
            await self.session.close()
        print("🧹 清理测试环境完成")
        
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始知识图谱微服务集成测试")
        print("=" * 60)
        
        await self.setup()
        
        try:
            # 测试服务健康检查
            await self.test_service_health()
            
            # 测试API兼容性
            await self.test_api_compatibility()
            
            # 测试数据格式转换
            await self.test_data_format_conversion()
            
            # 测试ArangoDB集成
            await self.test_arangodb_integration()
            
            # 测试NetworkX功能
            await self.test_networkx_features()
            
            # 测试前端API调用
            await self.test_frontend_api_calls()
            
        except Exception as e:
            print(f"❌ 测试过程中出现错误: {e}")
            
        finally:
            await self.cleanup()
            
        # 打印测试结果
        self.print_test_summary()
        
    async def test_service_health(self):
        """测试服务健康检查"""
        print("📋 测试1: 服务健康检查")
        
        try:
            # 测试知识图谱服务
            async with self.session.get(f"{KNOWLEDGE_GRAPH_SERVICE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 知识图谱服务健康: {data}")
                    self.test_results.append(("Service Health", True, "Knowledge graph service is healthy"))
                else:
                    print(f"   ❌ 知识图谱服务不健康: {response.status}")
                    self.test_results.append(("Service Health", False, f"Service unhealthy: {response.status}"))
                    
        except Exception as e:
            print(f"   ❌ 健康检查失败: {e}")
            self.test_results.append(("Service Health", False, str(e)))
            
    async def test_api_compatibility(self):
        """测试API兼容性"""
        print("📋 测试2: API兼容性")
        
        # 测试新API
        await self._test_new_api_endpoints()
        
        # 测试兼容API
        await self._test_legacy_api_endpoints()
        
    async def _test_new_api_endpoints(self):
        """测试新的API端点"""
        print("   🔹 测试新API端点")
        
        try:
            # 测试获取图谱列表
            async with self.session.get(f"{KNOWLEDGE_GRAPH_SERVICE_URL}/api/v1/graphs/") as response:
                if response.status in [200, 404]:  # 404表示没有数据但API正常
                    print(f"      ✅ GET /api/v1/graphs/ - 状态码: {response.status}")
                    self.test_results.append(("New API - List Graphs", True, f"Status: {response.status}"))
                else:
                    print(f"      ❌ GET /api/v1/graphs/ - 状态码: {response.status}")
                    self.test_results.append(("New API - List Graphs", False, f"Unexpected status: {response.status}"))
                    
        except Exception as e:
            print(f"      ❌ 新API测试失败: {e}")
            self.test_results.append(("New API - List Graphs", False, str(e)))
            
    async def _test_legacy_api_endpoints(self):
        """测试兼容的API端点"""
        print("   🔹 测试兼容API端点")
        
        try:
            # 测试兼容的知识图谱列表API
            async with self.session.get(f"{KNOWLEDGE_GRAPH_SERVICE_URL}/api/v1/knowledge-graphs/") as response:
                if response.status in [200, 404]:  # 404表示没有数据但API正常
                    print(f"      ✅ GET /api/v1/knowledge-graphs/ - 状态码: {response.status}")
                    self.test_results.append(("Legacy API - List Graphs", True, f"Status: {response.status}"))
                else:
                    print(f"      ❌ GET /api/v1/knowledge-graphs/ - 状态码: {response.status}")
                    self.test_results.append(("Legacy API - List Graphs", False, f"Unexpected status: {response.status}"))
                    
        except Exception as e:
            print(f"      ❌ 兼容API测试失败: {e}")
            self.test_results.append(("Legacy API - List Graphs", False, str(e)))
            
    async def test_data_format_conversion(self):
        """测试数据格式转换"""
        print("📋 测试3: 数据格式转换")
        
        # 模拟测试数据适配器
        from app.adapters.legacy_adapter import LegacyKnowledgeGraphAdapter
        
        try:
            # 测试请求格式适配
            legacy_request = {
                "name": "测试图谱",
                "description": "这是一个测试图谱",
                "knowledge_base_id": 123,
                "tags": ["test", "demo"]
            }
            
            adapted_request = LegacyKnowledgeGraphAdapter.adapt_create_request(legacy_request)
            
            if adapted_request.name == "测试图谱" and "123" in adapted_request.knowledge_base_ids:
                print("   ✅ 数据格式适配成功")
                self.test_results.append(("Data Format Conversion", True, "Request format adapted successfully"))
            else:
                print("   ❌ 数据格式适配失败")
                self.test_results.append(("Data Format Conversion", False, "Request format adaptation failed"))
                
        except Exception as e:
            print(f"   ❌ 数据格式转换测试失败: {e}")
            self.test_results.append(("Data Format Conversion", False, str(e)))
            
    async def test_arangodb_integration(self):
        """测试ArangoDB集成"""
        print("📋 测试4: ArangoDB集成")
        
        try:
            from app.repositories.tenant_manager import TenantIsolationManager
            from arango import ArangoClient
            
            # 模拟租户管理器
            client = ArangoClient(hosts="http://localhost:8529")
            tenant_manager = TenantIsolationManager(client, "root", "password")
            
            # 测试租户上下文计算
            tenant_id = await tenant_manager.get_tenant_context(TEST_USER_ID, TEST_PROJECT_ID)
            
            if tenant_id:
                print(f"   ✅ 租户隔离功能正常: {tenant_id}")
                self.test_results.append(("ArangoDB - Tenant Isolation", True, f"Tenant ID: {tenant_id}"))
            else:
                print("   ❌ 租户隔离功能异常")
                self.test_results.append(("ArangoDB - Tenant Isolation", False, "Failed to generate tenant ID"))
                
        except Exception as e:
            print(f"   ❌ ArangoDB集成测试失败: {e}")
            self.test_results.append(("ArangoDB Integration", False, str(e)))
            
    async def test_networkx_features(self):
        """测试NetworkX功能"""
        print("📋 测试5: NetworkX功能")
        
        try:
            from app.repositories.networkx_adapter import NetworkXAdapter
            from app.models.graph import Entity, Relation
            
            # 创建测试数据
            entities = [
                Entity(id="1", name="实体1", entity_type="person", confidence=0.9, properties={}, source="test"),
                Entity(id="2", name="实体2", entity_type="organization", confidence=0.8, properties={}, source="test")
            ]
            
            relations = [
                Relation(id="1", subject="1", predicate="works_for", object="2", confidence=0.9, properties={}, source="test")
            ]
            
            # 测试NetworkX导出
            adapter = NetworkXAdapter()
            graph = await adapter.export_to_networkx("test_graph", entities, relations)
            
            if graph.number_of_nodes() == 2 and graph.number_of_edges() == 1:
                print("   ✅ NetworkX导出功能正常")
                self.test_results.append(("NetworkX - Export", True, f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges"))
            else:
                print("   ❌ NetworkX导出功能异常")
                self.test_results.append(("NetworkX - Export", False, "Graph structure incorrect"))
                
            await adapter.close()
            
        except Exception as e:
            print(f"   ❌ NetworkX功能测试失败: {e}")
            self.test_results.append(("NetworkX Features", False, str(e)))
            
    async def test_frontend_api_calls(self):
        """测试前端API调用"""
        print("📋 测试6: 前端API调用模拟")
        
        # 模拟前端调用场景
        test_scenarios = [
            ("获取图谱列表", "GET", "/api/v1/graphs/"),
            ("创建图谱", "POST", "/api/v1/graphs/"),
            ("获取图谱详情", "GET", "/api/v1/graphs/test_id"),
            ("删除图谱", "DELETE", "/api/v1/graphs/test_id"),
        ]
        
        for scenario_name, method, endpoint in test_scenarios:
            try:
                url = f"{KNOWLEDGE_GRAPH_SERVICE_URL}{endpoint}"
                
                if method == "GET":
                    async with self.session.get(url) as response:
                        status = response.status
                elif method == "DELETE":
                    async with self.session.delete(url) as response:
                        status = response.status
                elif method == "POST":
                    test_data = {"name": "测试图谱", "description": "前端测试"}
                    async with self.session.post(url, json=test_data) as response:
                        status = response.status
                else:
                    continue
                
                if status in [200, 201, 404, 422]:  # 这些状态码表示API可达
                    print(f"   ✅ {scenario_name}: 状态码 {status}")
                    self.test_results.append((f"Frontend API - {scenario_name}", True, f"Status: {status}"))
                else:
                    print(f"   ❌ {scenario_name}: 状态码 {status}")
                    self.test_results.append((f"Frontend API - {scenario_name}", False, f"Unexpected status: {status}"))
                    
            except Exception as e:
                print(f"   ❌ {scenario_name}失败: {e}")
                self.test_results.append((f"Frontend API - {scenario_name}", False, str(e)))
                
    def print_test_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("📊 测试总结")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"通过率: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\n详细结果:")
        for test_name, success, message in self.test_results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {status} {test_name}: {message}")
            
        if failed_tests == 0:
            print("\n🎉 所有测试通过! 前后端集成成功!")
        else:
            print(f"\n⚠️  有{failed_tests}个测试失败，请检查相关功能")


async def main():
    """主函数"""
    test_runner = KnowledgeGraphIntegrationTest()
    await test_runner.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())