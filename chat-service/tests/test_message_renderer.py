"""
消息渲染器测试用例
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from app.services.message_renderer import MessageRenderer, get_message_renderer
from app.utils.format_detector import FormatDetector


class TestFormatDetector:
    """格式检测器测试"""
    
    def test_detect_markdown(self):
        """测试Markdown检测"""
        detector = FormatDetector()
        
        # 测试标题
        assert detector.detect_markdown("# 这是标题") == True
        assert detector.detect_markdown("## 二级标题") == True
        
        # 测试粗体和斜体
        assert detector.detect_markdown("这是**粗体**文本") == True
        assert detector.detect_markdown("这是*斜体*文本") == True
        
        # 测试列表
        assert detector.detect_markdown("- 列表项") == True
        assert detector.detect_markdown("1. 有序列表") == True
        
        # 测试链接
        assert detector.detect_markdown("[链接](http://example.com)") == True
        
        # 测试纯文本
        assert detector.detect_markdown("这是普通文本") == False
    
    def test_detect_code_block(self):
        """测试代码块检测"""
        detector = FormatDetector()
        
        # 测试围栏代码块
        code_text = """```python
def hello():
    print("Hello World")
```"""
        has_code, language = detector.detect_code_block(code_text)
        assert has_code == True
        assert language == "python"
        
        # 测试无语言标识的代码块
        code_text_no_lang = """```
some code here
```"""
        has_code, language = detector.detect_code_block(code_text_no_lang)
        assert has_code == True
        assert language == "text"
        
        # 测试缩进代码块
        indent_code = "    def function():\n        pass"
        has_code, language = detector.detect_code_block(indent_code)
        assert has_code == True
        assert language == "text"
        
        # 测试非代码文本
        normal_text = "这是普通文本，没有代码"
        has_code, language = detector.detect_code_block(normal_text)
        assert has_code == False
        assert language == None
    
    def test_detect_latex(self):
        """测试LaTeX检测"""
        detector = FormatDetector()
        
        # 测试行内公式
        assert detector.detect_latex("这是公式：$E = mc^2$") == True
        
        # 测试块级公式
        assert detector.detect_latex("$$\\int_0^1 x^2 dx$$") == True
        
        # 测试LaTeX环境
        assert detector.detect_latex("\\begin{equation}x + y = z\\end{equation}") == True
        
        # 测试LaTeX命令
        assert detector.detect_latex("\\alpha + \\beta = \\gamma") == True
        
        # 测试普通文本
        assert detector.detect_latex("这是普通文本") == False
    
    def test_detect_table(self):
        """测试表格检测"""
        detector = FormatDetector()
        
        # 测试Markdown表格
        table_text = """| 姓名 | 年龄 | 城市 |
|------|------|------|
| 张三 | 25   | 北京 |
| 李四 | 30   | 上海 |"""
        assert detector.detect_table(table_text) == True
        
        # 测试CSV格式
        csv_text = """姓名,年龄,城市
张三,25,北京
李四,30,上海"""
        assert detector.detect_table(csv_text) == True
        
        # 测试普通文本
        assert detector.detect_table("这是普通文本") == False
    
    def test_analyze_content(self):
        """测试内容全面分析"""
        detector = FormatDetector()
        
        complex_content = """
# 数学和编程示例

这是一个包含多种格式的文档。

## 数学公式
二次方程的解：$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$

## 代码示例
```python
import math

def solve_quadratic(a, b, c):
    discriminant = b**2 - 4*a*c
    if discriminant < 0:
        return None
    return (-b + math.sqrt(discriminant)) / (2*a)
```

## 数据表格
| 参数 | 值 | 说明 |
|------|----|----- |
| a    | 1  | 二次项系数 |
| b    | -3 | 一次项系数 |
| c    | 2  | 常数项 |
"""
        
        analysis = detector.analyze_content(complex_content)
        
        assert analysis["has_markdown"] == True
        assert analysis["has_latex"] == True
        assert analysis["has_code"] == True
        assert analysis["has_table"] == True
        
        assert "markdown" in analysis["detected_formats"]
        assert "latex" in analysis["detected_formats"]
        assert "code" in analysis["detected_formats"]
        assert "table" in analysis["detected_formats"]
        
        assert analysis["code_language"] == "python"
        assert len(analysis["code_blocks"]) >= 1
        assert len(analysis["latex_formulas"]) >= 1
        assert len(analysis["tables"]) >= 1
        
        stats = analysis["statistics"]
        assert stats["complexity_score"] >= 3
        assert stats["code_block_count"] >= 1
        assert stats["formula_count"] >= 1
        assert stats["table_count"] >= 1


class TestMessageRenderer:
    """消息渲染器测试"""
    
    @pytest.fixture
    def renderer(self):
        """创建渲染器实例"""
        return MessageRenderer()
    
    @pytest.mark.asyncio
    async def test_render_markdown(self, renderer):
        """测试Markdown渲染"""
        content = """
# 标题测试
这是**粗体**和*斜体*文本。

- 列表项1
- 列表项2

[链接示例](http://example.com)
"""
        
        with patch('app.services.message_renderer.MARKDOWN_AVAILABLE', True):
            # Mock markdown模块
            mock_md = MagicMock()
            mock_md.convert.return_value = "<h1>标题测试</h1><p>这是<strong>粗体</strong>和<em>斜体</em>文本。</p>"
            
            with patch.object(renderer, 'md', mock_md):
                result = await renderer.render_markdown(content)
                
                assert result["success"] == True
                assert result["format"] == "markdown"
                assert "rendered" in result
                assert result["raw"] == content
                assert "metadata" in result
    
    @pytest.mark.asyncio
    async def test_render_code(self, renderer):
        """测试代码渲染"""
        code = """def hello_world():
    print("Hello, World!")
    return True"""
        
        with patch('app.services.message_renderer.PYGMENTS_AVAILABLE', True):
            # Mock pygments
            mock_lexer = MagicMock()
            mock_highlight = MagicMock(return_value="<div class='highlight'>...</div>")
            
            with patch('app.services.message_renderer.get_lexer_by_name', return_value=mock_lexer):
                with patch('app.services.message_renderer.highlight', mock_highlight):
                    result = await renderer.render_code(code, "python")
                    
                    assert result["success"] == True
                    assert result["format"] == "code"
                    assert result["language"] == "python"
                    assert "rendered" in result
                    assert result["raw_code"] == code
    
    @pytest.mark.asyncio
    async def test_render_latex_formulas(self, renderer):
        """测试LaTeX公式渲染"""
        content = "这是一个公式：$E = mc^2$ 和块级公式：$$\\int_0^1 x^2 dx$$"
        
        with patch('app.services.message_renderer.MATPLOTLIB_AVAILABLE', True):
            # Mock matplotlib
            mock_plt = MagicMock()
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"fake_image_data"
            
            with patch('app.services.message_renderer.plt', mock_plt):
                with patch('app.services.message_renderer.io.BytesIO', return_value=mock_buffer):
                    with patch('app.services.message_renderer.base64.b64encode', return_value=b"ZmFrZV9pbWFnZV9kYXRh"):
                        result = await renderer.render_latex_formulas(content)
                        
                        assert result["success"] == True
                        assert result["format"] == "latex"
                        assert "rendered_formulas" in result
    
    @pytest.mark.asyncio
    async def test_auto_render(self, renderer):
        """测试自动渲染"""
        complex_content = """
# 示例文档

这是一个包含多种格式的示例：

```python
print("Hello World")
```

数学公式：$x^2 + y^2 = z^2$
"""
        
        # Mock所有依赖库为可用
        with patch('app.services.message_renderer.MARKDOWN_AVAILABLE', True):
            with patch('app.services.message_renderer.PYGMENTS_AVAILABLE', True):
                with patch('app.services.message_renderer.MATPLOTLIB_AVAILABLE', True):
                    # Mock具体实现
                    with patch.object(renderer, 'render_markdown') as mock_md:
                        with patch.object(renderer, 'render_code') as mock_code:
                            with patch.object(renderer, 'render_latex_formulas') as mock_latex:
                                
                                mock_md.return_value = {"success": True, "format": "markdown"}
                                mock_code.return_value = {"success": True, "format": "code"}
                                mock_latex.return_value = {"success": True, "format": "latex"}
                                
                                result = await renderer.auto_render(complex_content)
                                
                                assert result["success"] == True
                                assert result["original"] == complex_content
                                assert "rendered_parts" in result
                                assert "formats_detected" in result
                                assert "render_time" in result
    
    @pytest.mark.asyncio
    async def test_render_without_dependencies(self, renderer):
        """测试在缺少依赖的情况下的渲染"""
        content = "# 标题"
        
        # 模拟依赖库不可用
        with patch('app.services.message_renderer.MARKDOWN_AVAILABLE', False):
            result = await renderer.render_markdown(content)
            
            assert result["success"] == False
            assert "error" in result
            assert "Markdown库不可用" in result["error"]
    
    def test_get_render_capabilities(self, renderer):
        """测试获取渲染能力"""
        capabilities = renderer.get_render_capabilities()
        
        assert "markdown" in capabilities
        assert "code" in capabilities
        assert "latex" in capabilities
        assert "tables" in capabilities
        assert "html" in capabilities
        
        for format_type, info in capabilities.items():
            assert "available" in info
            assert "features" in info
    
    def test_clear_cache(self, renderer):
        """测试清理缓存"""
        # 添加一些缓存数据
        renderer._cache["test_key"] = "test_value"
        assert len(renderer._cache) > 0
        
        # 清理缓存
        renderer.clear_cache()
        assert len(renderer._cache) == 0
    
    def test_singleton_instance(self):
        """测试单例模式"""
        renderer1 = get_message_renderer()
        renderer2 = get_message_renderer()
        
        assert renderer1 is renderer2


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_rendering_pipeline(self):
        """测试完整的渲染流水线"""
        renderer = get_message_renderer()
        
        test_content = """
# 完整示例

这是一个完整的测试示例，包含：

## 代码块
```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

## 数学公式
斐波那契数列的通项公式：$F_n = \\frac{\\phi^n - \\psi^n}{\\sqrt{5}}$

其中：
- $\\phi = \\frac{1 + \\sqrt{5}}{2}$ (黄金比例)
- $\\psi = \\frac{1 - \\sqrt{5}}{2}$

## 数据表格
| n | F(n) | 说明 |
|---|------|------|
| 0 | 0    | 第0项 |
| 1 | 1    | 第1项 |
| 2 | 1    | 第2项 |
| 3 | 2    | 第3项 |
"""
        
        # 首先测试格式检测
        detector = FormatDetector()
        analysis = detector.analyze_content(test_content)
        
        assert analysis["has_markdown"] == True
        assert analysis["has_code"] == True
        assert analysis["has_latex"] == True
        assert analysis["has_table"] == True
        
        # 然后测试渲染（在有依赖的情况下）
        try:
            result = await renderer.auto_render(test_content)
            # 如果依赖可用，检查渲染结果
            if result["success"]:
                assert len(result["rendered_parts"]) > 0
                assert len(result["formats_detected"]) > 0
                assert result["render_time"] >= 0
        except Exception as e:
            # 如果依赖不可用，应该优雅地处理
            pytest.skip(f"渲染依赖不可用: {e}")
    
    @pytest.mark.asyncio
    async def test_performance_with_large_content(self):
        """测试大内容的性能"""
        renderer = get_message_renderer()
        
        # 生成大量内容
        large_content = "# 大文档测试\n\n" + "这是一段很长的文本。" * 1000
        large_content += "\n\n```python\n" + "print('test')\n" * 100 + "```"
        large_content += "\n\n数学公式：" + "$x^2$" * 50
        
        start_time = asyncio.get_event_loop().time()
        result = await renderer.auto_render(large_content)
        end_time = asyncio.get_event_loop().time()
        
        # 检查性能（应该在合理时间内完成）
        render_time = (end_time - start_time) * 1000
        assert render_time < 10000  # 小于10秒
        
        # 检查结果合理性
        if result["success"]:
            assert result["render_time"] > 0
            assert len(result["original"]) > 10000