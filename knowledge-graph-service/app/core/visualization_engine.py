"""
可视化引擎核心组件
基于vis.js生成交互式知识图谱可视化
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path

from ..models.graph import Entity, Relation, VisualizationConfig
from ..config.settings import settings

logger = logging.getLogger(__name__)


class VisualizationEngine:
    """可视化引擎
    
    生成基于vis.js的交互式知识图谱可视化
    """
    
    def __init__(self):
        """初始化可视化引擎"""
        self.static_dir = Path(__file__).parent.parent.parent / "static"
        self.templates_dir = Path(__file__).parent.parent.parent / "templates"
        
        # 确保目录存在
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # 可视化配置
        self.default_config = VisualizationConfig()
        
        # 初始化HTML模板
        self._init_html_template()
        
        logger.info("Visualization engine initialized")
    
    def _init_html_template(self):
        """初始化HTML模板"""
        try:
            template_path = self.templates_dir / "knowledge_graph.html"
            
            if not template_path.exists():
                # 创建默认HTML模板
                self._create_default_html_template(template_path)
            
            self.html_template = template_path.read_text(encoding='utf-8')
            logger.info("HTML template initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize HTML template: {e}")
            raise
    
    def _create_default_html_template(self, template_path: Path):
        """创建默认HTML模板"""
        html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>{{ graph_title }} - 知识图谱</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background-color: {{ background_color }};
            color: {{ font_color }};
        }
        
        .container {
            display: flex;
            height: 100vh;
        }
        
        .sidebar {
            width: 300px;
            background-color: #f8f9fa;
            border-right: 1px solid #dee2e6;
            padding: 20px;
            overflow-y: auto;
        }
        
        .main-content {
            flex: 1;
            position: relative;
        }
        
        #graph-container {
            width: 100%;
            height: 100%;
            border: none;
        }
        
        .controls {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.9);
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        
        .controls button {
            margin: 0 5px 5px 0;
            padding: 5px 10px;
            border: 1px solid #ddd;
            background: white;
            cursor: pointer;
            border-radius: 3px;
        }
        
        .controls button:hover {
            background: #f5f5f5;
        }
        
        .stats {
            margin-bottom: 20px;
            padding: 15px;
            background: white;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .stats h3 {
            margin: 0 0 10px 0;
            color: #495057;
        }
        
        .stats-item {
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
        }
        
        .legend {
            margin-top: 20px;
            padding: 15px;
            background: white;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .legend h3 {
            margin: 0 0 10px 0;
            color: #495057;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
        }
        
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 10px;
        }
        
        .search-box {
            margin-bottom: 20px;
        }
        
        .search-box input {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        
        .entity-list {
            max-height: 300px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
        }
        
        .entity-item {
            padding: 8px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
        }
        
        .entity-item:hover {
            background: #f8f9fa;
        }
        
        .entity-item:last-child {
            border-bottom: none;
        }
        
        .entity-name {
            font-weight: bold;
            margin-bottom: 2px;
        }
        
        .entity-type {
            font-size: 0.9em;
            color: #6c757d;
        }
        
        .dark-theme {
            background-color: #1a1a1a;
            color: #ffffff;
        }
        
        .dark-theme .sidebar {
            background-color: #2d2d2d;
            border-right-color: #444;
        }
        
        .dark-theme .stats,
        .dark-theme .legend,
        .dark-theme .entity-list {
            background-color: #3d3d3d;
            color: #ffffff;
        }
        
        .dark-theme .controls {
            background: rgba(45, 45, 45, 0.9);
            color: #ffffff;
        }
        
        .dark-theme .controls button {
            background: #4d4d4d;
            border-color: #666;
            color: #ffffff;
        }
        
        .dark-theme .controls button:hover {
            background: #5d5d5d;
        }
        
        .dark-theme .search-box input {
            background: #4d4d4d;
            border-color: #666;
            color: #ffffff;
        }
        
        .dark-theme .entity-item {
            border-bottom-color: #555;
        }
        
        .dark-theme .entity-item:hover {
            background: #4d4d4d;
        }
    </style>
    
    <!-- vis.js CSS -->
    <link href="https://unpkg.com/vis-network@9.1.7/dist/vis-network.min.css" rel="stylesheet" type="text/css">
</head>
<body id="app-body">
    <div class="container">
        <!-- 侧边栏 -->
        <div class="sidebar">
            <!-- 统计信息 -->
            <div class="stats">
                <h3>图谱统计</h3>
                <div class="stats-item">
                    <span>实体数量:</span>
                    <span id="entity-count">{{ entity_count }}</span>
                </div>
                <div class="stats-item">
                    <span>关系数量:</span>
                    <span id="relation-count">{{ relation_count }}</span>
                </div>
                <div class="stats-item">
                    <span>图谱密度:</span>
                    <span id="graph-density">{{ graph_density }}</span>
                </div>
                <div class="stats-item">
                    <span>平均置信度:</span>
                    <span id="avg-confidence">{{ avg_confidence }}</span>
                </div>
            </div>
            
            <!-- 图例 -->
            <div class="legend">
                <h3>实体类型</h3>
                <div id="legend-content">
                    {{ legend_content }}
                </div>
            </div>
            
            <!-- 搜索功能 -->
            <div class="search-box">
                <input type="text" id="search-input" placeholder="搜索实体...">
            </div>
            
            <!-- 实体列表 -->
            <div class="entity-list" id="entity-list">
                {{ entity_list }}
            </div>
        </div>
        
        <!-- 主内容区域 -->
        <div class="main-content">
            <!-- 控制面板 -->
            <div class="controls">
                <button onclick="resetView()">重置视图</button>
                <button onclick="togglePhysics()">物理模拟</button>
                <button onclick="toggleTheme()">切换主题</button>
                <button onclick="exportData()">导出数据</button>
                <button onclick="showHelp()">帮助</button>
            </div>
            
            <!-- 图谱容器 -->
            <div id="graph-container"></div>
        </div>
    </div>
    
    <!-- vis.js JavaScript -->
    <script src="https://unpkg.com/vis-network@9.1.7/dist/vis-network.min.js"></script>
    
    <script>
        // 图谱数据
        const nodes = new vis.DataSet({{ nodes_data }});
        const edges = new vis.DataSet({{ edges_data }});
        
        // 网络配置
        const options = {
            nodes: {
                shape: 'dot',
                size: 16,
                font: {
                    size: 14,
                    face: 'Arial'
                },
                borderWidth: 2,
                shadow: true
            },
            edges: {
                width: 2,
                color: {
                    color: '#848484',
                    highlight: '#3366cc',
                    hover: '#333333'
                },
                arrows: {
                    to: {
                        enabled: true,
                        scaleFactor: 1,
                        type: 'arrow'
                    }
                },
                smooth: {
                    enabled: {{ smooth_edges }},
                    type: 'dynamic',
                    roundness: 0.5
                },
                font: {
                    size: 12,
                    face: 'Arial'
                },
                labelHighlightBold: true
            },
            physics: {
                enabled: {{ physics_enabled }},
                stabilization: {
                    iterations: 1000
                },
                barnesHut: {
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 95,
                    springConstant: 0.04,
                    damping: 0.09,
                    avoidOverlap: 0.1
                }
            },
            interaction: {
                hover: true,
                selectConnectedEdges: false,
                tooltipDelay: 300
            },
            layout: {
                randomSeed: 42
            }
        };
        
        // 创建网络
        const container = document.getElementById('graph-container');
        const data = { nodes: nodes, edges: edges };
        const network = new vis.Network(container, data, options);
        
        // 变量
        let physicsEnabled = {{ physics_enabled }};
        let isDarkTheme = false;
        
        // 事件监听
        network.on('click', function(event) {
            const nodeId = event.nodes[0];
            if (nodeId) {
                highlightNode(nodeId);
            }
        });
        
        network.on('hoverNode', function(event) {
            const nodeId = event.node;
            showNodeTooltip(nodeId, event.pointer.DOM);
        });
        
        network.on('blurNode', function(event) {
            hideNodeTooltip();
        });
        
        // 功能函数
        function resetView() {
            network.fit();
            network.setOptions({ physics: { enabled: physicsEnabled } });
        }
        
        function togglePhysics() {
            physicsEnabled = !physicsEnabled;
            network.setOptions({ physics: { enabled: physicsEnabled } });
        }
        
        function toggleTheme() {
            isDarkTheme = !isDarkTheme;
            const body = document.getElementById('app-body');
            
            if (isDarkTheme) {
                body.classList.add('dark-theme');
                network.setOptions({
                    nodes: {
                        color: {
                            border: '#ffffff',
                            background: '#4d4d4d'
                        }
                    },
                    edges: {
                        color: {
                            color: '#cccccc',
                            highlight: '#66ccff',
                            hover: '#ffffff'
                        }
                    }
                });
            } else {
                body.classList.remove('dark-theme');
                network.setOptions({
                    nodes: {
                        color: {
                            border: '#2B7CE9',
                            background: '#D2E5FF'
                        }
                    },
                    edges: {
                        color: {
                            color: '#848484',
                            highlight: '#3366cc',
                            hover: '#333333'
                        }
                    }
                });
            }
        }
        
        function exportData() {
            const graphData = {
                nodes: nodes.get(),
                edges: edges.get(),
                metadata: {
                    title: '{{ graph_title }}',
                    generated_at: new Date().toISOString(),
                    entity_count: {{ entity_count }},
                    relation_count: {{ relation_count }}
                }
            };
            
            const dataStr = JSON.stringify(graphData, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(dataBlob);
            
            const link = document.createElement('a');
            link.href = url;
            link.download = '{{ graph_title }}_graph_data.json';
            link.click();
            
            URL.revokeObjectURL(url);
        }
        
        function showHelp() {
            alert('知识图谱操作帮助:\\n\\n' +
                  '• 拖拽：移动节点\\n' +
                  '• 滚轮：缩放视图\\n' +
                  '• 点击节点：高亮显示相关节点\\n' +
                  '• 悬停：显示节点详情\\n' +
                  '• 搜索：在左侧搜索框输入关键词\\n' +
                  '• 重置视图：恢复到初始状态\\n' +
                  '• 物理模拟：开启/关闭动态布局\\n' +
                  '• 切换主题：明暗主题切换\\n' +
                  '• 导出数据：下载图谱数据JSON文件');
        }
        
        function highlightNode(nodeId) {
            const connectedNodes = network.getConnectedNodes(nodeId);
            const connectedEdges = network.getConnectedEdges(nodeId);
            
            // 高亮相关节点和边
            const highlightNodes = [nodeId].concat(connectedNodes);
            const highlightEdges = connectedEdges;
            
            // 更新节点颜色
            nodes.update(nodes.get().map(node => {
                if (highlightNodes.includes(node.id)) {
                    return { ...node, color: { border: '#ff6b6b', background: '#ffe0e0' } };
                } else {
                    return { ...node, color: { border: '#cccccc', background: '#f0f0f0' } };
                }
            }));
            
            // 更新边颜色
            edges.update(edges.get().map(edge => {
                if (highlightEdges.includes(edge.id)) {
                    return { ...edge, color: { color: '#ff6b6b' } };
                } else {
                    return { ...edge, color: { color: '#cccccc' } };
                }
            }));
            
            // 3秒后恢复原色
            setTimeout(() => {
                resetHighlight();
            }, 3000);
        }
        
        function resetHighlight() {
            // 重置所有节点和边的颜色
            nodes.update(nodes.get().map(node => {
                const originalColor = node.originalColor || { border: '#2B7CE9', background: '#D2E5FF' };
                return { ...node, color: originalColor };
            }));
            
            edges.update(edges.get().map(edge => {
                const originalColor = edge.originalColor || { color: '#848484' };
                return { ...edge, color: originalColor };
            }));
        }
        
        function showNodeTooltip(nodeId, position) {
            const node = nodes.get(nodeId);
            if (!node) return;
            
            // 创建tooltip
            const tooltip = document.createElement('div');
            tooltip.id = 'node-tooltip';
            tooltip.style.cssText = `
                position: absolute;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
                z-index: 1000;
                max-width: 200px;
                pointer-events: none;
                left: ${position.x + 10}px;
                top: ${position.y - 10}px;
            `;
            
            tooltip.innerHTML = `
                <div><strong>${node.label}</strong></div>
                <div>类型: ${node.group || 'Unknown'}</div>
                <div>置信度: ${node.confidence || 'N/A'}</div>
                <div>频次: ${node.frequency || 'N/A'}</div>
            `;
            
            document.body.appendChild(tooltip);
        }
        
        function hideNodeTooltip() {
            const tooltip = document.getElementById('node-tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        }
        
        // 搜索功能
        document.getElementById('search-input').addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase();
            const entityItems = document.querySelectorAll('.entity-item');
            
            entityItems.forEach(item => {
                const entityName = item.querySelector('.entity-name').textContent.toLowerCase();
                const entityType = item.querySelector('.entity-type').textContent.toLowerCase();
                
                if (entityName.includes(query) || entityType.includes(query)) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        });
        
        // 实体列表点击事件
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('entity-item') || e.target.closest('.entity-item')) {
                const entityItem = e.target.closest('.entity-item');
                const entityId = entityItem.dataset.entityId;
                
                // 聚焦到该节点
                network.focus(entityId, {
                    scale: 1.5,
                    animation: {
                        duration: 1000,
                        easingFunction: 'easeInOutQuad'
                    }
                });
                
                // 高亮该节点
                highlightNode(entityId);
            }
        });
        
        // 初始化完成
        network.on('stabilizationIterationsDone', function() {
            console.log('Knowledge graph visualization initialized');
        });
    </script>
</body>
</html>'''
        
        template_path.write_text(html_content, encoding='utf-8')
        logger.info(f"Created default HTML template: {template_path}")
    
    async def generate_html_visualization(self, entities: List[Entity], relations: List[Relation], 
                                        config: VisualizationConfig = None, graph_title: str = "知识图谱") -> str:
        """生成HTML可视化
        
        Args:
            entities: 实体列表
            relations: 关系列表
            config: 可视化配置
            graph_title: 图谱标题
            
        Returns:
            HTML内容
        """
        try:
            if not entities:
                logger.warning("No entities provided for visualization")
                return self._generate_empty_visualization(graph_title)
            
            # 使用配置
            viz_config = config or self.default_config
            
            # 生成节点数据
            nodes_data = self._generate_nodes_data(entities, viz_config)
            
            # 生成边数据
            edges_data = self._generate_edges_data(relations, viz_config)
            
            # 生成统计信息
            stats = self._calculate_visualization_stats(entities, relations)
            
            # 生成图例
            legend_content = self._generate_legend(entities)
            
            # 生成实体列表
            entity_list = self._generate_entity_list(entities)
            
            # 替换模板变量
            html_content = self.html_template.format(
                graph_title=graph_title,
                background_color=viz_config.background_color,
                font_color="#000000",
                entity_count=len(entities),
                relation_count=len(relations),
                graph_density=f"{stats['density']:.3f}",
                avg_confidence=f"{stats['avg_confidence']:.3f}",
                legend_content=legend_content,
                entity_list=entity_list,
                nodes_data=json.dumps(nodes_data, ensure_ascii=False),
                edges_data=json.dumps(edges_data, ensure_ascii=False),
                smooth_edges=str(viz_config.physics_enabled).lower(),
                physics_enabled=str(viz_config.physics_enabled).lower()
            )
            
            logger.info(f"Generated HTML visualization with {len(entities)} entities and {len(relations)} relations")
            return html_content
            
        except Exception as e:
            logger.error(f"Failed to generate HTML visualization: {e}")
            raise
    
    def _generate_nodes_data(self, entities: List[Entity], config: VisualizationConfig) -> List[Dict[str, Any]]:
        """生成节点数据"""
        try:
            nodes = []
            
            # 实体类型颜色映射
            entity_colors = self._get_entity_colors(entities, config)
            
            # 计算节点大小范围
            max_freq = max(entity.frequency for entity in entities) if entities else 1
            min_freq = min(entity.frequency for entity in entities) if entities else 1
            size_range = config.node_size_range
            
            for entity in entities:
                # 计算节点大小
                if max_freq > min_freq:
                    size_ratio = (entity.frequency - min_freq) / (max_freq - min_freq)
                    node_size = size_range[0] + (size_range[1] - size_range[0]) * size_ratio
                else:
                    node_size = size_range[0]
                
                # 获取颜色
                color = entity_colors.get(entity.entity_type, '#2B7CE9')
                
                node = {
                    'id': entity.id,
                    'label': entity.name,
                    'group': entity.entity_type,
                    'size': node_size,
                    'confidence': entity.confidence,
                    'frequency': entity.frequency,
                    'centrality': entity.centrality,
                    'color': {
                        'border': color,
                        'background': self._lighten_color(color, 0.3)
                    },
                    'originalColor': {
                        'border': color,
                        'background': self._lighten_color(color, 0.3)
                    },
                    'title': f"{entity.name}\\n类型: {entity.entity_type}\\n置信度: {entity.confidence:.3f}\\n频次: {entity.frequency}",
                    'font': {
                        'size': 12 if config.show_labels else 0
                    }
                }
                
                nodes.append(node)
            
            logger.info(f"Generated {len(nodes)} nodes")
            return nodes
            
        except Exception as e:
            logger.error(f"Failed to generate nodes data: {e}")
            raise
    
    def _generate_edges_data(self, relations: List[Relation], config: VisualizationConfig) -> List[Dict[str, Any]]:
        """生成边数据"""
        try:
            edges = []
            
            # 计算边宽度范围
            max_conf = max(relation.confidence for relation in relations) if relations else 1
            min_conf = min(relation.confidence for relation in relations) if relations else 1
            width_range = config.edge_width_range
            
            for relation in relations:
                # 计算边宽度
                if max_conf > min_conf:
                    width_ratio = (relation.confidence - min_conf) / (max_conf - min_conf)
                    edge_width = width_range[0] + (width_range[1] - width_range[0]) * width_ratio
                else:
                    edge_width = width_range[0]
                
                # 边颜色和样式
                edge_color = config.edge_color
                edge_style = 'dashed' if relation.inferred else 'solid'
                
                edge = {
                    'id': relation.id,
                    'from': relation.subject,
                    'to': relation.object,
                    'label': relation.predicate if config.show_edge_labels else '',
                    'width': edge_width,
                    'color': {
                        'color': edge_color,
                        'highlight': '#3366cc',
                        'hover': '#333333'
                    },
                    'originalColor': {
                        'color': edge_color
                    },
                    'dashes': edge_style == 'dashed',
                    'title': f"{relation.predicate}\\n置信度: {relation.confidence:.3f}\\n{'推理关系' if relation.inferred else '直接关系'}",
                    'confidence': relation.confidence,
                    'inferred': relation.inferred,
                    'arrows': {
                        'to': {
                            'enabled': True,
                            'scaleFactor': 1
                        }
                    }
                }
                
                edges.append(edge)
            
            logger.info(f"Generated {len(edges)} edges")
            return edges
            
        except Exception as e:
            logger.error(f"Failed to generate edges data: {e}")
            raise
    
    def _get_entity_colors(self, entities: List[Entity], config: VisualizationConfig) -> Dict[str, str]:
        """获取实体类型颜色映射"""
        try:
            entity_types = list(set(entity.entity_type for entity in entities))
            
            # 预定义颜色方案
            color_schemes = {
                'category10': [
                    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
                ],
                'category20': [
                    '#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', '#2ca02c',
                    '#98df8a', '#d62728', '#ff9896', '#9467bd', '#c5b0d5',
                    '#8c564b', '#c49c94', '#e377c2', '#f7b6d3', '#7f7f7f',
                    '#c7c7c7', '#bcbd22', '#dbdb8d', '#17becf', '#9edae5'
                ],
                'pastel': [
                    '#fbb4ae', '#b3cde3', '#ccebc5', '#decbe4', '#fed9a6',
                    '#ffffcc', '#e5d8bd', '#fddaec', '#f2f2f2', '#b3e2cd'
                ]
            }
            
            # 选择颜色方案
            colors = color_schemes.get(config.node_color_scheme, color_schemes['category10'])
            
            # 分配颜色
            entity_colors = {}
            for i, entity_type in enumerate(entity_types):
                color_index = i % len(colors)
                entity_colors[entity_type] = colors[color_index]
            
            return entity_colors
            
        except Exception as e:
            logger.error(f"Failed to get entity colors: {e}")
            return {}
    
    def _lighten_color(self, color: str, factor: float) -> str:
        """加亮颜色"""
        try:
            # 简单的颜色加亮实现
            if color.startswith('#'):
                hex_color = color[1:]
                if len(hex_color) == 6:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    
                    r = min(255, int(r + (255 - r) * factor))
                    g = min(255, int(g + (255 - g) * factor))
                    b = min(255, int(b + (255 - b) * factor))
                    
                    return f"#{r:02x}{g:02x}{b:02x}"
            
            return color
            
        except Exception as e:
            logger.error(f"Failed to lighten color: {e}")
            return color
    
    def _calculate_visualization_stats(self, entities: List[Entity], relations: List[Relation]) -> Dict[str, float]:
        """计算可视化统计信息"""
        try:
            entity_count = len(entities)
            relation_count = len(relations)
            
            # 计算图谱密度
            density = 0.0
            if entity_count > 1:
                max_edges = entity_count * (entity_count - 1)
                density = (2 * relation_count) / max_edges if max_edges > 0 else 0.0
            
            # 计算平均置信度
            total_confidence = sum(entity.confidence for entity in entities) + sum(relation.confidence for relation in relations)
            total_items = entity_count + relation_count
            avg_confidence = total_confidence / total_items if total_items > 0 else 0.0
            
            return {
                'density': density,
                'avg_confidence': avg_confidence
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate visualization stats: {e}")
            return {'density': 0.0, 'avg_confidence': 0.0}
    
    def _generate_legend(self, entities: List[Entity]) -> str:
        """生成图例HTML"""
        try:
            entity_types = {}
            for entity in entities:
                entity_types[entity.entity_type] = entity_types.get(entity.entity_type, 0) + 1
            
            # 获取颜色映射
            entity_colors = self._get_entity_colors(entities, self.default_config)
            
            legend_html = ""
            for entity_type, count in entity_types.items():
                color = entity_colors.get(entity_type, '#2B7CE9')
                legend_html += f'''
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: {color};"></div>
                        <span>{entity_type} ({count})</span>
                    </div>
                '''
            
            return legend_html
            
        except Exception as e:
            logger.error(f"Failed to generate legend: {e}")
            return ""
    
    def _generate_entity_list(self, entities: List[Entity]) -> str:
        """生成实体列表HTML"""
        try:
            # 按置信度排序
            sorted_entities = sorted(entities, key=lambda x: x.confidence, reverse=True)
            
            entity_list_html = ""
            for entity in sorted_entities:
                entity_list_html += f'''
                    <div class="entity-item" data-entity-id="{entity.id}">
                        <div class="entity-name">{entity.name}</div>
                        <div class="entity-type">{entity.entity_type}</div>
                    </div>
                '''
            
            return entity_list_html
            
        except Exception as e:
            logger.error(f"Failed to generate entity list: {e}")
            return ""
    
    def _generate_empty_visualization(self, graph_title: str) -> str:
        """生成空图谱可视化"""
        try:
            empty_html = f'''
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="utf-8">
                <title>{graph_title} - 知识图谱</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                        background-color: #f5f5f5;
                    }}
                    .empty-message {{
                        color: #666;
                        font-size: 18px;
                        margin-top: 100px;
                    }}
                </style>
            </head>
            <body>
                <div class="empty-message">
                    <h2>{graph_title}</h2>
                    <p>暂无图谱数据可显示</p>
                </div>
            </body>
            </html>
            '''
            
            return empty_html
            
        except Exception as e:
            logger.error(f"Failed to generate empty visualization: {e}")
            return f"<html><body><h2>{graph_title}</h2><p>Error generating visualization</p></body></html>"
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查模板文件
            template_exists = (self.templates_dir / "knowledge_graph.html").exists()
            
            # 检查静态文件目录
            static_exists = self.static_dir.exists()
            
            return {
                'status': 'healthy' if template_exists and static_exists else 'unhealthy',
                'template_exists': template_exists,
                'static_dir_exists': static_exists,
                'templates_dir': str(self.templates_dir),
                'static_dir': str(self.static_dir),
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }


# 全局可视化引擎实例
visualization_engine = VisualizationEngine()


async def get_visualization_engine() -> VisualizationEngine:
    """获取可视化引擎实例"""
    return visualization_engine