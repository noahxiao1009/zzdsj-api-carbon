"""
消息渲染器 - 支持多种格式的消息渲染功能
"""

import asyncio
import base64
import hashlib
import io
import json
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

# 尝试导入依赖库，如果不存在则使用降级方案
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import HtmlFormatter
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from app.utils.format_detector import FormatDetector
from app.core.redis import redis_manager

logger = logging.getLogger(__name__)


class MessageRenderer:
    """消息渲染器"""
    
    def __init__(self):
        self._cache = {}
        self._setup_components()
    
    def _setup_components(self):
        """设置渲染组件"""
        # Markdown设置
        if MARKDOWN_AVAILABLE:
            self.md = markdown.Markdown(
                extensions=[
                    'tables', 'fenced_code', 'toc', 'codehilite',
                    'nl2br', 'attr_list', 'def_list'
                ],
                extension_configs={
                    'codehilite': {
                        'css_class': 'highlight',
                        'use_pygments': PYGMENTS_AVAILABLE
                    }
                }
            )
        
        # 代码高亮设置
        if PYGMENTS_AVAILABLE:
            self.html_formatter = HtmlFormatter(
                style='github',
                linenos=True,
                linenostart=1,
                cssclass='highlight',
                wrapcode=True
            )
        
        # 支持的编程语言
        self.supported_languages = [
            'python', 'javascript', 'java', 'cpp', 'c', 'csharp',
            'sql', 'html', 'css', 'json', 'yaml', 'xml', 'bash',
            'shell', 'powershell', 'go', 'rust', 'php', 'ruby',
            'swift', 'kotlin', 'scala', 'r', 'matlab', 'latex'
        ]
    
    async def auto_render(self, content: str, enable_cache: bool = True) -> Dict[str, Any]:
        """自动检测格式并渲染"""
        try:
            # 检查缓存
            cache_key = f"render_{hashlib.md5(content.encode()).hexdigest()}"
            if enable_cache and cache_key in self._cache:
                return self._cache[cache_key]
            
            start_time = datetime.now()
            detector = FormatDetector()
            
            # 分析内容
            analysis = detector.analyze_content(content)
            rendered_parts = []
            
            # 渲染Markdown
            if analysis["has_markdown"]:
                md_result = await self.render_markdown(content)
                if md_result["success"]:
                    rendered_parts.append(md_result)
            
            # 渲染代码块
            if analysis["code_blocks"]:
                for code_block in analysis["code_blocks"]:
                    code_result = await self.render_code(
                        code_block["code"], 
                        code_block["language"]
                    )
                    if code_result["success"]:
                        rendered_parts.append(code_result)
            
            # 渲染LaTeX公式
            if analysis["latex_formulas"]:
                latex_result = await self.render_latex_formulas(content)
                if latex_result["success"]:
                    rendered_parts.append(latex_result)
            
            # 渲染表格
            if analysis["tables"]:
                for table in analysis["tables"]:
                    table_result = await self.render_table_data(table)
                    if table_result["success"]:
                        rendered_parts.append(table_result)
            
            # 处理HTML内容
            if analysis["has_html"]:
                html_result = await self.render_html_content(content)
                if html_result["success"]:
                    rendered_parts.append(html_result)
            
            end_time = datetime.now()
            render_time = (end_time - start_time).total_seconds() * 1000
            
            result = {
                "success": True,
                "original": content,
                "rendered_parts": rendered_parts,
                "formats_detected": analysis["detected_formats"],
                "render_time": render_time,
                "analysis": analysis,
                "timestamp": end_time.isoformat()
            }
            
            # 缓存结果
            if enable_cache:
                self._cache[cache_key] = result
                # 同时缓存到Redis
                try:
                    redis_manager.set_json(f"render_cache:{cache_key}", result, ex=3600)
                except Exception as e:
                    logger.warning(f"Redis缓存失败: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"自动渲染失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "original": content,
                "rendered_parts": [],
                "formats_detected": []
            }
    
    async def render_markdown(self, content: str) -> Dict[str, Any]:
        """渲染Markdown内容"""
        if not MARKDOWN_AVAILABLE:
            return {
                "success": False,
                "error": "Markdown库不可用",
                "format": "markdown"
            }
        
        try:
            html_content = self.md.convert(content)
            
            # 提取目录
            toc = getattr(self.md, 'toc', '')
            
            # 统计信息
            metadata = {
                "has_tables": '<table>' in html_content,
                "has_links": '<a href=' in html_content,
                "has_images": '<img' in html_content,
                "has_code": '<code>' in html_content,
                "has_toc": bool(toc),
                "word_count": len(content.split()),
                "estimated_reading_time": max(1, len(content.split()) // 200)  # 分钟
            }
            
            return {
                "success": True,
                "format": "markdown",
                "rendered": html_content,
                "toc": toc,
                "raw": content,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Markdown渲染失败: {e}")
            return {
                "success": False,
                "format": "markdown",
                "error": str(e),
                "raw": content
            }
    
    async def render_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """渲染代码块"""
        if not PYGMENTS_AVAILABLE:
            return {
                "success": False,
                "error": "Pygments库不可用",
                "format": "code"
            }
        
        try:
            # 清理代码
            code = code.strip()
            if not code:
                return {
                    "success": False,
                    "error": "代码内容为空",
                    "format": "code"
                }
            
            # 获取词法分析器
            try:
                if language and language in self.supported_languages:
                    lexer = get_lexer_by_name(language)
                else:
                    # 尝试自动检测语言
                    lexer = guess_lexer(code)
                    language = lexer.name.lower()
            except ClassNotFound:
                # 使用文本词法分析器
                lexer = get_lexer_by_name('text')
                language = 'text'
            
            # 语法高亮
            highlighted = highlight(code, lexer, self.html_formatter)
            
            # 代码统计
            lines = code.split('\n')
            metadata = {
                "language": language,
                "line_count": len(lines),
                "character_count": len(code),
                "estimated_complexity": self._estimate_code_complexity(code, language),
                "has_comments": self._has_comments(code, language),
                "max_line_length": max(len(line) for line in lines) if lines else 0
            }
            
            return {
                "success": True,
                "format": "code",
                "language": language,
                "rendered": highlighted,
                "raw_code": code,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"代码渲染失败: {e}")
            return {
                "success": False,
                "format": "code",
                "error": str(e),
                "raw_code": code
            }
    
    async def render_latex_formulas(self, content: str) -> Dict[str, Any]:
        """渲染LaTeX数学公式"""
        if not MATPLOTLIB_AVAILABLE:
            return {
                "success": False,
                "error": "Matplotlib库不可用",
                "format": "latex"
            }
        
        try:
            detector = FormatDetector()
            formulas = detector.extract_latex_formulas(content)
            
            rendered_formulas = []
            
            for formula_info in formulas:
                formula = formula_info["formula"]
                formula_type = formula_info["type"]
                
                try:
                    image_data = await self._render_latex_to_image(
                        formula, 
                        block=(formula_type == "block")
                    )
                    
                    if image_data:
                        rendered_formulas.append({
                            "type": formula_type,
                            "formula": formula,
                            "image": image_data,
                            "position": {
                                "start": formula_info["start_pos"],
                                "end": formula_info["end_pos"]
                            }
                        })
                except Exception as e:
                    logger.warning(f"LaTeX公式渲染失败: {formula} - {e}")
                    continue
            
            return {
                "success": True,
                "format": "latex",
                "rendered_formulas": rendered_formulas,
                "total_formulas": len(rendered_formulas),
                "original_content": content
            }
            
        except Exception as e:
            logger.error(f"LaTeX渲染失败: {e}")
            return {
                "success": False,
                "format": "latex",
                "error": str(e)
            }
    
    async def render_table_data(self, table_info: Dict[str, Any]) -> Dict[str, Any]:
        """渲染表格数据"""
        if not PANDAS_AVAILABLE:
            return {
                "success": False,
                "error": "Pandas库不可用",
                "format": "table"
            }
        
        try:
            headers = table_info["headers"]
            rows = table_info["rows"]
            
            # 创建DataFrame
            df = pd.DataFrame(rows, columns=headers)
            
            # 生成HTML表格
            html_table = df.to_html(
                classes='table table-striped table-hover table-bordered',
                table_id='rendered-table',
                escape=False,
                index=False
            )
            
            # 表格统计
            metadata = {
                "row_count": len(rows),
                "column_count": len(headers),
                "headers": headers,
                "data_types": self._analyze_table_types(df),
                "has_numeric_data": any(df.select_dtypes(include=['number']).columns),
                "has_empty_cells": df.isnull().sum().sum() > 0
            }
            
            return {
                "success": True,
                "format": "table",
                "rendered": html_table,
                "headers": headers,
                "rows": rows,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"表格渲染失败: {e}")
            return {
                "success": False,
                "format": "table",
                "error": str(e)
            }
    
    async def render_html_content(self, content: str) -> Dict[str, Any]:
        """渲染HTML内容"""
        if not BS4_AVAILABLE:
            return {
                "success": False,
                "error": "BeautifulSoup库不可用",
                "format": "html"
            }
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # 清理和安全化HTML
            cleaned_html = self._sanitize_html(soup)
            
            # HTML分析
            metadata = {
                "tag_count": len(soup.find_all()),
                "has_links": bool(soup.find_all('a')),
                "has_images": bool(soup.find_all('img')),
                "has_tables": bool(soup.find_all('table')),
                "has_forms": bool(soup.find_all('form')),
                "text_length": len(soup.get_text().strip())
            }
            
            return {
                "success": True,
                "format": "html",
                "rendered": str(cleaned_html),
                "raw": content,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"HTML渲染失败: {e}")
            return {
                "success": False,
                "format": "html",
                "error": str(e),
                "raw": content
            }
    
    async def _render_latex_to_image(self, formula: str, block: bool = False) -> Optional[str]:
        """将LaTeX公式渲染为图片"""
        try:
            # 设置图像尺寸
            fig_size = (12, 3) if block else (8, 1.5)
            fig, ax = plt.subplots(figsize=fig_size)
            
            # 渲染公式
            ax.text(
                0.5, 0.5, f"${formula}$",
                fontsize=16 if block else 14,
                ha='center', va='center',
                transform=ax.transAxes
            )
            ax.axis('off')
            
            # 转换为图片
            buffer = io.BytesIO()
            plt.savefig(
                buffer, format='png',
                bbox_inches='tight',
                dpi=150,
                transparent=True,
                pad_inches=0.1
            )
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return f"data:image/png;base64,{image_base64}"
            
        except Exception as e:
            logger.error(f"LaTeX图片渲染失败: {e}")
            return None
    
    def _estimate_code_complexity(self, code: str, language: str) -> str:
        """估算代码复杂度"""
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # 基于行数的基础复杂度
        if len(non_empty_lines) <= 10:
            base_complexity = 1
        elif len(non_empty_lines) <= 50:
            base_complexity = 2
        else:
            base_complexity = 3
        
        # 基于控制结构的复杂度
        control_keywords = ['if', 'else', 'for', 'while', 'try', 'catch', 'switch', 'case']
        control_count = sum(1 for line in non_empty_lines 
                          for keyword in control_keywords 
                          if keyword in line.lower())
        
        complexity_score = base_complexity + min(control_count // 5, 2)
        
        if complexity_score <= 2:
            return "simple"
        elif complexity_score <= 4:
            return "moderate"
        else:
            return "complex"
    
    def _has_comments(self, code: str, language: str) -> bool:
        """检查代码是否包含注释"""
        comment_patterns = {
            'python': [r'#.*', r'""".*?"""', r"'''.*?'''"],
            'javascript': [r'//.*', r'/\*.*?\*/'],
            'java': [r'//.*', r'/\*.*?\*/', r'/\*\*.*?\*/'],
            'cpp': [r'//.*', r'/\*.*?\*/'],
            'c': [r'//.*', r'/\*.*?\*/'],
            'sql': [r'--.*', r'/\*.*?\*/'],
            'html': [r'<!--.*?-->'],
            'css': [r'/\*.*?\*/'],
        }
        
        patterns = comment_patterns.get(language.lower(), [r'#.*', r'//.*', r'/\*.*?\*/'])
        
        for pattern in patterns:
            if re.search(pattern, code, re.DOTALL):
                return True
        
        return False
    
    def _analyze_table_types(self, df) -> Dict[str, str]:
        """分析表格列的数据类型"""
        if not PANDAS_AVAILABLE:
            return {}
        
        type_mapping = {
            'object': 'text',
            'int64': 'integer',
            'float64': 'float',
            'bool': 'boolean',
            'datetime64[ns]': 'datetime'
        }
        
        return {
            col: type_mapping.get(str(df[col].dtype), 'unknown')
            for col in df.columns
        }
    
    def _sanitize_html(self, soup) -> str:
        """清理和安全化HTML内容"""
        # 移除危险标签
        dangerous_tags = ['script', 'style', 'meta', 'link', 'base', 'object', 'embed']
        for tag in dangerous_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 移除危险属性
        dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus']
        for element in soup.find_all():
            for attr in dangerous_attrs:
                if attr in element.attrs:
                    del element.attrs[attr]
        
        return soup
    
    def get_render_capabilities(self) -> Dict[str, Any]:
        """获取渲染能力信息"""
        return {
            "markdown": {
                "available": MARKDOWN_AVAILABLE,
                "features": ["headers", "lists", "links", "images", "tables", "code", "quotes"]
            },
            "code": {
                "available": PYGMENTS_AVAILABLE,
                "supported_languages": self.supported_languages,
                "features": ["syntax_highlighting", "line_numbers", "auto_detection"]
            },
            "latex": {
                "available": MATPLOTLIB_AVAILABLE,
                "features": ["inline_formulas", "block_formulas", "mathematical_symbols"]
            },
            "tables": {
                "available": PANDAS_AVAILABLE,
                "features": ["markdown_tables", "csv_import", "data_analysis"]
            },
            "html": {
                "available": BS4_AVAILABLE,
                "features": ["tag_parsing", "content_sanitization", "metadata_extraction"]
            }
        }
    
    def clear_cache(self):
        """清理缓存"""
        self._cache.clear()
        logger.info("消息渲染缓存已清理")


# 全局渲染器实例
_message_renderer: Optional[MessageRenderer] = None


def get_message_renderer() -> MessageRenderer:
    """获取消息渲染器实例"""
    global _message_renderer
    if _message_renderer is None:
        _message_renderer = MessageRenderer()
    return _message_renderer