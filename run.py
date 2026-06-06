#!/usr/bin/env python3
"""三个臭皮匠 · 一键启动脚本

用法:
    python run.py              # 启动 Web 服务 (默认端口 8080)
    python run.py --port 3000  # 指定端口
    python run.py --cli        # CLI 交互模式

首次使用:
    1. 配置 API Key: 在 Web UI 的「模型配置」页面设置, 或编辑 config.yaml
    2. 自定义提示词: 在 Web UI 的「提示词配置」页面编辑
    3. 创建任务模板: 在 Web UI 的「模板管理」页面创建
"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    args = sys.argv[1:]

    if "--cli" in args:
        # CLI 交互模式
        from src.main import main as cli_main
        cli_main()
    else:
        # Web 服务模式
        port = 8080
        for i, arg in enumerate(args):
            if arg == "--port" and i + 1 < len(args):
                port = int(args[i + 1])

        from src.web.app import start_server
        start_server(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
