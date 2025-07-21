"""
图谱管理API路由
提供知识图谱的REST API接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from typing import List, Optional
import logging

from ..models.graph import (
    KnowledgeGraph,
    GraphCreateRequest,
    GraphUpdateRequest,
    GraphGenerateRequest,
    GraphListResponse,
    GraphDataResponse,
    GraphExportRequest,
    GraphSearchRequest,
    GraphSearchResponse,
    Entity,
    Relation,
    GraphStatistics
)
from ..services.graph_service import GraphService, get_graph_service
from ..utils.auth import get_current_user
from ..adapters.legacy_adapter import LegacyKnowledgeGraphAdapter, LegacyAPIResponseAdapter

logger = logging.getLogger(__name__)

# 创建兼容的路由器
router = APIRouter(prefix="/graphs", tags=["Graphs"])

# 为了兼容前端调用，创建单数形式的路由器
frontend_router = APIRouter(prefix="/graph", tags=["Graph (Frontend)"])

# 为了兼容原始项目的API，创建一个额外的路由器  
legacy_router = APIRouter(prefix="/knowledge-graphs", tags=["Knowledge Graphs (Legacy)"])


@router.post("/", response_model=KnowledgeGraph)
async def create_graph(
    request: GraphCreateRequest,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """创建图谱"""
    try:
        user_id = current_user["user_id"]
        graph = await graph_service.create_graph(request, user_id)
        return graph
    except Exception as e:
        logger.error(f"Failed to create graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{graph_id}", response_model=KnowledgeGraph)
async def get_graph(
    graph_id: str,
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取图谱详情"""
    try:
        user_id = current_user["user_id"]
        graph = await graph_service.get_graph(graph_id, user_id, project_id)
        if not graph:
            raise HTTPException(status_code=404, detail="图谱未找到")
        return graph
    except Exception as e:
        logger.error(f"Failed to get graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{graph_id}", response_model=KnowledgeGraph)
async def update_graph(
    graph_id: str,
    request: GraphUpdateRequest,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """更新图谱"""
    try:
        user_id = current_user["user_id"]
        graph = await graph_service.update_graph(graph_id, request, user_id)
        if not graph:
            raise HTTPException(status_code=404, detail="图谱未找到")
        return graph
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{graph_id}")
async def delete_graph(
    graph_id: str,
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """删除图谱"""
    try:
        user_id = current_user["user_id"]
        success = await graph_service.delete_graph(graph_id, user_id, project_id)
        if not success:
            raise HTTPException(status_code=404, detail="图谱未找到")
        return {"message": "图谱删除成功"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{graph_id}/data", response_model=GraphDataResponse)
async def get_graph_data(
    graph_id: str,
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取图谱数据"""
    try:
        user_id = current_user["user_id"]
        entities, relations = await graph_service.get_graph_data(graph_id, user_id, project_id)
        statistics = await graph_service.get_graph_statistics(graph_id, user_id, project_id)
        
        return GraphDataResponse(
            graph_id=graph_id,
            entities=entities,
            relations=relations,
            statistics=statistics
        )
    except Exception as e:
        logger.error(f"Failed to get graph data: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{graph_id}/statistics", response_model=GraphStatistics)
async def get_graph_statistics(
    graph_id: str,
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取图谱统计信息"""
    try:
        user_id = current_user["user_id"]
        statistics = await graph_service.get_graph_statistics(graph_id, user_id, project_id)
        return statistics
    except Exception as e:
        logger.error(f"Failed to get graph statistics: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{graph_id}/visualization", response_class=HTMLResponse)
async def get_graph_visualization(
    graph_id: str,
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取图谱可视化HTML"""
    try:
        user_id = current_user["user_id"]
        html_content = await graph_service.get_visualization(graph_id, user_id, project_id)
        if not html_content:
            raise HTTPException(status_code=404, detail="可视化文件未找到")
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Failed to get graph visualization: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate")
async def generate_graph_async(
    request: GraphGenerateRequest,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """异步生成图谱"""
    try:
        user_id = current_user["user_id"]
        task_id = await graph_service.generate_graph_async(request, user_id)
        return {"task_id": task_id, "message": "图谱生成任务已创建"}
    except Exception as e:
        logger.error(f"Failed to generate graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{graph_id}/search", response_model=GraphSearchResponse)
async def search_graph(
    graph_id: str,
    request: GraphSearchRequest,
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """搜索图谱"""
    try:
        user_id = current_user["user_id"]
        entities = await graph_service.search_entities(
            graph_id, request.query, request.max_results, user_id, project_id
        )
        
        # TODO: 实现关系搜索
        relations = []
        
        return GraphSearchResponse(
            entities=entities,
            relations=relations,
            total_entities=len(entities),
            total_relations=len(relations),
            query_time=0.0  # TODO: 实现查询时间统计
        )
    except Exception as e:
        logger.error(f"Failed to search graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{graph_id}/entities/{entity_id}/neighbors")
async def get_entity_neighbors(
    graph_id: str,
    entity_id: str,
    depth: int = Query(1, ge=1, le=3, description="邻居深度"),
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取实体邻居"""
    try:
        user_id = current_user["user_id"]
        neighbors = await graph_service.get_entity_neighbors(
            graph_id, entity_id, depth, user_id, project_id
        )
        return neighbors
    except Exception as e:
        logger.error(f"Failed to get entity neighbors: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{graph_id}/path/{start_entity_id}/{end_entity_id}")
async def get_shortest_path(
    graph_id: str,
    start_entity_id: str,
    end_entity_id: str,
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取最短路径"""
    try:
        user_id = current_user["user_id"]
        path = await graph_service.get_shortest_path(
            graph_id, start_entity_id, end_entity_id, user_id, project_id
        )
        if path is None:
            return {"path": None, "message": "未找到路径"}
        return {"path": path}
    except Exception as e:
        logger.error(f"Failed to get shortest path: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{graph_id}/export")
async def export_graph(
    graph_id: str,
    request: GraphExportRequest,
    project_id: Optional[str] = Query(None, description="项目ID"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """导出图谱"""
    try:
        user_id = current_user["user_id"]
        export_data = await graph_service.export_graph(
            graph_id, request.export_format, user_id, project_id
        )
        return export_data
    except Exception as e:
        logger.error(f"Failed to export graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# 项目相关的图谱管理路由
project_graphs_router = APIRouter(prefix="/projects/{project_id}/graphs", tags=["Project Graphs"])


@project_graphs_router.post("/", response_model=KnowledgeGraph)
async def create_project_graph(
    project_id: str,
    request: GraphCreateRequest,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """在项目中创建图谱"""
    try:
        # 确保请求中的项目ID与路径参数一致
        request.project_id = project_id
        
        user_id = current_user["user_id"]
        graph = await graph_service.create_graph(request, user_id)
        return graph
    except Exception as e:
        logger.error(f"Failed to create project graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@project_graphs_router.get("/", response_model=GraphListResponse)
async def get_project_graphs(
    project_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取项目图谱列表"""
    try:
        user_id = current_user["user_id"]
        # TODO: 实现项目图谱列表查询
        graphs = []
        total = 0
        
        return GraphListResponse(
            graphs=graphs,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total
        )
    except Exception as e:
        logger.error(f"Failed to get project graphs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@project_graphs_router.get("/{graph_id}", response_model=KnowledgeGraph)
async def get_project_graph(
    project_id: str,
    graph_id: str,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取项目中的图谱详情"""
    try:
        user_id = current_user["user_id"]
        graph = await graph_service.get_graph(graph_id, user_id, project_id)
        if not graph:
            raise HTTPException(status_code=404, detail="图谱未找到")
        
        # 验证图谱确实属于该项目
        if graph.project_id != project_id:
            raise HTTPException(status_code=404, detail="图谱不属于该项目")
        
        return graph
    except Exception as e:
        logger.error(f"Failed to get project graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@project_graphs_router.delete("/{graph_id}")
async def delete_project_graph(
    project_id: str,
    graph_id: str,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """删除项目中的图谱"""
    try:
        user_id = current_user["user_id"]
        
        # 验证图谱属于该项目
        graph = await graph_service.get_graph(graph_id, user_id, project_id)
        if not graph or graph.project_id != project_id:
            raise HTTPException(status_code=404, detail="图谱未找到或不属于该项目")
        
        success = await graph_service.delete_graph(graph_id, user_id, project_id)
        if not success:
            raise HTTPException(status_code=404, detail="图谱删除失败")
        
        return {"message": "图谱删除成功"}
    except Exception as e:
        logger.error(f"Failed to delete project graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@project_graphs_router.post("/generate")
async def generate_project_graph(
    project_id: str,
    request: GraphGenerateRequest,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """在项目中异步生成图谱"""
    try:
        # 确保请求中的项目ID与路径参数一致
        request.project_id = project_id
        
        user_id = current_user["user_id"]
        task_id = await graph_service.generate_graph_async(request, user_id)
        return {"task_id": task_id, "message": "图谱生成任务已创建"}
    except Exception as e:
        logger.error(f"Failed to generate project graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# 包含项目图谱路由
router.include_router(project_graphs_router)


# ===== 兼容原始项目API的路由实现 =====

@legacy_router.get("/")
async def legacy_list_knowledge_graphs(
    kb_id: Optional[int] = Query(None, alias="knowledge_base_id", description="知识库ID"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取知识图谱列表 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        # TODO: 集成知识库服务，根据kb_id过滤
        graphs = []  # 从服务获取图谱列表
        
        # 使用适配器转换为原始API格式
        adapted_graphs = LegacyAPIResponseAdapter.adapt_list_response(graphs)
        return adapted_graphs
    except Exception as e:
        logger.error(f"Failed to list knowledge graphs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.post("/")
async def legacy_create_knowledge_graph(
    request: dict,  # 兼容原始的KnowledgeGraphCreate格式
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """创建知识图谱 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        
        # 使用适配器转换请求格式
        adapted_request = LegacyKnowledgeGraphAdapter.adapt_create_request(request)
        
        graph = await graph_service.create_graph(adapted_request, user_id)
        
        # 使用适配器转换响应格式
        adapted_response = LegacyKnowledgeGraphAdapter.adapt_graph_response(graph)
        return adapted_response
    except Exception as e:
        logger.error(f"Failed to create knowledge graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.get("/{graph_id}")
async def legacy_get_knowledge_graph(
    graph_id: str,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取知识图谱详情 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        graph = await graph_service.get_graph(graph_id, user_id, None)
        if not graph:
            raise HTTPException(status_code=404, detail="图谱未找到")
        
        # 使用适配器转换响应格式
        adapted_response = LegacyKnowledgeGraphAdapter.adapt_graph_response(graph)
        return adapted_response
    except Exception as e:
        logger.error(f"Failed to get knowledge graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.put("/{graph_id}", response_model=KnowledgeGraph)
async def legacy_update_knowledge_graph(
    graph_id: str,
    request: dict,  # 兼容原始的KnowledgeGraphUpdate格式
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """更新知识图谱 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        
        # 适配原始格式到新格式
        adapted_request = GraphUpdateRequest(
            name=request.get("name"),
            description=request.get("description"),
            # 处理其他字段...
        )
        
        graph = await graph_service.update_graph(graph_id, adapted_request, user_id)
        if not graph:
            raise HTTPException(status_code=404, detail="图谱未找到")
        return graph
    except Exception as e:
        logger.error(f"Failed to update knowledge graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.delete("/{graph_id}")
async def legacy_delete_knowledge_graph(
    graph_id: str,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """删除知识图谱 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        success = await graph_service.delete_graph(graph_id, user_id, None)
        if not success:
            raise HTTPException(status_code=404, detail="图谱未找到")
        return {"message": "图谱删除成功"}
    except Exception as e:
        logger.error(f"Failed to delete knowledge graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.get("/{graph_id}/visualization", response_class=HTMLResponse)
async def legacy_get_html_visualization(
    graph_id: str,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取HTML可视化 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        html_content = await graph_service.get_visualization(graph_id, user_id, None)
        if not html_content:
            raise HTTPException(status_code=404, detail="可视化文件未找到")
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Failed to get visualization: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.get("/{graph_id}/processing-status")
async def legacy_get_processing_status(
    graph_id: str,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取处理状态 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        graph = await graph_service.get_graph(graph_id, user_id, None)
        if not graph:
            raise HTTPException(status_code=404, detail="图谱未找到")
        
        return {
            "status": graph.status,
            "progress": graph.processing_progress.__dict__ if graph.processing_progress else None,
            "statistics": graph.statistics.__dict__ if graph.statistics else None
        }
    except Exception as e:
        logger.error(f"Failed to get processing status: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.post("/{graph_id}/export")
async def legacy_export_graph(
    graph_id: str,
    export_format: str = Query("json", description="导出格式"),
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """导出图谱数据 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        export_request = GraphExportRequest(
            graph_id=graph_id,
            export_format=export_format
        )
        export_data = await graph_service.export_graph(graph_id, export_format, user_id, None)
        return export_data
    except Exception as e:
        logger.error(f"Failed to export graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# 知识库相关的兼容接口
@legacy_router.post("/knowledge-bases/{kb_id}/create-graph")
async def legacy_create_graph_from_knowledge_base(
    kb_id: int,
    request: dict,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """从知识库创建图谱 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        
        # 适配请求格式
        adapted_request = GraphCreateRequest(
            project_id=request.get("project_id", "default"),
            name=request["name"],
            description=request.get("description"),
            knowledge_base_ids=[str(kb_id)],
        )
        
        graph = await graph_service.create_graph(adapted_request, user_id)
        return graph
    except Exception as e:
        logger.error(f"Failed to create graph from knowledge base: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.post("/knowledge-bases/{kb_id}/generate-html")
async def legacy_generate_html_from_knowledge_base(
    kb_id: int,
    request: dict,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """从知识库生成HTML可视化 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        
        # TODO: 实现从知识库直接生成HTML的逻辑
        # 这需要集成knowledge-service
        
        return {"message": "HTML生成任务已启动", "task_id": "temp_task_id"}
    except Exception as e:
        logger.error(f"Failed to generate HTML from knowledge base: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.get("/knowledge-bases/{kb_id}/statistics")
async def legacy_get_knowledge_base_statistics(
    kb_id: int,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取知识库图谱统计 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        
        # TODO: 实现知识库图谱统计
        # 需要查询与该知识库关联的所有图谱
        
        return {
            "total_graphs": 0,
            "total_entities": 0,
            "total_relations": 0,
            "status_distribution": {}
        }
    except Exception as e:
        logger.error(f"Failed to get knowledge base statistics: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.post("/text-visualization", response_class=HTMLResponse)
async def legacy_text_visualization(
    request: dict,  # 包含text和配置
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """文本即时可视化 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        
        # TODO: 实现即时文本可视化
        # 这需要集成AI知识图谱框架的即时处理功能
        
        text_content = request.get("text", "")
        config = request.get("config", {})
        
        # 暂时返回简单HTML
        simple_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>文本可视化</title></head>
        <body>
            <h1>文本可视化</h1>
            <p>文本内容: {text_content[:100]}...</p>
            <p>配置: {config}</p>
        </body>
        </html>
        """
        
        return HTMLResponse(content=simple_html)
    except Exception as e:
        logger.error(f"Failed to generate text visualization: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@legacy_router.post("/custom/create-graph")
async def legacy_create_custom_graph(
    request: dict,
    current_user: dict = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """自定义创建图谱 - 兼容原始API"""
    try:
        user_id = current_user["user_id"]
        
        # 适配自定义创建请求
        adapted_request = GraphCreateRequest(
            project_id=request.get("project_id", "default"),
            name=request["name"],
            description=request.get("description"),
            text_content=request.get("text_content"),
        )
        
        graph = await graph_service.create_graph(adapted_request, user_id)
        return graph
    except Exception as e:
        logger.error(f"Failed to create custom graph: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== 前端兼容路由 =====

# 添加不带尾部斜杠的路由重定向
@frontend_router.get("", response_model=list)
async def frontend_get_graphs_no_slash(
    # current_user: dict = Depends(get_current_user),  # 临时注释掉认证
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取图列表 - 前端兼容接口（无尾部斜杠）"""
    try:
        user_id = "test_user_001"  # 使用固定用户ID
        # 返回简化的图列表格式，符合前端期望
        graphs = []  # TODO: 从服务获取图谱列表
        
        # 转换为前端期望的格式
        frontend_graphs = []
        for graph in graphs:
            frontend_graph = {
                "id": graph.graph_id,
                "name": graph.name,
                "description": graph.description,
                "status": graph.status,
                "nodeCount": graph.statistics.entity_count if graph.statistics else 0,
                "edgeCount": graph.statistics.relation_count if graph.statistics else 0,
                "createdAt": graph.created_at.isoformat() if graph.created_at else None,
                "updatedAt": graph.updated_at.isoformat() if graph.updated_at else None
            }
            frontend_graphs.append(frontend_graph)
        
        return frontend_graphs
    except Exception as e:
        logger.error(f"Failed to get graphs for frontend: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@frontend_router.get("/", response_model=list)
async def frontend_get_graphs(
    # current_user: dict = Depends(get_current_user),  # 临时注释掉认证
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取图列表 - 前端兼容接口"""
    try:
        user_id = "test_user_001"  # 使用固定用户ID
        # 返回简化的图列表格式，符合前端期望
        graphs = []  # TODO: 从服务获取图谱列表
        
        # 转换为前端期望的格式
        frontend_graphs = []
        for graph in graphs:
            frontend_graph = {
                "id": graph.graph_id,
                "name": graph.name,
                "description": graph.description,
                "status": graph.status,
                "nodeCount": graph.statistics.entity_count if graph.statistics else 0,
                "edgeCount": graph.statistics.relation_count if graph.statistics else 0,
                "createdAt": graph.created_at.isoformat() if graph.created_at else None,
                "updatedAt": graph.updated_at.isoformat() if graph.updated_at else None
            }
            frontend_graphs.append(frontend_graph)
        
        return frontend_graphs
    except Exception as e:
        logger.error(f"Failed to get graphs for frontend: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@frontend_router.get("/{graph_id}")
async def frontend_get_graph(
    graph_id: str,
    # current_user: dict = Depends(get_current_user),  # 临时注释掉认证
    graph_service: GraphService = Depends(get_graph_service)
):
    """获取图详情 - 前端兼容接口"""
    try:
        user_id = "test_user_001"  # 使用固定用户ID
        graph = await graph_service.get_graph(graph_id, user_id, None)
        if not graph:
            raise HTTPException(status_code=404, detail="图谱未找到")
        
        # 转换为前端期望的格式
        frontend_graph = {
            "id": graph.graph_id,
            "name": graph.name,
            "description": graph.description,
            "status": graph.status,
            "nodeCount": graph.statistics.entity_count if graph.statistics else 0,
            "edgeCount": graph.statistics.relation_count if graph.statistics else 0,
            "createdAt": graph.created_at.isoformat() if graph.created_at else None,
            "updatedAt": graph.updated_at.isoformat() if graph.updated_at else None
        }
        
        return frontend_graph
    except Exception as e:
        logger.error(f"Failed to get graph for frontend: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@frontend_router.post("/")
async def frontend_create_graph(
    request: dict,
    # current_user: dict = Depends(get_current_user),  # 临时注释掉认证
    graph_service: GraphService = Depends(get_graph_service)
):
    """创建图 - 前端兼容接口"""
    try:
        user_id = "test_user_001"  # 使用固定用户ID
        
        # 适配前端请求格式到后端格式
        adapted_request = GraphCreateRequest(
            project_id=request.get("project_id", "default"),
            name=request["name"],
            description=request.get("description", ""),
            knowledge_base_ids=request.get("knowledgeBaseIds", []),
            document_ids=request.get("documentIds", []),
        )
        
        graph = await graph_service.create_graph(adapted_request, user_id)
        
        # 转换为前端期望的格式
        frontend_graph = {
            "id": graph.graph_id,
            "name": graph.name,
            "description": graph.description,
            "status": graph.status,
            "nodeCount": 0,
            "edgeCount": 0,
            "createdAt": graph.created_at.isoformat() if graph.created_at else None,
            "updatedAt": graph.updated_at.isoformat() if graph.updated_at else None
        }
        
        return frontend_graph
    except Exception as e:
        logger.error(f"Failed to create graph for frontend: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# 将路由包含到主路由器中
router.include_router(frontend_router)
router.include_router(legacy_router)