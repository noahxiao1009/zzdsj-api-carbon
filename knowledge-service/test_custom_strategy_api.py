#!/usr/bin/env python3
"""
测试自定义切分策略API
"""

import requests
import json
import sys

def test_custom_strategy_api():
    """测试自定义策略API"""
    
    # 测试参数
    base_url = "http://localhost:8082"
    kb_id = "2337adac-4659-4802-aeec-4143f38a354e"
    
    print("=== 测试自定义切分策略API ===")
    print(f"知识库ID: {kb_id}")
    
    # 测试创建自定义策略
    create_url = f"{base_url}/api/v1/knowledge-bases/{kb_id}/splitter-strategies"
    
    # 自定义策略数据
    strategy_data = {
        "name": f"测试自定义策略_{int(time.time())}",
        "description": "API测试用的自定义策略",
        "chunk_strategy": "token_based",
        "chunk_size": 1200,
        "chunk_overlap": 250,
        "preserve_structure": True,
        "parameters": {
            "test": True,
            "created_via": "api_test"
        },
        "is_active": True,
        "category": "custom"
    }
    
    try:
        print(f"\n请求URL: {create_url}")
        print(f"请求数据: {json.dumps(strategy_data, indent=2, ensure_ascii=False)}")
        
        response = requests.post(
            create_url,
            headers={"Content-Type": "application/json"},
            json=strategy_data
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API调用成功!")
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data.get("success"):
                strategy = data.get("strategy", {})
                print(f"\n📊 策略创建结果:")
                print(f"- 策略ID: {strategy.get('id')}")
                print(f"- 策略名称: {strategy.get('name')}")
                print(f"- 分块大小: {strategy.get('config', {}).get('chunk_size')}")
                print(f"- 重叠大小: {strategy.get('config', {}).get('chunk_overlap')}")
                
                return strategy.get('id')
            else:
                print(f"❌ API返回失败: {data}")
                
        elif response.status_code == 404:
            print("❌ API路由不存在 (404) - 可能服务未启动或路由未注册")
            try:
                error_data = response.json()
                print(f"错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"响应内容: {response.text}")
                
        elif response.status_code == 422:
            print("❌ 请求参数验证失败 (422)")
            try:
                error_data = response.json()
                print(f"验证错误: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
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
    
    return None

def test_list_strategies_api():
    """测试获取策略列表API"""
    
    base_url = "http://localhost:8082"
    kb_id = "2337adac-4659-4802-aeec-4143f38a354e"
    
    print("\n=== 测试策略列表API ===")
    
    list_url = f"{base_url}/api/v1/knowledge-bases/{kb_id}/splitter-strategies"
    
    try:
        print(f"请求URL: {list_url}")
        response = requests.get(list_url, headers={"Content-Type": "application/json"})
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 策略列表获取成功!")
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data.get("success"):
                strategies = data.get("strategies", [])
                print(f"\n📊 策略列表:")
                print(f"- 策略总数: {data.get('total', 0)}")
                for i, strategy in enumerate(strategies, 1):
                    print(f"  {i}. {strategy.get('name')} (ID: {strategy.get('id')})")
        else:
            print(f"❌ 获取策略列表失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
                
    except Exception as e:
        print(f"❌ 获取策略列表异常: {e}")

if __name__ == "__main__":
    import time
    
    print("自定义切分策略 - API测试")
    print("=" * 50)
    
    # 测试策略列表
    test_list_strategies_api()
    
    # 测试创建自定义策略
    strategy_id = test_custom_strategy_api()
    
    print("\n" + "=" * 50)
    print("测试完成")
    
    if strategy_id:
        print(f"✅ 成功创建策略ID: {strategy_id}")
    else:
        print("❌ 策略创建失败")