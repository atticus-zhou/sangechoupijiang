"""终端 Bot — 在命令行中与三省六部交互

最简使用方式:
    python bots/console.py

启动后在终端输入需求，可以看到三省六部 agent 的实时对话。
"""

import asyncio
import sys
import io

# Windows UTF-8
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
except Exception:
    pass

# 确保项目根目录在 path 中
sys.path.insert(0, '.')

from sanshengliubu.session import CourtSession
from sanshengliubu.config.loader import CourtConfig
from sanshengliubu.protocols import format_agent_message, Speaker


async def console_bot():
    """终端交互式 Bot"""
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║       三省六部 · 多Agent协作框架                       ║")
    print("║                                                      ║")
    print("║  输入需求，朝堂即刻议事。                              ║")
    print("║  /report — 查看朝堂报告                               ║")
    print("║  /quit   — 退朝                                       ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    # 加载配置
    config = CourtConfig.from_yaml("config.yaml")

    while True:
        try:
            user_input = input("👤 奏事 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退朝。")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("退朝。")
            break

        if user_input == "/report":
            print("(朝堂报告需在任务进行中查看)")
            continue

        # 创建朝堂会话并提交任务
        print()
        court = CourtSession(config=config)

        async for msg in court.submit(user_input):
            # 格式化输出
            if msg.speaker == Speaker.USER:
                print(f"\n{format_agent_message(msg)}")
            else:
                print(f"\n{format_agent_message(msg)}")
                # 小停顿，让输出可读
                await asyncio.sleep(0.3)

        # 任务完成后输出报告
        print()
        print(court.get_report())
        print()


if __name__ == "__main__":
    asyncio.run(console_bot())
