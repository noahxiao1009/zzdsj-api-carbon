# Chat-Service 开发计划文档

## 一、项目概述

本文档详细描述了Chat-Service与Agent-Service对接及消息渲染功能的完整开发计划。Chat-Service是ZZDSJ NextAgent的核心对话服务，负责处理用户与智能体的实时交互。

## 二、现状分析

### Agent-Service 状态分析
- ✅ **完整度：85%** - 核心功能完整，Agno框架集成良好
- ✅ **智能体管理**：支持创建、配置、生命周期管理
- ✅ **模板系统**：三种核心模板（基础对话、知识库、深度思考）
- ✅ **API接口**：RESTful API完整，支持Flow Builder
- ⚠️ **待完善**：数据持久化层需要补充

### Chat-Service 状态分析
- ✅ **完整度：75%** - 核心对话功能完整
- ✅ **Agno集成**：基础集成完成，支持多智能体
- ✅ **会话管理**：完整的会话生命周期和历史记录
- ✅ **流式响应**：SSE和非SSE处理完整
- ⚠️ **待完善**：消息格式渲染、权限细化、WebSocket支持

## 三、对接架构设计

### 系统架构图

```
前端应用 (Vue.js)
    ↓ HTTP/WebSocket
Chat-Service (8089)
    ↓ ServiceClient SDK
Agent-Service (8081) 
    ↓ Agno Framework
AI模型提供商 (Claude/GPT)
```

### 核心数据流

```
用户输入 → Chat-Service → Agent-Service → Agno → AI模型
         ↓                            ↓
    消息渲染 ← 格式检测 ← 原始响应 ← AI响应
         ↓
    前端展示
```

## 四、开发计划

### Phase 1: 消息格式渲染模块 (第1周)

**目标：** 实现完整的消息渲染功能，支持MD/LaTeX/代码/表格等格式

#### 1.1 核心渲染器实现

**文件位置：** `app/services/message_renderer.py`

**功能列表：**
- Markdown渲染 (标题、列表、链接、图片)
- 代码高亮 (支持多种编程语言)
- LaTeX数学公式渲染
- 表格格式化
- HTML内容处理

**依赖库：**
```
markdown==3.5.1
pygments==2.16.1
matplotlib==3.8.0
pandas==2.1.3
beautifulsoup4==4.12.2
```

#### 1.2 格式检测器

**文件位置：** `app/utils/format_detector.py`

**检测能力：**
- Markdown语法检测
- 代码块识别（包含语言类型）
- LaTeX公式识别
- 表格格式检测
- HTML标签检测

#### 1.3 渲染API集成

**增强现有API端点：**
- `POST /api/v1/chat/message` - 支持自动渲染
- `POST /api/v1/chat/message/stream` - 流式渲染支持

**响应格式标准：**
```json
{
    "success": true,
    "session_id": "session_123",
    "message": {
        "raw": "原始内容",
        "rendered": "渲染后内容",
        "format": "markdown|code|latex|table|html",
        "metadata": {
            "language": "python",
            "has_formula": true,
            "render_time": 150
        }
    }
}
```

### Phase 2: SSE和非SSE消息格式化增强 (第2周)

**目标：** 优化流式响应处理，实现实时格式检测和渲染

#### 2.1 流式渲染增强

**实现特性：**
- 实时格式检测
- 增量渲染处理
- 渲染缓存机制
- 错误恢复策略

#### 2.2 性能优化

**优化策略：**
- 渲染结果缓存 (Redis)
- 异步渲染处理
- 批量渲染支持
- 渲染队列管理

#### 2.3 WebSocket支持

**新增端点：**
- `WebSocket /ws/chat/{session_id}` - 实时对话

### Phase 3: 智能体实例状态管理优化 (第3周)

**目标：** 优化智能体实例的创建、使用和销毁流程

#### 3.1 实例池管理

**文件位置：** `app/services/agent_pool.py`

**功能特性：**
- 智能体实例复用
- 自动扩缩容
- 健康检查机制
- 资源清理策略

#### 3.2 状态同步机制

**同步策略：**
- Agent-Service状态实时同步
- 本地缓存更新机制
- 故障转移处理
- 状态一致性保证

### Phase 4: 权限控制和历史记录增强 (第4周)

**目标：** 完善权限系统和历史记录管理

#### 4.1 细粒度权限控制

**文件位置：** `app/middleware/permission.py`

**权限类型：**
- 智能体访问权限
- 会话操作权限
- 功能使用权限
- 资源配额限制

#### 4.2 智能历史记录

**增强功能：**
- 上下文相关历史加载
- 历史记录搜索
- 分层存储策略
- 智能摘要生成

## 五、技术实现细节

### 5.1 消息渲染器核心实现

```python
# app/services/message_renderer.py
import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
import matplotlib.pyplot as plt
import io
import base64
import asyncio
from typing import Dict, Any, Optional

class MessageRenderer:
    def __init__(self):
        self.md = markdown.Markdown(extensions=[
            'tables', 'fenced_code', 'toc', 'codehilite'
        ])
        self.html_formatter = HtmlFormatter(
            style='github',
            linenos=True,
            cssclass='highlight'
        )
        self._cache = {}
    
    async def auto_render(self, content: str) -> Dict[str, Any]:
        """自动检测格式并渲染"""
        from app.utils.format_detector import FormatDetector
        
        detector = FormatDetector()
        rendered_parts = []
        
        # 检测并渲染不同格式
        if detector.detect_markdown(content):
            md_result = await self.render_markdown(content)
            rendered_parts.append(md_result)
        
        if detector.detect_latex(content):
            latex_result = await self.render_latex_formulas(content)
            rendered_parts.append(latex_result)
        
        code_detected, language = detector.detect_code_block(content)
        if code_detected:
            code_result = await self.render_code_blocks(content, language)
            rendered_parts.append(code_result)
        
        return {
            "original": content,
            "rendered_parts": rendered_parts,
            "formats_detected": [part["format"] for part in rendered_parts],
            "render_time": asyncio.get_event_loop().time()
        }
    
    async def render_markdown(self, content: str) -> Dict[str, Any]:
        """渲染Markdown内容"""
        try:
            cache_key = f"md_{hash(content)}"
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            html_content = self.md.convert(content)
            result = {
                "success": True,
                "format": "markdown",
                "rendered": html_content,
                "raw": content,
                "metadata": {
                    "has_tables": '<table>' in html_content,
                    "has_links": '<a href=' in html_content,
                    "word_count": len(content.split())
                }
            }
            
            self._cache[cache_key] = result
            return result
            
        except Exception as e:
            return {
                "success": False,
                "format": "markdown",
                "error": str(e),
                "raw": content
            }
    
    async def render_code_blocks(self, content: str, language: str = "python") -> Dict[str, Any]:
        """渲染代码块"""
        try:
            import re
            
            # 提取代码块
            code_pattern = r'```(\w+)?\n(.*?)```'
            matches = re.findall(code_pattern, content, re.DOTALL)
            
            rendered_blocks = []
            for lang, code in matches:
                if not lang:
                    lang = language
                
                try:
                    lexer = get_lexer_by_name(lang)
                    highlighted = highlight(code.strip(), lexer, self.html_formatter)
                    rendered_blocks.append({
                        "language": lang,
                        "highlighted": highlighted,
                        "raw_code": code.strip(),
                        "line_count": len(code.strip().split('\n'))
                    })
                except Exception:
                    # 如果语言不支持，使用文本渲染
                    rendered_blocks.append({
                        "language": "text",
                        "highlighted": f"<pre><code>{code.strip()}</code></pre>",
                        "raw_code": code.strip(),
                        "line_count": len(code.strip().split('\n'))
                    })
            
            return {
                "success": True,
                "format": "code",
                "rendered_blocks": rendered_blocks,
                "total_blocks": len(rendered_blocks)
            }
            
        except Exception as e:
            return {
                "success": False,
                "format": "code",
                "error": str(e)
            }
    
    async def render_latex_formulas(self, content: str) -> Dict[str, Any]:
        """渲染LaTeX数学公式"""
        try:
            import re
            
            # 提取LaTeX公式
            inline_pattern = r'\$(.*?)\$'
            block_pattern = r'\$\$(.*?)\$\$'
            
            inline_formulas = re.findall(inline_pattern, content)
            block_formulas = re.findall(block_pattern, content, re.DOTALL)
            
            rendered_formulas = []
            
            # 渲染行内公式
            for formula in inline_formulas:
                image_data = await self._render_latex_to_image(formula.strip())
                if image_data:
                    rendered_formulas.append({
                        "type": "inline",
                        "formula": formula.strip(),
                        "image": image_data
                    })
            
            # 渲染块级公式
            for formula in block_formulas:
                image_data = await self._render_latex_to_image(formula.strip(), block=True)
                if image_data:
                    rendered_formulas.append({
                        "type": "block",
                        "formula": formula.strip(),
                        "image": image_data
                    })
            
            return {
                "success": True,
                "format": "latex",
                "rendered_formulas": rendered_formulas,
                "total_formulas": len(rendered_formulas)
            }
            
        except Exception as e:
            return {
                "success": False,
                "format": "latex",
                "error": str(e)
            }
    
    async def _render_latex_to_image(self, formula: str, block: bool = False) -> Optional[str]:
        """将LaTeX公式渲染为图片"""
        try:
            fig_size = (12, 3) if block else (8, 2)
            fig, ax = plt.subplots(figsize=fig_size)
            
            ax.text(
                0.5, 0.5, f"${formula}$",
                fontsize=16 if block else 14,
                ha='center', va='center',
                transform=ax.transAxes
            )
            ax.axis('off')
            
            buffer = io.BytesIO()
            plt.savefig(
                buffer, format='png',
                bbox_inches='tight',
                dpi=150,
                transparent=True
            )
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return f"data:image/png;base64,{image_base64}"
            
        except Exception as e:
            print(f"LaTeX rendering error: {e}")
            return None
    
    async def render_table(self, table_data: str) -> Dict[str, Any]:
        """渲染表格数据"""
        try:
            import pandas as pd
            from io import StringIO
            
            # 尝试解析Markdown表格
            lines = table_data.strip().split('\n')
            if len(lines) >= 2 and '|' in lines[0]:
                # Markdown表格格式
                headers = [col.strip() for col in lines[0].split('|')[1:-1]]
                rows = []
                
                for line in lines[2:]:  # 跳过分隔行
                    if '|' in line:
                        row = [col.strip() for col in line.split('|')[1:-1]]
                        rows.append(row)
                
                df = pd.DataFrame(rows, columns=headers)
                html_table = df.to_html(
                    classes='table table-striped table-hover',
                    table_id='rendered-table',
                    escape=False
                )
                
                return {
                    "success": True,
                    "format": "table",
                    "rendered": html_table,
                    "metadata": {
                        "rows": len(rows),
                        "columns": len(headers),
                        "headers": headers
                    }
                }
            
        except Exception as e:
            return {
                "success": False,
                "format": "table",
                "error": str(e)
            }
```

### 5.2 格式检测器实现

```python
# app/utils/format_detector.py
import re
from typing import Tuple, Optional, List

class FormatDetector:
    """智能格式检测器"""
    
    @staticmethod
    def detect_markdown(text: str) -> bool:
        """检测Markdown格式"""
        md_patterns = [
            r'#{1,6}\s+.+',          # 标题
            r'\*\*.*?\*\*',          # 粗体
            r'\*.*?\*(?!\*)',        # 斜体
            r'`[^`]+`',              # 行内代码
            r'\[.*?\]\(.*?\)',       # 链接
            r'^\|.*\|.*$',           # 表格行
            r'^\d+\.\s+',            # 有序列表
            r'^[-*+]\s+',            # 无序列表
            r'^>\s+',                # 引用
            r'!\[.*?\]\(.*?\)',      # 图片
        ]
        
        for pattern in md_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True
        return False
    
    @staticmethod
    def detect_code_block(text: str) -> Tuple[bool, Optional[str]]:
        """检测代码块并识别语言"""
        # 围栏代码块 ```language
        fenced_pattern = r'```(\w+)?\n(.*?)```'
        match = re.search(fenced_pattern, text, re.DOTALL)
        if match:
            language = match.group(1) or 'text'
            return True, language
        
        # 缩进代码块
        indent_pattern = r'^(    |\t).+$'
        if re.search(indent_pattern, text, re.MULTILINE):
            return True, 'text'
        
        return False, None
    
    @staticmethod
    def detect_latex(text: str) -> bool:
        """检测LaTeX数学公式"""
        latex_patterns = [
            r'\$\$.*?\$\$',          # 块级公式
            r'(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)',  # 行内公式
            r'\\begin\{.*?\}.*?\\end\{.*?\}',      # LaTeX环境
            r'\\[a-zA-Z]+\{.*?\}',   # LaTeX命令
        ]
        
        for pattern in latex_patterns:
            if re.search(pattern, text, re.DOTALL):
                return True
        return False
    
    @staticmethod
    def detect_table(text: str) -> bool:
        """检测表格格式"""
        # Markdown表格
        md_table_pattern = r'^\|.*\|.*$\n^\|[-\s:|]+\|.*$'
        if re.search(md_table_pattern, text, re.MULTILINE):
            return True
        
        # CSV格式表格
        csv_pattern = r'^.*,.*,.*$'
        lines = text.strip().split('\n')
        if len(lines) >= 2:
            csv_lines = [line for line in lines if re.match(csv_pattern, line)]
            if len(csv_lines) >= 2:
                return True
        
        return False
    
    @staticmethod
    def detect_html(text: str) -> bool:
        """检测HTML内容"""
        html_patterns = [
            r'<[^>]+>.*?</[^>]+>',   # HTML标签对
            r'<[^/>]+/>',            # 自闭合标签
            r'&[a-zA-Z]+;',          # HTML实体
        ]
        
        for pattern in html_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    @classmethod
    def analyze_content(cls, text: str) -> Dict[str, Any]:
        """全面分析内容格式"""
        analysis = {
            "has_markdown": cls.detect_markdown(text),
            "has_latex": cls.detect_latex(text),
            "has_table": cls.detect_table(text),
            "has_html": cls.detect_html(text),
            "detected_formats": []
        }
        
        # 检测代码块
        has_code, language = cls.detect_code_block(text)
        analysis["has_code"] = has_code
        if has_code:
            analysis["code_language"] = language
        
        # 收集检测到的格式
        if analysis["has_markdown"]:
            analysis["detected_formats"].append("markdown")
        if analysis["has_latex"]:
            analysis["detected_formats"].append("latex")
        if analysis["has_code"]:
            analysis["detected_formats"].append("code")
        if analysis["has_table"]:
            analysis["detected_formats"].append("table")
        if analysis["has_html"]:
            analysis["detected_formats"].append("html")
        
        # 内容统计
        analysis["statistics"] = {
            "character_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.split('\n')),
            "complexity_score": len(analysis["detected_formats"])
        }
        
        return analysis
```

### 5.3 增强的API路由

```python
# app/api/routers/enhanced_chat_router.py
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
import json
import asyncio
from datetime import datetime

from app.services.chat_manager import get_chat_manager
from app.services.message_renderer import MessageRenderer
from app.utils.format_detector import FormatDetector
from app.core.dependencies import get_current_user
from app.schemas.enhanced_chat import EnhancedChatRequest, EnhancedChatResponse

router = APIRouter(prefix="/api/v1/chat", tags=["enhanced-chat"])

@router.post("/message/enhanced", response_model=EnhancedChatResponse)
async def send_enhanced_message(
    request: EnhancedChatRequest,
    current_user: Dict = Depends(get_current_user),
    chat_manager = Depends(get_chat_manager)
):
    """
    增强的消息发送接口
    支持自动格式检测、渲染和权限控制
    """
    try:
        user_id = current_user["user_id"]
        
        # 1. 权限检查
        if request.agent_id:
            has_permission = await chat_manager.check_agent_permission(
                user_id, request.agent_id
            )
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail="无权限访问该智能体"
                )
        
        # 2. 创建或获取会话
        session_id = request.session_id
        if not session_id:
            session_result = await chat_manager.create_session(
                user_id=user_id,
                agent_id=request.agent_id,
                session_config=request.session_config
            )
            if not session_result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"创建会话失败: {session_result['error']}"
                )
            session_id = session_result["session_id"]
        
        # 3. 发送消息到智能体
        if request.stream:
            return await _handle_stream_response(
                chat_manager, session_id, request, current_user
            )
        else:
            return await _handle_normal_response(
                chat_manager, session_id, request, current_user
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"内部服务器错误: {str(e)}"
        )

async def _handle_normal_response(
    chat_manager, session_id: str, request: EnhancedChatRequest, current_user: Dict
) -> EnhancedChatResponse:
    """处理非流式响应"""
    # 发送消息
    response = await chat_manager.send_message(
        session_id=session_id,
        message=request.message,
        message_type=request.message_type,
        stream=False,
        voice_config=request.voice_config.dict() if request.voice_config else None
    )
    
    if not response.get("success"):
        raise HTTPException(
            status_code=400,
            detail=response.get("error", "发送消息失败")
        )
    
    # 消息渲染
    rendered_content = None
    if request.enable_rendering and response.get("response"):
        renderer = MessageRenderer()
        rendered_content = await renderer.auto_render(response["response"])
    
    # 格式分析
    format_analysis = None
    if request.analyze_format and response.get("response"):
        detector = FormatDetector()
        format_analysis = detector.analyze_content(response["response"])
    
    return EnhancedChatResponse(
        success=True,
        session_id=session_id,
        message_id=response.get("message_id"),
        response=response.get("response", ""),
        rendered_content=rendered_content,
        format_analysis=format_analysis,
        audio_response=response.get("audio_response"),
        timestamp=response.get("timestamp", datetime.now().isoformat()),
        agent_id=request.agent_id,
        processing_time=response.get("processing_time", 0)
    )

async def _handle_stream_response(
    chat_manager, session_id: str, request: EnhancedChatRequest, current_user: Dict
):
    """处理流式响应"""
    async def generate_enhanced_stream():
        try:
            renderer = MessageRenderer() if request.enable_rendering else None
            detector = FormatDetector() if request.analyze_format else None
            accumulated_content = ""
            
            # 发送开始事件
            yield f"data: {json.dumps({
                'type': 'session_start',
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            }, ensure_ascii=False)}\n\n"
            
            # 获取流式响应
            response_stream = await chat_manager.send_message(
                session_id=session_id,
                message=request.message,
                message_type=request.message_type,
                stream=True,
                voice_config=request.voice_config.dict() if request.voice_config else None
            )
            
            async for chunk in response_stream:
                if chunk.get("type") == "assistant_chunk":
                    chunk_text = chunk.get("chunk", "")
                    accumulated_content += chunk_text
                    
                    # 基础chunk事件
                    chunk_event = {
                        "type": "content_chunk",
                        "session_id": session_id,
                        "chunk": chunk_text,
                        "accumulated": accumulated_content,
                        "finished": chunk.get("finished", False),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # 实时格式分析
                    if detector and accumulated_content:
                        format_info = detector.analyze_content(accumulated_content)
                        chunk_event["format_analysis"] = format_info
                    
                    yield f"data: {json.dumps(chunk_event, ensure_ascii=False)}\n\n"
                    
                    # 如果消息完成，进行最终渲染
                    if chunk.get("finished", False) and renderer and accumulated_content:
                        rendered_result = await renderer.auto_render(accumulated_content)
                        render_event = {
                            "type": "content_rendered",
                            "session_id": session_id,
                            "rendered_content": rendered_result,
                            "timestamp": datetime.now().isoformat()
                        }
                        yield f"data: {json.dumps(render_event, ensure_ascii=False)}\n\n"
                
                elif chunk.get("type") == "audio_response":
                    # 语音响应事件
                    audio_event = {
                        "type": "audio_response",
                        "session_id": session_id,
                        "audio_data": chunk.get("audio"),
                        "timestamp": datetime.now().isoformat()
                    }
                    yield f"data: {json.dumps(audio_event, ensure_ascii=False)}\n\n"
                
                elif chunk.get("type") == "error":
                    # 错误事件
                    error_event = {
                        "type": "error",
                        "session_id": session_id,
                        "error": chunk.get("error"),
                        "timestamp": datetime.now().isoformat()
                    }
                    yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                    break
            
            # 发送结束事件
            yield f"data: {json.dumps({
                'type': 'session_complete',
                'session_id': session_id,
                'total_content': accumulated_content,
                'timestamp': datetime.now().isoformat()
            }, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            error_event = {
                "type": "error",
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_enhanced_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
            "X-Session-ID": session_id
        }
    )

@router.get("/formats/supported")
async def get_supported_formats():
    """获取支持的渲染格式列表"""
    return {
        "success": True,
        "supported_formats": [
            {
                "format": "markdown",
                "description": "Markdown文本格式",
                "features": ["标题", "列表", "链接", "图片", "表格", "代码"]
            },
            {
                "format": "code",
                "description": "代码语法高亮",
                "supported_languages": [
                    "python", "javascript", "java", "c++", "sql", 
                    "html", "css", "json", "yaml", "bash"
                ]
            },
            {
                "format": "latex",
                "description": "LaTeX数学公式",
                "features": ["行内公式", "块级公式", "数学符号", "方程组"]
            },
            {
                "format": "table",
                "description": "表格数据",
                "supported_types": ["markdown_table", "csv", "json_array"]
            },
            {
                "format": "html",
                "description": "HTML内容",
                "features": ["基础标签", "样式", "链接", "图片"]
            }
        ]
    }
```

## 六、数据模型定义

### 6.1 增强的请求/响应模型

```python
# app/schemas/enhanced_chat.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class EnhancedChatRequest(BaseModel):
    """增强的聊天请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    stream: bool = Field(False, description="是否流式响应")
    message_type: str = Field("text", description="消息类型")
    enable_rendering: bool = Field(True, description="是否启用消息渲染")
    analyze_format: bool = Field(True, description="是否分析格式")
    voice_config: Optional[Dict[str, Any]] = Field(None, description="语音配置")
    session_config: Optional[Dict[str, Any]] = Field(None, description="会话配置")

class RenderedContent(BaseModel):
    """渲染后的内容"""
    original: str = Field(..., description="原始内容")
    rendered_parts: List[Dict[str, Any]] = Field(default_factory=list)
    formats_detected: List[str] = Field(default_factory=list)
    render_time: float = Field(..., description="渲染耗时(ms)")

class FormatAnalysis(BaseModel):
    """格式分析结果"""
    has_markdown: bool = False
    has_latex: bool = False
    has_code: bool = False
    has_table: bool = False
    has_html: bool = False
    detected_formats: List[str] = Field(default_factory=list)
    code_language: Optional[str] = None
    statistics: Dict[str, Any] = Field(default_factory=dict)

class EnhancedChatResponse(BaseModel):
    """增强的聊天响应"""
    success: bool = Field(..., description="请求是否成功")
    session_id: str = Field(..., description="会话ID")
    message_id: Optional[str] = Field(None, description="消息ID")
    response: str = Field(..., description="AI响应内容")
    rendered_content: Optional[RenderedContent] = Field(None, description="渲染后内容")
    format_analysis: Optional[FormatAnalysis] = Field(None, description="格式分析")
    audio_response: Optional[Dict[str, Any]] = Field(None, description="语音响应")
    timestamp: str = Field(..., description="响应时间戳")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    processing_time: float = Field(0, description="处理耗时(ms)")
```

## 七、部署和测试

### 7.1 环境配置

**requirements.txt 更新：**
```
# 现有依赖保持不变
fastapi==0.104.1
uvicorn==0.24.0
redis==5.0.1
pydantic==2.5.0

# 新增渲染依赖
markdown==3.5.1
pygments==2.16.1
matplotlib==3.8.0
pandas==2.1.3
beautifulsoup4==4.12.2
lxml==4.9.3
```

### 7.2 配置更新

**config/settings.py 增加配置：**
```python
# 消息渲染配置
MESSAGE_RENDERING_ENABLED: bool = True
RENDER_CACHE_TTL: int = 3600  # 1小时
MAX_RENDER_SIZE: int = 100000  # 100KB
SUPPORTED_CODE_LANGUAGES: List[str] = [
    "python", "javascript", "java", "cpp", "sql",
    "html", "css", "json", "yaml", "bash"
]

# LaTeX渲染配置
LATEX_DPI: int = 150
LATEX_FONT_SIZE: int = 14
LATEX_FIGURE_SIZE: Tuple[int, int] = (10, 2)

# 性能配置
RENDER_TIMEOUT: int = 30  # 30秒
CONCURRENT_RENDERS: int = 10
```

### 7.3 测试用例

```python
# tests/test_message_renderer.py
import pytest
from app.services.message_renderer import MessageRenderer
from app.utils.format_detector import FormatDetector

class TestMessageRenderer:
    
    @pytest.fixture
    def renderer(self):
        return MessageRenderer()
    
    @pytest.fixture
    def detector(self):
        return FormatDetector()
    
    @pytest.mark.asyncio
    async def test_markdown_rendering(self, renderer):
        """测试Markdown渲染"""
        content = """
        # 标题
        这是**粗体**和*斜体*文本。
        
        - 列表项1
        - 列表项2
        
        ```python
        print("Hello World")
        ```
        """
        
        result = await renderer.render_markdown(content)
        
        assert result["success"] == True
        assert "h1" in result["rendered"]
        assert "strong" in result["rendered"]
        assert "em" in result["rendered"]
        assert "ul" in result["rendered"]
    
    @pytest.mark.asyncio
    async def test_code_highlighting(self, renderer):
        """测试代码高亮"""
        content = """
        ```python
        def hello_world():
            print("Hello, World!")
            return True
        ```
        """
        
        result = await renderer.render_code_blocks(content, "python")
        
        assert result["success"] == True
        assert len(result["rendered_blocks"]) == 1
        assert result["rendered_blocks"][0]["language"] == "python"
        assert "highlight" in result["rendered_blocks"][0]["highlighted"]
    
    @pytest.mark.asyncio
    async def test_latex_rendering(self, renderer):
        """测试LaTeX公式渲染"""
        content = "这是一个数学公式：$E = mc^2$"
        
        result = await renderer.render_latex_formulas(content)
        
        assert result["success"] == True
        assert len(result["rendered_formulas"]) == 1
        assert result["rendered_formulas"][0]["type"] == "inline"
        assert "data:image/png;base64," in result["rendered_formulas"][0]["image"]
    
    def test_format_detection(self, detector):
        """测试格式检测"""
        markdown_text = "# 标题\n**粗体**文本"
        assert detector.detect_markdown(markdown_text) == True
        
        code_text = "```python\nprint('hello')\n```"
        has_code, language = detector.detect_code_block(code_text)
        assert has_code == True
        assert language == "python"
        
        latex_text = "公式：$x^2 + y^2 = z^2$"
        assert detector.detect_latex(latex_text) == True
    
    @pytest.mark.asyncio
    async def test_auto_render(self, renderer):
        """测试自动渲染"""
        complex_content = """
        # 数学和代码示例
        
        这是一个二次方程的解：$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$
        
        对应的Python代码：
        ```python
        import math
        
        def solve_quadratic(a, b, c):
            discriminant = b**2 - 4*a*c
            if discriminant < 0:
                return None
            sqrt_discriminant = math.sqrt(discriminant)
            x1 = (-b + sqrt_discriminant) / (2*a)
            x2 = (-b - sqrt_discriminant) / (2*a)
            return x1, x2
        ```
        """
        
        result = await renderer.auto_render(complex_content)
        
        assert "markdown" in result["formats_detected"]
        assert "latex" in result["formats_detected"]
        assert "code" in result["formats_detected"]
        assert len(result["rendered_parts"]) >= 3
```

## 八、监控和维护

### 8.1 性能监控

```python
# app/middleware/performance_monitor.py
import time
import logging
from fastapi import Request, Response
from app.core.metrics import metrics_collector

async def performance_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    # 记录API性能指标
    metrics_collector.record_api_latency(
        endpoint=request.url.path,
        method=request.method,
        latency=process_time,
        status_code=response.status_code
    )
    
    # 添加性能头
    response.headers["X-Process-Time"] = str(process_time)
    
    return response
```

### 8.2 错误处理

```python
# app/middleware/error_handler.py
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

async def error_handler_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "success": False,
                "error": e.detail,
                "error_code": e.status_code,
                "timestamp": time.time(),
                "path": request.url.path
            }
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "内部服务器错误",
                "error_code": 500,
                "timestamp": time.time(),
                "path": request.url.path
            }
        )
```

## 九、发布计划

### 9.1 版本规划

- **v1.1.0** - 基础消息渲染功能
- **v1.2.0** - 流式渲染优化
- **v1.3.0** - 权限和状态管理增强
- **v1.4.0** - WebSocket和高级功能

### 9.2 部署步骤

1. **开发环境验证**
2. **单元测试和集成测试**
3. **性能基准测试**
4. **预生产环境部署**
5. **生产环境滚动更新**

---

## 总结

本开发计划确保了Chat-Service能够提供专业级的消息渲染功能，完整对接Agent-Service，并支持智能办公助手的所有对话需求。通过分阶段的开发方式，可以逐步提升系统功能和用户体验。