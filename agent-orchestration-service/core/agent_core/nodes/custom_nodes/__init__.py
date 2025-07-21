"""
Custom tool node package.
Nodes in this directory will be automatically discovered and registered as Agent tools.
"""

# 导入所有工具节点以确保注册
try:
    from .google_search_node import GoogleSearchNode
    print("Google搜索工具节点 (基于DuckDuckGo) 已加载")
except ImportError as e:
    print(f"Google搜索工具节点加载失败: {e}")

# 导入其他现有工具节点
try:
    from .jina_search_node import JinaSearchNode
    from .jina_visit_node import JinaVisitNode
    print("Jina搜索工具节点已加载")
except ImportError as e:
    print(f"Jina搜索工具节点加载失败: {e}")

try:
    from .generate_report_tool import *
    from .get_principal_status_tool import *
    from .launch_principal_tool import *
    from .list_rag_sources_tool import *
    from .review_workspace_tool import *
    from .send_directive_to_principal_tool import *
    from .write_file_tool import *
    print("其他工具节点已加载")
except ImportError as e:
    print(f"部分工具节点加载失败: {e}")