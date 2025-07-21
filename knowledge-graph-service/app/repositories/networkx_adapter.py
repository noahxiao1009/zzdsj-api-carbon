"""
NetworkX集成适配器
提供图算法计算和NetworkX对象导出功能
"""

import logging
import networkx as nx
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib

from ..models.graph import Entity, Relation, GraphStatistics

logger = logging.getLogger(__name__)


class NetworkXAdapter:
    """NetworkX集成适配器"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._graph_cache: Dict[str, nx.DiGraph] = {}
        self.max_cache_size = 10
        
    async def export_to_networkx(self, graph_id: str, entities: List[Entity], relations: List[Relation]) -> nx.DiGraph:
        """将图数据导出为NetworkX图对象"""
        try:
            # 检查缓存
            cache_key = self._generate_cache_key(graph_id, entities, relations)
            if cache_key in self._graph_cache:
                logger.info(f"Using cached NetworkX graph for {graph_id}")
                return self._graph_cache[cache_key]
            
            # 在线程池中创建NetworkX图
            graph = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._build_networkx_graph,
                entities,
                relations
            )
            
            # 缓存管理
            if len(self._graph_cache) >= self.max_cache_size:
                # 移除最旧的缓存
                oldest_key = next(iter(self._graph_cache))
                del self._graph_cache[oldest_key]
            
            self._graph_cache[cache_key] = graph
            
            logger.info(f"Successfully exported graph {graph_id} to NetworkX: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
            return graph
            
        except Exception as e:
            logger.error(f"Failed to export graph {graph_id} to NetworkX: {e}")
            raise
    
    def _build_networkx_graph(self, entities: List[Entity], relations: List[Relation]) -> nx.DiGraph:
        """构建NetworkX图对象"""
        G = nx.DiGraph()
        
        # 添加节点
        for entity in entities:
            G.add_node(
                entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                confidence=entity.confidence,
                properties=entity.properties,
                frequency=entity.frequency,
                centrality=entity.centrality,
                **entity.properties  # 将属性展开为节点属性
            )
        
        # 添加边
        for relation in relations:
            if G.has_node(relation.subject) and G.has_node(relation.object):
                G.add_edge(
                    relation.subject,
                    relation.object,
                    predicate=relation.predicate,
                    confidence=relation.confidence,
                    properties=relation.properties,
                    inferred=relation.inferred,
                    source=relation.source,
                    **relation.properties  # 将属性展开为边属性
                )
            else:
                logger.warning(f"Skipping relation {relation.id}: missing nodes {relation.subject} or {relation.object}")
        
        return G
    
    async def compute_advanced_metrics(self, graph_id: str, entities: List[Entity], relations: List[Relation], algorithms: List[str] = None) -> Dict[str, Any]:
        """计算高级图指标"""
        try:
            # 获取NetworkX图
            G = await self.export_to_networkx(graph_id, entities, relations)
            
            if G.number_of_nodes() == 0:
                return {"error": "Empty graph"}
            
            # 默认算法列表
            if algorithms is None:
                algorithms = [
                    'degree_centrality',
                    'betweenness_centrality', 
                    'closeness_centrality',
                    'pagerank',
                    'clustering',
                    'communities'
                ]
            
            # 在线程池中计算指标
            metrics = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._compute_graph_algorithms,
                G,
                algorithms
            )
            
            logger.info(f"Computed advanced metrics for graph {graph_id}: {list(metrics.keys())}")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to compute advanced metrics for graph {graph_id}: {e}")
            return {"error": str(e)}
    
    def _compute_graph_algorithms(self, G: nx.DiGraph, algorithms: List[str]) -> Dict[str, Any]:
        """计算图算法（在线程池中执行）"""
        metrics = {}
        
        try:
            # 度中心性
            if 'degree_centrality' in algorithms:
                metrics['degree_centrality'] = nx.degree_centrality(G)
            
            # 介数中心性
            if 'betweenness_centrality' in algorithms:
                metrics['betweenness_centrality'] = nx.betweenness_centrality(G)
            
            # 接近中心性
            if 'closeness_centrality' in algorithms:
                metrics['closeness_centrality'] = nx.closeness_centrality(G)
            
            # PageRank
            if 'pagerank' in algorithms:
                metrics['pagerank'] = nx.pagerank(G)
            
            # 聚类系数
            if 'clustering' in algorithms:
                metrics['clustering_coefficient'] = nx.clustering(G)
                metrics['average_clustering'] = nx.average_clustering(G)
            
            # 社区检测（使用Louvain算法的简化版本）
            if 'communities' in algorithms:
                try:
                    # 转换为无向图进行社区检测
                    UG = G.to_undirected()
                    # 使用贪心模块化社区检测
                    communities = list(nx.community.greedy_modularity_communities(UG))
                    metrics['communities'] = [list(community) for community in communities]
                    metrics['modularity'] = nx.community.modularity(UG, communities)
                except Exception as e:
                    logger.warning(f"Community detection failed: {e}")
                    metrics['communities'] = []
                    metrics['modularity'] = 0.0
            
            # 图的基本指标
            metrics['basic_metrics'] = {
                'nodes': G.number_of_nodes(),
                'edges': G.number_of_edges(),
                'density': nx.density(G),
                'is_connected': nx.is_weakly_connected(G),
                'number_of_components': nx.number_weakly_connected_components(G)
            }
            
            # 路径相关指标
            if nx.is_weakly_connected(G):
                try:
                    metrics['basic_metrics']['average_shortest_path_length'] = nx.average_shortest_path_length(G)
                    metrics['basic_metrics']['diameter'] = nx.diameter(G)
                except Exception as e:
                    logger.warning(f"Path metrics computation failed: {e}")
            
        except Exception as e:
            logger.error(f"Error computing graph algorithms: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    async def get_subgraph(self, graph_id: str, entities: List[Entity], relations: List[Relation], 
                          center_entity: str, depth: int = 2, limit: int = 100) -> Dict[str, Any]:
        """获取以指定实体为中心的子图"""
        try:
            # 获取完整的NetworkX图
            G = await self.export_to_networkx(graph_id, entities, relations)
            
            if center_entity not in G:
                return {
                    "error": f"Center entity '{center_entity}' not found in graph",
                    "nodes": [],
                    "edges": []
                }
            
            # 在线程池中计算子图
            subgraph_data = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._extract_subgraph,
                G,
                center_entity,
                depth,
                limit
            )
            
            logger.info(f"Extracted subgraph for {center_entity}: {len(subgraph_data['nodes'])} nodes, {len(subgraph_data['edges'])} edges")
            return subgraph_data
            
        except Exception as e:
            logger.error(f"Failed to get subgraph for {center_entity}: {e}")
            return {"error": str(e), "nodes": [], "edges": []}
    
    def _extract_subgraph(self, G: nx.DiGraph, center_entity: str, depth: int, limit: int) -> Dict[str, Any]:
        """提取子图（在线程池中执行）"""
        # 使用BFS获取指定深度内的所有节点
        visited_nodes = set()
        queue = [(center_entity, 0)]
        visited_nodes.add(center_entity)
        
        while queue and len(visited_nodes) < limit:
            current_node, current_depth = queue.pop(0)
            
            if current_depth < depth:
                # 获取邻居节点（包括入边和出边）
                neighbors = list(G.predecessors(current_node)) + list(G.successors(current_node))
                
                for neighbor in neighbors:
                    if neighbor not in visited_nodes and len(visited_nodes) < limit:
                        visited_nodes.add(neighbor)
                        queue.append((neighbor, current_depth + 1))
        
        # 创建子图
        subgraph = G.subgraph(visited_nodes)
        
        # 转换为标准格式
        nodes = []
        for node_id in subgraph.nodes():
            node_data = subgraph.nodes[node_id]
            nodes.append({
                "id": node_id,
                "name": node_data.get("name", node_id),
                "entity_type": node_data.get("entity_type", "unknown"),
                "confidence": node_data.get("confidence", 1.0),
                "properties": node_data.get("properties", {}),
                "is_center": node_id == center_entity
            })
        
        edges = []
        for source, target in subgraph.edges():
            edge_data = subgraph.edges[source, target]
            edges.append({
                "source": source,
                "target": target,
                "predicate": edge_data.get("predicate", "related_to"),
                "confidence": edge_data.get("confidence", 1.0),
                "properties": edge_data.get("properties", {}),
                "inferred": edge_data.get("inferred", False)
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "center_entity": center_entity,
            "depth": depth,
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }
    
    async def find_shortest_path(self, graph_id: str, entities: List[Entity], relations: List[Relation],
                                start_entity: str, end_entity: str) -> Dict[str, Any]:
        """查找两个实体之间的最短路径"""
        try:
            # 获取NetworkX图
            G = await self.export_to_networkx(graph_id, entities, relations)
            
            if start_entity not in G or end_entity not in G:
                return {
                    "error": "Start or end entity not found in graph",
                    "path": []
                }
            
            # 在线程池中计算最短路径
            path_data = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._find_path,
                G,
                start_entity,
                end_entity
            )
            
            return path_data
            
        except Exception as e:
            logger.error(f"Failed to find shortest path from {start_entity} to {end_entity}: {e}")
            return {"error": str(e), "path": []}
    
    def _find_path(self, G: nx.DiGraph, start_entity: str, end_entity: str) -> Dict[str, Any]:
        """查找路径（在线程池中执行）"""
        try:
            # 尝试找到最短路径
            path = nx.shortest_path(G, start_entity, end_entity)
            
            # 获取路径上的边信息
            path_edges = []
            for i in range(len(path) - 1):
                source, target = path[i], path[i + 1]
                edge_data = G.edges[source, target]
                path_edges.append({
                    "source": source,
                    "target": target,
                    "predicate": edge_data.get("predicate", "related_to"),
                    "confidence": edge_data.get("confidence", 1.0)
                })
            
            return {
                "path": path,
                "edges": path_edges,
                "length": len(path) - 1,
                "found": True
            }
            
        except nx.NetworkXNoPath:
            return {
                "path": [],
                "edges": [],
                "length": -1,
                "found": False,
                "error": "No path found between entities"
            }
        except Exception as e:
            return {
                "path": [],
                "edges": [],
                "length": -1,
                "found": False,
                "error": str(e)
            }
    
    def _generate_cache_key(self, graph_id: str, entities: List[Entity], relations: List[Relation]) -> str:
        """生成图缓存键"""
        # 基于图ID和数据hash生成缓存键
        entities_hash = hashlib.md5(str(len(entities)).encode()).hexdigest()[:8]
        relations_hash = hashlib.md5(str(len(relations)).encode()).hexdigest()[:8]
        return f"{graph_id}_{entities_hash}_{relations_hash}"
    
    async def export_to_formats(self, graph_id: str, entities: List[Entity], relations: List[Relation],
                               export_format: str = "json") -> Dict[str, Any]:
        """导出图数据为不同格式"""
        try:
            G = await self.export_to_networkx(graph_id, entities, relations)
            
            if export_format.lower() == "json":
                return nx.node_link_data(G)
            elif export_format.lower() == "gml":
                # 返回GML格式字符串
                import io
                output = io.StringIO()
                nx.write_gml(G, output)
                return {"gml_data": output.getvalue()}
            elif export_format.lower() == "graphml":
                # 返回GraphML格式字符串
                import io
                output = io.StringIO()
                nx.write_graphml(G, output)
                return {"graphml_data": output.getvalue()}
            else:
                return {"error": f"Unsupported export format: {export_format}"}
                
        except Exception as e:
            logger.error(f"Failed to export graph {graph_id} to format {export_format}: {e}")
            return {"error": str(e)}
    
    def clear_cache(self):
        """清理缓存"""
        self._graph_cache.clear()
        logger.info("NetworkX graph cache cleared")
    
    async def close(self):
        """关闭适配器"""
        self.executor.shutdown(wait=True)
        self.clear_cache()