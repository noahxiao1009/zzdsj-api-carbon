#!/bin/bash

# 交互式PM2管理功能测试脚本

echo "=== NextAgent 微服务交互式管理测试 ==="
echo ""

# 测试帮助功能
echo "1. 测试帮助功能："
./pm2-manager.sh help | head -20
echo ""

# 测试服务状态检查
echo "2. 测试服务状态检查："
./pm2-manager.sh status
echo ""

# 显示可用的交互式命令
echo "3. 可用的交互式命令："
echo "   ./pm2-manager.sh                    # 默认交互式界面"
echo "   ./pm2-manager.sh interactive        # 完整交互式管理"
echo "   ./pm2-manager.sh i production       # 生产环境交互式管理"
echo "   ./pm2-manager.sh select:start       # 交互选择启动服务"
echo "   ./pm2-manager.sh select:stop        # 交互选择停止服务"
echo "   ./pm2-manager.sh select:restart     # 交互选择重启服务"
echo ""

# 显示快速启动选项
echo "4. 快速启动选项："
echo "   ./start-services.sh                 # 默认交互式界面"
echo "   ./start-services.sh interactive     # 交互式管理"
echo "   ./start-services.sh core            # 启动核心服务"
echo "   ./start-services.sh all             # 启动所有服务"
echo ""

echo "测试完成！"
echo ""
echo "建议使用以下命令开始："
echo "  ./start-services.sh                 # 推荐：交互式管理界面"
echo "  ./pm2-manager.sh select:start       # 选择性启动服务"