"""
图谱生成器核心组件
集成原始AI知识图谱框架，提供完整的图谱生成功能
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime
import asyncio
import json
from pathlib import Path

from ..models.graph import Entity, Relation, ProcessingConfig
from ..config.settings import settings

# 导入原始AI知识图谱框架
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "frameworks"))

from ai_knowledge_graph.processor import AIKnowledgeGraphProcessor
from ai_knowledge_graph.config import get_config
from ai_knowledge_graph.core.extractor import TripleExtractor
from ai_knowledge_graph.core.standardizer import EntityStandardizer
from ai_knowledge_graph.core.inference import RelationshipInference as RelationInferencer
from ai_knowledge_graph.core.visualizer import KnowledgeGraphVisualizer as GraphVisualizer
from ai_knowledge_graph.adapters.llm_adapter import LLMAdapter
from ai_knowledge_graph.adapters.storage_adapter import StorageAdapter

logger = logging.getLogger(__name__)


class GraphGenerator:
    """图谱生成器
    
    集成原始AI知识图谱框架，提供异步图谱生成功能
    """
    
    def __init__(self):
        """初始化图谱生成器"""
        self.processor = None
        self.extractor = None
        self.standardizer = None
        self.inferencer = None
        self.visualizer = None
        self.llm_adapter = None
        self.storage_adapter = None
        
        # 配置
        self.kg_config = get_config()
        
        # 初始化组件
        self._init_components()
    
    def _init_components(self):
        """初始化组件"""
        try:
            # 更新配置以适应微服务环境
            self._update_config_for_microservice()
            
            # 初始化AI知识图谱处理器
            self.processor = AIKnowledgeGraphProcessor()
            
            # 获取配置
            config = get_config()
            
            # 初始化各个组件
            self.extractor = TripleExtractor(config)
            self.standardizer = EntityStandardizer(config)
            self.inferencer = RelationInferencer(config)
            self.visualizer = GraphVisualizer(config)
            self.llm_adapter = LLMAdapter()
            self.storage_adapter = StorageAdapter({"storage_path": "storage/knowledge_graphs", "use_database": False})
            
            logger.info("Graph generator components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize graph generator components: {e}")
            raise
    
    def _update_config_for_microservice(self):
        """更新配置以适应微服务环境"""
        try:
            # 从微服务配置更新AI知识图谱配置
            config_updates = {
                'chunk_size': settings.CHUNK_SIZE,
                'max_tokens': settings.LLM_MAX_TOKENS,
                'temperature': settings.LLM_TEMPERATURE,
                'standardization_enabled': True,
                'inference_enabled': True,
                'base_dir': settings.VISUALIZATION_DIR,
                'storage_type': 'database'
            }
            
            self.kg_config.update_config(config_updates)
            logger.info("Updated AI knowledge graph config for microservice")
            
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            raise
    
    async def process_text(self, text_content: str, config: ProcessingConfig = None, 
                          progress_callback: Optional[Callable] = None) -> Tuple[List[Entity], List[Relation]]:
        """处理文本内容生成图谱
        
        Args:
            text_content: 文本内容
            config: 处理配置
            progress_callback: 进度回调函数
            
        Returns:
            实体和关系列表
        """
        try:
            logger.info(f"Processing text content, length: {len(text_content)}")
            
            # 应用配置
            if config:
                self._apply_processing_config(config)
            
            # 创建进度回调函数
            if progress_callback:
                callback_func = self._create_progress_callback(progress_callback)
            else:
                callback_func = None
            
            # 使用原始框架处理文本
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.processor.process_text,
                text_content,
                None,  # knowledge_base_id
                callback_func
            )
            
            # 转换结果格式
            entities, relations = self._convert_processor_result(result)
            
            logger.info(f"Processed text: {len(entities)} entities, {len(relations)} relations")
            return entities, relations
            
        except Exception as e:
            logger.error(f"Failed to process text: {e}")
            raise
    
    async def process_knowledge_bases(self, knowledge_base_ids: List[str], config: ProcessingConfig = None,
                                    progress_callback: Optional[Callable] = None) -> Tuple[List[Entity], List[Relation]]:
        """处理知识库生成图谱
        
        Args:
            knowledge_base_ids: 知识库ID列表
            config: 处理配置
            progress_callback: 进度回调函数
            
        Returns:
            实体和关系列表
        """
        try:
            logger.info(f"Processing knowledge bases: {knowledge_base_ids}")
            
            # 应用配置
            if config:
                self._apply_processing_config(config)
            
            # 创建进度回调函数
            if progress_callback:
                callback_func = self._create_progress_callback(progress_callback)
            else:
                callback_func = None
            
            all_entities = []
            all_relations = []
            
            # 处理每个知识库
            for i, kb_id in enumerate(knowledge_base_ids):
                try:
                    # 获取知识库内容
                    kb_content = await self._get_knowledge_base_content(kb_id)
                    
                    if not kb_content:
                        logger.warning(f"No content found for knowledge base {kb_id}")
                        continue
                    
                    # 更新进度
                    if callback_func:
                        callback_func(f"正在处理知识库 {i+1}/{len(knowledge_base_ids)}", (i / len(knowledge_base_ids)) * 100)
                    
                    # 处理知识库内容
                    result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.processor.process_text,
                        kb_content,
                        kb_id,
                        callback_func
                    )
                    
                    # 转换结果格式
                    entities, relations = self._convert_processor_result(result)
                    
                    all_entities.extend(entities)
                    all_relations.extend(relations)
                    
                    logger.info(f"Processed knowledge base {kb_id}: {len(entities)} entities, {len(relations)} relations")
                    
                except Exception as e:
                    logger.error(f"Failed to process knowledge base {kb_id}: {e}")
                    continue
            
            # 去重和合并
            merged_entities, merged_relations = self._merge_graph_data(all_entities, all_relations)
            
            logger.info(f"Processed {len(knowledge_base_ids)} knowledge bases: {len(merged_entities)} entities, {len(merged_relations)} relations")
            return merged_entities, merged_relations
            
        except Exception as e:
            logger.error(f"Failed to process knowledge bases: {e}")
            raise
    
    async def process_documents(self, document_ids: List[str], config: ProcessingConfig = None,
                              progress_callback: Optional[Callable] = None) -> Tuple[List[Entity], List[Relation]]:
        """处理文档生成图谱
        
        Args:
            document_ids: 文档ID列表
            config: 处理配置
            progress_callback: 进度回调函数
            
        Returns:
            实体和关系列表
        """
        try:
            logger.info(f"Processing documents: {document_ids}")
            
            # 应用配置
            if config:
                self._apply_processing_config(config)
            
            # 创建进度回调函数
            if progress_callback:
                callback_func = self._create_progress_callback(progress_callback)
            else:
                callback_func = None
            
            all_entities = []
            all_relations = []
            
            # 处理每个文档
            for i, doc_id in enumerate(document_ids):
                try:
                    # 获取文档内容
                    doc_content = await self._get_document_content(doc_id)
                    
                    if not doc_content:
                        logger.warning(f"No content found for document {doc_id}")
                        continue
                    
                    # 更新进度
                    if callback_func:
                        callback_func(f"正在处理文档 {i+1}/{len(document_ids)}", (i / len(document_ids)) * 100)
                    
                    # 处理文档内容
                    result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.processor.process_text,
                        doc_content,
                        doc_id,
                        callback_func
                    )
                    
                    # 转换结果格式
                    entities, relations = self._convert_processor_result(result)
                    
                    all_entities.extend(entities)
                    all_relations.extend(relations)
                    
                    logger.info(f"Processed document {doc_id}: {len(entities)} entities, {len(relations)} relations")
                    
                except Exception as e:
                    logger.error(f"Failed to process document {doc_id}: {e}")
                    continue
            
            # 去重和合并
            merged_entities, merged_relations = self._merge_graph_data(all_entities, all_relations)
            
            logger.info(f"Processed {len(document_ids)} documents: {len(merged_entities)} entities, {len(merged_relations)} relations")
            return merged_entities, merged_relations
            
        except Exception as e:
            logger.error(f"Failed to process documents: {e}")
            raise
    
    def _apply_processing_config(self, config: ProcessingConfig):
        """应用处理配置"""
        try:
            config_updates = {
                'chunk_size': config.chunk_size,
                'chunk_overlap': config.overlap_size,
                'max_tokens': config.max_tokens,
                'temperature': config.temperature,
                'standardization_enabled': config.enable_standardization,
                'inference_enabled': config.enable_inference,
                'use_llm_for_entities': True,
                'use_llm_for_inference': True,
                'apply_transitive': True
            }
            
            self.kg_config.update_config(config_updates)
            logger.info("Applied processing configuration")
            
        except Exception as e:
            logger.error(f"Failed to apply processing config: {e}")
            raise
    
    def _create_progress_callback(self, progress_callback: Callable) -> Callable:
        """创建进度回调函数"""
        def callback(message: str, progress: float):
            try:
                asyncio.create_task(progress_callback(message, progress))
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
        
        return callback
    
    def _convert_processor_result(self, result: Dict[str, Any]) -> Tuple[List[Entity], List[Relation]]:
        """转换处理器结果格式"""
        try:
            entities = []
            relations = []
            
            # 转换实体
            if 'entities' in result:
                for entity_data in result['entities']:
                    entity = Entity(
                        id=self._generate_entity_id(entity_data['name'], entity_data.get('type', 'Entity')),
                        name=entity_data['name'],
                        entity_type=entity_data.get('type', 'Entity'),
                        confidence=entity_data.get('confidence', 0.8),
                        properties=entity_data.get('properties', {}),
                        source=entity_data.get('source', ''),
                        frequency=entity_data.get('frequency', 1),
                        centrality=entity_data.get('centrality', 0.0)
                    )
                    entities.append(entity)
            
            # 转换关系
            if 'relations' in result:
                for relation_data in result['relations']:
                    relation = Relation(
                        id=self._generate_relation_id(
                            relation_data['subject'], 
                            relation_data['predicate'], 
                            relation_data['object']
                        ),
                        subject=self._generate_entity_id(relation_data['subject'], 'Entity'),
                        predicate=relation_data['predicate'],
                        object=self._generate_entity_id(relation_data['object'], 'Entity'),
                        confidence=relation_data.get('confidence', 0.8),
                        properties=relation_data.get('properties', {}),
                        source=relation_data.get('source', ''),
                        inferred=relation_data.get('inferred', False)
                    )
                    relations.append(relation)
            
            logger.info(f"Converted result: {len(entities)} entities, {len(relations)} relations")
            return entities, relations
            
        except Exception as e:
            logger.error(f"Failed to convert processor result: {e}")
            raise
    
    def _generate_entity_id(self, name: str, entity_type: str) -> str:
        """生成实体ID"""
        import hashlib
        source = f"{name}_{entity_type}".lower()
        hash_obj = hashlib.md5(source.encode())
        return f"entity_{hash_obj.hexdigest()[:16]}"
    
    def _generate_relation_id(self, subject: str, predicate: str, object: str) -> str:
        """生成关系ID"""
        import hashlib
        source = f"{subject}_{predicate}_{object}".lower()
        hash_obj = hashlib.md5(source.encode())
        return f"relation_{hash_obj.hexdigest()[:16]}"
    
    def _merge_graph_data(self, entities: List[Entity], relations: List[Relation]) -> Tuple[List[Entity], List[Relation]]:
        """合并图数据，去重和整合"""
        try:
            # 按ID去重实体
            entity_dict = {}
            for entity in entities:
                if entity.id not in entity_dict:
                    entity_dict[entity.id] = entity
                else:
                    # 合并实体数据
                    existing = entity_dict[entity.id]
                    existing.frequency += entity.frequency
                    existing.confidence = max(existing.confidence, entity.confidence)
                    existing.properties.update(entity.properties)
            
            # 按ID去重关系
            relation_dict = {}
            for relation in relations:
                if relation.id not in relation_dict:
                    relation_dict[relation.id] = relation
                else:
                    # 合并关系数据
                    existing = relation_dict[relation.id]
                    existing.confidence = max(existing.confidence, relation.confidence)
                    existing.properties.update(relation.properties)
            
            merged_entities = list(entity_dict.values())
            merged_relations = list(relation_dict.values())
            
            logger.info(f"Merged graph data: {len(merged_entities)} entities, {len(merged_relations)} relations")
            return merged_entities, merged_relations
            
        except Exception as e:
            logger.error(f"Failed to merge graph data: {e}")
            raise
    
    async def _get_knowledge_base_content(self, kb_id: str) -> Optional[str]:
        """获取知识库内容"""
        try:
            # 这里需要调用知识服务API获取知识库内容
            # 暂时返回示例内容
            logger.info(f"Getting content for knowledge base {kb_id}")
            
            # TODO: 实现知识库内容获取逻辑
            # 可能需要调用知识服务的API
            return f"知识库 {kb_id} 的示例内容"
            
        except Exception as e:
            logger.error(f"Failed to get knowledge base content: {e}")
            return None
    
    async def _get_document_content(self, doc_id: str) -> Optional[str]:
        """获取文档内容"""
        try:
            # 这里需要调用基础服务API获取文档内容
            # 暂时返回示例内容
            logger.info(f"Getting content for document {doc_id}")
            
            # TODO: 实现文档内容获取逻辑
            # 可能需要调用基础服务的API
            return f"文档 {doc_id} 的示例内容"
            
        except Exception as e:
            logger.error(f"Failed to get document content: {e}")
            return None
    
    async def generate_from_custom_data(self, custom_data: Dict[str, Any], config: ProcessingConfig = None) -> Tuple[List[Entity], List[Relation]]:
        """从自定义数据生成图谱"""
        try:
            logger.info("Generating graph from custom data")
            
            # 应用配置
            if config:
                self._apply_processing_config(config)
            
            # 处理自定义数据
            if 'text' in custom_data:
                return await self.process_text(custom_data['text'], config)
            elif 'entities' in custom_data and 'relations' in custom_data:
                # 直接从实体和关系数据构建图谱
                entities = [Entity(**entity) for entity in custom_data['entities']]
                relations = [Relation(**relation) for relation in custom_data['relations']]
                return entities, relations
            else:
                raise ValueError("Invalid custom data format")
                
        except Exception as e:
            logger.error(f"Failed to generate graph from custom data: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查各个组件状态
            health_status = {
                'processor': self.processor is not None,
                'extractor': self.extractor is not None,
                'standardizer': self.standardizer is not None,
                'inferencer': self.inferencer is not None,
                'visualizer': self.visualizer is not None,
                'llm_adapter': self.llm_adapter is not None,
                'storage_adapter': self.storage_adapter is not None,
                'config': self.kg_config is not None
            }
            
            all_healthy = all(health_status.values())
            
            return {
                'status': 'healthy' if all_healthy else 'unhealthy',
                'components': health_status,
                'config': self.kg_config.get_config_dict() if self.kg_config else {},
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }


# 全局生成器实例
graph_generator = GraphGenerator()


async def get_graph_generator() -> GraphGenerator:
    """获取图谱生成器实例"""
    return graph_generator