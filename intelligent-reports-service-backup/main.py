#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能报告服务主入口
基于Co-Sight架构的完整实现
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入Co-Sight核心组件
from CoSight import CoSight
from llm import llm_for_plan, llm_for_act, llm_for_tool, llm_for_vision, init_models
from app.cosight.task.plan_report_manager import plan_report_event_manager
from app.cosight.task.task_manager import TaskManager
from app.common.logger_util import logger
from app.config.database import init_connections, close_connections
from shared.service_client import call_service, CallMethod

# 环境变量加载
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("环境变量加载成功")
except ImportError:
    logger.warning("python-dotenv未安装，跳过.env文件加载")

# 初始化FastAPI应用
app = FastAPI(
    title="智能报告服务",
    description="基于ReportVision架构的智能报告生成服务",
    version="1.0.0"
)

# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("正在启动智能报告服务...")
    try:
        # 初始化数据库连接
        await init_connections()
        logger.info("数据库连接初始化完成")
        
        # 初始化模型实例
        await init_models()
        logger.info("模型实例初始化完成")
        
        # 向网关服务注册
        await register_to_gateway()
        logger.info("服务注册完成")
        
    except Exception as e:
        logger.error(f"启动初始化失败: {e}", exc_info=True)
        raise

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("正在关闭智能报告服务...")
    try:
        # 清理所有活跃会话
        for session_id in list(active_sessions.keys()):
            cleanup_session(session_id)
        
        # 关闭数据库连接
        await close_connections()
        logger.info("数据库连接关闭完成")
        
    except Exception as e:
        logger.error(f"关闭清理失败: {e}", exc_info=True)

# 网关注册
async def register_to_gateway():
    """向网关服务注册"""
    try:
        registration_data = {
            "service_name": "intelligent-reports-service",
            "service_url": f"http://localhost:{os.getenv('PORT', '8000')}",
            "health_check_path": "/health",
            "routes": [
                {
                    "path": "/api/reports/*",
                    "methods": ["GET", "POST", "PUT", "DELETE"]
                },
                {
                    "path": "/api/files/*",
                    "methods": ["GET"]
                },
                {
                    "path": "/api/sessions/*",
                    "methods": ["GET", "POST", "DELETE"]
                },
                {
                    "path": "/ws/*",
                    "methods": ["WS"]
                }
            ]
        }
        
        await call_service(
            service_name="gateway-service",
            method=CallMethod.POST,
            path="/api/v1/services/register",
            json=registration_data
        )
        
    except Exception as e:
        logger.warning(f"网关注册失败: {e}")

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
active_sessions: Dict[str, Dict[str, Any]] = {}
workspace_base = os.getenv("WORKSPACE_PATH", "./workspace")

# 确保工作空间目录存在
os.makedirs(workspace_base, exist_ok=True)

# 数据模型
class ReportRequest(BaseModel):
    query: str
    output_format: str = ""
    session_id: Optional[str] = None

class ReportResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

# 工具函数
def create_session_workspace(session_id: str) -> str:
    """为会话创建独立的工作空间"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    workspace_path = os.path.join(workspace_base, f'session_{session_id}_{timestamp}')
    os.makedirs(workspace_path, exist_ok=True)
    return workspace_path

def get_session_info(session_id: str) -> Dict[str, Any]:
    """获取会话信息"""
    return active_sessions.get(session_id, {})

def cleanup_session(session_id: str):
    """清理会话资源"""
    if session_id in active_sessions:
        session_info = active_sessions[session_id]
        # 清理任务管理器中的计划
        if 'plan_id' in session_info:
            TaskManager.cleanup_plan(session_info['plan_id'])
        del active_sessions[session_id]
        logger.info(f"已清理会话 {session_id}")

# API端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/reports/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """生成报告接口"""
    try:
        session_id = request.session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        workspace_path = create_session_workspace(session_id)
        
        # 记录用户请求
        await log_user_request(request, session_id)
        
        # 创建ReportVision实例
        cosight = CoSight(
            plan_llm=llm_for_plan,
            act_llm=llm_for_act,
            tool_llm=llm_for_tool,
            vision_llm=llm_for_vision,
            work_space_path=workspace_path
        )
        
        # 存储会话信息
        active_sessions[session_id] = {
            "cosight": cosight,
            "workspace_path": workspace_path,
            "plan_id": cosight.plan_id,
            "start_time": datetime.now().isoformat()
        }
        
        # 执行报告生成
        result = cosight.execute(request.query, request.output_format)
        
        # 获取生成的文件列表
        files = []
        try:
            for file in os.listdir(workspace_path):
                if os.path.isfile(os.path.join(workspace_path, file)):
                    files.append({
                        "name": file,
                        "path": f"/api/files/{session_id}/{file}",
                        "size": os.path.getsize(os.path.join(workspace_path, file))
                    })
        except Exception as e:
            logger.error(f"获取文件列表失败: {e}")
        
        # 记录报告生成结果
        await log_report_result(session_id, result, files)
        
        return ReportResponse(
            success=True,
            message="报告生成成功",
            data={
                "result": result,
                "files": files,
                "workspace_path": workspace_path,
                "plan_id": cosight.plan_id
            },
            session_id=session_id
        )
        
    except Exception as e:
        logger.error(f"报告生成失败: {e}", exc_info=True)
        
        # 记录错误信息
        await log_error(session_id, str(e))
        
        return ReportResponse(
            success=False,
            message=f"报告生成失败: {str(e)}",
            session_id=session_id
        )

@app.get("/api/reports/status/{session_id}")
async def get_report_status(session_id: str):
    """获取报告生成状态"""
    try:
        session_info = get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        cosight = session_info["cosight"]
        plan = cosight.plan
        
        return {
            "success": True,
            "data": {
                "plan_id": cosight.plan_id,
                "title": plan.title,
                "progress": plan.get_progress(),
                "steps": [{"index": i, "content": step, "status": plan.step_statuses.get(step, "not_started")} 
                         for i, step in enumerate(plan.steps)],
                "result": plan.get_plan_result() if plan.get_plan_result() else None
            }
        }
    except Exception as e:
        logger.error(f"获取状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")

@app.get("/api/files/{session_id}/{filename}")
async def get_file(session_id: str, filename: str):
    """获取生成的文件"""
    try:
        session_info = get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        file_path = os.path.join(session_info["workspace_path"], filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        def iterfile():
            with open(file_path, mode="rb") as file_like:
                yield from file_like
        
        return StreamingResponse(iterfile(), media_type="application/octet-stream")
    except Exception as e:
        logger.error(f"获取文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取文件失败: {str(e)}")

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    try:
        cleanup_session(session_id)
        return {"success": True, "message": "会话已删除"}
    except Exception as e:
        logger.error(f"删除会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket连接，用于实时推送计划执行状态"""
    await websocket.accept()
    logger.info(f"WebSocket连接建立: {session_id}")
    
    try:
        # 实时推送计划执行状态
        def plan_event_handler(event_type: str, plan):
            try:
                asyncio.create_task(websocket.send_text(json.dumps({
                    "type": event_type,
                    "data": {
                        "plan_id": plan.plan_id if hasattr(plan, 'plan_id') else session_id,
                        "title": plan.title,
                        "progress": plan.get_progress(),
                        "steps": [{"index": i, "content": step, "status": plan.step_statuses.get(step, "not_started")} 
                                 for i, step in enumerate(plan.steps)]
                    }
                }, ensure_ascii=False)))
            except Exception as e:
                logger.error(f"WebSocket消息发送失败: {e}")
        
        # 注册事件监听器
        plan_report_event_manager.subscribe("plan_process", plan_event_handler)
        plan_report_event_manager.subscribe("plan_created", plan_event_handler)
        plan_report_event_manager.subscribe("plan_updated", plan_event_handler)
        plan_report_event_manager.subscribe("plan_result", plan_event_handler)
        
        while True:
            # 保持连接活跃
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}", exc_info=True)
    finally:
        # 清理事件监听器
        plan_report_event_manager.unsubscribe("plan_process", plan_event_handler)

# 新增API端点
@app.get("/api/models/status")
async def get_model_status():
    """获取模型服务状态"""
    try:
        result = await call_service(
            service_name="model-service",
            method=CallMethod.GET,
            path="/api/v1/models/health"
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"获取模型状态失败: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/services/status")
async def get_services_status():
    """获取相关服务状态"""
    services = [
        "model-service",
        "database-service",
        "gateway-service"
    ]
    
    status_results = {}
    for service in services:
        try:
            result = await call_service(
                service_name=service,
                method=CallMethod.GET,
                path="/health"
            )
            status_results[service] = {"status": "healthy", "data": result}
        except Exception as e:
            status_results[service] = {"status": "error", "error": str(e)}
    
    return {"success": True, "data": status_results}

# 辅助函数
async def log_user_request(request: ReportRequest, session_id: str):
    """记录用户请求"""
    try:
        # 可以调用database-service记录用户请求
        logger.info(f"用户请求 - Session: {session_id}, Query: {request.query[:100]}...")
    except Exception as e:
        logger.error(f"记录用户请求失败: {e}")

async def log_report_result(session_id: str, result: Any, files: List[Dict]):
    """记录报告生成结果"""
    try:
        # 可以调用database-service记录生成结果
        logger.info(f"报告生成成功 - Session: {session_id}, Files: {len(files)}")
    except Exception as e:
        logger.error(f"记录报告结果失败: {e}")

async def log_error(session_id: str, error_message: str):
    """记录错误信息"""
    try:
        # 可以调用database-service记录错误
        logger.error(f"会话错误 - Session: {session_id}, Error: {error_message}")
    except Exception as e:
        logger.error(f"记录错误失败: {e}")

# 静态文件服务
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"静态文件服务初始化失败: {e}")

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "服务器内部错误", "detail": str(exc)}
    )

if __name__ == "__main__":
    logger.info("启动智能报告服务...")
    logger.info(f"工作空间: {workspace_base}")
    
    # 启动服务
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"服务将在端口 {port} 上启动")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )