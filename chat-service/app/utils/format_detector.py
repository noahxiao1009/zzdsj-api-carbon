"""
格式检测器 - 智能检测消息中的各种格式
"""

import re
from typing import Tuple, Optional, List, Dict, Any

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
    
    @staticmethod
    def extract_code_blocks(text: str) -> List[Dict[str, str]]:
        """提取所有代码块"""
        code_blocks = []
        
        # 围栏代码块
        fenced_pattern = r'```(\w+)?\n(.*?)```'
        matches = re.finditer(fenced_pattern, text, re.DOTALL)
        for match in matches:
            language = match.group(1) or 'text'
            code = match.group(2).strip()
            code_blocks.append({
                'type': 'fenced',
                'language': language,
                'code': code,
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        return code_blocks
    
    @staticmethod
    def extract_latex_formulas(text: str) -> List[Dict[str, str]]:
        """提取所有LaTeX公式"""
        formulas = []
        
        # 块级公式 $$...$$
        block_pattern = r'\$\$(.*?)\$\$'
        matches = re.finditer(block_pattern, text, re.DOTALL)
        for match in matches:
            formulas.append({
                'type': 'block',
                'formula': match.group(1).strip(),
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        # 行内公式 $...$
        inline_pattern = r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)'
        matches = re.finditer(inline_pattern, text)
        for match in matches:
            formulas.append({
                'type': 'inline',
                'formula': match.group(1).strip(),
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        return formulas
    
    @staticmethod
    def extract_tables(text: str) -> List[Dict[str, Any]]:
        """提取表格数据"""
        tables = []
        
        # Markdown表格
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if '|' in line and i + 1 < len(lines):
                next_line = lines[i + 1]
                # 检查下一行是否是分隔符
                if re.match(r'^\|[-\s:|]+\|.*$', next_line):
                    # 找到表格头
                    headers = [cell.strip() for cell in line.split('|')[1:-1]]
                    rows = []
                    
                    # 提取表格行
                    for j in range(i + 2, len(lines)):
                        if '|' in lines[j] and lines[j].strip():
                            row = [cell.strip() for cell in lines[j].split('|')[1:-1]]
                            if len(row) == len(headers):
                                rows.append(row)
                            else:
                                break
                        else:
                            break
                    
                    if rows:
                        tables.append({
                            'type': 'markdown',
                            'headers': headers,
                            'rows': rows,
                            'start_line': i,
                            'end_line': i + 2 + len(rows)
                        })
        
        return tables
    
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
        
        # 详细提取
        analysis["code_blocks"] = cls.extract_code_blocks(text)
        analysis["latex_formulas"] = cls.extract_latex_formulas(text)
        analysis["tables"] = cls.extract_tables(text)
        
        # 内容统计
        analysis["statistics"] = {
            "character_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.split('\n')),
            "complexity_score": len(analysis["detected_formats"]),
            "code_block_count": len(analysis["code_blocks"]),
            "formula_count": len(analysis["latex_formulas"]),
            "table_count": len(analysis["tables"])
        }
        
        return analysis
    
    @staticmethod
    def get_content_complexity(text: str) -> str:
        """评估内容复杂度"""
        analysis = FormatDetector.analyze_content(text)
        complexity_score = analysis["statistics"]["complexity_score"]
        
        if complexity_score == 0:
            return "simple"      # 纯文本
        elif complexity_score <= 2:
            return "moderate"    # 包含少量格式
        else:
            return "complex"     # 包含多种复杂格式
    
    @staticmethod
    def should_render(text: str, min_complexity: str = "simple") -> bool:
        """判断是否需要渲染"""
        complexity = FormatDetector.get_content_complexity(text)
        
        complexity_levels = {"simple": 0, "moderate": 1, "complex": 2}
        min_level = complexity_levels.get(min_complexity, 0)
        current_level = complexity_levels.get(complexity, 0)
        
        return current_level >= min_level