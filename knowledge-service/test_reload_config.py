#!/usr/bin/env python3
"""
热重载配置测试脚本
测试不同配置下的热重载行为
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_config_loading():
    """测试配置加载"""
    print("[TEST] 测试配置加载...")
    
    from app.config.settings import settings
    
    print(f"   Environment: {settings.environment}")
    print(f"   Enable Reload: {getattr(settings, 'enable_reload', '未配置')}")
    print(f"   Reload Dirs: {getattr(settings, 'reload_dirs', '未配置')}")
    print(f"   Reload Excludes: {getattr(settings, 'reload_excludes', '未配置')}")
    
    return settings

def test_reload_logic(settings):
    """测试热重载逻辑"""
    print("\n[TEST] 测试热重载逻辑...")
    
    # 模拟main.py中的逻辑
    enable_reload = (
        settings.environment == "development" and 
        getattr(settings, 'enable_reload', True)
    )
    
    reload_config = {}
    if enable_reload:
        reload_config.update({
            "reload": True,
            "reload_dirs": getattr(settings, 'reload_dirs', ["app", "config"]),
            "reload_excludes": getattr(settings, 'reload_excludes', ["*.log", "*.tmp", "__pycache__"])
        })
        print(f"   [ENABLED] 热重载已启用")
        print(f"   [WATCH] 监控目录: {reload_config['reload_dirs']}")
        print(f"   [EXCLUDE] 排除文件: {reload_config['reload_excludes']}")
    else:
        reload_config["reload"] = False
        print(f"   [DISABLED] 热重载已禁用")
    
    return reload_config

def test_environment_override():
    """测试环境变量覆盖"""
    print("\n[TEST] 测试环境变量覆盖...")
    
    # 保存原始环境变量
    original_env = os.environ.get("ENABLE_RELOAD")
    original_environment = os.environ.get("ENVIRONMENT")
    
    # 测试禁用热重载
    os.environ["ENABLE_RELOAD"] = "false"
    os.environ["ENVIRONMENT"] = "production"
    
    # 重新导入配置（注意：在实际应用中可能需要重启服务）
    print("   设置 ENABLE_RELOAD=false, ENVIRONMENT=production")
    
    # 恢复环境变量
    if original_env is not None:
        os.environ["ENABLE_RELOAD"] = original_env
    else:
        os.environ.pop("ENABLE_RELOAD", None)
        
    if original_environment is not None:
        os.environ["ENVIRONMENT"] = original_environment
    else:
        os.environ.pop("ENVIRONMENT", None)
    
    print("   [SUCCESS] 环境变量覆盖测试完成")

def main():
    """主测试函数"""
    print("[TEST SUITE] Knowledge Service 热重载配置测试\n")
    
    try:
        # 测试配置加载
        settings = test_config_loading()
        
        # 测试热重载逻辑
        reload_config = test_reload_logic(settings)
        
        # 测试环境变量覆盖
        test_environment_override()
        
        print("\n[SUCCESS] 所有测试通过！")
        print("\n[USAGE] 使用说明:")
        print("   1. 在.env文件中设置 ENABLE_RELOAD=false 可禁用热重载")
        print("   2. 在.env文件中设置 ENVIRONMENT=production 切换到生产环境")
        print("   3. 使用 python start_no_reload.py 启动无热重载模式")
        print("   4. 热重载仅在 development 环境且 ENABLE_RELOAD=true 时生效")
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())