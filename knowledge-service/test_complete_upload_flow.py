#!/usr/bin/env python3
"""
测试完整的文件上传流程，包括策略记录
"""

import requests
import io
import time

def test_complete_upload_flow():
    """测试完整上传流程"""
    
    print("测试完整文件上传流程")
    print("=" * 40)
    
    # 测试参数
    base_url = "http://localhost:8082"
    kb_id = "2337adac-4659-4802-aeec-4143f38a354e"
    
    # 创建测试文件
    test_content = """
    测试文档内容
    
    这是一个用于测试文档处理流程的示例文档。
    文档包含多个段落，用于验证切分策略的效果。
    
    第一段：人工智能基础概念
    第二段：机器学习技术原理  
    第三段：深度学习应用场景
    """
    
    # 测试策略
    strategy_id = "token_basic"
    
    print(f"使用策略: {strategy_id}")
    print("-" * 30)
    
    # 准备上传数据
    files = {
        'files': ('complete_test.txt', io.StringIO(test_content), 'text/plain')
    }
    
    data = {
        'user_id': 'test_user_complete',
        'splitter_strategy_id': strategy_id,
        'enable_async_processing': 'true',
        'chunk_size': '1000',
        'chunk_overlap': '200'
    }
    
    try:
        print("发送上传请求...")
        response = requests.post(
            f"{base_url}/api/v1/knowledge-bases/{kb_id}/documents/upload-async",
            files=files,
            data=data
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("上传成功!")
            
            if result.get('success') and result.get('data', {}).get('tasks'):
                task_info = result['data']['tasks'][0]
                task_id = task_info['task_id']
                print(f"任务ID: {task_id}")
                print(f"文件名: {task_info['filename']}")
                print(f"文件大小: {task_info['file_size']} bytes")
                print(f"状态: {task_info['status']}")
                
                # 等待一下让任务开始处理
                time.sleep(2)
                
                print("\n检查文档列表...")
                list_response = requests.get(
                    f"{base_url}/api/v1/knowledge-bases/{kb_id}/documents"
                )
                
                if list_response.status_code == 200:
                    list_result = list_response.json()
                    if list_result.get('success'):
                        documents = list_result.get('data', {}).get('documents', [])
                        print(f"文档列表中的文档数量: {len(documents)}")
                        
                        # 查找刚上传的文档
                        uploaded_doc = None
                        for doc in documents:
                            if task_info['filename'] in doc.get('filename', ''):
                                uploaded_doc = doc
                                break
                        
                        if uploaded_doc:
                            print(f"找到上传的文档:")
                            print(f"  - ID: {uploaded_doc['id']}")
                            print(f"  - 文件名: {uploaded_doc['filename']}")
                            print(f"  - 状态: {uploaded_doc['status']}")
                            print(f"  - 分块数: {uploaded_doc.get('chunk_count', 0)}")
                        else:
                            print("未在文档列表中找到上传的文档")
                    else:
                        print("获取文档列表失败")
                else:
                    print(f"文档列表请求失败: {list_response.status_code}")
                
            else:
                print("警告: 响应格式异常")
                print(f"响应内容: {result}")
        
        else:
            print(f"上传失败: {response.status_code}")
            print(f"错误: {response.text}")
            
    except Exception as e:
        print(f"请求异常: {e}")

if __name__ == "__main__":
    test_complete_upload_flow()