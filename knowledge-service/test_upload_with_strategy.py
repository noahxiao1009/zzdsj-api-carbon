#!/usr/bin/env python3
"""
测试带有切分策略的文件上传
"""

import requests
import io

def test_upload_with_strategy():
    """测试文件上传和策略应用"""
    
    print("测试文档上传和切分策略应用")
    print("=" * 40)
    
    # 测试参数
    base_url = "http://localhost:8082"
    kb_id = "2337adac-4659-4802-aeec-4143f38a354e"
    
    # 创建测试文件
    test_content = """
    这是一个测试文档。
    
    第一段：介绍人工智能的基本概念。人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，
    它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。
    
    第二段：机器学习是人工智能的核心技术之一。通过算法和统计模型，计算机系统能够有效地执行
    特定任务，而不需要明确的指令，仅依靠模式和推理。
    
    第三段：深度学习是机器学习的一个子集，它基于人工神经网络的表示学习。深度学习已经在
    图像识别、语音识别和自然语言处理等领域取得了显著成果。
    """
    
    # 测试不同的策略
    strategies_to_test = [
        ("token_basic", "基础Token分块"),
        ("semantic_smart", "语义分块"),
        ("smart_adaptive", "智能自适应")
    ]
    
    for strategy_id, strategy_name in strategies_to_test:
        print(f"\n测试策略: {strategy_name} ({strategy_id})")
        print("-" * 30)
        
        # 准备上传数据
        files = {
            'files': ('test_document.txt', io.StringIO(test_content), 'text/plain')
        }
        
        data = {
            'user_id': 'test_user',
            'splitter_strategy_id': strategy_id,
            'enable_async_processing': 'true'
        }
        
        try:
            response = requests.post(
                f"{base_url}/api/v1/knowledge-bases/{kb_id}/documents/upload-async",
                files=files,
                data=data
            )
            
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("上传成功!")
                print(f"响应: {result}")
                
                if result.get('success') and result.get('tasks'):
                    task_id = result['tasks'][0]['task_id']
                    print(f"任务ID: {task_id}")
                else:
                    print("警告: 响应格式异常")
            
            else:
                print(f"上传失败: {response.status_code}")
                print(f"错误: {response.text}")
                
        except Exception as e:
            print(f"请求异常: {e}")
    
    print(f"\n所有策略测试完成")

if __name__ == "__main__":
    test_upload_with_strategy()