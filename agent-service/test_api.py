#!/usr/bin/env python3
"""
Agent Service API 测试脚本
测试前后端接口对接功能
"""

import asyncio
import json
import requests
from typing import Dict, Any
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 服务配置
BASE_URL = "http://localhost:8081"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

class AgentServiceTester:
    """Agent Service API 测试类"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def test_health(self) -> bool:
        """测试健康检查"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                logger.info("✅ 健康检查通过")
                return True
            else:
                logger.error(f"❌ 健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 健康检查异常: {str(e)}")
            return False
    
    def test_get_templates(self) -> Dict[str, Any]:
        """测试获取模板列表"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/agents/templates")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 获取模板列表成功: {len(data.get('data', []))} 个模板")
                return data
            else:
                logger.error(f"❌ 获取模板列表失败: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"❌ 获取模板列表异常: {str(e)}")
            return {}
    
    def test_get_template_detail(self, template_id: str) -> Dict[str, Any]:
        """测试获取模板详情"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/agents/templates/{template_id}")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 获取模板详情成功: {template_id}")
                return data
            else:
                logger.error(f"❌ 获取模板详情失败: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"❌ 获取模板详情异常: {str(e)}")
            return {}
    
    def test_create_agent(self) -> Dict[str, Any]:
        """测试创建智能体"""
        try:
            # 对应前端 AgentBuilder 的配置结构
            agent_config = {
                "template_id": "simple_qa",
                "configuration": {
                    "template_selection": {
                        "template_id": "simple_qa",
                        "template_name": "简单问答",
                        "description": "适合快速问答的轻量级智能体",
                        "use_cases": ["客户服务", "FAQ", "快速咨询"],
                        "estimated_cost": "low"
                    },
                    "basic_configuration": {
                        "agent_name": "测试客服助手",
                        "agent_description": "这是一个用于测试的客服助手",
                        "system_prompt": "你是一个友好的客服助手，请简洁明了地回答用户问题。",
                        "language": "zh-CN",
                        "response_style": "friendly",
                        "max_context_length": 4000
                    },
                    "model_configuration": {
                        "provider": "zhipu",
                        "model": "glm-4-flash",
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "top_p": 1.0,
                        "frequency_penalty": 0.0,
                        "presence_penalty": 0.0
                    },
                    "capability_configuration": {
                        "tools": ["search", "calculator"],
                        "integrations": [],
                        "knowledge_base_ids": [],
                        "custom_instructions": ""
                    },
                    "advanced_configuration": {
                        "execution_timeout": 300,
                        "max_iterations": 10,
                        "enable_streaming": True,
                        "enable_citations": True,
                        "privacy_level": "private"
                    }
                },
                "tags": ["测试", "客服"],
                "is_public": False
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/agents/",
                json=agent_config
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 创建智能体成功: {data.get('data', {}).get('id', 'unknown')}")
                return data
            else:
                logger.error(f"❌ 创建智能体失败: {response.status_code}, {response.text}")
                return {}
        except Exception as e:
            logger.error(f"❌ 创建智能体异常: {str(e)}")
            return {}
    
    def test_list_agents(self) -> Dict[str, Any]:
        """测试获取智能体列表"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/agents/")
            if response.status_code == 200:
                data = response.json()
                agents = data.get('data', {}).get('agents', [])
                logger.info(f"✅ 获取智能体列表成功: {len(agents)} 个智能体")
                return data
            else:
                logger.error(f"❌ 获取智能体列表失败: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"❌ 获取智能体列表异常: {str(e)}")
            return {}
    
    def test_get_node_templates(self) -> Dict[str, Any]:
        """测试获取节点模板"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/orchestration/node-templates")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 获取节点模板成功: {len(data.get('data', []))} 个节点模板")
                return data
            else:
                logger.error(f"❌ 获取节点模板失败: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"❌ 获取节点模板异常: {str(e)}")
            return {}
    
    def test_create_flow(self) -> Dict[str, Any]:
        """测试创建流程"""
        try:
            # 对应前端 FlowDesigner 的流程结构
            flow_config = {
                "id": "test_flow_001",
                "name": "测试客服流程",
                "description": "一个简单的客服处理流程",
                "version": "1.0",
                "nodes": [
                    {
                        "id": "input_node",
                        "type": "input",
                        "name": "用户输入",
                        "description": "接收用户问题",
                        "position": {"x": 100, "y": 100},
                        "config": {"format": "text"}
                    },
                    {
                        "id": "llm_node",
                        "type": "model",
                        "name": "LLM处理",
                        "description": "使用大语言模型处理问题",
                        "position": {"x": 300, "y": 100},
                        "config": {
                            "model_name": "glm-4-flash",
                            "temperature": 0.7,
                            "max_tokens": 1000
                        }
                    },
                    {
                        "id": "output_node",
                        "type": "output",
                        "name": "输出结果",
                        "description": "返回处理结果",
                        "position": {"x": 500, "y": 100},
                        "config": {"format": "text"}
                    }
                ],
                "connections": [
                    {
                        "id": "conn_1",
                        "source": "input_node",
                        "target": "llm_node",
                        "type": "sequence"
                    },
                    {
                        "id": "conn_2",
                        "source": "llm_node",
                        "target": "output_node",
                        "type": "sequence"
                    }
                ],
                "variables": {},
                "timeout": 300,
                "tags": ["测试", "客服"]
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/orchestration/flows",
                json=flow_config
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 创建流程成功: {flow_config['id']}")
                return data
            else:
                logger.error(f"❌ 创建流程失败: {response.status_code}, {response.text}")
                return {}
        except Exception as e:
            logger.error(f"❌ 创建流程异常: {str(e)}")
            return {}
    
    def test_get_flow_builder_templates(self) -> Dict[str, Any]:
        """测试获取Flow Builder模板"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/flow-builder/templates")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 获取Flow Builder模板成功: {len(data.get('data', []))} 个模板")
                return data
            else:
                logger.error(f"❌ 获取Flow Builder模板失败: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"❌ 获取Flow Builder模板异常: {str(e)}")
            return {}
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始运行 Agent Service API 测试...")
        
        # 1. 健康检查
        logger.info("\n📋 测试 1: 健康检查")
        if not self.test_health():
            logger.error("❌ 服务不健康，停止测试")
            return
        
        # 2. 获取智能体模板
        logger.info("\n📋 测试 2: 获取智能体模板列表")
        templates = self.test_get_templates()
        if templates and templates.get('data'):
            # 测试获取第一个模板的详情
            first_template = templates['data'][0]
            logger.info(f"\n📋 测试 3: 获取模板详情 - {first_template['id']}")
            self.test_get_template_detail(first_template['id'])
        
        # 3. 创建智能体
        logger.info("\n📋 测试 4: 创建智能体")
        agent_result = self.test_create_agent()
        
        # 4. 获取智能体列表
        logger.info("\n📋 测试 5: 获取智能体列表")
        self.test_list_agents()
        
        # 5. 获取节点模板
        logger.info("\n📋 测试 6: 获取节点模板")
        self.test_get_node_templates()
        
        # 6. 创建流程
        logger.info("\n📋 测试 7: 创建流程")
        self.test_create_flow()
        
        # 7. 获取Flow Builder模板
        logger.info("\n📋 测试 8: 获取Flow Builder模板")
        self.test_get_flow_builder_templates()
        
        logger.info("\n🎉 所有测试完成！")

def main():
    """主函数"""
    print("=" * 60)
    print("🧪 Agent Service API 测试工具")
    print("=" * 60)
    
    tester = AgentServiceTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()