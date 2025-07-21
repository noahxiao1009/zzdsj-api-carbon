"""
知识图谱服务的服务间通信集成
基于原始项目的知识图谱实现，提供实体关系抽取、图谱构建、推理查询等功能
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
import json
import sys
import os
import uuid
import re
from collections import defaultdict

# 添加shared模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../shared"))

from service_client import (
    ServiceClient, 
    AsyncServiceClient,
    CallMethod, 
    CallConfig, 
    RetryStrategy,
    ServiceCallError,
    call_service,
    publish_event
)

logger = logging.getLogger(__name__)


class GraphProcessor:
    """图谱处理器"""
    
    def __init__(self):
        self.entity_types = {
            "PERSON": "人物",
            "ORGANIZATION": "组织",
            "LOCATION": "地点", 
            "EVENT": "事件",
            "CONCEPT": "概念",
            "TIME": "时间",
            "NUMBER": "数值"
        }
        
        self.relation_types = {
            "WORKS_FOR": "供职于",
            "LOCATED_IN": "位于",
            "PART_OF": "隶属于",
            "RELATED_TO": "相关",
            "CAUSED_BY": "由于",
            "LEADS_TO": "导致"
        }
    
    def standardize_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """标准化实体格式"""
        return {
            "id": entity.get("id", str(uuid.uuid4())),
            "text": entity.get("text", ""),
            "type": entity.get("type", "CONCEPT"),
            "confidence": entity.get("confidence", 0.8),
            "properties": entity.get("properties", {}),
            "aliases": entity.get("aliases", [])
        }
    
    def standardize_relation(self, relation: Dict[str, Any]) -> Dict[str, Any]:
        """标准化关系格式"""
        return {
            "id": relation.get("id", str(uuid.uuid4())),
            "source": relation.get("source", ""),
            "target": relation.get("target", ""),
            "type": relation.get("type", "RELATED_TO"),
            "confidence": relation.get("confidence", 0.7),
            "properties": relation.get("properties", {})
        }


class KnowledgeGraphServiceIntegration:
    """知识图谱服务集成类 - 智能实体关系抽取和图谱构建"""
    
    def __init__(self):
        self.service_client = None
        self.async_client = None
        self.graph_processor = GraphProcessor()
        
        # 不同操作的配置
        self.model_config = CallConfig(
            timeout=120,  # 模型调用需要更长时间
            retry_times=2,
            retry_strategy=RetryStrategy.EXPONENTIAL,
            circuit_breaker_enabled=True
        )
        
        self.knowledge_config = CallConfig(
            timeout=30,   # 知识库操作
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.database_config = CallConfig(
            timeout=20,   # 图数据库操作
            retry_times=3,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        self.auth_config = CallConfig(
            timeout=5,    # 权限检查要快
            retry_times=2,
            retry_strategy=RetryStrategy.LINEAR
        )
        
        # 支持的知识图谱功能
        self.graph_capabilities = {
            "entity_extraction": {
                "description": "实体抽取",
                "models": ["bert-ner", "spacy-ner", "custom-ner"]
            },
            "relation_extraction": {
                "description": "关系抽取", 
                "models": ["bert-relation", "gpt-relation", "rule-based"]
            },
            "graph_reasoning": {
                "description": "图谱推理",
                "algorithms": ["path-finding", "community-detection", "centrality"]
            },
            "knowledge_fusion": {
                "description": "知识融合",
                "strategies": ["entity-linking", "conflict-resolution", "trust-propagation"]
            }
        }
        
        # 处理统计
        self.processing_stats = {
            "total_documents": 0,
            "total_entities": 0,
            "total_relations": 0,
            "processing_time": 0.0
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.service_client = ServiceClient()
        self.async_client = AsyncServiceClient()
        await self.service_client.__aenter__()
        await self.async_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.service_client:
            await self.service_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.async_client:
            await self.async_client.__aexit__(exc_type, exc_val, exc_tb)
    
    # ==================== 实体和关系抽取 ====================
    
    async def extract_entities_from_text(
        self, 
        text: str, 
        user_id: str,
        model: str = "bert-ner",
        confidence_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """从文本中提取实体（调用模型服务）"""
        try:
            # 权限检查
            permission_check = await self._check_graph_permission(user_id, "entity_extraction")
            if not permission_check.get("allowed"):
                return {
                    "success": False,
                    "error": "权限不足",
                    "required_permission": "knowledge_graph:entity_extraction"
                }
            
            logger.info(f"开始从文本提取实体，用户: {user_id}, 模型: {model}")
            
            # 调用模型服务进行实体抽取
            result = await self.service_client.call(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/nlp/entity-extraction",
                config=self.model_config,
                json={
                    "text": text,
                    "model": model,
                    "user_id": user_id,
                    "language": "zh",
                    "confidence_threshold": confidence_threshold
                }
            )
            
            raw_entities = result.get("entities", [])
            
            # 标准化实体格式
            entities = []
            for entity in raw_entities:
                if entity.get("confidence", 0) >= confidence_threshold:
                    standardized = self.graph_processor.standardize_entity(entity)
                    entities.append(standardized)
            
            # 更新统计
            self.processing_stats["total_entities"] += len(entities)
            
            logger.info(f"提取到 {len(entities)} 个实体 (阈值: {confidence_threshold})")
            
            return entities
            
        except ServiceCallError as e:
            logger.error(f"实体提取失败: {e}")
            if e.status_code == 503:
                # 服务不可用，使用规则提取
                return await self._fallback_entity_extraction(text)
            raise
        except Exception as e:
            logger.error(f"实体提取异常: {e}")
            raise
    
    async def build_knowledge_graph_workflow(
        self, 
        document_id: str, 
        user_id: str,
        extraction_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """构建知识图谱完整工作流"""
        try:
            start_time = datetime.now()
            logger.info(f"开始构建知识图谱，文档: {document_id}, 用户: {user_id}")
            
            # 权限检查
            permission_check = await self._check_graph_permission(user_id, "graph_building")
            if not permission_check.get("allowed"):
                return {
                    "success": False,
                    "error": "权限不足",
                    "required_permission": "knowledge_graph:graph_building"
                }
            
            # 1. 获取文档内容
            document_result = await self._get_document_content(document_id, user_id)
            if not document_result.get("success"):
                return document_result
            
            document = document_result["data"]
            document_content = document.get("content", "")
            
            if not document_content.strip():
                return {
                    "success": False,
                    "error": "文档内容为空",
                    "document_id": document_id
                }
            
            # 2. 并发执行实体和关系抽取
            extraction_config = extraction_config or {}
            entity_model = extraction_config.get("entity_model", "bert-ner")
            relation_model = extraction_config.get("relation_model", "bert-relation")
            confidence_threshold = extraction_config.get("confidence_threshold", 0.7)
            
            tasks = [
                self.extract_entities_from_text(
                    document_content, user_id, entity_model, confidence_threshold
                ),
                self.extract_relations_from_text(
                    document_content, user_id, relation_model, confidence_threshold
                )
            ]
            
            entities, relations = await asyncio.gather(*tasks)
            
            # 3. 实体链接和去重
            entities = await self._process_entities(entities, user_id)
            relations = await self._process_relations(relations, entities, user_id)
            
            # 4. 构建图谱结构
            graph_structure = await self._build_graph_structure(entities, relations)
            
            # 5. 保存到图数据库
            graph_result = await self._save_graph_to_database(
                document_id, user_id, graph_structure, document
            )
            
            if not graph_result.get("success"):
                return graph_result
            
            graph_id = graph_result["graph_id"]
            
            # 6. 生成图谱摘要
            graph_summary = await self._generate_graph_summary(graph_structure)
            
            # 7. 发布完成事件
            processing_time = (datetime.now() - start_time).total_seconds()
            await publish_event(
                "knowledge_graph.built",
                {
                    "document_id": document_id,
                    "graph_id": graph_id,
                    "user_id": user_id,
                    "entity_count": len(entities),
                    "relation_count": len(relations),
                    "processing_time": processing_time,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # 更新统计
            self.processing_stats["total_documents"] += 1
            self.processing_stats["processing_time"] += processing_time
            
            logger.info(f"知识图谱构建完成，图谱ID: {graph_id}, 耗时: {processing_time:.2f}秒")
            
            return {
                "success": True,
                "graph_id": graph_id,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "processing_time": processing_time,
                "graph_summary": graph_summary,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"知识图谱构建失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "document_id": document_id
            }
    
    async def extract_relations_from_text(
        self, 
        text: str, 
        user_id: str,
        model: str = "bert-relation",
        confidence_threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """从文本中提取关系（调用模型服务）"""
        try:
            result = await self.service_client.call(
                service_name="model-service",
                method=CallMethod.POST,
                path="/api/v1/nlp/relation-extraction",
                config=self.model_config,
                json={
                    "text": text,
                    "model": model,
                    "user_id": user_id,
                    "confidence_threshold": confidence_threshold
                }
            )
            
            raw_relations = result.get("relations", [])
            
            # 标准化关系格式
            relations = []
            for relation in raw_relations:
                if relation.get("confidence", 0) >= confidence_threshold:
                    standardized = self.graph_processor.standardize_relation(relation)
                    relations.append(standardized)
            
            # 更新统计
            self.processing_stats["total_relations"] += len(relations)
            
            logger.info(f"提取到 {len(relations)} 个关系 (阈值: {confidence_threshold})")
            
            return relations
            
        except ServiceCallError as e:
            logger.error(f"关系提取失败: {e}")
            if e.status_code == 503:
                # 服务不可用，返回空列表
                return []
            raise
    
    async def _fallback_entity_extraction(self, text: str) -> List[Dict[str, Any]]:
        """实体提取的降级策略"""
        # 简单的规则提取（作为降级策略）
        import re
        
        entities = []
        
        # 人名提取
        person_pattern = r'[\u4e00-\u9fa5]{2,4}(?:先生|女士|教授|博士|老师|主任|经理|总监|董事长)?'
        persons = re.findall(person_pattern, text)
        for person in set(persons)[:5]:  # 去重并限制数量
            entities.append({
                "id": str(uuid.uuid4()),
                "text": person,
                "type": "PERSON",
                "confidence": 0.5,
                "properties": {"fallback": True}
            })
        
        # 组织机构提取
        org_pattern = r'[\u4e00-\u9fa5]{2,10}(?:公司|企业|集团|机构|组织|部门|学院|大学|研究所)'
        orgs = re.findall(org_pattern, text)
        for org in set(orgs)[:5]:
            entities.append({
                "id": str(uuid.uuid4()),
                "text": org,
                "type": "ORGANIZATION", 
                "confidence": 0.4,
                "properties": {"fallback": True}
            })
        
        # 地点提取
        location_pattern = r'[\u4e00-\u9fa5]{2,8}(?:省|市|县|区|镇|村|街道|路|大道|广场|医院|学校)'
        locations = re.findall(location_pattern, text)
        for location in set(locations)[:3]:
            entities.append({
                "id": str(uuid.uuid4()),
                "text": location,
                "type": "LOCATION",
                "confidence": 0.3,
                "properties": {"fallback": True}
            })
        
        logger.info(f"降级策略提取到 {len(entities)} 个实体")
        return entities
    
    # ==================== 权限和认证 ====================
    
    async def _check_graph_permission(self, user_id: str, operation: str) -> Dict[str, Any]:
        """检查知识图谱操作权限"""
        try:
            result = await self.service_client.call(
                service_name="base-service",
                method=CallMethod.POST,
                path="/api/v1/auth/check-permission",
                config=self.auth_config,
                json={
                    "user_id": user_id,
                    "resource_type": "KNOWLEDGE_GRAPH",
                    "action": operation,
                    "context": {
                        "service": "knowledge-graph-service",
                        "operation": operation
                    }
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return {"allowed": False, "error": str(e)}
    
    # ==================== 数据获取和处理 ====================
    
    async def _get_document_content(self, document_id: str, user_id: str) -> Dict[str, Any]:
        """获取文档内容"""
        try:
            result = await self.service_client.call(
                service_name="knowledge-service",
                method=CallMethod.GET,
                path=f"/api/v1/documents/{document_id}",
                config=self.knowledge_config,
                params={"user_id": user_id}
            )
            
            return {
                "success": True,
                "data": result
            }
            
        except ServiceCallError as e:
            logger.error(f"获取文档失败: {e}")
            return {
                "success": False,
                "error": f"文档不存在或无权限访问: {document_id}",
                "status_code": e.status_code
            }
    
    async def _process_entities(self, entities: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
        """处理实体：去重、链接、标准化"""
        if not entities:
            return []
        
        # 实体去重 (基于文本相似度)
        unique_entities = []
        seen_texts = set()
        
        for entity in entities:
            entity_text = entity.get("text", "").lower().strip()
            if entity_text and entity_text not in seen_texts:
                seen_texts.add(entity_text)
                unique_entities.append(entity)
        
        # 实体链接 (可以调用外部知识库API进行实体链接)
        linked_entities = []
        for entity in unique_entities:
            # 这里可以扩展实体链接逻辑
            entity["linked"] = False
            entity["kb_id"] = None
            linked_entities.append(entity)
        
        logger.info(f"实体处理完成：{len(entities)} -> {len(linked_entities)}")
        return linked_entities
    
    async def _process_relations(
        self, 
        relations: List[Dict[str, Any]], 
        entities: List[Dict[str, Any]], 
        user_id: str
    ) -> List[Dict[str, Any]]:
        """处理关系：验证、过滤、标准化"""
        if not relations:
            return []
        
        entity_texts = {entity.get("text", "").lower() for entity in entities}
        
        valid_relations = []
        for relation in relations:
            source = relation.get("source", "").lower()
            target = relation.get("target", "").lower()
            
            # 验证关系的实体是否存在
            if source in entity_texts and target in entity_texts:
                valid_relations.append(relation)
        
        logger.info(f"关系处理完成：{len(relations)} -> {len(valid_relations)}")
        return valid_relations
    
    async def _build_graph_structure(self, entities: List[Dict[str, Any]], relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建图谱结构"""
        # 构建节点和边的图结构
        nodes = []
        edges = []
        
        entity_map = {}
        for entity in entities:
            node_id = entity.get("id", str(uuid.uuid4()))
            entity_map[entity.get("text", "")] = node_id
            
            nodes.append({
                "id": node_id,
                "label": entity.get("text", ""),
                "type": entity.get("type", "CONCEPT"),
                "properties": entity.get("properties", {}),
                "confidence": entity.get("confidence", 0.8)
            })
        
        for relation in relations:
            source_text = relation.get("source", "")
            target_text = relation.get("target", "")
            
            if source_text in entity_map and target_text in entity_map:
                edges.append({
                    "id": relation.get("id", str(uuid.uuid4())),
                    "source": entity_map[source_text],
                    "target": entity_map[target_text],
                    "type": relation.get("type", "RELATED_TO"),
                    "properties": relation.get("properties", {}),
                    "confidence": relation.get("confidence", 0.7)
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "created_at": datetime.now().isoformat()
        }
    
    async def _save_graph_to_database(
        self, 
        document_id: str, 
        user_id: str, 
        graph_structure: Dict[str, Any],
        document_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """保存图谱到数据库"""
        try:
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/graph/create",
                config=self.database_config,
                json={
                    "document_id": document_id,
                    "user_id": user_id,
                    "graph_data": graph_structure,
                    "metadata": {
                        "document_title": document_metadata.get("title", ""),
                        "document_type": document_metadata.get("type", ""),
                        "created_at": datetime.now().isoformat(),
                        "extraction_stats": {
                            "node_count": graph_structure["node_count"],
                            "edge_count": graph_structure["edge_count"]
                        }
                    }
                }
            )
            
            return {
                "success": True,
                "graph_id": result.get("graph_id")
            }
            
        except Exception as e:
            logger.error(f"保存图谱失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_graph_summary(self, graph_structure: Dict[str, Any]) -> Dict[str, Any]:
        """生成图谱摘要"""
        nodes = graph_structure.get("nodes", [])
        edges = graph_structure.get("edges", [])
        
        # 统计实体类型
        entity_types = defaultdict(int)
        for node in nodes:
            entity_types[node.get("type", "UNKNOWN")] += 1
        
        # 统计关系类型
        relation_types = defaultdict(int)
        for edge in edges:
            relation_types[edge.get("type", "UNKNOWN")] += 1
        
        # 找出度最高的节点
        node_degrees = defaultdict(int)
        for edge in edges:
            node_degrees[edge.get("source", "")] += 1
            node_degrees[edge.get("target", "")] += 1
        
        top_nodes = sorted(node_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_entities": len(nodes),
            "total_relations": len(edges),
            "entity_types": dict(entity_types),
            "relation_types": dict(relation_types),
            "top_connected_entities": top_nodes,
            "graph_density": len(edges) / max(len(nodes) * (len(nodes) - 1) / 2, 1) if len(nodes) > 1 else 0
        }


    # ==================== 批量处理和查询 ====================
    
    async def batch_process_documents(self, document_ids: List[str], user_id: str) -> Dict[str, Any]:
        """批量处理文档，构建知识图谱"""
        start_time = datetime.now()
        results = {
            "success": 0,
            "failed": 0,
            "total": len(document_ids),
            "results": [],
            "failed_documents": []
        }
        
        logger.info(f"开始批量处理 {len(document_ids)} 个文档")
        
        # 限制并发数量，避免过载
        semaphore = asyncio.Semaphore(3)
        
        async def process_single_document(doc_id: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    result = await self.build_knowledge_graph_workflow(doc_id, user_id)
                    if result.get("success"):
                        results["success"] += 1
                        results["results"].append({
                            "document_id": doc_id,
                            "graph_id": result.get("graph_id"),
                            "entity_count": result.get("entity_count"),
                            "relation_count": result.get("relation_count")
                        })
                    else:
                        results["failed"] += 1
                        results["failed_documents"].append({
                            "document_id": doc_id,
                            "error": result.get("error")
                        })
                    return result
                except Exception as e:
                    results["failed"] += 1
                    results["failed_documents"].append({
                        "document_id": doc_id,
                        "error": str(e)
                    })
                    logger.error(f"处理文档 {doc_id} 失败: {e}")
                    return {"success": False, "error": str(e)}
        
        # 并发处理
        await asyncio.gather(
            *[process_single_document(doc_id) for doc_id in document_ids],
            return_exceptions=True
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        results["processing_time"] = processing_time
        
        logger.info(f"批量处理完成：成功 {results['success']}/{results['total']}, 耗时: {processing_time:.2f}秒")
        
        return results
    
    async def query_related_knowledge(
        self, 
        query: str, 
        user_id: str,
        limit: int = 10,
        confidence_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """查询相关知识"""
        try:
            # 权限检查
            permission_check = await self._check_graph_permission(user_id, "query")
            if not permission_check.get("allowed"):
                return {
                    "success": False,
                    "error": "权限不足",
                    "required_permission": "knowledge_graph:query"
                }
            
            # 调用图数据库查询相关实体和关系
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/graph/query",
                config=self.database_config,
                json={
                    "query": query,
                    "user_id": user_id,
                    "query_type": "semantic_search",
                    "limit": limit,
                    "confidence_threshold": confidence_threshold
                }
            )
            
            return {
                "success": True,
                "query": query,
                "results": result.get("results", []),
                "total_count": result.get("total_count", 0)
            }
            
        except Exception as e:
            logger.error(f"知识查询失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    async def graph_reasoning(
        self, 
        source_entity: str, 
        target_entity: str, 
        user_id: str,
        max_depth: int = 3,
        reasoning_type: str = "shortest_path"
    ) -> Dict[str, Any]:
        """图谱推理：查找实体间的路径"""
        try:
            # 权限检查
            permission_check = await self._check_graph_permission(user_id, "reasoning")
            if not permission_check.get("allowed"):
                return {
                    "success": False,
                    "error": "权限不足"
                }
            
            result = await self.service_client.call(
                service_name="database-service",
                method=CallMethod.POST,
                path="/api/v1/graph/reasoning",
                config=self.database_config,
                json={
                    "source_entity": source_entity,
                    "target_entity": target_entity,
                    "user_id": user_id,
                    "reasoning_type": reasoning_type,
                    "max_depth": max_depth
                }
            )
            
            return {
                "success": True,
                "source": source_entity,
                "target": target_entity,
                "paths": result.get("paths", []),
                "shortest_distance": result.get("shortest_distance", -1)
            }
            
        except Exception as e:
            logger.error(f"图谱推理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== 服务监控和管理 ====================
    
    async def health_check_all_services(self) -> Dict[str, bool]:
        """检查所有相关服务的健康状态"""
        services = ["model-service", "knowledge-service", "database-service", "base-service"]
        health_status = {}
        
        async def check_service_health(service_name: str) -> Tuple[str, bool]:
            try:
                result = await self.service_client.call(
                    service_name=service_name,
                    method=CallMethod.GET,
                    path="/health",
                    config=CallConfig(timeout=5, retry_times=1)
                )
                return service_name, result.get("status") == "healthy"
            except Exception:
                return service_name, False
        
        # 并发检查所有服务
        health_results = await asyncio.gather(
            *[check_service_health(service) for service in services],
            return_exceptions=True
        )
        
        for service_name, is_healthy in health_results:
            if isinstance(is_healthy, bool):
                health_status[service_name] = is_healthy
            else:
                health_status[service_name] = False
        
        return health_status
    
    async def get_service_metrics(self) -> Dict[str, Any]:
        """获取服务调用指标"""
        return {
            "processing_stats": self.processing_stats.copy(),
            "graph_capabilities": self.graph_capabilities,
            "service_configs": {
                "model_timeout": self.model_config.timeout,
                "knowledge_timeout": self.knowledge_config.timeout,
                "database_timeout": self.database_config.timeout,
                "auth_timeout": self.auth_config.timeout
            },
            "last_updated": datetime.now().isoformat()
        }
    
    async def reset_stats(self):
        """重置统计信息"""
        self.processing_stats = {
            "total_documents": 0,
            "total_entities": 0,
            "total_relations": 0,
            "processing_time": 0.0
        }
        logger.info("统计信息已重置")


# ==================== 便捷的全局函数 ====================

async def build_knowledge_graph(document_id: str, user_id: str, extraction_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """便捷的知识图谱构建函数"""
    async with KnowledgeGraphServiceIntegration() as kg_service:
        return await kg_service.build_knowledge_graph_workflow(document_id, user_id, extraction_config)


async def batch_build_knowledge_graphs(document_ids: List[str], user_id: str) -> Dict[str, Any]:
    """便捷的批量知识图谱构建函数"""
    async with KnowledgeGraphServiceIntegration() as kg_service:
        return await kg_service.batch_process_documents(document_ids, user_id)


async def query_knowledge_graph(query: str, user_id: str, limit: int = 10) -> Dict[str, Any]:
    """便捷的知识图谱查询函数"""
    async with KnowledgeGraphServiceIntegration() as kg_service:
        return await kg_service.query_related_knowledge(query, user_id, limit)


# ==================== 使用示例 ====================

async def knowledge_graph_demo():
    """知识图谱服务集成模块"""
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async with KnowledgeGraphServiceIntegration() as kg_service:
        
        # 1. 服务健康检查
        logger.info("=== 🏥 服务健康检查 ===")
        health_status = await kg_service.health_check_all_services()
        for service, status in health_status.items():
            print(f"{service}: {'✅ 正常' if status else '❌ 异常'}")
        
        # 2. 单文档知识图谱构建
        logger.info("\n=== 📄 单文档图谱构建 ===")
        extraction_config = {
            "entity_model": "bert-ner",
            "relation_model": "bert-relation", 
            "confidence_threshold": 0.7
        }
        
        try:
            result = await kg_service.build_knowledge_graph_workflow(
                "doc_001", "user_123", extraction_config
            )
            if result.get("success"):
                print(f"✅ 图谱构建成功:")
                print(f"   图谱ID: {result.get('graph_id')}")
                print(f"   实体数: {result.get('entity_count')}")
                print(f"   关系数: {result.get('relation_count')}")
                print(f"   处理时间: {result.get('processing_time'):.2f}秒")
            else:
                print(f"❌ 图谱构建失败: {result.get('error')}")
        except Exception as e:
            print(f"❌ 异常: {e}")
        
        # 3. 批量文档处理
        logger.info("\n=== 📚 批量文档处理 ===")
        document_ids = ["doc_001", "doc_002", "doc_003", "doc_004"]
        batch_result = await kg_service.batch_process_documents(document_ids, "user_123")
        
        print(f"批量处理结果:")
        print(f"   总文档数: {batch_result['total']}")
        print(f"   成功: {batch_result['success']}")
        print(f"   失败: {batch_result['failed']}")
        print(f"   处理时间: {batch_result.get('processing_time', 0):.2f}秒")
        
        if batch_result.get('failed_documents'):
            print(f"   失败文档: {[doc['document_id'] for doc in batch_result['failed_documents']]}")
        
        # 4. 实体抽取测试
        logger.info("\n=== 🔍 实体抽取测试 ===")
        test_text = "张三是北京大学的教授，他在人工智能领域有很深的研究。"
        entities = await kg_service.extract_entities_from_text(test_text, "user_123")
        print(f"从文本中提取到 {len(entities)} 个实体:")
        for entity in entities[:5]:  # 只显示前5个
            print(f"   - {entity.get('text')} ({entity.get('type')}, 置信度: {entity.get('confidence'):.2f})")
        
        # 5. 关系抽取测试
        logger.info("\n=== 🔗 关系抽取测试 ===")
        relations = await kg_service.extract_relations_from_text(test_text, "user_123")
        print(f"从文本中提取到 {len(relations)} 个关系:")
        for relation in relations[:5]:
            print(f"   - {relation.get('source')} → {relation.get('target')} ({relation.get('type')})")
        
        # 6. 知识查询
        logger.info("\n=== 🔍 知识查询 ===")
        query_result = await kg_service.query_related_knowledge("人工智能", "user_123", limit=5)
        if query_result.get("success"):
            print(f"查询 '人工智能' 相关知识:")
            print(f"   找到 {query_result.get('total_count', 0)} 条相关结果")
            for i, result in enumerate(query_result.get('results', [])[:3], 1):
                print(f"   {i}. {result}")
        else:
            print(f"❌ 查询失败: {query_result.get('error')}")
        
        # 7. 图谱推理
        logger.info("\n=== 🧠 图谱推理 ===")
        reasoning_result = await kg_service.graph_reasoning(
            "张三", "北京大学", "user_123", max_depth=3
        )
        if reasoning_result.get("success"):
            print(f"推理路径 '张三' → '北京大学':")
            paths = reasoning_result.get("paths", [])
            if paths:
                print(f"   找到 {len(paths)} 条路径")
                print(f"   最短距离: {reasoning_result.get('shortest_distance')}")
            else:
                print("   未找到连接路径")
        else:
            print(f"❌ 推理失败: {reasoning_result.get('error')}")
        
        # 8. 服务指标
        logger.info("\n=== 📊 服务指标 ===")
        metrics = await kg_service.get_service_metrics()
        stats = metrics.get("processing_stats", {})
        print(f"处理统计:")
        print(f"   已处理文档: {stats.get('total_documents', 0)}")
        print(f"   抽取实体: {stats.get('total_entities', 0)}")
        print(f"   抽取关系: {stats.get('total_relations', 0)}")
        print(f"   总处理时间: {stats.get('processing_time', 0):.2f}秒")
        
        # 9. 重置统计
        await kg_service.reset_stats()
        logger.info("✅ 统计信息已重置")


# 简单的单用途函数示例
async def simple_examples():
    """简单使用示例"""
    
    # 构建单个文档的知识图谱
    result = await build_knowledge_graph("doc_001", "user_123")
    print(f"图谱构建结果: {result}")
    
    # 批量构建知识图谱
    batch_result = await batch_build_knowledge_graphs(
        ["doc_001", "doc_002"], "user_123"
    )
    print(f"批量处理结果: {batch_result}")
    
    # 查询知识图谱
    query_result = await query_knowledge_graph("机器学习", "user_123")
    print(f"查询结果: {query_result}")


if __name__ == "__main__":
    print("🚀 知识图谱服务集成启动")
    print("=" * 50)
    asyncio.run(knowledge_graph_demo()) 