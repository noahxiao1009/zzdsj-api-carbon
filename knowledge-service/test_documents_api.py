#!/usr/bin/env python3
"""
测试文档列表API
"""

import requests
import json
import sys

def test_documents_api():
    """测试文档列表API"""
    
    # 测试参数
    base_url = "http://localhost:8082"
    kb_id = "2337adac-4659-4802-aeec-4143f38a354e"
    
    print("=== 测试知识库文档列表API ===")
    print(f"知识库ID: {kb_id}")
    
    # 测试GET请求
    url = f"{base_url}/api/v1/knowledge-bases/{kb_id}/documents"
    
    try:
        print(f"\n请求URL: {url}")
        response = requests.get(url, headers={"Content-Type": "application/json"})
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API调用成功!")
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # 分析响应结构
            if data.get("success"):
                documents = data.get("data", {}).get("documents", [])
                pagination = data.get("data", {}).get("pagination", {})
                
                print(f"\n📊 结果分析:")
                print(f"- 成功: {data.get('success')}")
                print(f"- 文档数量: {len(documents)}")
                print(f"- 总数: {pagination.get('total', 0)}")
                print(f"- 当前页: {pagination.get('page', 1)}")
                print(f"- 每页大小: {pagination.get('page_size', 20)}")
                
                if documents:
                    print(f"\n📄 文档列表:")
                    for i, doc in enumerate(documents, 1):
                        print(f"  {i}. {doc.get('filename', 'Unknown')} ({doc.get('status', 'No status')})")
                else:
                    print("\n📄 文档列表: 空")
            else:
                print(f"❌ API返回失败: {data}")
                
        elif response.status_code == 404:
            print("❌ 知识库不存在 (404)")
            try:
                error_data = response.json()
                print(f"错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"响应内容: {response.text}")
                
        elif response.status_code == 405:
            print("❌ 方法不允许 (405) - API路由可能未正确注册")
            print(f"响应内容: {response.text}")
            
        else:
            print(f"❌ API调用失败，状态码: {response.status_code}")
            try:
                error_data = response.json()
                print(f"错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"响应内容: {response.text}")
                
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败 - 检查服务是否运行在端口8082")
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")

def test_api_routes():
    """测试API路由是否注册"""
    
    print("\n=== 测试API路由注册 ===")
    
    base_url = "http://localhost:8082"
    
    # 测试根路径
    try:
        response = requests.get(f"{base_url}/")
        print(f"根路径 (/): {response.status_code}")
    except:
        print("根路径 (/): 连接失败")
    
    # 测试文档路径
    try:
        response = requests.get(f"{base_url}/docs")
        print(f"API文档 (/docs): {response.status_code}")
    except:
        print("API文档 (/docs): 连接失败")
    
    # 测试OpenAPI规范
    try:
        response = requests.get(f"{base_url}/openapi.json")
        if response.status_code == 200:
            print(f"OpenAPI规范 (/openapi.json): {response.status_code}")
            openapi_data = response.json()
            paths = openapi_data.get("paths", {})
            
            # 查找文档相关的路径
            doc_paths = [path for path in paths.keys() if "documents" in path]
            print(f"发现的文档相关路径: {doc_paths}")
        else:
            print(f"OpenAPI规范 (/openapi.json): {response.status_code}")
    except Exception as e:
        print(f"OpenAPI规范检查失败: {e}")

if __name__ == "__main__":
    print("知识库服务 - 文档API测试")
    print("=" * 50)
    
    # 测试API路由
    test_api_routes()
    
    # 测试文档API
    test_documents_api()
    
    print("\n" + "=" * 50)
    print("测试完成")