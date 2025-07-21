"""
前端 API 路由 - 为看板界面提供前端接口
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/board", response_class=HTMLResponse)
async def board_page():
    """看板界面页面"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kaiban 工作流看板</title>
        <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
        <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
        <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f6fa;
            }
            .kaiban-header {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .kaiban-board {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                padding: 20px;
                min-height: 600px;
            }
            .board-columns {
                display: flex;
                gap: 20px;
                overflow-x: auto;
            }
            .board-column {
                min-width: 300px;
                background: #f8f9fa;
                border-radius: 6px;
                padding: 16px;
            }
            .column-header {
                font-weight: 600;
                margin-bottom: 16px;
                color: #495057;
            }
            .task-card {
                background: white;
                border-radius: 4px;
                padding: 12px;
                margin-bottom: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                cursor: pointer;
                transition: transform 0.2s;
            }
            .task-card:hover {
                transform: translateY(-1px);
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            }
            .task-title {
                font-weight: 500;
                margin-bottom: 4px;
            }
            .task-meta {
                font-size: 12px;
                color: #6c757d;
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #6c757d;
            }
        </style>
    </head>
    <body>
        <div id="kaiban-root"></div>
        
        <script type="text/babel">
            const { useState, useEffect } = React;
            
            function KaibanBoard() {
                const [boards, setBoards] = useState([]);
                const [loading, setLoading] = useState(true);
                
                useEffect(() => {
                    // 模拟加载数据
                    setTimeout(() => {
                        setBoards([
                            {
                                id: 'board-1',
                                name: '客户服务工作流',
                                columns: [
                                    {
                                        id: 'col-1',
                                        name: '待处理',
                                        tasks: [
                                            { id: 'task-1', title: '处理客户咨询', priority: 'high' },
                                            { id: 'task-2', title: '回复产品问题', priority: 'medium' }
                                        ]
                                    },
                                    {
                                        id: 'col-2',
                                        name: '进行中',
                                        tasks: [
                                            { id: 'task-3', title: '准备技术文档', priority: 'low' }
                                        ]
                                    },
                                    {
                                        id: 'col-3',
                                        name: '已完成',
                                        tasks: [
                                            { id: 'task-4', title: '更新FAQ页面', priority: 'medium' }
                                        ]
                                    }
                                ]
                            }
                        ]);
                        setLoading(false);
                    }, 1000);
                }, []);
                
                if (loading) {
                    return <div className="loading">正在加载看板...</div>;
                }
                
                return (
                    <div>
                        <div className="kaiban-header">
                            <h1>🚀 Kaiban 工作流看板</h1>
                            <p>事件驱动的协作工作流管理系统</p>
                        </div>
                        
                        {boards.map(board => (
                            <div key={board.id} className="kaiban-board">
                                <h2>{board.name}</h2>
                                <div className="board-columns">
                                    {board.columns.map(column => (
                                        <div key={column.id} className="board-column">
                                            <div className="column-header">
                                                {column.name} ({column.tasks.length})
                                            </div>
                                            {column.tasks.map(task => (
                                                <div key={task.id} className="task-card">
                                                    <div className="task-title">{task.title}</div>
                                                    <div className="task-meta">
                                                        优先级: {task.priority} | ID: {task.id}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                );
            }
            
            ReactDOM.render(<KaibanBoard />, document.getElementById('kaiban-root'));
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get("/board/data")
async def get_board_data():
    """获取看板数据 API"""
    try:
        # 这里应该调用后端服务获取真实数据
        board_data = {
            "boards": [
                {
                    "id": "board-1",
                    "name": "客户服务工作流",
                    "workflow_id": "workflow-1",
                    "columns": [
                        {
                            "id": "col-1",
                            "name": "待处理",
                            "position": 0,
                            "tasks": [
                                {
                                    "id": "task-1",
                                    "title": "处理客户咨询",
                                    "description": "回复客户关于产品功能的咨询",
                                    "priority": "high",
                                    "assignee": "张三",
                                    "status": "pending",
                                    "tags": ["客服", "咨询"]
                                }
                            ]
                        },
                        {
                            "id": "col-2", 
                            "name": "进行中",
                            "position": 1,
                            "tasks": [
                                {
                                    "id": "task-2",
                                    "title": "准备技术文档",
                                    "description": "为新功能编写用户手册",
                                    "priority": "medium",
                                    "assignee": "李四",
                                    "status": "in_progress",
                                    "tags": ["文档", "技术"]
                                }
                            ]
                        },
                        {
                            "id": "col-3",
                            "name": "已完成", 
                            "position": 2,
                            "tasks": [
                                {
                                    "id": "task-3",
                                    "title": "更新FAQ页面",
                                    "description": "添加常见问题和解答",
                                    "priority": "low",
                                    "assignee": "王五",
                                    "status": "completed",
                                    "tags": ["FAQ", "更新"]
                                }
                            ]
                        }
                    ]
                }
            ],
            "metadata": {
                "total_tasks": 3,
                "active_workflows": 1,
                "last_updated": "2024-01-15T10:30:00Z"
            }
        }
        
        return JSONResponse(content=board_data)
    except Exception as e:
        logger.error(f"获取看板数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取看板数据失败")


@router.get("/board/config")
async def get_board_config():
    """获取看板配置"""
    try:
        config = {
            "theme": "light",
            "columns": {
                "max_width": 300,
                "min_width": 250
            },
            "tasks": {
                "enable_drag_drop": True,
                "auto_save": True
            },
            "features": {
                "comments": True,
                "attachments": True,
                "time_tracking": True
            }
        }
        
        return JSONResponse(content=config)
    except Exception as e:
        logger.error(f"获取看板配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取看板配置失败") 