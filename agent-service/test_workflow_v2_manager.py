#!/usr/bin/env python3
"""
Agno Workflow v2 Manager 单元测试
验证核心功能的正确性
"""
import asyncio
import pytest
import json
import tempfile
import shutil
from pathlib import Path
import sys
import os

# 添加app路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.workflow_v2_manager import (
    AgnoWorkflowV2Manager, 
    WorkflowV2Config, 
    WorkflowComponents, 
    WorkflowLogic,
    AgentComponent,
    ModelComponent,
    ToolComponent,
    WorkflowStep,
    WorkflowCodeGenerator
)


class TestWorkflowCodeGenerator:
    """测试代码生成器"""
    
    def setup_method(self):
        """测试前准备"""
        self.generator = WorkflowCodeGenerator()
    
    def test_generate_class_name(self):
        """测试类名生成"""
        assert self.generator._generate_class_name("客服助手") == "CustomerServiceWorkflow"
        assert self.generator._generate_class_name("simple test") == "SimpleTestWorkflow"
        assert self.generator._generate_class_name("") == "CustomWorkflow"
    
    def test_format_tools(self):
        """测试工具格式化"""
        tools = ['reasoning', 'search', 'calculator']
        result = self.generator._format_tools(tools)
        expected = "ReasoningTools(), SearchTools(), CalculatorTools()"
        assert result == expected
    
    def test_get_model_class(self):
        """测试模型类映射"""
        assert self.generator._get_model_class('gpt-4') == 'OpenAIChat(id="gpt-4")'
        assert self.generator._get_model_class('claude-3-5-sonnet') == 'Claude(id="claude-3-5-sonnet-20241022")'
        assert self.generator._get_model_class('custom-model') == 'OpenAIChat(id="custom-model")'
    
    def test_generate_workflow_code(self):
        """测试完整代码生成"""
        # 创建测试配置
        config = self._create_test_config()
        
        # 生成代码
        code = self.generator.generate_workflow_code(config)
        
        # 验证代码内容
        assert "class TestWorkflow(Workflow):" in code
        assert "test_agent = Agent(" in code
        assert "def run(self, message: str) -> Iterator[RunResponse]:" in code
        assert "from agno.workflow import Workflow" in code
    
    def test_validate_generated_code(self):
        """测试代码验证"""
        # 生成有效代码
        config = self._create_test_config()
        code = self.generator.generate_workflow_code(config)
        
        # 验证
        result = self.generator.validate_generated_code(code)
        assert result['syntax_valid'] is True
        assert result['agno_compliant'] is True
        assert len(result['errors']) == 0
    
    def test_validate_invalid_code(self):
        """测试无效代码验证"""
        invalid_code = "def invalid_syntax("
        result = self.generator.validate_generated_code(invalid_code)
        assert result['syntax_valid'] is False
        assert len(result['errors']) > 0
    
    def _create_test_config(self) -> WorkflowV2Config:
        """创建测试配置"""
        agent = AgentComponent(
            id="test_agent",
            name="测试智能体",
            description="用于测试的智能体",
            model_name="gpt-4",
            instructions="你是一个测试智能体",
            tools=["reasoning", "search"],
            temperature=0.7,
            max_tokens=1000
        )
        
        step = WorkflowStep(
            id="step1",
            name="执行智能体",
            type="agent_run",
            component_ref="test_agent",
            config={},
            dependencies=[]
        )
        
        components = WorkflowComponents(agents=[agent])
        logic = WorkflowLogic(
            steps=[step],
            variables={"inputs": ["message"]}
        )
        
        return WorkflowV2Config(
            id="test_workflow",
            name="测试工作流",
            description="这是一个测试工作流",
            components=components,
            logic=logic
        )


class TestAgnoWorkflowV2Manager:
    """测试Workflow v2管理器"""
    
    def setup_method(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # 创建管理器实例
        self.manager = AgnoWorkflowV2Manager()
        self.manager.storage_path = self.temp_dir
    
    def teardown_method(self):
        """测试后清理"""
        # 清理临时目录
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """测试初始化"""
        # 由于依赖DAG orchestrator，这里只测试基本初始化逻辑
        assert self.manager._initialized is False
        # await self.manager.initialize()  # 需要完整环境才能测试
        # assert self.manager._initialized is True
    
    @pytest.mark.asyncio
    async def test_create_workflow_from_config(self):
        """测试从配置创建工作流"""
        config = self._create_test_config()
        
        # 创建工作流
        workflow_id = await self.manager.create_workflow_from_config(config)
        
        # 验证
        assert workflow_id == config.id
        assert workflow_id in self.manager.workflow_registry
        
        # 验证文件保存
        config_file = self.temp_dir / f"{workflow_id}_config.json"
        code_file = self.temp_dir / f"{workflow_id}_code.py"
        assert config_file.exists()
        assert code_file.exists()
    
    @pytest.mark.asyncio
    async def test_update_workflow_config(self):
        """测试更新工作流配置"""
        config = self._create_test_config()
        workflow_id = await self.manager.create_workflow_from_config(config)
        
        # 更新配置
        updates = {"name": "更新后的名称", "description": "更新后的描述"}
        updated_config = await self.manager.update_workflow_config(workflow_id, updates)
        
        # 验证更新
        assert updated_config.name == "更新后的名称"
        assert updated_config.description == "更新后的描述"
    
    @pytest.mark.asyncio
    async def test_get_workflow_config(self):
        """测试获取工作流配置"""
        config = self._create_test_config()
        workflow_id = await self.manager.create_workflow_from_config(config)
        
        # 获取配置
        retrieved_config = await self.manager.get_workflow_config(workflow_id)
        
        # 验证
        assert retrieved_config is not None
        assert retrieved_config.id == workflow_id
        assert retrieved_config.name == config.name
    
    @pytest.mark.asyncio
    async def test_list_workflows(self):
        """测试列出工作流"""
        # 创建多个工作流
        config1 = self._create_test_config()
        config1.id = "workflow_1"
        config1.name = "工作流1"
        
        config2 = self._create_test_config()
        config2.id = "workflow_2"
        config2.name = "工作流2"
        
        await self.manager.create_workflow_from_config(config1)
        await self.manager.create_workflow_from_config(config2)
        
        # 列出工作流
        workflows = await self.manager.list_workflows()
        
        # 验证
        assert len(workflows) == 2
        workflow_ids = [w.id for w in workflows]
        assert "workflow_1" in workflow_ids
        assert "workflow_2" in workflow_ids
    
    @pytest.mark.asyncio
    async def test_delete_workflow(self):
        """测试删除工作流"""
        config = self._create_test_config()
        workflow_id = await self.manager.create_workflow_from_config(config)
        
        # 确认工作流存在
        assert workflow_id in self.manager.workflow_registry
        
        # 删除工作流
        result = await self.manager.delete_workflow(workflow_id)
        
        # 验证删除
        assert result is True
        assert workflow_id not in self.manager.workflow_registry
        
        # 验证文件删除
        config_file = self.temp_dir / f"{workflow_id}_config.json"
        code_file = self.temp_dir / f"{workflow_id}_code.py"
        assert not config_file.exists()
        assert not code_file.exists()
    
    @pytest.mark.asyncio
    async def test_generate_workflow_code(self):
        """测试生成工作流代码"""
        config = self._create_test_config()
        workflow_id = await self.manager.create_workflow_from_config(config)
        
        # 生成代码
        code = await self.manager.generate_workflow_code(workflow_id)
        
        # 验证代码
        assert "class TestWorkflow(Workflow):" in code
        assert "def run(self" in code
        assert "test_agent = Agent(" in code
    
    def test_validate_config(self):
        """测试配置验证"""
        # 测试有效配置
        config = self._create_test_config()
        self.manager._validate_config(config)  # 不应抛出异常
        
        # 测试无效配置 - 缺少名称
        config.name = ""
        with pytest.raises(ValueError, match="Workflow name is required"):
            self.manager._validate_config(config)
        
        # 测试无效配置 - 缺少描述
        config.name = "测试"
        config.description = ""
        with pytest.raises(ValueError, match="Workflow description is required"):
            self.manager._validate_config(config)
    
    def test_convert_to_dag_template(self):
        """测试转换为DAG模板"""
        config = self._create_test_config()
        dag_template = self.manager._convert_to_dag_template(config)
        
        # 验证DAG模板
        assert dag_template.template_id == f"workflow_v2_{config.id}"
        assert dag_template.name == config.name
        assert len(dag_template.nodes) >= 3  # input, agent, output
        assert len(dag_template.edges) >= 2  # input->agent, agent->output
    
    @pytest.mark.asyncio
    async def test_save_and_load_workflow(self):
        """测试保存和加载工作流"""
        config = self._create_test_config()
        
        # 保存工作流
        python_code = self.manager.code_generator.generate_workflow_code(config)
        await self.manager._save_workflow_config(config, python_code)
        
        # 验证文件存在
        config_file = self.temp_dir / f"{config.id}_config.json"
        code_file = self.temp_dir / f"{config.id}_code.py"
        assert config_file.exists()
        assert code_file.exists()
        
        # 读取并验证内容
        with open(config_file, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)
        
        assert saved_config['id'] == config.id
        assert saved_config['name'] == config.name
        
        with open(code_file, 'r', encoding='utf-8') as f:
            saved_code = f.read()
        
        assert "class TestWorkflow(Workflow):" in saved_code
    
    def _create_test_config(self) -> WorkflowV2Config:
        """创建测试配置"""
        agent = AgentComponent(
            id="test_agent",
            name="测试智能体",
            description="用于测试的智能体",
            model_name="gpt-4",
            instructions="你是一个测试智能体",
            tools=["reasoning", "search"],
            temperature=0.7,
            max_tokens=1000
        )
        
        step = WorkflowStep(
            id="step1",
            name="执行智能体",
            type="agent_run",
            component_ref="test_agent",
            config={},
            dependencies=[]
        )
        
        components = WorkflowComponents(agents=[agent])
        logic = WorkflowLogic(
            steps=[step],
            variables={"inputs": ["message"]}
        )
        
        return WorkflowV2Config(
            id="test_workflow",
            name="测试工作流",
            description="这是一个测试工作流",
            components=components,
            logic=logic
        )


def test_integration():
    """集成测试示例"""
    print("运行集成测试...")
    
    # 创建管理器
    manager = AgnoWorkflowV2Manager()
    
    # 创建测试配置
    agent = AgentComponent(
        id="customer_service_agent",
        name="客服助手",
        description="智能客服助手",
        model_name="gpt-4",
        instructions="你是一个专业的客服助手，请礼貌地回答用户问题",
        tools=["reasoning", "search"],
        temperature=0.7,
        max_tokens=1000
    )
    
    step = WorkflowStep(
        id="service_step",
        name="客服处理",
        type="agent_run",
        component_ref="customer_service_agent",
        config={},
        dependencies=[]
    )
    
    components = WorkflowComponents(agents=[agent])
    logic = WorkflowLogic(
        steps=[step],
        variables={"inputs": ["message"]}
    )
    
    config = WorkflowV2Config(
        id="customer_service_workflow",
        name="客服工作流",
        description="智能客服处理工作流",
        components=components,
        logic=logic
    )
    
    # 生成代码
    code = manager.code_generator.generate_workflow_code(config)
    print("生成的Python代码:")
    print("=" * 50)
    print(code)
    print("=" * 50)
    
    # 验证代码
    validation = manager.code_generator.validate_generated_code(code)
    print(f"代码验证结果: {validation}")
    
    print("集成测试完成!")


if __name__ == "__main__":
    # 运行集成测试
    test_integration()
    
    # 运行单元测试
    print("\n运行单元测试...")
    pytest.main([__file__, "-v"]) 