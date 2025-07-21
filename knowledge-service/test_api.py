"""
知识库微服务API测试脚本
验证第二阶段的API集成是否正常工作
"""

import asyncio
import requests
import json
import time
from pathlib import Path
from typing import Dict, Any

# 服务配置
SERVICE_URL = "http://localhost:8082"
API_BASE = f"{SERVICE_URL}/api/v1"

class KnowledgeServiceTester:
    """知识库服务测试器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def test_health(self) -> Dict[str, Any]:
        """测试健康检查"""
        print("🔍 Testing health check...")
        try:
            response = self.session.get(f"{SERVICE_URL}/health")
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Health check passed")
                print(f"   Status: {result.get('status')}")
                print(f"   Service: {result.get('service')}")
                print(f"   Version: {result.get('version')}")
                return {"success": True, "data": result}
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_root_endpoint(self) -> Dict[str, Any]:
        """测试根端点"""
        print("\n🔍 Testing root endpoint...")
        try:
            response = self.session.get(SERVICE_URL)
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Root endpoint passed")
                print(f"   Message: {result.get('message')}")
                print(f"   Features: {result.get('features', [])}")
                return {"success": True, "data": result}
            else:
                print(f"❌ Root endpoint failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_get_statistics(self) -> Dict[str, Any]:
        """测试获取统计信息"""
        print("\n🔍 Testing statistics endpoint...")
        try:
            response = self.session.get(f"{API_BASE}/knowledge-bases/statistics")
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Statistics endpoint passed")
                if result.get('success'):
                    stats = result.get('data', {})
                    print(f"   Unified Manager: {stats.get('unified_manager', {})}")
                    print(f"   Knowledge Bases: {stats.get('knowledge_bases', {})}")
                    print(f"   Chunks: {stats.get('chunks', {})}")
                return {"success": True, "data": result}
            else:
                print(f"❌ Statistics endpoint failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Statistics endpoint error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_list_knowledge_bases(self) -> Dict[str, Any]:
        """测试获取知识库列表"""
        print("\n🔍 Testing list knowledge bases...")
        try:
            response = self.session.get(f"{API_BASE}/knowledge-bases/")
            result = response.json()
            
            if response.status_code == 200:
                print("✅ List knowledge bases passed")
                if result.get('success'):
                    data = result.get('data', {})
                    kbs = data.get('knowledge_bases', [])
                    pagination = data.get('pagination', {})
                    print(f"   Total KBs: {pagination.get('total', 0)}")
                    print(f"   Current page: {pagination.get('page', 1)}")
                    print(f"   Page size: {pagination.get('page_size', 10)}")
                return {"success": True, "data": result}
            else:
                print(f"❌ List knowledge bases failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ List knowledge bases error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_create_knowledge_base(self) -> Dict[str, Any]:
        """测试创建知识库"""
        print("\n🔍 Testing create knowledge base...")
        try:
            test_kb = {
                "name": f"测试知识库_{int(time.time())}",
                "description": "这是一个API测试创建的知识库",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
                "embedding_dimension": 1536,
                "vector_store_type": "milvus",
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "similarity_threshold": 0.7,
                "enable_hybrid_search": True,
                "enable_agno_integration": True,
                "agno_search_type": "hybrid",
                "settings": {
                    "test_created": True,
                    "created_by": "api_test_script"
                }
            }
            
            response = self.session.post(f"{API_BASE}/knowledge-bases/", json=test_kb)
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Create knowledge base passed")
                if result.get('success'):
                    kb_data = result.get('data', {})
                    print(f"   KB ID: {kb_data.get('id')}")
                    print(f"   KB Name: {kb_data.get('name')}")
                    print(f"   LlamaIndex enabled: {result.get('frameworks', {}).get('llamaindex_enabled')}")
                    print(f"   Agno enabled: {result.get('frameworks', {}).get('agno_enabled')}")
                    return {"success": True, "data": result, "kb_id": kb_data.get('id')}
            else:
                print(f"❌ Create knowledge base failed: {response.status_code}")
                print(f"   Error: {result}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Create knowledge base error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_get_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """测试获取知识库详情"""
        print(f"\n🔍 Testing get knowledge base {kb_id}...")
        try:
            response = self.session.get(f"{API_BASE}/knowledge-bases/{kb_id}")
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Get knowledge base passed")
                if result.get('success'):
                    kb_data = result.get('data', {})
                    print(f"   KB Name: {kb_data.get('name')}")
                    print(f"   Status: {kb_data.get('status')}")
                    print(f"   Document Count: {kb_data.get('document_count', 0)}")
                    print(f"   Chunk Count: {kb_data.get('chunk_count', 0)}")
                return {"success": True, "data": result}
            else:
                print(f"❌ Get knowledge base failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Get knowledge base error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_search_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """测试搜索知识库"""
        print(f"\n🔍 Testing search knowledge base {kb_id}...")
        try:
            search_request = {
                "query": "这是一个测试搜索",
                "search_mode": "hybrid",
                "top_k": 5,
                "similarity_threshold": 0.7,
                "enable_reranking": True,
                "vector_weight": 0.7,
                "text_weight": 0.3,
                "agno_confidence_threshold": 0.6
            }
            
            response = self.session.post(f"{API_BASE}/knowledge-bases/{kb_id}/search", json=search_request)
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Search knowledge base passed")
                if result.get('success'):
                    data = result.get('data', {})
                    print(f"   Query: {data.get('query')}")
                    print(f"   Search Mode: {data.get('search_mode')}")
                    print(f"   Total Results: {data.get('total_results', 0)}")
                    print(f"   Search Time: {data.get('search_time', 0):.3f}s")
                    print(f"   LlamaIndex Results: {data.get('llamaindex_results', 0)}")
                    print(f"   Agno Results: {data.get('agno_results', 0)}")
                return {"success": True, "data": result}
            else:
                print(f"❌ Search knowledge base failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Search knowledge base error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_get_embedding_models(self) -> Dict[str, Any]:
        """测试获取嵌入模型列表"""
        print("\n🔍 Testing get embedding models...")
        try:
            response = self.session.get(f"{API_BASE}/knowledge-bases/models/embedding")
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Get embedding models passed")
                if result.get('success'):
                    data = result.get('data', {})
                    models = data.get('models', [])
                    print(f"   Total Models: {data.get('total', 0)}")
                    print(f"   Provider Counts: {data.get('provider_counts', {})}")
                    if models:
                        print(f"   First Model: {models[0].get('model_name')} ({models[0].get('provider')})")
                return {"success": True, "data": result}
            else:
                print(f"❌ Get embedding models failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Get embedding models error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_delete_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """测试删除知识库"""
        print(f"\n🔍 Testing delete knowledge base {kb_id}...")
        try:
            response = self.session.delete(f"{API_BASE}/knowledge-bases/{kb_id}")
            result = response.json()
            
            if response.status_code == 200:
                print("✅ Delete knowledge base passed")
                if result.get('success'):
                    data = result.get('data', {})
                    print(f"   KB ID: {data.get('kb_id')}")
                    print(f"   LlamaIndex deleted: {data.get('llamaindex_deleted')}")
                    print(f"   Agno deleted: {data.get('agno_deleted')}")
                return {"success": True, "data": result}
            else:
                print(f"❌ Delete knowledge base failed: {response.status_code}")
                return {"success": False, "error": result}
                
        except Exception as e:
            print(f"❌ Delete knowledge base error: {e}")
            return {"success": False, "error": str(e)}
    
    def run_full_test(self):
        """运行完整测试套件"""
        print("🚀 Starting Knowledge Service API Test Suite")
        print("=" * 50)
        
        # 测试统计
        test_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }
        
        # 1. 健康检查
        test_results["total"] += 1
        health_result = self.test_health()
        if health_result["success"]:
            test_results["passed"] += 1
        else:
            test_results["failed"] += 1
            test_results["errors"].append("Health check failed")
        
        # 2. 根端点
        test_results["total"] += 1
        root_result = self.test_root_endpoint()
        if root_result["success"]:
            test_results["passed"] += 1
        else:
            test_results["failed"] += 1
            test_results["errors"].append("Root endpoint failed")
        
        # 3. 统计信息
        test_results["total"] += 1
        stats_result = self.test_get_statistics()
        if stats_result["success"]:
            test_results["passed"] += 1
        else:
            test_results["failed"] += 1
            test_results["errors"].append("Statistics failed")
        
        # 4. 知识库列表
        test_results["total"] += 1
        list_result = self.test_list_knowledge_bases()
        if list_result["success"]:
            test_results["passed"] += 1
        else:
            test_results["failed"] += 1
            test_results["errors"].append("List knowledge bases failed")
        
        # 5. 嵌入模型列表
        test_results["total"] += 1
        models_result = self.test_get_embedding_models()
        if models_result["success"]:
            test_results["passed"] += 1
        else:
            test_results["failed"] += 1
            test_results["errors"].append("Get embedding models failed")
        
        # 6. 创建知识库
        test_results["total"] += 1
        create_result = self.test_create_knowledge_base()
        if create_result["success"]:
            test_results["passed"] += 1
            kb_id = create_result.get("kb_id")
            
            if kb_id:
                # 7. 获取知识库详情
                test_results["total"] += 1
                get_result = self.test_get_knowledge_base(kb_id)
                if get_result["success"]:
                    test_results["passed"] += 1
                else:
                    test_results["failed"] += 1
                    test_results["errors"].append("Get knowledge base failed")
                
                # 8. 搜索知识库
                test_results["total"] += 1
                search_result = self.test_search_knowledge_base(kb_id)
                if search_result["success"]:
                    test_results["passed"] += 1
                else:
                    test_results["failed"] += 1
                    test_results["errors"].append("Search knowledge base failed")
                
                # 9. 删除知识库
                test_results["total"] += 1
                delete_result = self.test_delete_knowledge_base(kb_id)
                if delete_result["success"]:
                    test_results["passed"] += 1
                else:
                    test_results["failed"] += 1
                    test_results["errors"].append("Delete knowledge base failed")
        else:
            test_results["failed"] += 1
            test_results["errors"].append("Create knowledge base failed")
        
        # 输出测试结果
        print("\n" + "=" * 50)
        print("📊 Test Results Summary")
        print("=" * 50)
        print(f"Total Tests: {test_results['total']}")
        print(f"✅ Passed: {test_results['passed']}")
        print(f"❌ Failed: {test_results['failed']}")
        print(f"Success Rate: {(test_results['passed'] / test_results['total'] * 100):.1f}%")
        
        if test_results['errors']:
            print("\n❌ Failed Tests:")
            for error in test_results['errors']:
                print(f"   - {error}")
        
        if test_results['failed'] == 0:
            print("\n🎉 All tests passed! Knowledge Service API is working correctly.")
        else:
            print(f"\n⚠️  {test_results['failed']} tests failed. Please check the service configuration.")
        
        return test_results


def main():
    """主函数"""
    print("🔧 Knowledge Service API Tester")
    print("Testing enhanced knowledge service with new data models and processing pipeline")
    print()
    
    # 检查服务是否运行
    try:
        response = requests.get(f"{SERVICE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Service is not healthy at {SERVICE_URL}")
            print("Please start the knowledge service first:")
            print("   cd /home/wxn/carbon/zzdsl-api-carbon/knowledge-service")
            print("   python main.py")
            return
    except Exception as e:
        print(f"❌ Cannot connect to service at {SERVICE_URL}")
        print(f"Error: {e}")
        print("Please start the knowledge service first:")
        print("   cd /home/wxn/carbon/zzdsl-api-carbon/knowledge-service")
        print("   python main.py")
        return
    
    # 运行测试
    tester = KnowledgeServiceTester()
    results = tester.run_full_test()
    
    # 退出码
    exit_code = 0 if results['failed'] == 0 else 1
    exit(exit_code)


if __name__ == "__main__":
    main()