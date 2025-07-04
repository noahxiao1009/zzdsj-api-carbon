import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
import logging

from ..schemas.splitter_schemas import (
    SplitterType, SplitterTemplate, SplitterTemplateCreate, 
    SplitterTemplateUpdate, TokenBasedConfig, SemanticBasedConfig,
    ParagraphBasedConfig, AgenticBasedConfig, SystemTemplatesResponse
)

logger = logging.getLogger(__name__)


class SplitterTemplateManager:
    """文档切分模板管理器"""
    
    def __init__(self):
        """初始化模板管理器"""
        self.templates: Dict[str, SplitterTemplate] = {}
        self.usage_stats: Dict[str, int] = {}
        self.last_used: Dict[str, datetime] = {}
        
        # 初始化系统默认模板
        asyncio.create_task(self._initialize_system_templates())
        
        logger.info("SplitterTemplateManager initialized")
    
    async def _initialize_system_templates(self):
        """初始化系统默认模板"""
        system_templates = [
            # Token切分模板
            {
                "name": "标准Token切分",
                "description": "按字符数进行标准切分，适用于大多数文档类型",
                "splitter_type": SplitterType.TOKEN_BASED,
                "config": TokenBasedConfig(
                    chunk_size=1000,
                    chunk_overlap=200,
                    use_token_count=False,
                    separator="\n\n",
                    secondary_separators=["\n", "。", "！", "？", ". ", "! ", "? "],
                    keep_separator=True,
                    strip_whitespace=True
                ),
                "tags": ["通用", "标准", "推荐"]
            },
            {
                "name": "大文档Token切分",
                "description": "适用于长文档的大块切分，减少分块数量",
                "splitter_type": SplitterType.TOKEN_BASED,
                "config": TokenBasedConfig(
                    chunk_size=2000,
                    chunk_overlap=300,
                    use_token_count=False,
                    separator="\n\n",
                    secondary_separators=["\n", "。", "！", "？"],
                    keep_separator=True,
                    strip_whitespace=True
                ),
                "tags": ["长文档", "大块", "高效"]
            },
            {
                "name": "精细Token切分",
                "description": "小块切分，适用于需要精确检索的场景",
                "splitter_type": SplitterType.TOKEN_BASED,
                "config": TokenBasedConfig(
                    chunk_size=500,
                    chunk_overlap=100,
                    use_token_count=True,
                    separator="\n",
                    secondary_separators=["。", "！", "？", ". ", "! ", "? "],
                    keep_separator=True,
                    strip_whitespace=True
                ),
                "tags": ["精细", "小块", "精确检索"]
            },
            
            # 语义切分模板
            {
                "name": "中文语义切分",
                "description": "基于中文语义理解的智能切分",
                "splitter_type": SplitterType.SEMANTIC_BASED,
                "config": SemanticBasedConfig(
                    min_chunk_size=200,
                    max_chunk_size=1500,
                    similarity_threshold=0.75,
                    sentence_split_method="punctuation",
                    embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    language="zh",
                    merge_threshold=0.8
                ),
                "tags": ["中文", "语义", "智能"]
            },
            {
                "name": "英文语义切分",
                "description": "基于英文语义理解的智能切分",
                "splitter_type": SplitterType.SEMANTIC_BASED,
                "config": SemanticBasedConfig(
                    min_chunk_size=150,
                    max_chunk_size=1200,
                    similarity_threshold=0.7,
                    sentence_split_method="punctuation",
                    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                    language="en",
                    merge_threshold=0.8
                ),
                "tags": ["英文", "语义", "智能"]
            },
            
            # 段落切分模板
            {
                "name": "标准段落切分",
                "description": "按自然段落进行切分，保持文档结构",
                "splitter_type": SplitterType.PARAGRAPH_BASED,
                "config": ParagraphBasedConfig(
                    paragraph_separators=["\n\n", "\r\n\r\n"],
                    merge_short_paragraphs=True,
                    min_paragraph_length=100,
                    max_paragraph_length=2000,
                    preserve_structure=True,
                    split_long_paragraphs=True,
                    structure_markers=["#", "##", "###", "第", "章", "节"]
                ),
                "tags": ["段落", "结构", "自然"]
            },
            {
                "name": "Markdown段落切分",
                "description": "专门针对Markdown文档的段落切分",
                "splitter_type": SplitterType.PARAGRAPH_BASED,
                "config": ParagraphBasedConfig(
                    paragraph_separators=["\n\n", "\n---\n", "\n***\n"],
                    merge_short_paragraphs=False,
                    min_paragraph_length=50,
                    max_paragraph_length=1500,
                    preserve_structure=True,
                    split_long_paragraphs=True,
                    structure_markers=["#", "##", "###", "####", "1.", "2.", "*", "-"]
                ),
                "tags": ["markdown", "代码", "技术文档"]
            },
            
            # Agentic切分模板
            {
                "name": "智能主题切分",
                "description": "使用AI代理进行主题边界识别的智能切分",
                "splitter_type": SplitterType.AGENTIC_BASED,
                "config": AgenticBasedConfig(
                    agent_model="gpt-3.5-turbo",
                    analysis_depth="medium",
                    context_window=4000,
                    coherence_score_threshold=0.7,
                    topic_boundary_detection=True,
                    semantic_clustering=True,
                    adaptive_chunking=True,
                    instruction_template="请分析以下文档内容，识别自然的主题边界和语义单元，将文档切分为连贯的片段。",
                    max_chunks_per_call=8
                ),
                "tags": ["AI", "主题", "智能", "高级"]
            },
            {
                "name": "深度语义分析切分",
                "description": "深度语义分析，适用于复杂文档",
                "splitter_type": SplitterType.AGENTIC_BASED,
                "config": AgenticBasedConfig(
                    agent_model="gpt-4",
                    analysis_depth="deep",
                    context_window=8000,
                    coherence_score_threshold=0.8,
                    topic_boundary_detection=True,
                    semantic_clustering=True,
                    adaptive_chunking=True,
                    instruction_template="请对文档进行深度语义分析，识别复杂的主题结构和概念边界，创建高质量的语义片段。",
                    max_chunks_per_call=5
                ),
                "tags": ["深度分析", "复杂文档", "高质量", "GPT-4"]
            }
        ]
        
        # 创建系统模板
        for template_data in system_templates:
            await self._create_system_template(template_data)
        
        logger.info(f"Initialized {len(system_templates)} system templates")
    
    async def _create_system_template(self, template_data: Dict[str, Any]):
        """创建系统模板"""
        template_id = str(uuid.uuid4())
        
        template = SplitterTemplate(
            id=template_id,
            name=template_data["name"],
            description=template_data["description"],
            splitter_type=template_data["splitter_type"],
            config=template_data["config"].dict(),
            is_system_template=True,
            is_active=True,
            tags=template_data.get("tags", []),
            priority=10,  # 系统模板高优先级
            created_at=datetime.now(timezone.utc),
            usage_count=0
        )
        
        self.templates[template_id] = template
        self.usage_stats[template_id] = 0
    
    async def create_template(self, request: SplitterTemplateCreate, created_by: Optional[str] = None) -> SplitterTemplate:
        """
        创建新的切分模板
        
        Args:
            request: 创建模板请求
            created_by: 创建者ID
            
        Returns:
            创建的模板
        """
        template_id = str(uuid.uuid4())
        
        template = SplitterTemplate(
            id=template_id,
            name=request.name,
            description=request.description,
            splitter_type=request.splitter_type,
            config=request.config.dict(),
            is_system_template=False,
            is_active=request.is_active,
            tags=request.tags,
            priority=request.priority,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            usage_count=0
        )
        
        self.templates[template_id] = template
        self.usage_stats[template_id] = 0
        
        logger.info(f"Created new template: {template_id} - {request.name}")
        return template
    
    async def get_template(self, template_id: str) -> Optional[SplitterTemplate]:
        """
        获取模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            模板对象或None
        """
        return self.templates.get(template_id)
    
    async def update_template(self, template_id: str, request: SplitterTemplateUpdate) -> Optional[SplitterTemplate]:
        """
        更新模板
        
        Args:
            template_id: 模板ID
            request: 更新请求
            
        Returns:
            更新后的模板或None
        """
        template = self.templates.get(template_id)
        if not template:
            return None
        
        # 系统模板不允许修改
        if template.is_system_template:
            raise ValueError("System templates cannot be modified")
        
        # 更新字段
        if request.name is not None:
            template.name = request.name
        if request.description is not None:
            template.description = request.description
        if request.config is not None:
            template.config = request.config.dict()
        if request.is_active is not None:
            template.is_active = request.is_active
        if request.tags is not None:
            template.tags = request.tags
        if request.priority is not None:
            template.priority = request.priority
        
        template.updated_at = datetime.now(timezone.utc)
        
        logger.info(f"Updated template: {template_id}")
        return template
    
    async def delete_template(self, template_id: str) -> bool:
        """
        删除模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            是否删除成功
        """
        template = self.templates.get(template_id)
        if not template:
            return False
        
        # 系统模板不允许删除
        if template.is_system_template:
            raise ValueError("System templates cannot be deleted")
        
        del self.templates[template_id]
        if template_id in self.usage_stats:
            del self.usage_stats[template_id]
        if template_id in self.last_used:
            del self.last_used[template_id]
        
        logger.info(f"Deleted template: {template_id}")
        return True
    
    async def list_templates(
        self, 
        splitter_type: Optional[SplitterType] = None,
        is_active: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        列出模板
        
        Args:
            splitter_type: 过滤切分器类型
            is_active: 过滤激活状态
            tags: 过滤标签
            page: 页码
            page_size: 页面大小
            
        Returns:
            模板列表和分页信息
        """
        # 过滤模板
        filtered_templates = []
        for template in self.templates.values():
            # 类型过滤
            if splitter_type and template.splitter_type != splitter_type:
                continue
            # 激活状态过滤
            if is_active is not None and template.is_active != is_active:
                continue
            # 标签过滤
            if tags and not any(tag in template.tags for tag in tags):
                continue
            
            filtered_templates.append(template)
        
        # 排序：优先级降序，创建时间降序
        filtered_templates.sort(
            key=lambda x: (x.priority, x.created_at),
            reverse=True
        )
        
        # 分页
        total = len(filtered_templates)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_templates = filtered_templates[start_idx:end_idx]
        
        return {
            "templates": page_templates,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    
    async def get_system_templates(self) -> SystemTemplatesResponse:
        """
        获取系统默认模板
        
        Returns:
            按类型分组的系统模板
        """
        system_templates = [t for t in self.templates.values() if t.is_system_template]
        
        # 按类型分组
        token_based = [t for t in system_templates if t.splitter_type == SplitterType.TOKEN_BASED]
        semantic_based = [t for t in system_templates if t.splitter_type == SplitterType.SEMANTIC_BASED]
        paragraph_based = [t for t in system_templates if t.splitter_type == SplitterType.PARAGRAPH_BASED]
        agentic_based = [t for t in system_templates if t.splitter_type == SplitterType.AGENTIC_BASED]
        
        return SystemTemplatesResponse(
            token_based_templates=token_based,
            semantic_based_templates=semantic_based,
            paragraph_based_templates=paragraph_based,
            agentic_based_templates=agentic_based,
            total_templates=len(system_templates)
        )
    
    async def record_template_usage(self, template_id: str):
        """
        记录模板使用
        
        Args:
            template_id: 模板ID
        """
        if template_id in self.templates:
            self.usage_stats[template_id] = self.usage_stats.get(template_id, 0) + 1
            self.last_used[template_id] = datetime.now(timezone.utc)
            self.templates[template_id].usage_count = self.usage_stats[template_id]
    
    async def get_popular_templates(self, limit: int = 10) -> List[SplitterTemplate]:
        """
        获取热门模板
        
        Args:
            limit: 返回数量限制
            
        Returns:
            热门模板列表
        """
        templates_with_usage = [
            (template, self.usage_stats.get(template.id, 0))
            for template in self.templates.values()
            if template.is_active
        ]
        
        # 按使用次数排序
        templates_with_usage.sort(key=lambda x: x[1], reverse=True)
        
        return [template for template, _ in templates_with_usage[:limit]]
    
    async def search_templates(self, query: str) -> List[SplitterTemplate]:
        """
        搜索模板
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的模板列表
        """
        query_lower = query.lower()
        matched_templates = []
        
        for template in self.templates.values():
            if not template.is_active:
                continue
            
            # 在名称、描述、标签中搜索
            if (query_lower in template.name.lower() or
                (template.description and query_lower in template.description.lower()) or
                any(query_lower in tag.lower() for tag in template.tags)):
                matched_templates.append(template)
        
        # 按优先级和使用次数排序
        matched_templates.sort(
            key=lambda x: (x.priority, self.usage_stats.get(x.id, 0)),
            reverse=True
        )
        
        return matched_templates
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取模板管理器统计信息
        
        Returns:
            统计信息
        """
        total_templates = len(self.templates)
        active_templates = sum(1 for t in self.templates.values() if t.is_active)
        system_templates = sum(1 for t in self.templates.values() if t.is_system_template)
        user_templates = total_templates - system_templates
        
        # 按类型统计
        type_stats = {}
        for splitter_type in SplitterType:
            type_stats[splitter_type.value] = sum(
                1 for t in self.templates.values() 
                if t.splitter_type == splitter_type
            )
        
        return {
            "total_templates": total_templates,
            "active_templates": active_templates,
            "system_templates": system_templates,
            "user_templates": user_templates,
            "type_statistics": type_stats,
            "total_usage": sum(self.usage_stats.values()),
            "most_used_template": max(
                self.usage_stats.items(), 
                key=lambda x: x[1]
            )[0] if self.usage_stats else None
        }


# 全局模板管理器实例
_template_manager = None

def get_template_manager() -> SplitterTemplateManager:
    """获取模板管理器实例"""
    global _template_manager
    if _template_manager is None:
        _template_manager = SplitterTemplateManager()
    return _template_manager 